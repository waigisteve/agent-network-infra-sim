from __future__ import annotations

import argparse
import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db import SessionLocal
from backend.app.events import publisher
from backend.app.models import (
    AgentORM,
    ComplianceStatus,
    CustomerORM,
    FloatRequestORM,
    FloatRequestStatus,
    KycDocumentORM,
    PartnerORM,
    RawPartnerTransactionORM,
    Role,
    TransactionCreate,
    UserORM,
)
from backend.app.services.float_ops import approve_float_request, reject_float_request
from backend.app.services.kyc_documents import store_kyc_document
from backend.app.services.partner_ingestion import ingest_bank_settlements, ingest_telco_transactions, reconcile_partner_settlement
from backend.app.services.transactions import create_transaction


TRANSACTION_TYPES = ("deposit", "withdrawal", "airtime", "registration")
DOCUMENT_TYPES = ("customer_photo", "national_id_front", "national_id_back", "proof_of_address")
MIME_OPTIONS = (
    ("image/jpeg", "jpg"),
    ("image/png", "png"),
    ("application/pdf", "pdf"),
)


@dataclass
class SimulationStats:
    transactions: int = 0
    float_requests: int = 0
    float_reviews: int = 0
    kyc_documents: int = 0
    kyc_reviews: int = 0
    location_updates: int = 0
    partner_runs: int = 0
    reconciliation_matches: int = 0
    reconciliation_exceptions: int = 0
    errors: list[str] = field(default_factory=list)


def _fake_file_bytes(mime_type: str, randomizer: random.Random) -> bytes:
    nonce = randomizer.randbytes(96)
    if mime_type == "image/jpeg":
        return b"\xff\xd8\xff\xe0SIMULATED-KYC-JPEG" + nonce + b"\xff\xd9"
    if mime_type == "image/png":
        return b"\x89PNG\r\n\x1a\nSIMULATED-KYC-PNG" + nonce
    return b"%PDF-1.4\n% simulated KYC PDF\n1 0 obj<<>>endobj\n" + nonce + b"\n%%EOF\n"


async def _create_transaction(db: Session, randomizer: random.Random) -> str:
    agents = list(db.scalars(select(AgentORM)).all())
    customers = list(db.scalars(select(CustomerORM)).all())
    if not agents:
        raise RuntimeError("No agents found. Run migrations and seed data first.")

    agent = randomizer.choice(agents)
    customer = randomizer.choice(customers) if customers and randomizer.random() < 0.65 else None
    transaction = await create_transaction(
        db,
        TransactionCreate(
            agent_id=agent.id,
            customer_id=customer.id if customer else None,
            customer_phone=customer.phone if customer else f"25677{randomizer.randint(1_000_000, 9_999_999)}",
            transaction_type=randomizer.choice(TRANSACTION_TYPES),
            amount=randomizer.randint(500, 50_000),
        ),
    )
    return transaction.id


async def _create_float_request(db: Session, randomizer: random.Random) -> str:
    agents = list(db.scalars(select(AgentORM)).all())
    agent = randomizer.choice(agents)
    request = FloatRequestORM(
        id=f"sim_fr_{time.time_ns()}_{randomizer.randint(1000, 9999)}",
        agent_id=agent.id,
        amount=randomizer.choice([3_000, 5_000, 10_000, 15_000, 20_000, 35_000, 50_000]),
        request_type=randomizer.choice(["float", "cash"]),
    )
    db.add(request)
    db.flush()
    await publisher.publish(
        db,
        "float.requested",
        {
            "aggregate_type": "float_request",
            "aggregate_id": request.id,
            "request_id": request.id,
            "float_request_id": request.id,
            "agent_id": request.agent_id,
            "amount": request.amount,
            "source": "workflow-cycle-simulator",
        },
    )
    db.commit()
    return request.id


async def _review_float_request(db: Session, randomizer: random.Random) -> str | None:
    pending = db.scalar(select(FloatRequestORM).where(FloatRequestORM.status == FloatRequestStatus.pending).limit(1))
    if pending is None:
        return None
    if randomizer.random() < 0.78:
        reviewed = await approve_float_request(db, pending.id, "workflow-cycle-simulator")
    else:
        reviewed = await reject_float_request(db, pending.id, "workflow-cycle-simulator")
    return reviewed.id


