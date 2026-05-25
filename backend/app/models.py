from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    admin = "admin"
    field_agent = "field_agent"
    agent = "agent"
    kyc_reviewer = "kyc_reviewer"


class FloatRequestStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ComplianceStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FieldAgentORM(Base):
    __tablename__ = "field_agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(64))
    agents: Mapped[list[AgentORM]] = relationship(back_populates="field_agent")


class AgentORM(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_field_agent_name", "field_agent_id", "name"),
        Index("ix_agents_location", "latitude", "longitude"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    field_agent_id: Mapped[str] = mapped_column(ForeignKey("field_agents.id"), index=True)
    outlet: Mapped[str] = mapped_column(String(255))
    float_balance: Mapped[int] = mapped_column(Integer, default=0)
    cash_balance: Mapped[int] = mapped_column(Integer, default=0)
    outstanding_balance: Mapped[int] = mapped_column(Integer, default=0)
    latitude: Mapped[float]
    longitude: Mapped[float]
    field_agent: Mapped[FieldAgentORM] = relationship(back_populates="agents")
    transactions: Mapped[list[TransactionORM]] = relationship(back_populates="agent")


class CustomerORM(Base):
    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_status_verified", "compliance_status", "verified_at"),
        Index("ix_customers_name_surname", "name", "surname"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    surname: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(64), index=True)
    birthday: Mapped[str] = mapped_column(String(64))
    national_id: Mapped[str] = mapped_column(String(128))
    nationality: Mapped[str] = mapped_column(String(128))
    address: Mapped[str] = mapped_column(Text)
    compliance_status: Mapped[ComplianceStatus] = mapped_column(Enum(ComplianceStatus), default=ComplianceStatus.pending)
    kyc_collected_by: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compliance_comments: Mapped[str | None] = mapped_column(Text, nullable=True)


class FloatRequestORM(Base):
    __tablename__ = "float_requests"
    __table_args__ = (
        Index("ix_float_requests_status_requested", "status", "requested_at"),
        Index("ix_float_requests_agent_status", "agent_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    request_type: Mapped[str] = mapped_column(String(32), default="float")
    status: Mapped[FloatRequestStatus] = mapped_column(Enum(FloatRequestStatus), default=FloatRequestStatus.pending, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TransactionORM(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_agent_created", "agent_id", "created_at"),
        Index("ix_transactions_customer_created", "customer_id", "created_at"),
        Index("ix_transactions_type_created", "transaction_type", "created_at"),
        Index("ix_transactions_phone_created", "customer_phone", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    customer_phone: Mapped[str] = mapped_column(String(64))
    transaction_type: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    commission: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(64), default="posted")
    agent: Mapped[AgentORM] = relationship(back_populates="transactions")


class EventLogORM(Base):
    __tablename__ = "event_log"
    __table_args__ = (
        Index("ix_event_log_topic_created", "topic", "created_at"),
        Index("ix_event_log_name_created", "name", "created_at"),
        Index("ix_event_log_aggregate", "aggregate_type", "aggregate_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    aggregate_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    float_request_id: Mapped[str | None] = mapped_column(ForeignKey("float_requests.id"), nullable=True, index=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalyticsSnapshotORM(Base):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        Index("ix_analytics_scope_date", "scope", "snapshot_date"),
        Index("ix_analytics_agent_date", "agent_id", "snapshot_date"),
        Index("ix_analytics_field_agent_date", "field_agent_id", "snapshot_date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    scope: Mapped[str] = mapped_column(String(64), default="network", index=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    field_agent_id: Mapped[str | None] = mapped_column(ForeignKey("field_agents.id"), nullable=True, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkerErrorORM(Base):
    __tablename__ = "worker_errors"
    __table_args__ = (Index("ix_worker_errors_source_created", "source", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("event_log.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class LoginRequest(BaseModel):
    email: str
    password: str


class AgentOut(OrmModel):
    id: str
    name: str
    field_agent_id: str
    outlet: str
    float_balance: int
    cash_balance: int
    outstanding_balance: int
    latitude: float
    longitude: float


class FieldAgentOut(OrmModel):
    id: str
    name: str
    region: str
    phone: str


class CustomerOut(OrmModel):
    id: str
    name: str
    surname: str
    phone: str
    birthday: str
    national_id: str
    nationality: str
    address: str
    compliance_status: ComplianceStatus
    kyc_collected_by: str
    verified_at: datetime | None = None
    compliance_comments: str | None = None
    full_name: str


class FloatRequestCreate(BaseModel):
    agent_id: str
    amount: int
    request_type: str = "float"


class FloatReviewRequest(BaseModel):
    reviewer: str = "operations-admin"


class KycReviewRequest(BaseModel):
    customer_id: str
    status: ComplianceStatus
    reviewer: str
    comments: str | None = None


class TransactionCreate(BaseModel):
    agent_id: str
    customer_id: str | None = None
    customer_phone: str
    transaction_type: str
    amount: int


class ReconciliationRow(BaseModel):
    agent_id: str
    agent_name: str
    field_agent: str
    cash_in_amount: int
    cash_out_amount: int
    cash_received: int
    cash_returned: int
    float_received: int
    float_returned: int
    balance_owed: int


class AnalyticsMetric(BaseModel):
    label: str
    value: float
    benchmark_delta: float
    trend: list[int]


class AgentNetworkReport(BaseModel):
    metrics: list[AnalyticsMetric]
    generated_at: datetime = Field(default_factory=utcnow)
