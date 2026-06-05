# Superset Local BI

Superset starts with the default Compose stack:

```bash
docker compose up -d superset
```

Open:

```text
http://127.0.0.1:18088
```

## Bootstrap

Create an admin user inside the container:

```bash
docker compose exec superset superset fab create-admin \
  --username admin \
  --firstname Data \
  --lastname Admin \
  --email admin@example.com \
  --password password
docker compose exec superset superset db upgrade
docker compose exec superset superset init
```

## Database Connection

Use this SQLAlchemy URI for the app database:

```text
postgresql+psycopg2://agent_readonly:<POSTGRES_READONLY_PASSWORD>@postgres:5432/agent_network
```

Recommended datasets after dbt runs:

- `analytics_marts.dim_agents`
- `analytics_marts.dim_partners`
- `analytics_marts.fact_transactions`
- `analytics_marts.mart_partner_network_health`
- `analytics_marts.mart_liquidity_risk`
- `analytics_intermediate.int_settlement_reconciliation`

Bootstrap starter datasets, charts, and dashboards:

```bash
docker compose exec superset python /app/pythonpath/bootstrap_assets.py
```

The bootstrap refreshes Superset datasets, chart definitions, and dashboard
metadata. Superset's list-page "Modified" timestamp refers to this metadata
refresh time, while the actual dashboard data freshness comes from the latest
dbt mart build and source table timestamps.

## Partner-Facing RLS

For external dashboards, create partner-specific Superset roles and RLS filters:

```sql
partner_id = 'partner_telco_a_ug'
```

Internal admin dashboards can use the full marts. External dashboards should use only governed mart tables, not raw operational tables.
