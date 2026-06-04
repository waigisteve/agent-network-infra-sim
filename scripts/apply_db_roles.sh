#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER is required}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_READONLY_USER:?POSTGRES_READONLY_USER is required}"
POSTGRES_AUDIT_USER="${POSTGRES_AUDIT_USER:-agent_auditor}"

psql_base=(docker compose exec -T postgres psql -U "$POSTGRES_OWNER_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1)

role_count="$("${psql_base[@]}" -tAc "select count(*) from pg_roles where rolname in ('$POSTGRES_OWNER_USER', '$POSTGRES_APP_USER', '$POSTGRES_READONLY_USER')")"
if [[ "$role_count" != "3" ]]; then
  printf 'Expected core DB roles are missing. Found %s of 3. Recreate the volume or run the init bootstrap with a role that can CREATE ROLE.\n' "$role_count" >&2
  exit 1
fi

"${psql_base[@]}" \
  --set app_user="$POSTGRES_APP_USER" \
  --set readonly_user="$POSTGRES_READONLY_USER" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"app_user", :"readonly_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"readonly_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_user", :"readonly_user";
SQL

audit_role_exists="$("${psql_base[@]}" -tAc "select count(*) from pg_roles where rolname = '$POSTGRES_AUDIT_USER'")"
if [[ "$audit_role_exists" == "1" ]]; then
  "${psql_base[@]}" --set audit_user="$POSTGRES_AUDIT_USER" <<'SQL'
GRANT USAGE ON SCHEMA public TO :"audit_user";
GRANT SELECT ON event_log TO :"audit_user";
GRANT SELECT ON security_audit_log TO :"audit_user";
SQL
else
  printf 'Optional audit role %s does not exist in this volume; fresh volumes create it automatically.\n' "$POSTGRES_AUDIT_USER" >&2
fi

"${psql_base[@]}" \
  --set app_user="$POSTGRES_APP_USER" \
  --set readonly_user="$POSTGRES_READONLY_USER" \
  --set audit_user="$POSTGRES_AUDIT_USER" \
  -P pager=off <<'SQL'
select rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
from pg_roles
where rolname in (:'app_user', :'readonly_user', :'audit_user', current_user)
order by rolname;

select grantee, table_name, string_agg(privilege_type, ', ' order by privilege_type) as privileges
from information_schema.role_table_grants
where table_schema = 'public'
and grantee in (:'app_user', :'readonly_user', :'audit_user')
group by grantee, table_name
order by grantee, table_name;
SQL
