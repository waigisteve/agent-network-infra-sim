from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import create_access_token, get_current_user, require_roles, verify_password
from backend.app.db import get_db
from backend.app.events import publisher
from backend.app.jobs import build_agent_network_report
from backend.app.masking import mask_customer_record, mask_payload
from backend.app.models import (
    AgentORM,
    CustomerORM,
    EventLogORM,
    FieldAgentORM,
    FloatRequestCreate,
    FloatRequestORM,
    FloatReviewRequest,
    KycReviewRequest,
    LoginRequest,
    PartnerFeedIngestionRequest,
    PartnerORM,
    Role,
    SettlementReconciliationRequest,
    TokenResponse,
    TransactionCreate,
    TransactionORM,
    UserORM,
)
from backend.app.services.float_ops import approve_float_request, reconciliation, reject_float_request
from backend.app.services.partner_ingestion import ingest_bank_settlements, ingest_telco_transactions, reconcile_partner_settlement
from backend.app.services.transactions import create_transaction

router = APIRouter()


def customer_out(customer: CustomerORM) -> dict[str, object]:
    return {
        "id": customer.id,
        "name": customer.name,
        "surname": customer.surname,
        "full_name": f"{customer.name} {customer.surname}",
        "phone": customer.phone,
        "birthday": customer.birthday,
        "national_id": customer.national_id,
        "nationality": customer.nationality,
        "address": customer.address,
        "compliance_status": customer.compliance_status,
        "kyc_collected_by": customer.kyc_collected_by,
        "verified_at": customer.verified_at,
        "compliance_comments": customer.compliance_comments,
    }


def customer_public_out(customer: CustomerORM) -> dict[str, object]:
    return mask_customer_record(customer_out(customer))


def transaction_out(tx: TransactionORM, mask_customer: bool = True) -> dict[str, object]:
    record = {
        "id": tx.id,
        "agent_id": tx.agent_id,
        "customer_id": tx.customer_id,
        "customer_phone": tx.customer_phone,
        "transaction_type": tx.transaction_type,
        "amount": tx.amount,
        "commission": tx.commission,
        "created_at": tx.created_at,
        "status": tx.status,
    }
    return mask_customer_record(record) if mask_customer else record


def user_out(user: UserORM) -> dict[str, object]:
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role, "agent_id": user.agent_id}


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(UserORM).where(UserORM.email == request.email))
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user), user=user_out(user))


@router.get("/me")
async def me(user: Annotated[UserORM, Depends(get_current_user)]) -> dict[str, object]:
    return user_out(user)


@router.get("/agents")
async def agents(db: Annotated[Session, Depends(get_db)], user: Annotated[UserORM, Depends(get_current_user)]) -> list[dict[str, object]]:
    query = select(AgentORM)
    if user.role == Role.agent and user.agent_id:
        query = query.where(AgentORM.id == user.agent_id)
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "field_agent_id": agent.field_agent_id,
            "outlet": agent.outlet,
            "float_balance": agent.float_balance,
            "cash_balance": agent.cash_balance,
            "outstanding_balance": agent.outstanding_balance,
            "latitude": agent.latitude,
            "longitude": agent.longitude,
        }
        for agent in db.scalars(query).all()
    ]


@router.get("/field-agents")
async def field_agents(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.field_agent))],
) -> list[dict[str, object]]:
    return [
        {"id": field_agent.id, "name": field_agent.name, "region": field_agent.region, "phone": field_agent.phone}
        for field_agent in db.scalars(select(FieldAgentORM)).all()
    ]


@router.get("/customers")
async def customers(db: Annotated[Session, Depends(get_db)], _: Annotated[UserORM, Depends(get_current_user)]) -> list[dict[str, object]]:
    return [customer_public_out(customer) for customer in db.scalars(select(CustomerORM)).all()]


