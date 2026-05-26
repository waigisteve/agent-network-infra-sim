# Database Security

This repo implements local PostgreSQL hardening for the Docker stack and documents the provider-level controls required for hosted environments.

## Exposed Local Endpoints

| Service | URL or endpoint | Notes |
| --- | --- | --- |
| Frontend | `http://127.0.0.1:5173` | Browser UI |
| API | `http://127.0.0.1:8000` | FastAPI base URL |
| API docs | `http://127.0.0.1:8000/docs` | OpenAPI docs |
| Health | `http://127.0.0.1:8000/health` | Liveness check |
| Readiness | `http://127.0.0.1:8000/ready` | Database/Kafka readiness |
| Redpanda Console | `http://127.0.0.1:18081` | Kafka topic browser |
| Kafka external bootstrap | `127.0.0.1:19092` | External Kafka clients |
| PostgreSQL | `127.0.0.1:${POSTGRES_HOST_PORT:-55432}` | Local DB endpoint bound to loopback |

## Roles

| Role | Environment keys | Purpose | Expected permissions |
| --- | --- | --- | --- |
| Owner | `POSTGRES_OWNER_USER`, `POSTGRES_OWNER_PASSWORD`, `DATABASE_MIGRATION_URL` | Owns schema and runs Alembic migrations | Schema/table ownership, create/alter/drop during migrations |
| Application | `POSTGRES_APP_USER`, `POSTGRES_APP_PASSWORD`, `DATABASE_URL` | Runtime API and worker access | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on application tables |
| Read-only | `POSTGRES_READONLY_USER`, `POSTGRES_READONLY_PASSWORD` | Reporting, BI, audit review | `SELECT` only |

The API and worker should use `DATABASE_URL`. Migration commands should use `DATABASE_MIGRATION_URL`. Do not use the owner role for normal application traffic.

## Implemented Controls

| Control | Implementation | Effect |
| --- | --- | --- |
| RBAC and least privilege | Separate owner, app, and read-only roles in `docker/postgres/init/001-security-roles.sh` | Runtime credentials cannot perform schema ownership operations. Read-only credentials cannot mutate data. |
| Row-Level Security | `backend/alembic/versions/0002_postgres_security.py` enables and forces RLS on all application tables | Every table is RLS-protected. Current policies allow full app-role access and read-only select access; future tenant/agent-specific predicates can replace broad policies without changing table ownership. |
| pgAudit | Documented as a managed-platform/custom-image requirement | Requires `shared_preload_libraries = 'pgaudit'` and provider support. The stock `postgres:16` image does not include pgAudit by default. |
| SCRAM-SHA-256 authentication | `password_encryption=scram-sha-256` and `pg_hba.conf` network rules | New role passwords are SCRAM-hashed and network clients must authenticate with password auth. |
| Network restriction | Postgres binds to `127.0.0.1:${POSTGRES_HOST_PORT:-55432}` and uses `docker/postgres/pg_hba.conf` | Database is not exposed on public interfaces in local Docker. Hosted databases should also use firewall rules/private networking. |
| Backup encryption | `scripts/encrypted_pg_backup.sh` | `pg_dump` output is compressed and encrypted with AES-256-CBC using `BACKUP_ENCRYPTION_PASSPHRASE`. |
| Encryption at rest | Provider/disk-layer requirement | Local Docker volume encryption depends on host disk encryption. Hosted PostgreSQL must enable storage encryption at the provider layer. |
| TLS in transit | `DATABASE_SSL_MODE`, `DATABASE_SSL_ROOT_CERT`, `DATABASE_SSL_CERT`, `DATABASE_SSL_KEY` | Production should use `verify-full`. Local Docker defaults to `prefer` because no private key material is committed. |

## Schema State Effects

Fresh schema state:

- The Postgres container creates owner, app, and read-only roles during first initialization.
- Alembic should run with `DATABASE_MIGRATION_URL`, so tables are owned by the owner role.
- `0002_postgres_security` enables forced RLS, creates two policies per table, grants app-role read/write access, grants read-only select access, and revokes public schema creation.

Existing local schema state:

- Docker does not rerun `/docker-entrypoint-initdb.d` scripts for an existing `postgres-data` volume.
- If tables were created by the old pre-hardening role, run the role bootstrap once and transfer public object ownership to `POSTGRES_OWNER_USER`.
- After ownership transfer, run `alembic upgrade head` with `DATABASE_MIGRATION_URL` to apply the RLS migration.
- Existing rows remain intact; the migration changes ownership, grants, RLS flags, and policies. It does not rewrite business data.

Future schema changes:

- New migrations should run only through `DATABASE_MIGRATION_URL`.
- New tables should be added to the `TABLES` list in `0002_postgres_security.py` or covered by a follow-up migration that enables forced RLS and grants role-specific access.
- Runtime code should not require owner credentials.

## Local Validation Commands

```bash
docker-compose config --quiet
docker-compose up -d postgres
docker-compose exec -T postgres psql -U agent -d agent_network -tAc "SHOW password_encryption;"
docker-compose exec -T postgres psql -U agent -d agent_network -tAc "SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' AND relrowsecurity AND relforcerowsecurity;"
docker-compose run --rm api alembic -c backend/alembic.ini upgrade head
```

Use `docker-compose` in this WSL environment; the newer `docker compose` plugin has shown a local nil-pointer crash after rendering config.
