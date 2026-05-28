#!/usr/bin/env bash
set -euo pipefail

DURATION_SECONDS="${DURATION_SECONDS:-900}"
STREAM_INTERVAL_SECONDS="${STREAM_INTERVAL_SECONDS:-2}"
ENDPOINT_INTERVAL_SECONDS="${ENDPOINT_INTERVAL_SECONDS:-20}"
PARTNER_REFRESH_SECONDS="${PARTNER_REFRESH_SECONDS:-180}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

require_file() {
  if [[ ! -f "$1" ]]; then
    log "Missing required file: $1"
    exit 1
  fi
}

wait_for_api() {
  log "Waiting for API readiness"
  for _ in $(seq 1 90); do
    if docker compose exec -T api python - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8000/ready", timeout=3).read()
PY
    then
      log "API is ready"
      return
    fi
    sleep 2
  done
  log "API did not become ready in time"
  exit 1
}

bootstrap_superset() {
  log "Bootstrapping Superset metadata, database connection, and dashboards"
  docker compose --profile analytics exec -T superset superset db upgrade
  docker compose --profile analytics exec -T superset superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@example.com \
    --password password >/dev/null 2>&1 || true
  docker compose --profile analytics exec -T superset superset init
  docker compose --profile analytics exec -T superset superset set-database-uri \
    -d agent_network \
    -u postgresql+psycopg2://agent_readonly:local-agent-password@postgres:5432/agent_network
  docker compose --profile analytics exec -T superset python /app/pythonpath/bootstrap_assets.py
}

bootstrap_airflow() {
  log "Bootstrapping Airflow admin user and DAG state"
  docker compose --profile orchestration exec -T airflow airflow users reset-password -u admin -p password >/dev/null 2>&1 || true
  docker compose --profile orchestration exec -T airflow airflow dags unpause agent_network_partner_ingestion
}

refresh_partner_reporting_loop() {
  local deadline="$1"
  local remaining
  local sleep_for
  while (( "$(date +%s)" < deadline )); do
    log "Running partner feed simulation, dbt build, Superset asset refresh, and Airflow DAG trigger"
    docker compose exec -T api python -m backend.app.scripts.simulate_partner_e2e
    docker compose --profile analytics run --rm dbt build
    docker compose --profile analytics exec -T superset python /app/pythonpath/bootstrap_assets.py
    docker compose --profile orchestration exec -T airflow airflow dags trigger agent_network_partner_ingestion >/dev/null
    remaining=$(( deadline - $(date +%s) ))
    if (( remaining <= 0 )); then
      break
    fi
    sleep_for="${PARTNER_REFRESH_SECONDS}"
    if (( remaining < sleep_for )); then
      sleep_for="${remaining}"
    fi
    sleep "${sleep_for}"
  done
}

require_file ".env"

log "Starting full stack with analytics and orchestration profiles"
docker compose --profile analytics --profile orchestration up -d --build

wait_for_api

log "Applying migrations and seeding deterministic demo data"
docker compose exec -T api alembic -c backend/alembic.ini upgrade head
docker compose exec -T api python -m backend.app.scripts.seed

log "Building initial dbt marts"
docker compose --profile analytics run --rm dbt build

bootstrap_superset
bootstrap_airflow

DEADLINE=$(( "$(date +%s)" + DURATION_SECONDS ))

refresh_partner_reporting_loop "${DEADLINE}" &
PARTNER_PID="$!"

log "Running live API endpoint exerciser for ${DURATION_SECONDS} seconds"
docker compose exec -T api python -m backend.app.scripts.exercise_api_endpoints \
  --duration-seconds "${DURATION_SECONDS}" \
  --interval-seconds "${ENDPOINT_INTERVAL_SECONDS}" &
ENDPOINT_PID="$!"

log "Running Kafka/event stream simulation for ${DURATION_SECONDS} seconds"
docker compose exec -T api python -m backend.app.scripts.simulate_stream \
  --duration-seconds "${DURATION_SECONDS}" \
  --interval-seconds "${STREAM_INTERVAL_SECONDS}" &
STREAM_PID="$!"

wait "${ENDPOINT_PID}"
wait "${STREAM_PID}"
wait "${PARTNER_PID}" || true

log "Final dbt build and Superset dashboard refresh"
docker compose --profile analytics run --rm dbt build
docker compose --profile analytics exec -T superset python /app/pythonpath/bootstrap_assets.py

log "Recent Airflow runs"
docker compose --profile orchestration exec -T airflow airflow dags list-runs -d agent_network_partner_ingestion | tail -n 8

log "Demo complete"
log "Frontend: http://127.0.0.1:5173"
log "API docs: http://127.0.0.1:8000/docs"
log "Redpanda Console: http://127.0.0.1:18081"
log "Airflow: http://127.0.0.1:18080 admin/password"
log "Superset: http://127.0.0.1:18088 admin/password"
