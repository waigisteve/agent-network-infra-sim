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

## Backend Test

```bash
source .venv/bin/activate
pytest -q
```

## Docs

- [Development](docs/development.md)
- [Architecture](docs/architecture.md)
- [API](docs/api.md)
