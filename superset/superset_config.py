from __future__ import annotations

import os


SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "local-superset-secret-change-me")
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"
FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}

TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = True


def partner_rls_clause(partner_id: str) -> str:
    return f"partner_id = '{partner_id}'"
