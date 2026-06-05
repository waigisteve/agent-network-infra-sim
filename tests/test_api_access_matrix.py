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


def login(email: str) -> str:
    response = request("POST", "/api/v1/auth/login", json={"email": email, "password": "password"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_protected_get_endpoints_reject_anonymous_requests() -> None:
    protected_paths = [
        "/api/v1/me",
        "/api/v1/agents",
        "/api/v1/field-agents",
        "/api/v1/customers",
        "/api/v1/float/requests",
        "/api/v1/float/reconciliation",
        "/api/v1/transactions",
        "/api/v1/commissions",
        "/api/v1/reports/agent-network",
        "/api/v1/reports/agent/agent_neema",
        "/api/v1/maps/field-team",
        "/api/v1/events",
        "/api/v1/stream/readiness",
        "/api/v1/stream/dead-letter-events",
        "/api/v1/partners",
    ]

    for path in protected_paths:
        response = request("GET", path)
        assert response.status_code == 401, path


def test_admin_only_endpoints_reject_non_admin_roles() -> None:
    field_token = login("field@example.com")
    agent_token = login("agent@example.com")

    checks = [
        ("GET", "/api/v1/events", field_token, None),
        ("GET", "/api/v1/stream/readiness", field_token, None),
        ("GET", "/api/v1/stream/dead-letter-events", agent_token, None),
        ("POST", "/api/v1/float/requests/fr_001/approve", field_token, {"reviewer": "field"}),
        ("POST", "/api/v1/float/requests/fr_001/reject", agent_token, {"reviewer": "agent"}),
        (
            "POST",
            "/api/v1/integrations/telco-transactions",
            field_token,
            {"contract_name": "telco_transactions_v1", "source_reference": "security-test", "records": []},
        ),
        (
            "POST",
            "/api/v1/integrations/bank-settlements",
            field_token,
            {"contract_name": "bank_settlements_v1", "source_reference": "security-test", "records": []},
        ),
        (
            "POST",
            "/api/v1/integrations/reconcile-settlement",
            field_token,
            {"partner_id": "partner_telco_a", "settlement_reference": "security-test"},
        ),
    ]

    for method, path, token, payload in checks:
        kwargs = {"json": payload} if payload is not None else {}
        response = request(method, path, token=token, **kwargs)
        assert response.status_code == 403, path


def test_field_agent_scope_rejects_agent_role() -> None:
    agent_token = login("agent@example.com")

    field_scope_paths = [
        "/api/v1/field-agents",
        "/api/v1/float/reconciliation",
        "/api/v1/reports/agent-network",
        "/api/v1/maps/field-team",
        "/api/v1/partners",
    ]

    for path in field_scope_paths:
        response = request("GET", path, token=agent_token)
        assert response.status_code == 403, path


def test_kyc_review_scope_rejects_field_and_agent_roles() -> None:
    for email in ("field@example.com", "agent@example.com"):
        response = request(
            "POST",
            "/api/v1/kyc/reviews",
            token=login(email),
            json={"customer_id": "cust_hamadi", "status": "approved", "reviewer": "Security Test", "comments": "Not allowed"},
        )
        assert response.status_code == 403


def test_agent_can_only_view_own_agent_report() -> None:
    agent_token = login("agent@example.com")

    own_response = request("GET", "/api/v1/reports/agent/agent_neema", token=agent_token)
    other_response = request("GET", "/api/v1/reports/agent/agent_joseph", token=agent_token)

    assert own_response.status_code == 200
    assert other_response.status_code == 403


def test_failed_login_is_written_to_security_audit_log() -> None:
    failed = request("POST", "/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    audit = request("GET", "/api/v1/security/audit-log", token=login("admin@example.com"))

    assert failed.status_code == 401
    assert audit.status_code == 200
    latest = audit.json()[0]
    assert latest["event_type"] == "login_failed"
    assert latest["outcome"] == "blocked"
    assert latest["email"] == "admin@example.com"
    assert latest["detail"] == "invalid credentials"


def test_forbidden_role_attempt_is_written_to_security_audit_log() -> None:
    field_token = login("field@example.com")
    forbidden = request("GET", "/api/v1/events", token=field_token)
    audit = request("GET", "/api/v1/security/audit-log", token=login("admin@example.com"))

    assert forbidden.status_code == 403
    assert audit.status_code == 200
    event_types = {item["event_type"] for item in audit.json()}
    assert "role_forbidden" in event_types
    assert "api_access_blocked" in event_types


def test_security_audit_log_is_admin_only() -> None:
    field_token = login("field@example.com")

    assert request("GET", "/api/v1/security/audit-log", token=field_token).status_code == 403
    assert request("GET", "/api/v1/security/audit-log").status_code == 401
