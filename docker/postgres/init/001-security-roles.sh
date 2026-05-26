#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER is required}"
: "${POSTGRES_OWNER_PASSWORD:?POSTGRES_OWNER_PASSWORD is required}"
: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"
: "${POSTGRES_READONLY_USER:?POSTGRES_READONLY_USER is required}"
: "${POSTGRES_READONLY_PASSWORD:?POSTGRES_READONLY_PASSWORD is required}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set db_name="$POSTGRES_DB" \
  --set owner_user="$POSTGRES_OWNER_USER" \
  --set app_user="$POSTGRES_APP_USER" \
  --set readonly_user="$POSTGRES_READONLY_USER" <<'SQL'
ALTER SYSTEM SET password_encryption = 'scram-sha-256';
SQL

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_OWNER_USER') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$POSTGRES_OWNER_USER', '$POSTGRES_OWNER_PASSWORD');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_APP_USER') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$POSTGRES_APP_USER', '$POSTGRES_APP_PASSWORD');
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_READONLY_USER') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$POSTGRES_READONLY_USER', '$POSTGRES_READONLY_PASSWORD');
    END IF;
END
\$\$;
SQL

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set db_name="$POSTGRES_DB" \
  --set owner_user="$POSTGRES_OWNER_USER" \
  --set app_user="$POSTGRES_APP_USER" \
  --set readonly_user="$POSTGRES_READONLY_USER" <<'SQL'
GRANT CONNECT ON DATABASE :"db_name" TO :"owner_user", :"app_user", :"readonly_user";
GRANT CREATE, USAGE ON SCHEMA public TO :"owner_user";
GRANT USAGE ON SCHEMA public TO :"app_user", :"readonly_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public GRANT SELECT ON TABLES TO :"readonly_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_user" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"app_user", :"readonly_user";
SQL
