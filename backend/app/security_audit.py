from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.models import Role, SecurityAuditLogORM, UserORM


def client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


def write_security_audit(
    db: Session,
    *,
    request: Request,
    event_type: str,
    outcome: str,
    detail: str,
    user: UserORM | None = None,
    email: str | None = None,
) -> None:
    audit = SecurityAuditLogORM(
        id=str(uuid4()),
        event_type=event_type,
        outcome=outcome,
        user_id=user.id if user else None,
        email=email,
        role=user.role if user else None,
        method=request.method,
        path=request.url.path,
        client_host=client_host(request),
        detail=detail,
    )
    db.add(audit)
    db.commit()


def role_values(roles: tuple[Role, ...]) -> str:
    return ", ".join(role.value for role in roles)
