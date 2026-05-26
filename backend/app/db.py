from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import settings
from backend.app.models import Base


def database_connect_args() -> dict[str, str | bool]:
    if settings.database_url.startswith("sqlite"):
        return {"check_same_thread": False}

    connect_args: dict[str, str | bool] = {}
    if settings.database_ssl_mode:
        connect_args["sslmode"] = settings.database_ssl_mode
    if settings.database_ssl_root_cert:
        connect_args["sslrootcert"] = settings.database_ssl_root_cert
    if settings.database_ssl_cert:
        connect_args["sslcert"] = settings.database_ssl_cert
    if settings.database_ssl_key:
        connect_args["sslkey"] = settings.database_ssl_key
    return connect_args


connect_args = database_connect_args()
engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
if settings.database_url == "sqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def create_all() -> None:
    Base.metadata.create_all(bind=engine)


async def get_db() -> AsyncGenerator[Session, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
