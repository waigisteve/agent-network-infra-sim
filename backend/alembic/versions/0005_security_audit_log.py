"""security audit log

Revision ID: 0005_security_audit_log
Revises: 0004_analytics_schemas
Create Date: 2026-06-05
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_security_audit_log"
down_revision = "0004_analytics_schemas"
branch_labels = None
depends_on = None

role = postgresql.ENUM("admin", "field_agent", "agent", "kyc_reviewer", name="role", create_type=False)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", role, nullable=True),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("client_host", sa.String(128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_audit_event_created", "security_audit_log", ["event_type", "created_at"])
    op.create_index("ix_security_audit_outcome_created", "security_audit_log", ["outcome", "created_at"])
    op.create_index("ix_security_audit_user_created", "security_audit_log", ["user_id", "created_at"])

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    table_identifier = _quote_identifier("security_audit_log")
    app_user = os.getenv("POSTGRES_APP_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()

    op.execute(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_identifier} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY security_audit_log_app_rw ON security_audit_log
        FOR ALL
        USING (true)
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY security_audit_log_readonly ON security_audit_log
        FOR SELECT
        USING (true)
        """
    )

    if app_user:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_identifier} TO {_quote_identifier(app_user)}")
    if readonly_user:
        op.execute(f"GRANT SELECT ON {table_identifier} TO {_quote_identifier(readonly_user)}")


def downgrade() -> None:
    op.drop_index("ix_security_audit_user_created", table_name="security_audit_log")
    op.drop_index("ix_security_audit_outcome_created", table_name="security_audit_log")
    op.drop_index("ix_security_audit_event_created", table_name="security_audit_log")
    op.drop_table("security_audit_log")
