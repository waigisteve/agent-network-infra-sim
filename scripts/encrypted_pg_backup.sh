#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required}"

backup_dir="${BACKUP_DIR:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${backup_dir}/agent_network_${timestamp}.dump.gz.enc"

mkdir -p "$backup_dir"

pg_dump "$DATABASE_URL" --format=custom --no-owner --no-acl \
  | gzip \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 -out "$output" -pass env:BACKUP_ENCRYPTION_PASSPHRASE

printf '%s\n' "$output"
