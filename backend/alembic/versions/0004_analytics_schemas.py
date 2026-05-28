"""analytics schemas for dbt marts

Revision ID: 0004_analytics_schemas
Revises: 0003_partner_integrations
Create Date: 2026-05-28
"""
from __future__ import annotations

import os

from alembic import op

revision = "0004_analytics_schemas"
down_revision = "0003_partner_integrations"
branch_labels = None
depends_on = None

SCHEMAS = ("analytics_staging", "analytics_intermediate", "analytics_marts")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    owner_user = os.getenv("POSTGRES_OWNER_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()

    for schema in SCHEMAS:
        schema_identifier = _quote_identifier(schema)
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_identifier}")
        if owner_user:
            op.execute(f"ALTER SCHEMA {schema_identifier} OWNER TO {_quote_identifier(owner_user)}")
            op.execute(f"GRANT USAGE, CREATE ON SCHEMA {schema_identifier} TO {_quote_identifier(owner_user)}")
        if owner_user and readonly_user:
            op.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {_quote_identifier(owner_user)} "
                f"IN SCHEMA {schema_identifier} GRANT SELECT ON TABLES TO {_quote_identifier(readonly_user)}"
            )
        if readonly_user:
            op.execute(f"GRANT USAGE ON SCHEMA {schema_identifier} TO {_quote_identifier(readonly_user)}")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {_quote_identifier(schema)} CASCADE")