@router.post("/kyc/reviews")
async def review_kyc(
    request: KycReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.kyc_reviewer))],
) -> dict[str, object]:
    customer = db.get(CustomerORM, request.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.compliance_status = request.status
    customer.compliance_comments = request.comments
    customer.verified_at = datetime.now(UTC)
    await publisher.publish(
        db,
        "customer.kyc_reviewed",
        {"aggregate_type": "customer", "aggregate_id": customer.id, "customer_id": customer.id, "status": request.status, "reviewer": request.reviewer},
    )
    db.commit()
    db.refresh(customer)
    return customer_public_out(customer)


@router.get("/float/requests")
async def float_requests(db: Annotated[Session, Depends(get_db)], _: Annotated[UserORM, Depends(get_current_user)]) -> list[dict[str, object]]:
    requests = db.scalars(select(FloatRequestORM)).all()
    return [
        {
            "id": request.id,
            "agent_id": request.agent_id,
            "agent_name": db.get(AgentORM, request.agent_id).name if db.get(AgentORM, request.agent_id) else request.agent_id,
            "amount": request.amount,
            "request_type": request.request_type,
            "status": request.status,
            "requested_at": request.requested_at,
            "reviewed_by": request.reviewed_by,
            "reviewed_at": request.reviewed_at,
        }
        for request in requests
    ]


@router.post("/float/requests")
async def create_float_request(
    request: FloatRequestCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[UserORM, Depends(require_roles(Role.admin, Role.agent))],
) -> dict[str, object]:
    agent_id = user.agent_id if user.role == Role.agent and user.agent_id else request.agent_id
    item = FloatRequestORM(id=f"fr_{uuid4().hex[:10]}", agent_id=agent_id, amount=request.amount, request_type=request.request_type)
    db.add(item)
    db.flush()
    await publisher.publish(
        db,
        "float.requested",
        {"aggregate_type": "float_request", "aggregate_id": item.id, "request_id": item.id, "float_request_id": item.id, "agent_id": item.agent_id, "amount": item.amount},
    )
    db.commit()
    db.refresh(item)
    return {"id": item.id, "agent_id": item.agent_id, "amount": item.amount, "request_type": item.request_type, "status": item.status}


@router.post("/float/requests/{request_id}/approve")
async def approve_float(
    request_id: str,
    request: FloatReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> dict[str, object]:
    try:
        item = await approve_float_request(db, request_id, request.reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": item.id, "agent_id": item.agent_id, "amount": item.amount, "status": item.status}


@router.post("/float/requests/{request_id}/reject")
async def reject_float(
    request_id: str,
    request: FloatReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> dict[str, object]:
    try:
        item = await reject_float_request(db, request_id, request.reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": item.id, "agent_id": item.agent_id, "amount": item.amount, "status": item.status}


@router.get("/float/reconciliation")
async def float_reconciliation(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.field_agent))],
) -> list[dict[str, object]]:
    return [row.model_dump() for row in reconciliation(db)]


@router.get("/transactions")
async def transactions(db: Annotated[Session, Depends(get_db)], user: Annotated[UserORM, Depends(get_current_user)]) -> list[dict[str, object]]:
    query = select(TransactionORM)
    if user.role == Role.agent and user.agent_id:
        query = query.where(TransactionORM.agent_id == user.agent_id)
    return [
        transaction_out(tx)
        for tx in db.scalars(query).all()
    ]


@router.post("/transactions")
async def post_transaction(
    request: TransactionCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[UserORM, Depends(require_roles(Role.admin, Role.agent))],
) -> dict[str, object]:
    if user.role == Role.agent and user.agent_id:
        request.agent_id = user.agent_id
    try:
        tx = await create_transaction(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": tx.id, "agent_id": tx.agent_id, "amount": tx.amount, "commission": tx.commission, "transaction_type": tx.transaction_type}


@router.get("/commissions")
async def commissions(db: Annotated[Session, Depends(get_db)], _: Annotated[UserORM, Depends(get_current_user)]) -> dict[str, object]:
    by_agent: dict[str, int] = {}
    for tx in db.scalars(select(TransactionORM)).all():
        by_agent[tx.agent_id] = by_agent.get(tx.agent_id, 0) + tx.commission
    return {"total": sum(by_agent.values()), "by_agent": by_agent}


@router.get("/reports/agent-network")
async def agent_network_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.field_agent))],
) -> dict[str, object]:
    return build_agent_network_report(db).model_dump(mode="json")


