from __future__ import annotations

from datetime import UTC, date, datetime

from backend.app.db import SessionLocal
from backend.app.services.partner_ingestion import ingest_bank_settlements, ingest_telco_transactions, reconcile_partner_settlement


def main() -> None:
    run_key = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    settlement_reference = f"e2e-bank-settle-{run_key}"
    with SessionLocal() as db:
        telco_run = ingest_telco_transactions(
            db,
            "telco_transactions_v1",
            f"e2e-telco-feed-{run_key}",
            [
                {
                    "provider_reference": f"e2e-telco-ref-{run_key}",
                    "agent_id": "agent_neema",
                    "customer_msisdn": "256770000099",
                    "transaction_type": "DEPOSIT",
                    "amount": 4500,
                    "commission": 54,
                    "status": "SUCCESS",
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
        )
        bank_run = ingest_bank_settlements(
            db,
            "bank_settlements_v1",
            f"e2e-bank-feed-{run_key}",
            [
                {
                    "settlement_reference": settlement_reference,
                    "settlement_date": date.today().isoformat(),
                    "transaction_count": 1,
                    "gross_amount": 4500,
                    "commission_amount": 54,
                    "currency": "UGX",
                }
            ],
        )
        exception = reconcile_partner_settlement(db, bank_run.partner_id, settlement_reference)
        telco_summary = (telco_run.id, telco_run.status, telco_run.records_loaded)
        bank_summary = (bank_run.id, bank_run.status, bank_run.records_loaded)
        exception_id = exception.id if exception is not None else None

    print(f"telco_run={telco_summary[0]} status={telco_summary[1]} loaded={telco_summary[2]}")
    print(f"bank_run={bank_summary[0]} status={bank_summary[1]} loaded={bank_summary[2]}")
    print("reconciliation=matched" if exception_id is None else f"reconciliation=exception id={exception_id}")


if __name__ == "__main__":
    main()
