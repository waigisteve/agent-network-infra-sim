from __future__ import annotations

import argparse
import asyncio
import random
import time
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.events import publisher
from backend.app.models import AgentORM, ComplianceStatus, CustomerORM, FloatRequestORM, FloatRequestStatus, TransactionCreate
from backend.app.services.float_ops import approve_float_request, reject_float_request
from backend.app.services.transactions import create_transaction


TRANSACTION_TYPES = ["deposit", "withdrawal", "airtime", "registration"]


async def run_simulation(duration_seconds: int, interval_seconds: float) -> None:
    await publisher.start()
    iterations = max(int(duration_seconds / interval_seconds), 1)
    try:
        for index in range(iterations):
            with SessionLocal() as db:
                agents = list(db.scalars(select(AgentORM)).all())
                customers = list(db.scalars(select(CustomerORM)).all())
                if not agents:
                    raise RuntimeError("No agents found. Run the seed command first.")
                agent = random.choice(agents)
                customer = random.choice(customers) if customers else None
                action = random.choices(
                    ["transaction", "float_request", "float_review", "kyc_review", "location"],
                    weights=[55, 15, 10, 10, 10],
                    k=1,
                )[0]

                if action == "transaction":
                    tx = await create_transaction(
                        db,
                        TransactionCreate(
                            agent_id=agent.id,
                            customer_id=customer.id if customer else None,
                            customer_phone=customer.phone if customer else f"700{random.randint(100000, 999999)}",
                            transaction_type=random.choice(TRANSACTION_TYPES),
                            amount=random.randint(500, 25_000),
                        ),
                    )
                    print(f"{index + 1}/{iterations} transaction.created {tx.id} {tx.amount}")
                elif action == "float_request":
                    request = FloatRequestORM(
                        id=f"sim_fr_{time.time_ns()}",
                        agent_id=agent.id,
                        amount=random.choice([3000, 5000, 10000, 15000, 20000]),
                        request_type=random.choice(["float", "cash"]),
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
                        },
                    )
                    db.commit()
                    print(f"{index + 1}/{iterations} float.requested {request.id} {request.amount}")
                elif action == "float_review":
                    pending = db.scalar(select(FloatRequestORM).where(FloatRequestORM.status == FloatRequestStatus.pending).limit(1))
                    if pending is None:
                        print(f"{index + 1}/{iterations} skipped float_review no pending requests")
                    elif random.random() < 0.75:
                        reviewed = await approve_float_request(db, pending.id, "stream-simulator")
                        print(f"{index + 1}/{iterations} float.approved {reviewed.id}")
                    else:
                        reviewed = await reject_float_request(db, pending.id, "stream-simulator")
                        print(f"{index + 1}/{iterations} float.rejected {reviewed.id}")
                elif action == "kyc_review" and customer is not None:
                    customer.compliance_status = random.choice([ComplianceStatus.approved, ComplianceStatus.pending, ComplianceStatus.rejected])
                    customer.verified_at = datetime.now(UTC)
                    await publisher.publish(
                        db,
                        "customer.kyc_reviewed",
                        {
                            "aggregate_type": "customer",
                            "aggregate_id": customer.id,
                            "customer_id": customer.id,
                            "status": customer.compliance_status.value,
                            "reviewer": "stream-simulator",
                        },
                    )
                    db.commit()
                    print(f"{index + 1}/{iterations} customer.kyc_reviewed {customer.id}")
                else:
                    agent.latitude += random.uniform(-0.01, 0.01)
                    agent.longitude += random.uniform(-0.01, 0.01)
                    await publisher.publish(
                        db,
                        "agent.location_updated",
                        {
                            "aggregate_type": "agent",
                            "aggregate_id": agent.id,
                            "agent_id": agent.id,
                            "latitude": round(agent.latitude, 6),
                            "longitude": round(agent.longitude, 6),
                        },
                    )
                    db.commit()
                    print(f"{index + 1}/{iterations} agent.location_updated {agent.id}")
            await asyncio.sleep(interval_seconds)
    finally:
        await publisher.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate continuous agent-network events for Kafka testing.")
    parser.add_argument("--duration-seconds", type=int, default=600)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_simulation(args.duration_seconds, args.interval_seconds))


if __name__ == "__main__":
    main()
