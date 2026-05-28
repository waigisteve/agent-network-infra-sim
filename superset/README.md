# Superset Local BI

Superset is configured as an optional Compose profile:

```bash
docker compose --profile analytics up -d superset
```

Open:

```text
http://127.0.0.1:18088
```

## Bootstrap

Create an admin user inside the container:

```bash
docker compose --profile analytics exec superset superset fab create-admin \
  --username admin \
  --firstname Data \
  --lastname Admin \
  --email admin@example.com \
  --password password
docker compose --profile analytics exec superset superset db upgrade
docker compose --profile analytics exec superset superset init
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

## Partner-Facing RLS

For external dashboards, create partner-specific Superset roles and RLS filters:

```sql
partner_id = 'partner_telco_a_ug'
```

Internal admin dashboards can use the full marts. External dashboards should use only governed mart tables, not raw operational tables.
