from __future__ import annotations

import asyncio
import os
from typing import Any

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["KAFKA_ENABLED"] = "false"

import httpx

from backend.app.db import SessionLocal, create_all
from backend.app.main import app
from backend.app.scripts.seed import seed


def setup_function() -> None:
    create_all()
    with SessionLocal() as db:
        seed(db)


def request(method: str, path: str, token: str | None = None, **kwargs: Any) -> httpx.Response:
    async def run_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run_request())


def login(email: str = "admin@example.com") -> str:
    response = request("POST", "/api/v1/auth/login", json={"email": email, "password": "password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_and_ready_endpoints() -> None:
    assert request("GET", "/health").json() == {"status": "ok"}
    assert request("GET", "/ready").json()["database"] == "ok"


def test_auth_login_and_protected_route() -> None:
    token = login()
    response = request("GET", "/api/v1/me", token=token)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert request("GET", "/api/v1/me").status_code == 401


def test_seed_data_loads_into_database() -> None:
    response = request("GET", "/api/v1/agents", token=login())
    assert response.status_code == 200
    assert len(response.json()) >= 5


def test_float_approval_publishes_event_and_updates_balance() -> None:
    token = login()
    before = request("GET", "/api/v1/reports/agent/agent_neema", token=token).json()["float_balance"]
    response = request("POST", "/api/v1/float/requests/fr_001/approve", token=token, json={"reviewer": "ops"})
    after = request("GET", "/api/v1/reports/agent/agent_neema", token=token).json()["float_balance"]
    events = request("GET", "/api/v1/events", token=token).json()
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert after == before + 3000
    assert {"float.approved", "float.disbursed"}.issubset({event["name"] for event in events})


def test_float_reject_publishes_event_and_leaves_balance_unchanged() -> None:
    token = login()
    before = request("GET", "/api/v1/reports/agent/agent_joseph", token=token).json()["float_balance"]
    response = request("POST", "/api/v1/float/requests/fr_002/reject", token=token, json={"reviewer": "ops"})
    after = request("GET", "/api/v1/reports/agent/agent_joseph", token=token).json()["float_balance"]
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert after == before


def test_transaction_creation_emits_event_and_commission() -> None:
    token = login("agent@example.com")
    response = request("POST", "/api/v1/transactions", token=token, json={"agent_id": "agent_neema", "customer_phone": "782645673", "transaction_type": "deposit", "amount": 3400})
    events = request("GET", "/api/v1/events", token=login()).json()
    assert response.status_code == 200
    assert response.json()["commission"] == 41
    assert "transaction.created" in {event["name"] for event in events}
    assert "commission.calculated" in {event["name"] for event in events}


def test_reconciliation_rows_match_expected_shape() -> None:
    response = request("GET", "/api/v1/float/reconciliation", token=login())
    row = next(item for item in response.json() if item["agent_id"] == "agent_neema")
    assert response.status_code == 200
    assert isinstance(row["balance_owed"], int)


def test_kyc_review_updates_status_and_publishes_event() -> None:
    token = login("reviewer@example.com")
    response = request("POST", "/api/v1/kyc/reviews", token=token, json={"customer_id": "cust_hamadi", "status": "approved", "reviewer": "KYC Reviewer", "comments": "Verified"})
    events = request("GET", "/api/v1/events", token=login()).json()
    assert response.status_code == 200
    assert response.json()["compliance_status"] == "approved"
    assert "customer.kyc_reviewed" in {event["name"] for event in events}


def test_analytics_and_map_endpoints() -> None:
    token = login()
    report = request("GET", "/api/v1/reports/agent-network", token=token)
    map_response = request("GET", "/api/v1/maps/field-team", token=token)
    assert report.status_code == 200
    assert {"Value", "Volume", "Clients", "Float Utilization", "Stockout Rate"}.issubset({metric["label"] for metric in report.json()["metrics"]})
    assert len(map_response.json()["agents"]) >= 5


def test_role_permissions_block_unauthorized_actions() -> None:
    agent_token = login("agent@example.com")
    response = request("POST", "/api/v1/float/requests/fr_001/approve", token=agent_token, json={"reviewer": "agent"})
    assert response.status_code == 403
