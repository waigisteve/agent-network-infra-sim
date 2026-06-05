from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aiokafka import AIOKafkaConsumer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.jobs import materialize_analytics_snapshot
from backend.app.models import DeadLetterEventORM, StreamConsumerOffsetORM, WorkerErrorORM


TOPICS = ["float-events", "transaction-events", "kyc-events", "agent-location-events", "commission-events"]
CONSUMER_GROUP = "agent-network-worker"


def _offset_id(consumer_group: str, topic: str, partition: int) -> str:
    return f"{consumer_group}:{topic}:{partition}"


def record_stream_success(db: Session, consumer_group: str, topic: str, partition: int, offset: int, event_id: str | None) -> StreamConsumerOffsetORM:
    now = datetime.now(UTC)
    offset_row = db.scalar(
        select(StreamConsumerOffsetORM).where(
            StreamConsumerOffsetORM.consumer_group == consumer_group,
            StreamConsumerOffsetORM.topic == topic,
            StreamConsumerOffsetORM.partition == partition,
        )
    )
    if offset_row is None:
        offset_row = StreamConsumerOffsetORM(
            id=_offset_id(consumer_group, topic, partition),
            consumer_group=consumer_group,
            topic=topic,
            partition=partition,
            last_offset=offset,
            last_event_id=event_id,
            processed_count=1,
            failed_count=0,
            last_processed_at=now,
            updated_at=now,
        )
        db.add(offset_row)
    else:
        offset_row.last_offset = max(offset_row.last_offset, offset)
        offset_row.last_event_id = event_id
        offset_row.processed_count += 1
        offset_row.last_processed_at = now
        offset_row.updated_at = now
    return offset_row


def record_stream_failure(
    db: Session,
    consumer_group: str,
    topic: str,
    partition: int | None,
    offset: int | None,
    raw_payload: str,
    failure_reason: str,
) -> DeadLetterEventORM:
    event_id = None
    event_name = None
    payload: dict[str, Any] | None = None
    try:
        decoded = json.loads(raw_payload)
        payload = decoded if isinstance(decoded, dict) else {"value": decoded}
        event_id = payload.get("id")
        event_name = payload.get("name")
    except json.JSONDecodeError:
        payload = {"raw": raw_payload}

    dead_letter = DeadLetterEventORM(
        id=f"dlq_{uuid4().hex[:12]}",
        consumer_group=consumer_group,
        topic=topic,
        partition=partition,
        offset=offset,
        event_id=event_id,
        event_name=event_name,
        failure_reason=failure_reason,
        payload=payload,
    )
    db.add(dead_letter)

    if partition is not None and offset is not None:
        offset_row = db.scalar(
            select(StreamConsumerOffsetORM).where(
                StreamConsumerOffsetORM.consumer_group == consumer_group,
                StreamConsumerOffsetORM.topic == topic,
                StreamConsumerOffsetORM.partition == partition,
            )
        )
        if offset_row is None:
            now = datetime.now(UTC)
            offset_row = StreamConsumerOffsetORM(
                id=_offset_id(consumer_group, topic, partition),
                consumer_group=consumer_group,
                topic=topic,
                partition=partition,
                last_offset=offset,
                last_event_id=event_id,
                processed_count=0,
                failed_count=1,
                last_processed_at=now,
                updated_at=now,
            )
            db.add(offset_row)
        else:
            offset_row.failed_count += 1
            offset_row.updated_at = datetime.now(UTC)
    return dead_letter


def process_stream_message(db: Session, consumer_group: str, topic: str, partition: int, offset: int, raw_payload: str) -> dict[str, Any]:
    event = json.loads(raw_payload)
    if not isinstance(event, dict):
        raise ValueError("event payload must be a JSON object")
    event_id = event.get("id")
    if not event_id:
        raise ValueError("event id is required")
    materialize_analytics_snapshot(db)
    record_stream_success(db, consumer_group, topic, partition, offset, str(event_id))
    return event


async def consume_forever() -> None:
    if not settings.kafka_enabled:
        with SessionLocal() as db:
            materialize_analytics_snapshot(db)
        print("Kafka disabled; materialized analytics snapshot once.")
        return
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=CONSUMER_GROUP,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    try:
        async for message in consumer:
            raw_payload = message.value.decode("utf-8")
            try:
                with SessionLocal() as db:
                    process_stream_message(db, CONSUMER_GROUP, message.topic, message.partition, message.offset, raw_payload)
                    db.commit()
            except Exception as exc:  # pragma: no cover - defensive worker path
                with SessionLocal() as db:
                    dead_letter = record_stream_failure(db, CONSUMER_GROUP, message.topic, message.partition, message.offset, raw_payload, str(exc))
                    db.add(WorkerErrorORM(id=str(uuid4()), event_id=dead_letter.event_id, source=message.topic, message=str(exc), payload={"raw": raw_payload, "dead_letter_id": dead_letter.id}))
                    db.commit()
    finally:
        await consumer.stop()


def main() -> None:
    asyncio.run(consume_forever())


if __name__ == "__main__":
    main()
