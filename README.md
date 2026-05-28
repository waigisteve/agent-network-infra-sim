# Agent Network Platform

A production-shaped local project for agent banking and mobile money operations.

It includes:

- FastAPI backend
- PostgreSQL persistence
- Redpanda Kafka-compatible event streaming
- Worker process for analytics snapshots
- Partner data contracts for telco transaction feeds and bank settlement files
- Contract-backed ingestion run auditing and settlement reconciliation exceptions
- dbt analytics project for staging, intermediate, fact, dimension, and mart models
- Optional Airflow orchestration profile for ingestion, reconciliation, and dbt builds
- Optional Superset analytics profile for governed BI dashboards
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

Open:

- Frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- Redpanda Console: `http://127.0.0.1:18081`
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
- Airflow: `http://127.0.0.1:18080`
- Superset: `http://127.0.0.1:18088`

Non-HTTP service endpoints do not use `http://`:

- Kafka external bootstrap: `127.0.0.1:19092`
- PostgreSQL host endpoint: `127.0.0.1:${POSTGRES_HOST_PORT:-55432}`

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

The script starts the core, analytics, and orchestration Docker profiles; applies migrations; seeds deterministic data; builds dbt marts; bootstraps Superset dashboards; unpauses/triggers the Airflow DAG; runs continuous Kafka/event simulation; and repeatedly exercises the API endpoints used by the frontend.

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

Start optional analytics services:

```bash
make analytics
```

Run dbt locally through Docker:

```bash
make dbt-build
```

Start optional Airflow orchestration:

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
- [Database Security](docs/database-security.md)
- [Opareta Role Alignment](docs/opareta-role-alignment.md)
- [Data Platform Roadmap](docs/data-platform-roadmap.md)
- [Implementation Process](docs/implementation-process.md)
