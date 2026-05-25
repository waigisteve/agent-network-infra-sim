from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.events import publisher
from backend.app.models import AgentORM, FieldAgentORM, FloatRequestORM, FloatRequestStatus, ReconciliationRow, TransactionORM


async def approve_float_request(db: Session, request_id: str, reviewer: str) -> FloatRequestORM:
    request = db.get(FloatRequestORM, request_id)
    if request is None:
        raise ValueError("Float request not found")
    agent = db.get(AgentORM, request.agent_id)
    if agent is None:
        raise ValueError("Agent not found")
    request.status = FloatRequestStatus.approved
    request.reviewed_by = reviewer
    request.reviewed_at = datetime.now(UTC)
    agent.float_balance += request.amount
    agent.outstanding_balance -= request.amount
    await publisher.publish(db, "float.approved", {"request_id": request.id, "agent_id": agent.id, "amount": request.amount})
    await publisher.publish(db, "float.disbursed", {"request_id": request.id, "agent_id": agent.id, "amount": request.amount})
    db.commit()
    db.refresh(request)
    return request


async def reject_float_request(db: Session, request_id: str, reviewer: str) -> FloatRequestORM:
    request = db.get(FloatRequestORM, request_id)
    if request is None:
        raise ValueError("Float request not found")
    request.status = FloatRequestStatus.rejected
    request.reviewed_by = reviewer
    request.reviewed_at = datetime.now(UTC)
    await publisher.publish(db, "float.rejected", {"request_id": request.id, "agent_id": request.agent_id, "amount": request.amount})
    db.commit()
    db.refresh(request)
    return request


def reconciliation(db: Session) -> list[ReconciliationRow]:
    agents = list(db.scalars(select(AgentORM)).all())
    rows: list[ReconciliationRow] = []
    for agent in agents:
        field_agent = db.get(FieldAgentORM, agent.field_agent_id)
        agent_transactions = list(db.scalars(select(TransactionORM).where(TransactionORM.agent_id == agent.id)).all())
        cash_in = sum(tx.amount for tx in agent_transactions if tx.transaction_type in {"deposit", "registration", "airtime"})
        cash_out = sum(tx.amount for tx in agent_transactions if tx.transaction_type == "withdrawal")
        approved_requests = list(
            db.scalars(
                select(FloatRequestORM).where(
                    FloatRequestORM.agent_id == agent.id,
                    FloatRequestORM.status == FloatRequestStatus.approved,
                )
            ).all()
        )
        float_received = sum(req.amount for req in approved_requests)
        cash_received = -max(agent.outstanding_balance, 0)
        cash_returned = max(agent.cash_balance - cash_in, 0)
        rows.append(
            ReconciliationRow(
                agent_id=agent.id,
                agent_name=agent.name,
                field_agent=field_agent.name if field_agent else "Unassigned",
                cash_in_amount=cash_in,
                cash_out_amount=cash_out,
                cash_received=cash_received,
                cash_returned=cash_returned,
                float_received=-float_received,
                float_returned=max(-agent.outstanding_balance, 0),
                balance_owed=cash_received + cash_returned - float_received,
            )
        )
    return rows

