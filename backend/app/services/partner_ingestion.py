from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import (
    AgentORM,
    BankSettlementORM,
    IntegrationRunORM,
    IntegrationRunStatus,
    PartnerContractORM,
    PartnerORM,
    RawPartnerTransactionORM,
    ReconciliationExceptionORM,
)


def contract_path(contract_name: str) -> Path:
    return Path(__file__).resolve().parents[3] / "contracts" / f"{contract_name}.json"


def load_contract(contract_name: str) -> dict[str, Any]:
    return json.loads(contract_path(contract_name).read_text(encoding="utf-8"))


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ensure_partner_contract(db: Session, contract_name: str) -> PartnerContractORM:
    contract = load_contract(contract_name)
    partner_data = contract["partner"]
    partner = db.scalar(select(PartnerORM).where(PartnerORM.code == partner_data["code"]))
    if partner is None:
        partner = PartnerORM(
            id=f"partner_{partner_data['code'].lower()}",
            code=partner_data["code"],
            name=partner_data["name"],
            partner_type=partner_data["partner_type"],
            country=partner_data["country"],
            integration_mode=partner_data["integration_mode"],
            data_freshness_sla_minutes=partner_data["data_freshness_sla_minutes"],
        )
        db.add(partner)
        db.flush()

    feed_name = contract["feed"]["name"]
    version = contract["feed"]["version"]
    existing = db.scalar(
        select(PartnerContractORM).where(
            PartnerContractORM.partner_id == partner.id,
            PartnerContractORM.feed_name == feed_name,
            PartnerContractORM.version == version,
        )
    )
    if existing is not None:
        return existing

    partner_contract = PartnerContractORM(
        id=f"contract_{partner.code.lower()}_{feed_name}_{version}",
        partner_id=partner.id,
        feed_name=feed_name,
        version=version,
        schema_contract=contract,
        pii_fields=contract["feed"].get("pii_fields", []),
        dedupe_key=contract["feed"].get("dedupe_key", []),
        arrival_sla=contract["feed"].get("arrival_sla", "hourly"),
    )
    db.add(partner_contract)
    db.flush()
    return partner_contract