async def _upload_kyc_document(db: Session, randomizer: random.Random) -> str:
    customers = list(db.scalars(select(CustomerORM)).all())
    users = list(db.scalars(select(UserORM).where(UserORM.role == Role.kyc_reviewer)).all())
    if not customers:
        raise RuntimeError("No customers found. Run migrations and seed data first.")

    customer = randomizer.choice(customers)
    document_type = randomizer.choice(DOCUMENT_TYPES)
    mime_type, suffix = randomizer.choice(MIME_OPTIONS)
    data = _fake_file_bytes(mime_type, randomizer)
    filename = f"{document_type}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{randomizer.randint(1000, 9999)}.{suffix}"
    stored = store_kyc_document(customer.id, filename, mime_type, data)
    document = KycDocumentORM(
        id=f"kyc_doc_{uuid4().hex[:12]}",
        customer_id=customer.id,
        document_type=document_type,
        original_filename=filename,
        storage_backend=stored.storage_backend,
        storage_key=stored.storage_key,
        sha256_hash=stored.sha256_hash,
        mime_type=stored.mime_type,
        file_size_bytes=stored.file_size_bytes,
        uploaded_by=randomizer.choice(users).id if users else None,
    )
    db.add(document)
    await publisher.publish(
        db,
        "customer.kyc_submitted",
        {
            "aggregate_type": "customer",
            "aggregate_id": customer.id,
            "customer_id": customer.id,
            "document_id": document.id,
            "document_type": document.document_type,
            "mime_type": document.mime_type,
            "file_size_bytes": document.file_size_bytes,
            "sha256_hash": document.sha256_hash,
            "storage_backend": document.storage_backend,
            "source": "workflow-cycle-simulator",
        },
    )
    db.commit()
    return document.id


async def _review_kyc(db: Session, randomizer: random.Random) -> str:
    customers = list(db.scalars(select(CustomerORM)).all())
    customer = randomizer.choice(customers)
    customer.compliance_status = randomizer.choices(
        [ComplianceStatus.approved, ComplianceStatus.pending, ComplianceStatus.rejected],
        weights=[65, 25, 10],
        k=1,
    )[0]
    customer.verified_at = datetime.now(UTC)
    customer.compliance_comments = "Automated workflow-cycle simulator review"
    await publisher.publish(
        db,
        "customer.kyc_reviewed",
        {
            "aggregate_type": "customer",
            "aggregate_id": customer.id,
            "customer_id": customer.id,
            "status": customer.compliance_status.value,
            "reviewer": "workflow-cycle-simulator",
        },
    )
    db.commit()
    return customer.id


async def _update_location(db: Session, randomizer: random.Random) -> str:
    agent = randomizer.choice(list(db.scalars(select(AgentORM)).all()))
    agent.latitude += randomizer.uniform(-0.015, 0.015)
    agent.longitude += randomizer.uniform(-0.015, 0.015)
    await publisher.publish(
        db,
        "agent.location_updated",
        {
            "aggregate_type": "agent",
            "aggregate_id": agent.id,
            "agent_id": agent.id,
            "latitude": round(agent.latitude, 6),
            "longitude": round(agent.longitude, 6),
            "source": "workflow-cycle-simulator",
        },
    )
    db.commit()
    return agent.id


