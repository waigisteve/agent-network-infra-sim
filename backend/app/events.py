from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import EventLogORM


TOPICS = {
    "float.requested": "float-events",
    "float.approved": "float-events",
    "float.rejected": "float-events",
    "float.disbursed": "float-events",
    "cash.collected": "transaction-events",
    "cash.deposited": "transaction-events",
    "customer.kyc_submitted": "kyc-events",
    "customer.kyc_reviewed": "kyc-events",
    "transaction.created": "transaction-events",
    "commission.calculated": "commission-events",
    "agent.location_updated": "agent-location-events",
}


class EventPublisher:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if not settings.kafka_enabled:
            return
        self._producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, db: Session, name: str, payload: dict[str, Any]) -> EventLogORM:
        topic = TOPICS.get(name, "platform-events")
        event = EventLogORM(id=str(uuid4()), topic=topic, name=name, payload=payload)
        db.add(event)
        db.flush()
        if self._producer is not None:
            message = {"id": event.id, "name": name, "payload": payload, "created_at": event.created_at.isoformat()}
            await self._producer.send_and_wait(topic, json.dumps(message).encode("utf-8"))
        return event


publisher = EventPublisher()

