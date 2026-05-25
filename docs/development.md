# Development

## Local Docker Stack

```bash
cp .env.example .env
python - <<'PY'
from pathlib import Path
path = Path(".env")
text = path.read_text()
text = text.replace("change-this-local-password", "set-a-local-password")
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

## Local Without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app.scripts.seed
uvicorn backend.app.main:app --reload
```

Kafka is disabled by default outside Docker. Events are still stored in the `event_log` table.
