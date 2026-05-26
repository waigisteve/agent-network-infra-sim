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

Set `DATABASE_SSL_MODE=require` for encrypted PostgreSQL connections. Use `verify-ca` or `verify-full` with `DATABASE_SSL_ROOT_CERT=/path/to/ca.pem` when the server certificate should be verified. If the database requires mutual TLS, also set `DATABASE_SSL_CERT=/path/to/client-cert.pem` and `DATABASE_SSL_KEY=/path/to/client-key.pem`.

## Docs

- [Development](docs/development.md)
- [Architecture](docs/architecture.md)
- [API](docs/api.md)
