"""partner integration and reconciliation schema

Revision ID: 0003_partner_integrations
Revises: 0002_postgres_security
Create Date: 2026-05-28
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

revision = "0003_partner_integrations"
down_revision = "0002_postgres_security"
branch_labels = None
depends_on = None


partner_type = sa.Enum("telco", "bank", "agent_app", name="partnertype")
integration_mode = sa.Enum("kafka", "sftp", "api", "database_replica", name="integrationmode")
integration_status = sa.Enum("received", "validated", "loaded", "reconciled", "failed", name="integrationrunstatus")

TABLES = (
    "partners",
    "partner_contracts",
    "integration_runs",
    "raw_partner_transactions",
    "bank_settlements",
    "reconciliation_exceptions",
)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _apply_postgres_security() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    app_user = os.getenv("POSTGRES_APP_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()
    for table in TABLES:
        table_identifier = _quote_identifier(table)
        op.execute(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_identifier} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {table}_app_rw ON {table_identifier} FOR ALL USING (true) WITH CHECK (true)")
        op.execute(f"CREATE POLICY {table}_readonly ON {table_identifier} FOR SELECT USING (true)")
        if app_user:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_identifier} TO {_quote_identifier(app_user)}")
        if readonly_user:
            op.execute(f"GRANT SELECT ON {table_identifier} TO {_quote_identifier(readonly_user)}")


def upgrade() -> None:
    op.create_table(
        "partners",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("partner_type", partner_type, nullable=False),
        sa.Column("country", sa.String(64), nullable=False),
        sa.Column("integration_mode", integration_mode, nullable=False),
        sa.Column("data_freshness_sla_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_partners_code"),
    )
    op.create_index("ix_partners_type_country", "partners", ["partner_type", "country"])
    op.create_index(op.f("ix_partners_partner_type"), "partners", ["partner_type"])
    op.create_index(op.f("ix_partners_country"), "partners", ["country"])
    op.create_index(op.f("ix_partners_integration_mode"), "partners", ["integration_mode"])
    op.create_index(op.f("ix_partners_is_active"), "partners", ["is_active"])

    op.create_table(
        "partner_contracts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("feed_name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("schema_contract", sa.JSON(), nullable=False),
        sa.Column("pii_fields", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.JSON(), nullable=False),
        sa.Column("arrival_sla", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("partner_id", "feed_name", "version", name="uq_partner_contract_version"),
    )
    op.create_index("ix_partner_contracts_partner_active", "partner_contracts", ["partner_id", "is_active"])
    op.create_index(op.f("ix_partner_contracts_partner_id"), "partner_contracts", ["partner_id"])
    op.create_index(op.f("ix_partner_contracts_feed_name"), "partner_contracts", ["feed_name"])
    op.create_index(op.f("ix_partner_contracts_is_active"), "partner_contracts", ["is_active"])

    op.create_table(
        "integration_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("contract_id", sa.String(64), sa.ForeignKey("partner_contracts.id")),
        sa.Column("feed_name", sa.String(128), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=False),
        sa.Column("status", integration_status, nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False),
        sa.Column("records_loaded", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("partner_id", "feed_name", "source_reference", name="uq_integration_runs_source"),
    )
    op.create_index("ix_integration_runs_partner_started", "integration_runs", ["partner_id", "started_at"])
    op.create_index("ix_integration_runs_status_started", "integration_runs", ["status", "started_at"])
    op.create_index(op.f("ix_integration_runs_partner_id"), "integration_runs", ["partner_id"])
    op.create_index(op.f("ix_integration_runs_contract_id"), "integration_runs", ["contract_id"])
    op.create_index(op.f("ix_integration_runs_feed_name"), "integration_runs", ["feed_name"])
    op.create_index(op.f("ix_integration_runs_status"), "integration_runs", ["status"])

    op.create_table(
        "raw_partner_transactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("integration_run_id", sa.String(64), sa.ForeignKey("integration_runs.id"), nullable=False),
        sa.Column("provider_reference", sa.String(128), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("customer_msisdn_hash", sa.String(128), nullable=False),
        sa.Column("transaction_type", sa.String(64), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("commission", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("transaction_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("partner_id", "provider_reference", name="uq_raw_partner_provider_reference"),
    )
    op.create_index("ix_raw_partner_transactions_partner_created", "raw_partner_transactions", ["partner_id", "transaction_created_at"])
    op.create_index("ix_raw_partner_transactions_agent_created", "raw_partner_transactions", ["agent_id", "transaction_created_at"])
    op.create_index(op.f("ix_raw_partner_transactions_partner_id"), "raw_partner_transactions", ["partner_id"])
    op.create_index(op.f("ix_raw_partner_transactions_integration_run_id"), "raw_partner_transactions", ["integration_run_id"])
    op.create_index(op.f("ix_raw_partner_transactions_provider_reference"), "raw_partner_transactions", ["provider_reference"])
    op.create_index(op.f("ix_raw_partner_transactions_agent_id"), "raw_partner_transactions", ["agent_id"])
    op.create_index(op.f("ix_raw_partner_transactions_customer_msisdn_hash"), "raw_partner_transactions", ["customer_msisdn_hash"])
    op.create_index(op.f("ix_raw_partner_transactions_transaction_type"), "raw_partner_transactions", ["transaction_type"])
    op.create_index(op.f("ix_raw_partner_transactions_status"), "raw_partner_transactions", ["status"])
    op.create_index(op.f("ix_raw_partner_transactions_transaction_created_at"), "raw_partner_transactions", ["transaction_created_at"])

    op.create_table(
        "bank_settlements",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("integration_run_id", sa.String(64), sa.ForeignKey("integration_runs.id"), nullable=False),
        sa.Column("settlement_reference", sa.String(128), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("gross_amount", sa.Integer(), nullable=False),
        sa.Column("commission_amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("partner_id", "settlement_reference", name="uq_bank_settlement_reference"),
    )
    op.create_index("ix_bank_settlements_partner_date", "bank_settlements", ["partner_id", "settlement_date"])
    op.create_index(op.f("ix_bank_settlements_partner_id"), "bank_settlements", ["partner_id"])
    op.create_index(op.f("ix_bank_settlements_integration_run_id"), "bank_settlements", ["integration_run_id"])
    op.create_index(op.f("ix_bank_settlements_settlement_reference"), "bank_settlements", ["settlement_reference"])

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("partner_id", sa.String(64), sa.ForeignKey("partners.id"), nullable=False),
        sa.Column("integration_run_id", sa.String(64), sa.ForeignKey("integration_runs.id")),
        sa.Column("exception_type", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reconciliation_exceptions_partner_status", "reconciliation_exceptions", ["partner_id", "status"])
    op.create_index("ix_reconciliation_exceptions_type_created", "reconciliation_exceptions", ["exception_type", "created_at"])
    op.create_index(op.f("ix_reconciliation_exceptions_partner_id"), "reconciliation_exceptions", ["partner_id"])
    op.create_index(op.f("ix_reconciliation_exceptions_integration_run_id"), "reconciliation_exceptions", ["integration_run_id"])
    op.create_index(op.f("ix_reconciliation_exceptions_exception_type"), "reconciliation_exceptions", ["exception_type"])
    op.create_index(op.f("ix_reconciliation_exceptions_severity"), "reconciliation_exceptions", ["severity"])
    op.create_index(op.f("ix_reconciliation_exceptions_status"), "reconciliation_exceptions", ["status"])
    _apply_postgres_security()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in reversed(TABLES):
            table_identifier = _quote_identifier(table)
            op.execute(f"DROP POLICY IF EXISTS {table}_readonly ON {table_identifier}")
            op.execute(f"DROP POLICY IF EXISTS {table}_app_rw ON {table_identifier}")
            op.execute(f"ALTER TABLE {table_identifier} DISABLE ROW LEVEL SECURITY")
    for table in (
        "reconciliation_exceptions",
        "bank_settlements",
        "raw_partner_transactions",
        "integration_runs",
        "partner_contracts",
        "partners",
    ):
        op.drop_table(table)
    integration_status.drop(op.get_bind(), checkfirst=True)
    integration_mode.drop(op.get_bind(), checkfirst=True)
    partner_type.drop(op.get_bind(), checkfirst=True)
