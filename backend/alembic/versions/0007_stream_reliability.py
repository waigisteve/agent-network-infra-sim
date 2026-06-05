"""stream reliability

Revision ID: 0007_stream_reliability
Revises: 0006_settlement_counterparty
Create Date: 2026-06-05
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

revision = "0007_stream_reliability"
down_revision = "0006_settlement_counterparty"
branch_labels = None
depends_on = None


STREAM_TABLES = ("stream_consumer_offsets", "dead_letter_events")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    op.create_table(
        "stream_consumer_offsets",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("consumer_group", sa.String(128), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=False),
        sa.Column("last_offset", sa.Integer(), nullable=False),
        sa.Column("last_event_id", sa.String(64), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("consumer_group", "topic", "partition", name="uq_stream_consumer_offsets_position"),
    )
    op.create_index("ix_stream_offsets_group_topic", "stream_consumer_offsets", ["consumer_group", "topic"])
    op.create_index("ix_stream_offsets_updated", "stream_consumer_offsets", ["updated_at"])

    op.create_table(
        "dead_letter_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("consumer_group", sa.String(128), nullable=False),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=True),
        sa.Column("offset", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.String(64), nullable=True),
        sa.Column("event_name", sa.String(128), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_dead_letter_status_created", "dead_letter_events", ["status", "created_at"])
    op.create_index("ix_dead_letter_topic_created", "dead_letter_events", ["topic", "created_at"])
    op.create_index("ix_dead_letter_event_id", "dead_letter_events", ["event_id"])

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    app_user = os.getenv("POSTGRES_APP_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()
    for table in STREAM_TABLES:
        table_identifier = _quote_identifier(table)
        op.execute(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_identifier} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_app_rw ON {table_identifier}
            FOR ALL
            USING (true)
            WITH CHECK (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY {table}_readonly ON {table_identifier}
            FOR SELECT
            USING (true)
            """
        )
        if app_user:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_identifier} TO {_quote_identifier(app_user)}")
        if readonly_user:
            op.execute(f"GRANT SELECT ON {table_identifier} TO {_quote_identifier(readonly_user)}")


def downgrade() -> None:
    op.drop_index("ix_dead_letter_event_id", table_name="dead_letter_events")
    op.drop_index("ix_dead_letter_topic_created", table_name="dead_letter_events")
    op.drop_index("ix_dead_letter_status_created", table_name="dead_letter_events")
    op.drop_table("dead_letter_events")
    op.drop_index("ix_stream_offsets_updated", table_name="stream_consumer_offsets")
    op.drop_index("ix_stream_offsets_group_topic", table_name="stream_consumer_offsets")
    op.drop_table("stream_consumer_offsets")
