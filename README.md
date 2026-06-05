# Agent Network Platform

A production-shaped local project for agent banking and mobile money operations.

It includes:

- FastAPI backend
- PostgreSQL persistence
- Redpanda Kafka-compatible event streaming
- MinIO object storage for KYC image/PDF files
- Worker process for analytics snapshots
- Named Kafka monitor consumers for analytics, fraud, liquidity, and reconciliation demo groups
- Partner data contracts for telco transaction feeds and bank settlement files
- Contract-backed ingestion run auditing and settlement reconciliation exceptions
- dbt analytics project for staging, intermediate, fact, dimension, and mart models
- Airflow orchestration for ingestion, reconciliation, and dbt builds
- Superset analytics service for governed BI dashboards
- React/Vite frontend
- JWT role-based auth
- Alembic migrations
- Docker Compose local stack

## Quick Start

```bash
cp .env.example .env
# Edit .env and replace placeholder values before starting the stack.
make up
```

`make up` runs `docker compose up -d --build`. Long-running services use
`restart: unless-stopped`, so after this command has created the containers
they should start again when Docker Desktop or the Docker engine starts. If you
run `docker compose down`, the containers are removed and must be recreated with
`make up`.

Open:

- Frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- Redpanda Console: `http://127.0.0.1:18081`
- MinIO Console: `http://127.0.0.1:9001`
- Airflow: `http://127.0.0.1:18080`
- Superset: `http://127.0.0.1:18088`

## Testing URLs

When the Docker stack is running, use:

Browser and API endpoints use plain local HTTP, not HTTPS:

- Web app: `http://127.0.0.1:5173`
- API base URL: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- Readiness check: `http://127.0.0.1:8000/ready`
- Redpanda Console: `http://127.0.0.1:18081`
- MinIO Console: `http://127.0.0.1:9001`
- Airflow: `http://127.0.0.1:18080`
- Superset: `http://127.0.0.1:18088`

Non-HTTP service endpoints do not use `http://`:

- Kafka external bootstrap: `127.0.0.1:19092`
- PostgreSQL host endpoint: `127.0.0.1:${POSTGRES_HOST_PORT:-55432}`
- MinIO S3-compatible endpoint: `127.0.0.1:9000`

Use the application role for runtime database testing:

```text
postgresql://agent_app:<POSTGRES_APP_PASSWORD>@127.0.0.1:55432/agent_network
```

Use the owner role only for migrations:

```text
postgresql://agent_owner:<POSTGRES_OWNER_PASSWORD>@127.0.0.1:55432/agent_network
```

Seed users all use password `password`:

- `admin@example.com`
- `reviewer@example.com`
- `field@example.com`
- `agent@example.com`

Local Airflow and Superset bootstrap users also use:

- username: `admin`
- password: `password`

## Simulate Kafka Inputs

Run a 10-minute simulation with one generated event every 2 seconds:

```bash
make simulate
```

Watch the stream in Redpanda Console:

```text
http://127.0.0.1:18081
```

The Redpanda Console groups page should show these local consumer groups when the stack is running:

- `agent-network-worker`: application analytics snapshot worker
- `analytics-worker`: reads transaction, commission, and float topics
- `fraud-monitor`: reads transaction and KYC topics
- `liquidity-monitor`: reads float and transaction topics
- `reconciliation-monitor`: reads transaction and commission topics

Open: `http://127.0.0.1:18081/groups`

Run the event-to-snapshot lineage demo:

```bash
make event-snapshot-demo
```

This publishes simulated operational events, waits for the worker to consume them, and prints proof that `event_log`, `stream_consumer_offsets`, and `analytics_snapshots` advanced together.

Run the partner integration simulation:

```bash
make simulate-partner-e2e
make dbt-build
```

This loads a unique telco transaction feed, loads a unique bank settlement feed, opens a reconciliation result, and then builds the dbt marts used by Superset.

## 15-Minute End-to-End Demo

Run the full local process for 15 minutes:

```bash
make demo-e2e
```

The script starts the local stack, applies migrations, seeds deterministic data, builds dbt marts, bootstraps Superset dashboards, unpauses/triggers the Airflow DAG, runs continuous Kafka/event simulation, and repeatedly exercises the API endpoints used by the frontend.

During the run, watch:

- Frontend workflows: `http://127.0.0.1:5173`
- API docs and endpoint responses: `http://127.0.0.1:8000/docs`
- Kafka topics: `http://127.0.0.1:18081`
- Airflow DAG runs: `http://127.0.0.1:18080`
- Superset dashboards: `http://127.0.0.1:18088`

Override the default timing when needed:

```bash
DURATION_SECONDS=300 ENDPOINT_INTERVAL_SECONDS=10 make demo-e2e
```

## Platform Readiness Check

After starting the local stack, run:

```bash
make platform-check
```

The check validates Docker service state, API liveness/readiness, seeded admin login, protected API access, frontend availability, Kafka external port reachability, Redpanda Console, Airflow, Superset, and dbt project structure.

If a browser returns `127.0.0.1 refused to connect`, first confirm the containers
are present and running:

```bash
docker compose ps
make platform-check
```

For MinIO specifically, recreate the local object-storage services:

