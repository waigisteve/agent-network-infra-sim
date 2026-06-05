# Agent Network Role Alignment

This project is shaped around a realistic mobile-money and agent-banking data leadership problem: agent-network data from agents, field teams, telcos, banks, KYC reviewers, and object-storage evidence flows must be ingested, reconciled, governed, transformed, and exposed as trusted operational and customer-facing data products.

## Already Demonstrated

| Role requirement | Current project evidence |
| --- | --- |
| Expert SQL and Python | FastAPI services, SQLAlchemy models, Alembic migrations, Postgres-first schema design, event simulation, worker jobs, and pytest coverage. |
| Agent-network domain | Agents, field agents, customers, KYC reviews, float requests, transactions, commissions, field map, event audit, and network reports. |
| Kafka-style streaming | Redpanda broker, domain topics, persisted event log, worker consumer, and simulation stream. |
| Postgres operations | Runtime and migration roles, forced RLS, SCRAM configuration, pg_hba.conf, TLS connection settings, encrypted logical backups, and migration-controlled schema changes. |
| Customer-facing product direction | React dashboards for operations, reporting, KYC, field map, audit log, and agent workflow. |
| Cloud-native direction | Docker Compose local stack and architecture documentation for managed Postgres, MinIO/object storage, private networking, hosted audit, and cloud data platform controls. |

## Newly Added Integration Layer

The partner integration layer models realistic telco and bank workflows:

- `partners` captures telco, bank, and agent-app data providers.
- `partner_contracts` stores versioned feed contracts, required fields, accepted values, deduplication keys, PII fields, and arrival SLA.
- `integration_runs` records every file, stream window, or API pull with status, source reference, loaded count, rejected count, and error summary.
- `raw_partner_transactions` stores normalized telco transaction records with provider references, hashed customer identifiers, agent linkage, status, amount, commission, and raw payload.
- `bank_settlements` stores partner settlement summaries for count and amount reconciliation.
- `reconciliation_exceptions` records mismatches that operations or data teams must resolve.

The implementation uses JSON contracts in `contracts/`:

- `telco_transactions_v1.json`
- `bank_settlements_v1.json`

This reflects the production pattern expected in telco/bank integrations: raw immutable receipt, contract validation, deduplication, canonical fields, reconciliation, and auditability.

## KYC Evidence Layer

The KYC document layer models realistic customer-evidence handling:

- `kyc_documents` stores searchable metadata, hash, storage backend, storage key, status, uploader, and timestamps.
- MinIO stores KYC image/PDF file bytes in a private local bucket.
- PostgreSQL remains the source of metadata, constraints, audit relationships, and review status.
- The storage adapter can be swapped to S3, Azure Blob Storage, or Google Cloud Storage in hosted production.

## Still Missing Or Only Documented

| Stack/capability | Current state | Recommended next step |
| --- | --- | --- |
| Airflow | Default Compose service, persistent local metadata/log volumes, and first DAG scaffold implemented | Add file sensors, SLA alerts, and production-grade retries per partner feed. |
| dbt | Local Postgres dbt project implemented with staging, intermediate, fact, dimension, mart models, and tests | Add incremental models, snapshots, docs site, and BigQuery/Redshift execution validation. |
| Superset | Default Compose service, persistent local metadata volume, starter dashboards, and RLS guidance implemented | Bootstrap richer saved databases, datasets, charts, dashboards, and partner roles. |
| BigQuery | Documented only | Add optional dbt BigQuery profile and deployment notes for GCS landing plus BigQuery warehouse. |
| Redshift | Documented only | Add optional dbt Redshift profile and AWS S3/Redshift Serverless deployment notes. |
| Real SFTP/API adapters | Simulated in service layer | Add file-watcher or scripted CSV ingestion for bank settlement drops and API polling stubs. |
| Data observability | Basic tests and logs | Add feed freshness checks, alert policy docs, data-quality scorecards, and failed-run dashboards. |
| Customer-facing BI | React app plus Superset service scaffold | Build governed partner dashboards that expose only partner-authorized rows. |
| Hybrid/on-prem | Architecture docs only | Add a simulated on-prem partner export path using local file drops or a second Postgres container. |

## Interview Positioning

The strongest framing is:

> I treated the project as a data infrastructure and data product problem, not just a reporting problem. It models operational agent-network data, Kafka-style events, Postgres governance, KYC/PII controls, MinIO-backed KYC evidence storage, float liquidity, commissions, partner feed contracts, ingestion run auditability, settlement reconciliation, dbt marts, Airflow orchestration, and Superset BI scaffolding. The next maturity step is production-grade partner adapters, saved dashboards, and cloud warehouse validation on BigQuery or Redshift.

## Practical Learning Roadmap

1. Add Airflow file sensors and partner-specific DAG parameters for SFTP/API/Kafka feeds.
2. Add Superset saved dashboards for Partner Network Health, Liquidity Risk, Commission Trends, Reconciliation Exceptions, and Field Team Productivity.
3. Add cloud execution validation for BigQuery and Redshift while keeping Postgres as the local development path.
4. Add hybrid/on-prem simulation using a file-drop or replica pattern to represent constrained bank/telco environments.
5. Add observability metrics for freshness, rejected-record rate, failed-run rate, and dashboard readiness.
