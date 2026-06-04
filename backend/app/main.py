from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.config import settings
from backend.app.db import SessionLocal, create_all
from backend.app.events import publisher
from backend.app.models import SecurityAuditLogORM
from backend.app.routes import api
from backend.app.security_audit import write_security_audit


@asynccontextmanager
async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
    _ = app_instance
    create_all()
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api.router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.middleware("http")
async def security_audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1") and request.url.path != "/api/v1/auth/login" and response.status_code in {401, 403}:
        with SessionLocal() as db:
            write_security_audit(
                db,
                request=request,
                event_type="api_access_blocked",
                outcome="blocked",
                detail=f"HTTP {response.status_code}",
            )
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("backend/static/index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    started_at = perf_counter()
    with SessionLocal() as db:
        db.execute(text("select 1"))
        audit_count = db.query(SecurityAuditLogORM).count()
    kafka = "enabled" if settings.kafka_enabled else "disabled"
    database_latency_ms = round((perf_counter() - started_at) * 1000, 2)
    return {
        "status": "ready",
        "database": "ok",
        "kafka": kafka,
        "checked_at": datetime.now(UTC).isoformat(),
        "components": {
            "database": {"status": "ok", "latency_ms": database_latency_ms},
            "kafka": {"status": kafka, "bootstrap_servers": settings.kafka_bootstrap_servers if settings.kafka_enabled else None},
            "security_audit_log": {"status": "ok", "records": audit_count},
        },
    }