def validate_record(record: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    fields = contract["feed"]["fields"]
    for field in fields:
        name = field["name"]
        value = record.get(name)
        if field.get("required", False) and value in (None, ""):
            errors.append(f"{name} is required")
        if "accepted_values" in field and value not in field["accepted_values"]:
            errors.append(f"{name} must be one of {field['accepted_values']}")
    if "amount" in record and int(record["amount"]) < 0:
        errors.append("amount cannot be negative")
    return errors


def start_integration_run(db: Session, partner_contract: PartnerContractORM, source_reference: str, records_received: int) -> IntegrationRunORM:
    run = IntegrationRunORM(
        id=f"run_{uuid4().hex[:12]}",
        partner_id=partner_contract.partner_id,
        contract_id=partner_contract.id,
        feed_name=partner_contract.feed_name,
        source_reference=source_reference,
        status=IntegrationRunStatus.received,
        records_received=records_received,
    )
    db.add(run)
    db.flush()
    return run


def ingest_telco_transactions(db: Session, contract_name: str, source_reference: str, records: list[dict[str, Any]]) -> IntegrationRunORM:
    partner_contract = ensure_partner_contract(db, contract_name)
    contract = partner_contract.schema_contract
    run = start_integration_run(db, partner_contract, source_reference, len(records))
    rejected: list[str] = []

    for record in records:
        errors = validate_record(record, contract)
        if errors or db.get(AgentORM, record.get("agent_id")) is None:
            rejected.append(f"{record.get('provider_reference', 'unknown')}: {', '.join(errors or ['agent_id not found'])}")
            continue

        db.add(
            RawPartnerTransactionORM(
                id=f"raw_tx_{uuid4().hex[:12]}",
                partner_id=partner_contract.partner_id,
                integration_run_id=run.id,
                provider_reference=record["provider_reference"],
                agent_id=record["agent_id"],
                customer_msisdn_hash=hash_identifier(record["customer_msisdn"]),
                transaction_type=record["transaction_type"],
                amount=int(record["amount"]),
                commission=int(record.get("commission", 0)),
                status=record["status"],
                transaction_created_at=datetime.fromisoformat(record["created_at"]).astimezone(UTC),
                raw_payload=record,
            )
        )

    run.records_rejected = len(rejected)
    run.records_loaded = len(records) - len(rejected)
    run.status = IntegrationRunStatus.loaded if not rejected else IntegrationRunStatus.failed
    run.error_summary = "; ".join(rejected) if rejected else None
    run.completed_at = datetime.now(UTC)
    db.commit()
    return run


def ingest_bank_settlements(db: Session, contract_name: str, source_reference: str, records: list[dict[str, Any]]) -> IntegrationRunORM:
    partner_contract = ensure_partner_contract(db, contract_name)
    contract = partner_contract.schema_contract
    run = start_integration_run(db, partner_contract, source_reference, len(records))
    rejected: list[str] = []

    for record in records:
        errors = validate_record(record, contract)
        settled_partner_code = record.get("settled_partner_code") or contract["feed"].get("default_settled_partner_code")
        settled_partner = db.scalar(select(PartnerORM).where(PartnerORM.code == settled_partner_code)) if settled_partner_code else None
        if settled_partner is None:
            errors.append("settled_partner_code must reference a known partner")
        if errors:
            rejected.append(f"{record.get('settlement_reference', 'unknown')}: {', '.join(errors)}")
            continue
        db.add(
            BankSettlementORM(
                id=f"settlement_{uuid4().hex[:12]}",
                partner_id=partner_contract.partner_id,
                settled_partner_id=settled_partner.id,
                integration_run_id=run.id,
                settlement_reference=record["settlement_reference"],
                settlement_date=date.fromisoformat(record["settlement_date"]),
                transaction_count=int(record["transaction_count"]),
                gross_amount=int(record["gross_amount"]),
                commission_amount=int(record.get("commission_amount", 0)),
                currency=record.get("currency", "UGX"),
                raw_payload=record,
            )
        )

    run.records_rejected = len(rejected)
    run.records_loaded = len(records) - len(rejected)
    run.status = IntegrationRunStatus.loaded if not rejected else IntegrationRunStatus.failed
    run.error_summary = "; ".join(rejected) if rejected else None
    run.completed_at = datetime.now(UTC)
    db.commit()
    return run


def reconcile_partner_settlement(db: Session, partner_id: str, settlement_reference: str) -> ReconciliationExceptionORM | None:
    settlement = db.scalar(
        select(BankSettlementORM).where(
            BankSettlementORM.partner_id == partner_id,
            BankSettlementORM.settlement_reference == settlement_reference,
        )
    )
    if settlement is None:
        raise ValueError("Settlement not found")

    totals = db.execute(
        select(func.count(RawPartnerTransactionORM.id), func.coalesce(func.sum(RawPartnerTransactionORM.amount), 0)).where(
            RawPartnerTransactionORM.partner_id == settlement.settled_partner_id,
            RawPartnerTransactionORM.status == "SUCCESS",
        )
    ).one()
    transaction_count = int(totals[0])
    gross_amount = int(totals[1])
    if transaction_count == settlement.transaction_count and gross_amount == settlement.gross_amount:
        return None

    exception = ReconciliationExceptionORM(
        id=f"recon_{uuid4().hex[:12]}",
        partner_id=partner_id,
        integration_run_id=settlement.integration_run_id,
        exception_type="settlement_mismatch",
        severity="high",
        description="Bank settlement does not match loaded successful partner transactions.",
        evidence={
            "settlement_reference": settlement_reference,
            "settlement_partner_id": settlement.partner_id,
            "settled_partner_id": settlement.settled_partner_id,
            "settlement_transaction_count": settlement.transaction_count,
            "raw_transaction_count": transaction_count,
            "settlement_gross_amount": settlement.gross_amount,
            "raw_gross_amount": gross_amount,
        },
    )
    db.add(exception)
    db.commit()
    return exception
