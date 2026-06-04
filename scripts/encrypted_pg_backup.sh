#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"

backup_dir="${BACKUP_DIR:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${backup_dir}/agent_network_${timestamp}.dump.gz.enc"
pg_dump_url="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"

mkdir -p "$backup_dir"

if docker compose ps --services --status running 2>/dev/null | grep -qx postgres; then
  : "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER is required when backing up through Docker Compose}"
  : "${POSTGRES_DB:?POSTGRES_DB is required when backing up through Docker Compose}"
  docker compose exec -T postgres pg_dump -U "$POSTGRES_OWNER_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl --enable-row-security \
    | gzip \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 -out "$output" -pass env:BACKUP_ENCRYPTION_PASSPHRASE
else
  pg_dump "$pg_dump_url" --format=custom --no-owner --no-acl --enable-row-security \
    | gzip \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 -out "$output" -pass env:BACKUP_ENCRYPTION_PASSPHRASE
fi

printf '%s\n' "$output"