@router.get("/reports/agent/{agent_id}")
async def agent_report(agent_id: str, db: Annotated[Session, Depends(get_db)], user: Annotated[UserORM, Depends(get_current_user)]) -> dict[str, object]:
    if user.role == Role.agent and user.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Insufficient role")
    agent = db.get(AgentORM, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_transactions = list(db.scalars(select(TransactionORM).where(TransactionORM.agent_id == agent_id)).all())
    return {
        "agent": {"id": agent.id, "name": agent.name, "float_balance": agent.float_balance, "cash_balance": agent.cash_balance},
        "float_balance": agent.float_balance,
        "commission_earned": sum(tx.commission for tx in agent_transactions),
        "transactions": [
            transaction_out(tx)
            for tx in agent_transactions
        ],
    }


@router.get("/maps/field-team")
async def field_team_map(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.field_agent))],
) -> dict[str, object]:
    agents = [
        {"id": agent.id, "name": agent.name, "field_agent_id": agent.field_agent_id, "latitude": agent.latitude, "longitude": agent.longitude, "float_balance": agent.float_balance}
        for agent in db.scalars(select(AgentORM)).all()
    ]
    return {
        "center": {"latitude": 13.4549, "longitude": -16.5790},
        "agents": agents,
        "activity": [
            {"agent_id": tx.agent_id, "amount": tx.amount, "type": tx.transaction_type, "created_at": tx.created_at}
            for tx in db.scalars(select(TransactionORM)).all()
        ],
        "heatmap": [{"latitude": item["latitude"], "longitude": item["longitude"], "weight": max(item["float_balance"] / 10_000, 1)} for item in agents],
    }


@router.get("/events")
async def events(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> list[dict[str, object]]:
    return [
        {
            "id": event.id,
            "topic": event.topic,
            "name": event.name,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "agent_id": event.agent_id,
            "customer_id": event.customer_id,
            "float_request_id": event.float_request_id,
            "transaction_id": event.transaction_id,
            "payload": mask_payload(event.payload),
            "created_at": event.created_at,
        }
        for event in db.scalars(select(EventLogORM).order_by(EventLogORM.created_at.desc())).all()
    ]


@router.get("/partners")
async def partners(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin, Role.field_agent))],
) -> list[dict[str, object]]:
    return [
        {
            "id": partner.id,
            "code": partner.code,
            "name": partner.name,
            "partner_type": partner.partner_type,
            "country": partner.country,
            "integration_mode": partner.integration_mode,
            "data_freshness_sla_minutes": partner.data_freshness_sla_minutes,
            "is_active": partner.is_active,
        }
        for partner in db.scalars(select(PartnerORM)).all()
    ]


@router.post("/integrations/telco-transactions")
async def ingest_telco_transaction_feed(
    request: PartnerFeedIngestionRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> dict[str, object]:
    run = ingest_telco_transactions(db, request.contract_name, request.source_reference, request.records)
    return {
        "id": run.id,
        "partner_id": run.partner_id,
        "feed_name": run.feed_name,
        "status": run.status,
        "records_received": run.records_received,
        "records_loaded": run.records_loaded,
        "records_rejected": run.records_rejected,
        "error_summary": run.error_summary,
    }


@router.post("/integrations/bank-settlements")
async def ingest_bank_settlement_feed(
    request: PartnerFeedIngestionRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> dict[str, object]:
    run = ingest_bank_settlements(db, request.contract_name, request.source_reference, request.records)
    return {
        "id": run.id,
        "partner_id": run.partner_id,
        "feed_name": run.feed_name,
        "status": run.status,
        "records_received": run.records_received,
        "records_loaded": run.records_loaded,
        "records_rejected": run.records_rejected,
        "error_summary": run.error_summary,
    }


@router.post("/integrations/reconcile-settlement")
async def reconcile_settlement(
    request: SettlementReconciliationRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[UserORM, Depends(require_roles(Role.admin))],
) -> dict[str, object]:
    try:
        exception = reconcile_partner_settlement(db, request.partner_id, request.settlement_reference)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if exception is None:
        return {"status": "matched", "exception": None}
    return {"status": "exception", "exception": {"id": exception.id, "type": exception.exception_type, "evidence": exception.evidence}}
