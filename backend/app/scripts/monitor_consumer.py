from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import UTC, datetime

from aiokafka import AIOKafkaConsumer

from backend.app.config import settings


async def consume(group_id: str, topics: list[str]) -> None:
    if not settings.kafka_enabled:
        print(f"{group_id}: Kafka disabled; no monitor consumer started.", flush=True)
        return
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    counts: Counter[str] = Counter()
    await consumer.start()
    print(f"{group_id}: consuming topics={','.join(topics)}", flush=True)
    try:
        async for message in consumer:
            counts[message.topic] += 1
            try:
                event = json.loads(message.value.decode("utf-8"))
                event_name = event.get("name", "unknown")
            except json.JSONDecodeError:
                event_name = "invalid-json"
            total = sum(counts.values())
            print(
                f"{datetime.now(UTC).isoformat()} group={group_id} topic={message.topic} "
                f"event={event_name} topic_count={counts[message.topic]} total={total}",
                flush=True,
            )
    finally:
        await consumer.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a named Kafka monitor consumer for Redpanda Console demos.")
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--topics", required=True, help="Comma-separated Kafka topics to consume.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    topics = [topic.strip() for topic in args.topics.split(",") if topic.strip()]
    asyncio.run(consume(args.group_id, topics))


if __name__ == "__main__":
    main()
