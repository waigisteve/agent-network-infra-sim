"""settlement counterparty

Revision ID: 0006_settlement_counterparty
Revises: 0005_security_audit_log
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_settlement_counterparty"
down_revision = "0005_security_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_settlements", sa.Column("settled_partner_id", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_bank_settlements_settled_partner_id_partners",
        "bank_settlements",
        "partners",
        ["settled_partner_id"],
        ["id"],
    )
    op.create_index("ix_bank_settlements_settled_partner_date", "bank_settlements", ["settled_partner_id", "settlement_date"])
    op.create_index(op.f("ix_bank_settlements_settled_partner_id"), "bank_settlements", ["settled_partner_id"])
    op.execute("UPDATE bank_settlements SET settled_partner_id = partner_id WHERE settled_partner_id IS NULL")
    op.alter_column("bank_settlements", "settled_partner_id", nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bank_settlements_settled_partner_id"), table_name="bank_settlements")
    op.drop_index("ix_bank_settlements_settled_partner_date", table_name="bank_settlements")
    op.drop_constraint("fk_bank_settlements_settled_partner_id_partners", "bank_settlements", type_="foreignkey")
    op.drop_column("bank_settlements", "settled_partner_id")
