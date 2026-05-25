from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.app.config import settings
from backend.app.db import SessionLocal, create_all
from backend.app.events import publisher
from backend.app.routes import api


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


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("backend/static/index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("select 1"))
    kafka = "enabled" if settings.kafka_enabled else "disabled"
    return {"status": "ready", "database": "ok", "kafka": kafka}

