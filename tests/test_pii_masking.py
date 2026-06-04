from __future__ import annotations

import asyncio
import json
import os
from typing import Any

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["KAFKA_ENABLED"] = "false"

import httpx

from backend.app.db import SessionLocal, create_all
from backend.app.main import app
from backend.app.masking import mask_payload
from backend.app.scripts.seed import seed


RAW_PII_VALUES = {
    "Mamdou Hamadi",
    "Jallow",
    "782645673",
    "23019012221",
    "22 June, 1994",
    "Ndungu Kibbeh, Jokadu District, North Bank Division",
}


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


def assert_raw_pii_absent(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for raw_value in RAW_PII_VALUES:
        assert raw_value not in serialized


def test_customer_endpoint_masks_seeded_customer_pii() -> None:
    response = request("GET", "/api/v1/customers", token=login())
    payload = response.json()

    assert response.status_code == 200
    assert_raw_pii_absent(payload)
    assert payload[0]["name"] == "M***"
    assert payload[0]["surname"] == "J***"
    assert payload[0]["full_name"] == "M*** H*** J***"
    assert payload[0]["phone"] == "******673"
    assert payload[0]["national_id"] == "*******2221"
    assert payload[0]["birthday"] == "masked"
    assert payload[0]["address"] == "masked address"


def test_transaction_and_agent_report_outputs_mask_customer_phone() -> None:
    agent_token = login("agent@example.com")
    transactions = request("GET", "/api/v1/transactions", token=agent_token).json()
    report = request("GET", "/api/v1/reports/agent/agent_neema", token=agent_token).json()

    assert_raw_pii_absent(transactions)
    assert_raw_pii_absent(report)
    assert all(item["customer_phone"].startswith("*") for item in transactions)
    assert all(item["customer_phone"].startswith("*") for item in report["transactions"])


def test_event_audit_payload_masks_nested_pii() -> None:
    token = login("agent@example.com")
    response = request(
        "POST",
        "/api/v1/transactions",
        token=token,
        json={"agent_id": "agent_neema", "customer_phone": "782645673", "transaction_type": "deposit", "amount": 3400},
    )
    events = request("GET", "/api/v1/events", token=login()).json()

    assert response.status_code == 200
    assert_raw_pii_absent(events)
    transaction_event = next(event for event in events if event["name"] == "transaction.created")
    assert transaction_event["payload"]["customer_phone"] == "******673"


def test_mask_payload_recurses_into_nested_lists() -> None:
    payload = {
        "batch": [
            {"customer_phone": "782645673", "national_id": "23019012221"},
            {"nested": {"address": "Ndungu Kibbeh, Jokadu District, North Bank Division", "birthday": "22 June, 1994"}},
        ]
    }

    masked = mask_payload(payload)

    assert_raw_pii_absent(masked)
    assert masked["batch"][0]["customer_phone"] == "******673"
    assert masked["batch"][0]["national_id"] == "*******2221"
    assert masked["batch"][1]["nested"]["address"] == "masked"
    assert masked["batch"][1]["nested"]["birthday"] == "masked"
