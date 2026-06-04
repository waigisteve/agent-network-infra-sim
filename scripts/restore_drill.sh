#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"

backup_file="${BACKUP_FILE:-}"
if [[ -z "$backup_file" ]]; then
  backup_file="$(find "${BACKUP_DIR:-backups}" -maxdepth 1 -name 'agent_network_*.dump.gz.enc' -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR == 1 {print $2}')"
fi

if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
  printf 'No encrypted backup file found. Run BACKUP_ENCRYPTION_PASSPHRASE=... make backup first, or set BACKUP_FILE=/path/to/file.\n' >&2
  exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
drill_db="${RESTORE_DRILL_DB:-agent_network_restore_drill_${timestamp}}"
drill_user="restore_owner"
drill_password="restore_password"
drill_container="agent-network-restore-drill-${timestamp}"

cleanup() {
  docker rm -f "$drill_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf 'Restore drill source: %s\n' "$backup_file"
printf 'Temporary restore container: %s\n' "$drill_container"
printf 'Temporary restore database: %s\n' "$drill_db"

docker run -d --rm \
  --name "$drill_container" \
  -e POSTGRES_DB="$drill_db" \
  -e POSTGRES_USER="$drill_user" \
  -e POSTGRES_PASSWORD="$drill_password" \
  postgres:16 >/dev/null

for _ in {1..30}; do
  if docker exec "$drill_container" pg_isready -U "$drill_user" -d "$drill_db" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker exec "$drill_container" pg_isready -U "$drill_user" -d "$drill_db" >/dev/null

openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -in "$backup_file" -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  | gunzip \
  | docker exec -i "$drill_container" pg_restore -U "$drill_user" -d "$drill_db" --no-owner --no-acl

docker exec "$drill_container" psql -U "$drill_user" -d "$drill_db" -v ON_ERROR_STOP=1 -tAc "
select 'users=' || count(*) from users;
select 'agents=' || count(*) from agents;
select 'transactions=' || count(*) from transactions;
select 'event_log=' || count(*) from event_log;
select 'security_audit_log=' || count(*) from security_audit_log;
"

printf 'Restore drill passed. Temporary container will be removed: %s\n' "$drill_container"
