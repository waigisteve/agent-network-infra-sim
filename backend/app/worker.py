from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from aiokafka import AIOKafkaConsumer

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.jobs import materialize_analytics_snapshot
from backend.app.models import WorkerErrorORM


TOPICS = ["float-events", "transaction-events", "kyc-events", "agent-location-events", "commission-events"]


async def consume_forever() -> None:
    if not settings.kafka_enabled:
        with SessionLocal() as db:
            materialize_analytics_snapshot(db)
        print("Kafka disabled; materialized analytics snapshot once.")
        return
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="agent-network-worker",
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for message in consumer:
            try:
                _ = json.loads(message.value.decode("utf-8"))
                with SessionLocal() as db:
                    materialize_analytics_snapshot(db)
            except Exception as exc:  # pragma: no cover - defensive worker path
                with SessionLocal() as db:
                    event_id = None
                    try:
                        event_id = json.loads(message.value.decode("utf-8")).get("id")
                    except json.JSONDecodeError:
                        event_id = None
                    db.add(WorkerErrorORM(id=str(uuid4()), event_id=event_id, source=message.topic, message=str(exc), payload={"raw": message.value.decode("utf-8")}))
                    db.commit()
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(consume_forever())


if __name__ == "__main__":
    main()
