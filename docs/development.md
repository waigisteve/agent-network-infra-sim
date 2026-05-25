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
- Redpanda Console: `http://127.0.0.1:8080`

## Seed Users

All demo passwords are `password`.

- `admin@example.com`
- `reviewer@example.com`
- `field@example.com`
- `agent@example.com`

## Local Without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.app.scripts.seed
uvicorn backend.app.main:app --reload
```

Kafka is disabled by default outside Docker. Events are still stored in the `event_log` table.
