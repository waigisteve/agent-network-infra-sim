"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


role = sa.Enum("admin", "field_agent", "agent", "kyc_reviewer", name="role")
float_status = sa.Enum("pending", "approved", "rejected", name="floatrequeststatus")
compliance_status = sa.Enum("pending", "approved", "rejected", name="compliancestatus")


def upgrade() -> None:
    op.create_table("field_agents", sa.Column("id", sa.String(64), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("region", sa.String(255), nullable=False), sa.Column("phone", sa.String(64), nullable=False))
    op.create_table("agents", sa.Column("id", sa.String(64), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("field_agent_id", sa.String(64), sa.ForeignKey("field_agents.id"), nullable=False), sa.Column("outlet", sa.String(255), nullable=False), sa.Column("float_balance", sa.Integer(), nullable=False), sa.Column("cash_balance", sa.Integer(), nullable=False), sa.Column("outstanding_balance", sa.Integer(), nullable=False), sa.Column("latitude", sa.Float(), nullable=False), sa.Column("longitude", sa.Float(), nullable=False))
    op.create_table("users", sa.Column("id", sa.String(64), primary_key=True), sa.Column("email", sa.String(255), nullable=False, unique=True), sa.Column("full_name", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", role, nullable=False), sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id")), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("customers", sa.Column("id", sa.String(64), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("surname", sa.String(255), nullable=False), sa.Column("phone", sa.String(64), nullable=False), sa.Column("birthday", sa.String(64), nullable=False), sa.Column("national_id", sa.String(128), nullable=False), sa.Column("nationality", sa.String(128), nullable=False), sa.Column("address", sa.Text(), nullable=False), sa.Column("compliance_status", compliance_status, nullable=False), sa.Column("kyc_collected_by", sa.String(255), nullable=False), sa.Column("verified_at", sa.DateTime(timezone=True)), sa.Column("compliance_comments", sa.Text()))
    op.create_table("float_requests", sa.Column("id", sa.String(64), primary_key=True), sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False), sa.Column("amount", sa.Integer(), nullable=False), sa.Column("request_type", sa.String(32), nullable=False), sa.Column("status", float_status, nullable=False), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reviewed_by", sa.String(255)), sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_table("transactions", sa.Column("id", sa.String(64), primary_key=True), sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False), sa.Column("customer_phone", sa.String(64), nullable=False), sa.Column("transaction_type", sa.String(64), nullable=False), sa.Column("amount", sa.Integer(), nullable=False), sa.Column("commission", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(64), nullable=False))
    op.create_table("event_log", sa.Column("id", sa.String(64), primary_key=True), sa.Column("topic", sa.String(128), nullable=False), sa.Column("name", sa.String(128), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("analytics_snapshots", sa.Column("id", sa.String(64), primary_key=True), sa.Column("snapshot_date", sa.Date(), nullable=False), sa.Column("metrics", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("worker_errors", sa.Column("id", sa.String(64), primary_key=True), sa.Column("source", sa.String(128), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("payload", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    for table in ("worker_errors", "analytics_snapshots", "event_log", "transactions", "float_requests", "customers", "users", "agents", "field_agents"):
        op.drop_table(table)

