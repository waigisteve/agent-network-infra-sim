# Agent Network Platform

A production-shaped local project for agent banking and mobile money operations.

It includes:

- FastAPI backend
- PostgreSQL persistence
- Redpanda Kafka-compatible event streaming
- Worker process for analytics snapshots
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

## Testing URLs

When the Docker stack is running, use:

Browser and API endpoints use plain local HTTP, not HTTPS:

- Web app: `http://127.0.0.1:5173`
- API base URL: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`
- Readiness check: `http://127.0.0.1:8000/ready`
- Redpanda Console: `http://127.0.0.1:18081`

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

## Simulate Kafka Inputs

Run a 10-minute simulation with one generated event every 2 seconds:

```bash
make simulate
```

Watch the stream in Redpanda Console:

```text
http://127.0.0.1:18081
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
