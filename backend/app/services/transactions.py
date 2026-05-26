from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.events import publisher
from backend.app.models import AgentORM, CustomerORM, TransactionCreate, TransactionORM


COMMISSION_RATES = {
    "deposit": 0.012,
    "withdrawal": 0.015,
    "registration": 40.0,
    "airtime": 0.03,
    "float": 0.0,
}


def calculate_commission(transaction_type: str, amount: int) -> int:
    rate = COMMISSION_RATES.get(transaction_type, 0.01)
    if rate >= 1:
        return int(rate)
    return int(round(amount * rate))


async def create_transaction(db: Session, request: TransactionCreate) -> TransactionORM:
    agent = db.get(AgentORM, request.agent_id)
    if agent is None:
        raise ValueError("Agent not found")
    customer_id = request.customer_id
    if customer_id is None:
        customer = db.scalar(select(CustomerORM).where(CustomerORM.phone == request.customer_phone))
        customer_id = customer.id if customer else None
    commission = calculate_commission(request.transaction_type, request.amount)
    tx = TransactionORM(
        id=f"txn_{uuid4().hex[:10]}",
        agent_id=request.agent_id,
        customer_id=customer_id,
        customer_phone=request.customer_phone,
        transaction_type=request.transaction_type,
        amount=request.amount,
        commission=commission,
    )
    db.add(tx)
    if request.transaction_type in {"deposit", "registration", "airtime"}:
        agent.cash_balance += request.amount
        agent.float_balance -= request.amount
    elif request.transaction_type == "withdrawal":
        agent.cash_balance -= request.amount
        agent.float_balance += request.amount
    db.flush()
    await publisher.publish(
        db,
        "transaction.created",
        {
            "aggregate_type": "transaction",
            "aggregate_id": tx.id,
            "transaction_id": tx.id,
            "agent_id": tx.agent_id,
            "customer_id": tx.customer_id,
            "customer_phone": tx.customer_phone,
            "amount": tx.amount,
        },
    )
    await publisher.publish(
        db,
        "commission.calculated",
        {"aggregate_type": "transaction", "aggregate_id": tx.id, "transaction_id": tx.id, "agent_id": tx.agent_id, "commission": commission},
    )
    db.commit()
    db.refresh(tx)
    return tx
