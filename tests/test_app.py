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
from backend.app.worker import process_stream_message, record_stream_failure


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
    ready = request("GET", "/ready").json()
    assert ready["database"] == "ok"
    assert ready["components"]["security_audit_log"]["status"] == "ok"


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
    transaction_event = next(event for event in events if event["name"] == "transaction.created")
    assert transaction_event["transaction_id"] == response.json()["id"]
    assert transaction_event["agent_id"] == "agent_neema"
    assert transaction_event["payload"]["customer_phone"].startswith("*")
    assert transaction_event["payload"]["customer_phone"].endswith("673")


def test_transaction_event_references_persisted_transaction() -> None:
    token = login("agent@example.com")
    response = request("POST", "/api/v1/transactions", token=token, json={"agent_id": "agent_neema", "customer_phone": "782645673", "transaction_type": "deposit", "amount": 2400})
    payload = response.json()
    events = request("GET", "/api/v1/events", token=login()).json()
    transaction_event = next(event for event in events if event["name"] == "transaction.created" and event["transaction_id"] == payload["id"])

    assert response.status_code == 200
    assert transaction_event["transaction_id"] == payload["id"]


def test_float_request_event_references_persisted_request() -> None:
    token = login("agent@example.com")
    response = request("POST", "/api/v1/float/requests", token=token, json={"agent_id": "agent_neema", "amount": 1200, "request_type": "float"})
    payload = response.json()
    events = request("GET", "/api/v1/events", token=login()).json()
    float_event = next(event for event in events if event["name"] == "float.requested" and event["float_request_id"] == payload["id"])

    assert response.status_code == 200
    assert float_event["float_request_id"] == payload["id"]


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
    assert response.json()["national_id"].startswith("*")
    assert response.json()["address"] == "masked address"
    assert "customer.kyc_reviewed" in {event["name"] for event in events}


def test_analytics_and_map_endpoints() -> None:
    token = login()
    report = request("GET", "/api/v1/reports/agent-network", token=token)
    map_response = request("GET", "/api/v1/maps/field-team", token=token)
    assert report.status_code == 200
    assert {"Value", "Volume", "Clients", "Float Utilization", "Stockout Rate"}.issubset({metric["label"] for metric in report.json()["metrics"]})
    assert len(map_response.json()["agents"]) >= 5


def test_analytics_snapshots_endpoint_returns_materialized_worker_output() -> None:
    with SessionLocal() as db:
        process_stream_message(
            db,
            consumer_group="agent-network-worker",
            topic="transaction-events",
            partition=0,
            offset=88,
            raw_payload='{"id": "event-snapshot-88", "name": "transaction.created", "payload": {"amount": 5000}}',
        )
        db.commit()

    response = request("GET", "/api/v1/reports/analytics-snapshots", token=login())
    payload = response.json()

    assert response.status_code == 200
    assert payload[0]["scope"] == "network"
    assert "metrics" in payload[0]


def test_customer_and_reporting_outputs_mask_pii() -> None:
    admin_token = login()
    agent_token = login("agent@example.com")
    customers = request("GET", "/api/v1/customers", token=admin_token).json()
    transactions = request("GET", "/api/v1/transactions", token=agent_token).json()
    report = request("GET", "/api/v1/reports/agent/agent_neema", token=agent_token).json()
    assert customers[0]["phone"].startswith("*")
    assert customers[0]["national_id"].startswith("*")
    assert customers[0]["birthday"] == "masked"
    assert transactions[0]["customer_phone"].startswith("*")
    assert report["transactions"][0]["customer_phone"].startswith("*")


def test_role_permissions_block_unauthorized_actions() -> None:
    agent_token = login("agent@example.com")
    response = request("POST", "/api/v1/float/requests/fr_001/approve", token=agent_token, json={"reviewer": "agent"})
    assert response.status_code == 403


def test_partner_contracts_seed_and_partner_listing() -> None:
    response = request("GET", "/api/v1/partners", token=login())
    assert response.status_code == 200
    assert {"TELCO_A_UG", "BANK_B_UG"}.issubset({partner["code"] for partner in response.json()})


