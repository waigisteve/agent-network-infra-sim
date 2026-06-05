"""kyc documents

Revision ID: 0008_kyc_documents
Revises: 0007_stream_reliability
Create Date: 2026-06-05
"""
from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

revision = "0008_kyc_documents"
down_revision = "0007_stream_reliability"
branch_labels = None
depends_on = None


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade() -> None:
    op.create_table(
        "kyc_documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("customer_id", sa.String(64), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_backend", sa.String(32), nullable=False, server_default="local"),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_kyc_documents_customer_created", "kyc_documents", ["customer_id", "created_at"])
    op.create_index("ix_kyc_documents_status_created", "kyc_documents", ["verification_status", "created_at"])
    op.create_index("ix_kyc_documents_sha256_hash", "kyc_documents", ["sha256_hash"])
    op.create_index("ix_kyc_documents_uploaded_by", "kyc_documents", ["uploaded_by"])

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    table_identifier = _quote_identifier("kyc_documents")
    app_user = os.getenv("POSTGRES_APP_USER", "").strip()
    readonly_user = os.getenv("POSTGRES_READONLY_USER", "").strip()

    op.execute(f"ALTER TABLE {table_identifier} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_identifier} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY kyc_documents_app_rw ON kyc_documents
        FOR ALL
        USING (true)
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY kyc_documents_readonly ON kyc_documents
        FOR SELECT
        USING (true)
        """
    )
    if app_user:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_identifier} TO {_quote_identifier(app_user)}")
    if readonly_user:
        op.execute(f"GRANT SELECT ON {table_identifier} TO {_quote_identifier(readonly_user)}")


def downgrade() -> None:
    op.drop_index("ix_kyc_documents_uploaded_by", table_name="kyc_documents")
    op.drop_index("ix_kyc_documents_sha256_hash", table_name="kyc_documents")
    op.drop_index("ix_kyc_documents_status_created", table_name="kyc_documents")
    op.drop_index("ix_kyc_documents_customer_created", table_name="kyc_documents")
    op.drop_table("kyc_documents")