```bash
docker compose up -d minio minio-init api
```

Open the MinIO console at `http://127.0.0.1:9001`. Use
`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` from `.env`; the local defaults are
`agentminio` and `local-agent-minio-password`.

## Partner Integration Simulation

The repo includes versioned partner contracts that model telco and bank integrations:

- `contracts/telco_transactions_v1.json`
- `contracts/bank_settlements_v1.json`

Seed data creates the partner and contract metadata. Admin users can ingest sample records through:

- `POST /api/v1/integrations/telco-transactions`
- `POST /api/v1/integrations/bank-settlements`
- `POST /api/v1/integrations/reconcile-settlement`

The ingestion layer records source references, loaded/rejected counts, error summaries, hashed customer identifiers, raw payloads, settlement totals, and reconciliation exceptions. This is the local implementation path for telco/bank feeds before adding Airflow, dbt, Superset, BigQuery, or Redshift.

## Analytics Stack

Superset now starts with the default Docker stack. The `analytics` target remains useful for explicitly running the dbt container and refreshing analytics assets:

```bash
make analytics
```

Run dbt locally through Docker:

```bash
make dbt-build
```

Airflow now starts with the default Docker stack. The `orchestration` target remains as a direct convenience command:

```bash
make orchestration
```

Open:

- Airflow: `http://127.0.0.1:18080`
- Superset: `http://127.0.0.1:18088`

The dbt project lives in `dbt/` and builds marts such as `mart_partner_network_health` and `mart_liquidity_risk`. Airflow DAGs live in `airflow/dags/`. Superset local configuration lives in `superset/`.

End-to-end local flow:

1. `make up`
2. `docker compose exec -T api alembic -c backend/alembic.ini upgrade head`
3. `make simulate-partner-e2e`
4. `make dbt-build`
5. `make analytics`
6. Open Superset at `http://127.0.0.1:18088` and connect it to the `analytics_marts` schema.

For a fully automated local run, use `make demo-e2e`.

## 30-Minute Random Workflow Simulation

Run a practical randomized cycle against the live stack:

```bash
make simulate-workflow-30
```

This runs for 30 minutes by default and continuously mixes:

- agent transactions
- float requests and approvals/rejections
- KYC document uploads to MinIO with metadata in PostgreSQL
- KYC review decisions
- field-agent location updates
- telco partner feed ingestion
- bank settlement ingestion and reconciliation
- intentional reconciliation mismatches for exception queues
- Kafka event publication for worker analytics

To run faster or slower:

```bash
INTERVAL_SECONDS=1 make simulate-workflow-30
```

For a shorter smoke test:

```bash
docker compose exec -T api python -m backend.app.scripts.simulate_workflow_cycle --duration-seconds 60 --interval-seconds 1
```

## Backend Test

```bash
source .venv/bin/activate
pytest -q
```

## PostgreSQL TLS

Set `DATABASE_SSL_MODE=require` for encrypted PostgreSQL connections. Use `verify-ca` or `verify-full` with `DATABASE_SSL_ROOT_CERT=/path/to/ca.pem` when the server certificate should be verified. If the database requires mutual TLS, also set `DATABASE_SSL_CERT=/path/to/client-cert.pem` and `DATABASE_SSL_KEY=/path/to/client-key.pem`. The local Docker example uses `prefer` so it can run against the stock Postgres image without committed private keys; production should use `verify-full`.

## Database Hardening

Implemented in this repo:

- RBAC and least privilege through separate owner, application, and read-only database users.
- Owner-level schema changes use `DATABASE_MIGRATION_URL`; runtime API and worker processes use the restricted `DATABASE_URL` application role.
- Database grants can be reapplied and verified with `make db-roles`.
- SCRAM-SHA-256 password hashing and `pg_hba.conf` rules for the local PostgreSQL container.
- Row-Level Security enabled by the `0002_postgres_security` Alembic migration for PostgreSQL tables.
- Local network restriction by binding Postgres to `127.0.0.1:${POSTGRES_HOST_PORT:-55432}` and allowing only SCRAM-authenticated local/Docker subnets in `docker/postgres/pg_hba.conf`.
- Encrypted logical backups through `make backup`, which writes AES-256 encrypted dumps using `BACKUP_ENCRYPTION_PASSPHRASE`.

Managed-platform controls:

- pgAudit requires the `pgaudit` extension to be installed and loaded by the PostgreSQL provider or a custom image.
- Firewall rules and private networking should be enforced by the cloud database platform in addition to `pg_hba.conf`.
- Encryption at rest should be enabled on the managed PostgreSQL storage volume or disk encryption layer.

## Docs

- [Development](docs/development.md)
- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [SQL Logic And Lineage](docs/sql-logic.md)
- [Database Security](docs/database-security.md)
- [KYC Document Storage](docs/kyc-document-storage.md)
- [Streaming Reliability](docs/streaming-reliability.md)
- [SPOF Analysis](docs/spof-analysis.md)
- [Agent Network Role Alignment](docs/agent-network-role-alignment.md)
- [Data Platform Roadmap](docs/data-platform-roadmap.md)
- [Implementation Process](docs/implementation-process.md)
- [Platform Implementation Gantt](docs/platform-implementation-gantt.md)