def test_telco_transaction_ingestion_validates_contract_and_hashes_pii() -> None:
    token = login()
    response = request(
        "POST",
        "/api/v1/integrations/telco-transactions",
        token=token,
        json={
            "contract_name": "telco_transactions_v1",
            "source_reference": "kafka-offset-100",
            "records": [
                {
                    "provider_reference": "telco-ref-001",
                    "agent_id": "agent_neema",
                    "customer_msisdn": "256770000001",
                    "transaction_type": "DEPOSIT",
                    "amount": 2500,
                    "commission": 30,
                    "status": "SUCCESS",
                    "created_at": "2026-05-28T08:00:00+00:00",
                }
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "loaded"
    assert payload["records_loaded"] == 1
    assert payload["records_rejected"] == 0


def test_bank_settlement_reconciliation_creates_exception_for_mismatch() -> None:
    token = login()
    request(
        "POST",
        "/api/v1/integrations/telco-transactions",
        token=token,
        json={
            "contract_name": "telco_transactions_v1",
            "source_reference": "kafka-offset-101",
            "records": [
                {
                    "provider_reference": "telco-ref-002",
                    "agent_id": "agent_neema",
                    "customer_msisdn": "256770000002",
                    "transaction_type": "WITHDRAWAL",
                    "amount": 1000,
                    "commission": 12,
                    "status": "SUCCESS",
                    "created_at": "2026-05-28T08:05:00+00:00",
                }
            ],
        },
    )
    settlement = request(
        "POST",
        "/api/v1/integrations/bank-settlements",
        token=token,
        json={
            "contract_name": "bank_settlements_v1",
            "source_reference": "sftp-bank-b-2026-05-28.csv",
            "records": [
                {
                    "settlement_reference": "bank-settle-001",
                    "settlement_date": "2026-05-28",
                    "transaction_count": 2,
                    "gross_amount": 9999,
                    "commission_amount": 12,
                    "currency": "UGX",
                }
            ],
        },
    )
    response = request(
        "POST",
        "/api/v1/integrations/reconcile-settlement",
        token=token,
        json={"partner_id": settlement.json()["partner_id"], "settlement_reference": "bank-settle-001"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "exception"
    assert payload["exception"]["type"] == "settlement_mismatch"


def test_bank_settlement_reconciles_against_settled_telco_partner() -> None:
    token = login()
    request(
        "POST",
        "/api/v1/integrations/telco-transactions",
        token=token,
        json={
            "contract_name": "telco_transactions_v1",
            "source_reference": "kafka-offset-201",
            "records": [
                {
                    "provider_reference": "telco-ref-201",
                    "agent_id": "agent_neema",
                    "customer_msisdn": "256770000201",
                    "transaction_type": "DEPOSIT",
                    "amount": 4500,
                    "commission": 54,
                    "status": "SUCCESS",
                    "created_at": "2026-05-28T08:05:00+00:00",
                }
            ],
        },
    )
    settlement = request(
        "POST",
        "/api/v1/integrations/bank-settlements",
        token=token,
        json={
            "contract_name": "bank_settlements_v1",
            "source_reference": "sftp-bank-b-2026-05-29.csv",
            "records": [
                {
                    "settlement_reference": "bank-settle-201",
                    "settled_partner_code": "TELCO_A_UG",
                    "settlement_date": "2026-05-29",
                    "transaction_count": 1,
                    "gross_amount": 4500,
                    "commission_amount": 54,
                    "currency": "UGX",
                }
            ],
        },
    )
    response = request(
        "POST",
        "/api/v1/integrations/reconcile-settlement",
        token=token,
        json={"partner_id": settlement.json()["partner_id"], "settlement_reference": "bank-settle-201"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "matched", "exception": None}


def test_stream_processing_records_consumer_offset() -> None:
    with SessionLocal() as db:
        process_stream_message(
            db,
            consumer_group="agent-network-worker",
            topic="test-transaction-events",
            partition=7,
            offset=42,
            raw_payload='{"id": "event-42", "name": "transaction.created", "payload": {"amount": 5000}}',
        )
        db.commit()

    response = request("GET", "/api/v1/stream/readiness", token=login())
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["summary"]["processed_total"] >= 1
    offset_row = next(row for row in payload["consumer_groups"] if row["topic"] == "test-transaction-events" and row["partition"] == 7)
    assert offset_row["last_event_id"] == "event-42"
    assert offset_row["last_offset"] == 42


def test_stream_failure_records_dead_letter_event_and_degraded_readiness() -> None:
    with SessionLocal() as db:
        record_stream_failure(
            db,
            consumer_group="agent-network-worker",
            topic="transaction-events",
            partition=0,
            offset=43,
            raw_payload="{not-json",
            failure_reason="invalid json",
        )
        db.commit()

    readiness = request("GET", "/api/v1/stream/readiness", token=login()).json()
    dead_letters = request("GET", "/api/v1/stream/dead-letter-events", token=login()).json()

    assert readiness["status"] == "degraded"
    assert readiness["summary"]["open_dead_letters"] == 1
    assert dead_letters[0]["failure_reason"] == "invalid json"
    assert dead_letters[0]["topic"] == "transaction-events"


def test_stream_readiness_is_admin_only() -> None:
    response = request("GET", "/api/v1/stream/readiness", token=login("agent@example.com"))

    assert response.status_code == 403