def _partner_batch(db: Session, randomizer: random.Random) -> tuple[str, bool]:
    agents = list(db.scalars(select(AgentORM)).all())
    run_key = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    records: list[dict[str, object]] = []
    for index in range(randomizer.randint(4, 14)):
        amount = randomizer.randint(500, 45_000)
        records.append(
            {
                "provider_reference": f"sim-telco-{run_key}-{index}",
                "agent_id": randomizer.choice(agents).id,
                "customer_msisdn": f"25677{randomizer.randint(1_000_000, 9_999_999)}",
                "transaction_type": randomizer.choice(["DEPOSIT", "WITHDRAWAL", "AIRTIME", "REGISTRATION"]),
                "amount": amount,
                "commission": max(int(amount * randomizer.uniform(0.008, 0.018)), 1),
                "status": randomizer.choices(["SUCCESS", "FAILED", "REVERSED"], weights=[82, 12, 6], k=1)[0],
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    ingest_telco_transactions(db, "telco_transactions_v1", f"sim-telco-feed-{run_key}", records)
    telco_partner = db.scalar(select(PartnerORM).where(PartnerORM.code == "TELCO_A_UG"))
    if telco_partner is None:
        raise RuntimeError("TELCO_A_UG partner was not created")

    totals = db.execute(
        select(
            func.count(RawPartnerTransactionORM.id),
            func.coalesce(func.sum(RawPartnerTransactionORM.amount), 0),
            func.coalesce(func.sum(RawPartnerTransactionORM.commission), 0),
        ).where(
            RawPartnerTransactionORM.partner_id == telco_partner.id,
            RawPartnerTransactionORM.status == "SUCCESS",
        )
    ).one()
    transaction_count = int(totals[0])
    gross_amount = int(totals[1])
    commission_amount = int(totals[2])
    mismatch = randomizer.random() < 0.35
    if mismatch:
        gross_amount += randomizer.choice([-1, 1]) * randomizer.randint(100, 5_000)

    settlement_reference = f"sim-bank-settle-{run_key}"
    bank_run = ingest_bank_settlements(
        db,
        "bank_settlements_v1",
        f"sim-bank-feed-{run_key}",
        [
            {
                "settlement_reference": settlement_reference,
                "settled_partner_code": "TELCO_A_UG",
                "settlement_date": date.today().isoformat(),
                "transaction_count": transaction_count,
                "gross_amount": gross_amount,
                "commission_amount": commission_amount,
                "currency": "UGX",
            }
        ],
    )
    exception = reconcile_partner_settlement(db, bank_run.partner_id, settlement_reference)
    return bank_run.id, exception is not None


async def run_simulation(duration_seconds: int, interval_seconds: float, seed: int | None = None) -> None:
    randomizer = random.Random(seed)
    stats = SimulationStats()
    actions = (
        "transaction",
        "float_request",
        "float_review",
        "kyc_document",
        "kyc_review",
        "location",
        "partner_batch",
    )
    weights = (40, 12, 10, 12, 9, 12, 5)
    deadline = time.monotonic() + duration_seconds
    cycle = 0

    await publisher.start()
    try:
        while time.monotonic() < deadline:
            cycle += 1
            action = randomizer.choices(actions, weights=weights, k=1)[0]
            try:
                with SessionLocal() as db:
                    if action == "transaction":
                        item_id = await _create_transaction(db, randomizer)
                        stats.transactions += 1
                    elif action == "float_request":
                        item_id = await _create_float_request(db, randomizer)
                        stats.float_requests += 1
                    elif action == "float_review":
                        item_id = await _review_float_request(db, randomizer)
                        if item_id is None:
                            print(f"{cycle} float_review skipped no pending request", flush=True)
                            await asyncio.sleep(interval_seconds)
                            continue
                        stats.float_reviews += 1
                    elif action == "kyc_document":
                        item_id = await _upload_kyc_document(db, randomizer)
                        stats.kyc_documents += 1
                    elif action == "kyc_review":
                        item_id = await _review_kyc(db, randomizer)
                        stats.kyc_reviews += 1
                    elif action == "location":
                        item_id = await _update_location(db, randomizer)
                        stats.location_updates += 1
                    else:
                        item_id, has_exception = _partner_batch(db, randomizer)
                        stats.partner_runs += 1
                        if has_exception:
                            stats.reconciliation_exceptions += 1
                        else:
                            stats.reconciliation_matches += 1
                print(f"{cycle} {action} ok id={item_id}", flush=True)
            except Exception as exc:  # noqa: BLE001 - long-running demo should keep moving.
                message = f"{cycle} {action} error={type(exc).__name__}: {exc}"
                stats.errors.append(message)
                print(message, flush=True)
            sleep_for = min(interval_seconds, max(deadline - time.monotonic(), 0))
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
    finally:
        await publisher.stop()

    print("workflow_cycle_summary", flush=True)
    print(stats, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a random end-to-end agent-network workflow cycle.")
    parser.add_argument("--duration-seconds", type=int, default=1800)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_simulation(args.duration_seconds, args.interval_seconds, args.seed))


if __name__ == "__main__":
    main()
