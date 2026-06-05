#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

EVENT_DURATION_SECONDS="${EVENT_DURATION_SECONDS:-8}"
EVENT_INTERVAL_SECONDS="${EVENT_INTERVAL_SECONDS:-1}"
WAIT_SECONDS="${WAIT_SECONDS:-30}"

log() {
  printf '\n== %s ==\n' "$*"
}

query_scalar() {
  docker compose exec -T postgres psql -U "${POSTGRES_OWNER_USER:-agent_owner}" -d "${POSTGRES_DB:-agent_network}" -tAc "$1"
}

wait_for_worker_progress() {
  local before_snapshots="$1"
  local before_processed="$2"
  local deadline=$(( "$(date +%s)" + WAIT_SECONDS ))
  local snapshots
  local processed

  while (( "$(date +%s)" <= deadline )); do
    snapshots="$(query_scalar "select count(*) from analytics_snapshots;")"
    processed="$(query_scalar "select coalesce(sum(processed_count), 0) from stream_consumer_offsets;")"
    if (( snapshots > before_snapshots && processed > before_processed )); then
      return 0
    fi
    sleep 1
  done

  printf 'Worker did not advance within %s seconds. before_snapshots=%s current_snapshots=%s before_processed=%s current_processed=%s\n' \
    "${WAIT_SECONDS}" "${before_snapshots}" "${snapshots:-unknown}" "${before_processed}" "${processed:-unknown}"
  return 1
}

log "Apply migrations and seed base data"
docker compose exec -T api alembic -c backend/alembic.ini upgrade head
docker compose exec -T api python -m backend.app.scripts.seed

BEFORE_SNAPSHOTS="$(query_scalar "select count(*) from analytics_snapshots;")"
BEFORE_PROCESSED="$(query_scalar "select coalesce(sum(processed_count), 0) from stream_consumer_offsets;")"
BEFORE_EVENTS="$(query_scalar "select count(*) from event_log;")"

log "Before event simulation"
printf 'event_log=%s analytics_snapshots=%s stream_processed=%s\n' "${BEFORE_EVENTS}" "${BEFORE_SNAPSHOTS}" "${BEFORE_PROCESSED}"

log "Publish simulated operational events"
docker compose exec -T api python -m backend.app.scripts.simulate_stream \
  --duration-seconds "${EVENT_DURATION_SECONDS}" \
  --interval-seconds "${EVENT_INTERVAL_SECONDS}"

log "Wait for worker to consume events and materialize snapshots"
wait_for_worker_progress "${BEFORE_SNAPSHOTS}" "${BEFORE_PROCESSED}"

AFTER_EVENTS="$(query_scalar "select count(*) from event_log;")"
AFTER_SNAPSHOTS="$(query_scalar "select count(*) from analytics_snapshots;")"
AFTER_PROCESSED="$(query_scalar "select coalesce(sum(processed_count), 0) from stream_consumer_offsets;")"
OPEN_DEAD_LETTERS="$(query_scalar "select count(*) from dead_letter_events where status = 'open';")"

log "After event simulation"
printf 'event_log=%s analytics_snapshots=%s stream_processed=%s open_dead_letters=%s\n' \
  "${AFTER_EVENTS}" "${AFTER_SNAPSHOTS}" "${AFTER_PROCESSED}" "${OPEN_DEAD_LETTERS}"

log "Stream consumer offsets"
query_scalar "
select
  consumer_group || ' | ' || topic || ' | partition=' || partition ||
  ' | offset=' || last_offset ||
  ' | processed=' || processed_count ||
  ' | failed=' || failed_count
from stream_consumer_offsets
order by updated_at desc
limit 10;
"

log "Latest analytics snapshots"
query_scalar "
select
  id || ' | scope=' || scope || ' | created_at=' || created_at ||
  ' | metrics=' || jsonb_array_length((metrics::jsonb)->'metrics')
from analytics_snapshots
order by created_at desc
limit 5;
"

log "Demo result"
printf 'Event-to-snapshot lineage verified: events persisted, worker offsets advanced, snapshots materialized, dead_letters=%s\n' "${OPEN_DEAD_LETTERS}"
