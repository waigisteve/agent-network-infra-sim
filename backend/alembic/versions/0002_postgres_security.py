"""postgres security controls

Revision ID: 0002_postgres_security
Revises: 0001_initial
Create Date: 2026-05-26
"""
from __future__ import annotations

import os

from alembic import op

revision = "0002_postgres_security"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

TABLES = (
    "field_agents",
    "agents",
    "users",
    "customers",
    "float_requests",
    "transactions",
    "event_log",
    "analytics_snapshots",
    "worker_errors",
)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    app_user = os.getenv("POSTGRES_APP_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()

    for table in TABLES:
        table_identifier = _quote_identifier(table)
        op.execute(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_identifier} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public'
                    AND tablename = '{table}'
                    AND policyname = '{table}_app_rw'
                ) THEN
                    CREATE POLICY {table}_app_rw ON {table_identifier}
                    FOR ALL
                    USING (true)
                    WITH CHECK (true);
                END IF;
            END
            $$;
            """
        )
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public'
                    AND tablename = '{table}'
                    AND policyname = '{table}_readonly'
                ) THEN
                    CREATE POLICY {table}_readonly ON {table_identifier}
                    FOR SELECT
                    USING (true);
                END IF;
            END
            $$;
            """
        )

        if app_user:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_identifier} TO {_quote_identifier(app_user)}")
        if readonly_user:
            op.execute(f"GRANT SELECT ON {table_identifier} TO {_quote_identifier(readonly_user)}")

    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in reversed(TABLES):
        table_identifier = _quote_identifier(table)
        op.execute(f"DROP POLICY IF EXISTS {table}_readonly ON {table_identifier}")
        op.execute(f"DROP POLICY IF EXISTS {table}_app_rw ON {table_identifier}")
        op.execute(f"ALTER TABLE {table_identifier} DISABLE ROW LEVEL SECURITY")
