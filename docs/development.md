# Development

## Local Docker Stack

```bash
cp .env.example .env
python - <<'PY'
from pathlib import Path
path = Path(".env")
text = path.read_text()
text = text.replace("change-this-local-owner-password", "set-a-local-owner-password")
text = text.replace("change-this-local-app-password", "set-a-local-app-password")
text = text.replace("change-this-local-readonly-password", "set-a-local-readonly-password")
text = text.replace("replace-with-a-long-random-secret", "set-a-long-random-local-secret")
path.write_text(text)
PY
make up
```

Open:

- Frontend: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- Redpanda Console: `http://127.0.0.1:18081`

## Seed Users

All demo passwords are `password`.

- `admin@example.com`
- `reviewer@example.com`
- `field@example.com`
- `agent@example.com`

## Kafka Stream Simulation

After the Docker stack is running and seeded, run a 10-minute stream simulation with one event every 2 seconds:

```bash
make simulate
```

Equivalent direct command:

```bash
docker compose exec -T api python -m backend.app.scripts.simulate_stream --duration-seconds 600 --interval-seconds 2
```

The simulator emits a mixed workload:

- `transaction.created`
- `commission.calculated`
- `float.requested`
- `float.approved`
- `float.rejected`
- `customer.kyc_reviewed`
- `agent.location_updated`

Watch Kafka topics in Redpanda Console:

```text
http://127.0.0.1:18081
```

The same events are persisted in Postgres in `event_log` for audit/debugging.

## Database Hardening

The local PostgreSQL stack uses SCRAM authentication, separate owner/application/read-only users, `pg_hba.conf` network restrictions, and PostgreSQL RLS policies after migrations are applied. Use `POSTGRES_BIND_ADDRESS=127.0.0.1` for local-only exposure.

Run encrypted logical backups with:

```bash
BACKUP_ENCRYPTION_PASSPHRASE="set-a-secret-outside-git" make backup
```

Do not commit generated backup files or certificate/private-key material. For hosted PostgreSQL, enable provider firewall/private-network controls, pgAudit, and storage encryption at rest in the platform.

## Local Without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app.scripts.seed
uvicorn backend.app.main:app --reload
```

Kafka is disabled by default outside Docker. Events are still stored in the `event_log` table.
