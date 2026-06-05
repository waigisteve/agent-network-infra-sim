# Runtime Persistence

This document describes where local runtime state is stored and what survives a
container restart or recreation.

## Local Persistence Matrix

| Service | State | Local persistence | Docker volume/path | Notes |
| --- | --- | --- | --- | --- |
| PostgreSQL | Operational database, app users, KYC metadata, partner feeds, dbt mart tables, audit logs | Persistent | `postgres-data:/var/lib/postgresql/data` | Source of truth for transactional and analytical tables. Covered by encrypted backup and restore drill. |
| MinIO | KYC image/PDF object bytes | Persistent | `minio-data:/data` | Object bytes are linked to PostgreSQL through `kyc_documents.storage_key`, `sha256_hash`, and `customer_id`. |
| Redpanda | Kafka-compatible broker topics, broker log data, consumer group state | Persistent locally | `redpanda-data:/var/lib/redpanda/data` | Survives container recreation. Still single-node and not production-HA. The API also persists every domain event to PostgreSQL `event_log` for replay/audit. |
| Airflow | Local Airflow metadata DB, DAG run state, task state, admin user, and task logs | Persistent locally | `airflow-metadata:/opt/airflow-metadata`, `airflow-logs:/opt/airflow/logs` | Uses SQLite for local demo simplicity, but avoids persisting transient process files from the whole Airflow home directory. Production should use external PostgreSQL/MySQL metadata DB, durable log storage, and a HA executor. |
| Superset | Superset metadata DB, dashboards, charts, datasets, admin user | Persistent locally | `superset-home:/app/superset_home` | Uses SQLite for local demo simplicity. Production should use external PostgreSQL metadata DB and exported dashboard assets. |
| API/worker/frontend containers | Runtime process state | Ephemeral | no data volume, code bind mounts only | Services should be stateless; durable state belongs in PostgreSQL, MinIO, Redpanda, Airflow metadata, or Superset metadata. |
| dbt | dbt project files and generated warehouse tables | Project files persist in repo; model outputs persist in PostgreSQL | `./dbt:/usr/app` and PostgreSQL schemas | dbt container is run-on-demand. The tables/views it builds live in PostgreSQL schemas such as `analytics_marts`. |

## What `docker compose` Commands Do

`docker compose restart` restarts existing containers and keeps their attached
volumes.

`docker compose up -d` creates missing containers, recreates changed containers,
and keeps named volumes unless explicitly removed.

`docker compose down` stops and removes containers, but keeps named volumes by
default.

`docker compose down -v` removes containers and named volumes. This deletes local
PostgreSQL data, MinIO files, Redpanda broker data, Airflow metadata/logs, and
Superset metadata.

## Verify Local Volumes

List the project volumes:

```bash
docker volume ls --format '{{.Name}}' | grep agent-network-infra-sim
```

Expected project volumes:

```text
agent-network-infra-sim_airflow-logs
agent-network-infra-sim_airflow-metadata
agent-network-infra-sim_minio-data
agent-network-infra-sim_postgres-data
agent-network-infra-sim_redpanda-data
agent-network-infra-sim_superset-home
```

Check running services and platform readiness:

```bash
docker compose ps
make platform-check
```

## API And Event Durability

The API publishes domain events to Redpanda for asynchronous consumers. It also
persists every event to PostgreSQL `event_log` before or alongside publication.

This gives two useful durability layers in the local demo:

- Redpanda keeps broker-level topic data in `redpanda-data`.
- PostgreSQL keeps business-audit event data in `event_log`.
- API, worker, and frontend containers remain stateless; recreating them should
  not destroy business records, uploaded KYC objects, broker logs, or dashboard
  metadata.

The admin stream readiness API reads worker state from PostgreSQL tables:

```text
GET /api/v1/stream/readiness
```

Those readiness records persist in PostgreSQL through:

- `stream_consumer_offsets`
- `dead_letter_events`
- `worker_errors`

## Production Notes

The local named volumes improve reproducibility, but they do not provide high
availability.

Production targets:

- PostgreSQL: managed PostgreSQL with HA, PITR, encrypted backups, private
  networking, and restore drills.
- MinIO/object storage: S3, Azure Blob, GCS, or production MinIO with private
  buckets, encryption, lifecycle policies, and signed URLs.
- Redpanda/Kafka: Redpanda cluster, MSK, Confluent Cloud, or equivalent managed
  Kafka-compatible service with replicated topics and consumer lag alerts.
- Airflow: managed Airflow or external metadata database with backups and a HA
  executor.
- Superset: external metadata database, exported dashboard assets, backup/restore
  process, and production secret management.
