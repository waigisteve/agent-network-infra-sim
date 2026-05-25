from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from backend.app.auth import hash_password
from backend.app.db import SessionLocal, create_all
from backend.app.models import (
    AgentORM,
    AnalyticsSnapshotORM,
    CustomerORM,
    EventLogORM,
    FieldAgentORM,
    FloatRequestORM,
    Role,
    TransactionORM,
    UserORM,
    WorkerErrorORM,
)


def seed_path() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "seed.json"


def clear(db: Session) -> None:
    for model in (WorkerErrorORM, AnalyticsSnapshotORM, EventLogORM, TransactionORM, FloatRequestORM, CustomerORM, UserORM, AgentORM, FieldAgentORM):
        db.execute(delete(model))


def seed(db: Session) -> None:
    data = json.loads(seed_path().read_text(encoding="utf-8"))
    clear(db)
    db.add_all(FieldAgentORM(**item) for item in data["field_agents"])
    db.flush()
    db.add_all(AgentORM(**item) for item in data["agents"])
    db.flush()
    db.add_all(CustomerORM(**item) for item in data["customers"])
    db.add_all(FloatRequestORM(**item) for item in data["float_requests"])
    customers_by_phone = {item["phone"]: item["id"] for item in data["customers"]}
    db.add_all(
        TransactionORM(
            **(
                item
                | {
                    "customer_id": customers_by_phone.get(item["customer_phone"]),
                    "created_at": datetime.fromisoformat(item["created_at"]),
                }
            )
        )
        for item in data["transactions"]
    )
    db.add_all(
        [
            UserORM(id="user_admin", email="admin@example.com", full_name="Operations Admin", password_hash=hash_password("password"), role=Role.admin),
            UserORM(id="user_reviewer", email="reviewer@example.com", full_name="KYC Reviewer", password_hash=hash_password("password"), role=Role.kyc_reviewer),
            UserORM(id="user_field", email="field@example.com", full_name="Field Agent", password_hash=hash_password("password"), role=Role.field_agent),
            UserORM(id="user_agent", email="agent@example.com", full_name="Neema Diallo", password_hash=hash_password("password"), role=Role.agent, agent_id="agent_neema"),
        ]
    )
    db.commit()


def main() -> None:
    create_all()
    with SessionLocal() as db:
        seed(db)
    print("Seeded agent network data")


if __name__ == "__main__":
    main()
