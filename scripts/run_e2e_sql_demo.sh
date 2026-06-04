#!/usr/bin/env bash
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

psql_cmd=(docker compose exec -T postgres psql -U "$POSTGRES_OWNER_USER" -d "$POSTGRES_DB" -P pager=off)

printf '\n== 1. Apply migrations ==\n'
docker compose exec -T api alembic -c backend/alembic.ini upgrade head

printf '\n== 2. Insert real simulated partner feed entries ==\n'
docker compose exec -T api python -m backend.app.scripts.simulate_partner_e2e

printf '\n== 3. Build dbt SQL models ==\n'
docker compose --profile analytics run --rm dbt build

printf '\n== 4. OLTP record counts ==\n'
"${psql_cmd[@]}" -c "
select 'integration_runs' as table_name, count(*) as rows from integration_runs
union all select 'raw_partner_transactions', count(*) from raw_partner_transactions
union all select 'bank_settlements', count(*) from bank_settlements
union all select 'reconciliation_exceptions', count(*) from reconciliation_exceptions
union all select 'event_log', count(*) from event_log
order by table_name;
"

printf '\n== 5. Latest simulated integration runs ==\n'
"${psql_cmd[@]}" -c "
select
    id,
    partner_id,
    feed_name,
    source_reference,
    status,
    records_received,
    records_loaded,
    records_rejected,
    completed_at
from integration_runs
order by completed_at desc nulls last
limit 5;
"

printf '\n== 6. Latest raw partner transactions ==\n'
"${psql_cmd[@]}" -c "
select
    id,
    partner_id,
    provider_reference,
    agent_id,
    left(customer_msisdn_hash, 12) || '...' as customer_hash_prefix,
    transaction_type,
    amount,
    commission,
    status,
    transaction_created_at
from raw_partner_transactions
order by loaded_at desc
limit 5;
"

printf '\n== 7. Latest bank settlements and reconciliation exceptions ==\n'
"${psql_cmd[@]}" -c "
select
    settlement_reference,
    partner_id,
    transaction_count,
    gross_amount,
    commission_amount,
    loaded_at
from bank_settlements
order by loaded_at desc
limit 5;
"
"${psql_cmd[@]}" -c "
select
    id,
    partner_id,
    exception_type,
    severity,
    status,
    evidence,
    created_at
from reconciliation_exceptions
order by created_at desc
limit 5;
"

printf '\n== 8. Dashboard-ready dbt marts ==\n'
"${psql_cmd[@]}" -c "
select
    transaction_key,
    partner_id,
    provider_reference,
    agent_id,
    transaction_type,
    amount,
    commission,
    transaction_status,
    loaded_at
from analytics_marts.fact_transactions
order by loaded_at desc
limit 5;
"
"${psql_cmd[@]}" -c "
select
    partner_code,
    partner_name,
    country,
    transaction_volume,
    transaction_value,
    commission_value,
    active_agents,
    failed_transactions,
    latest_loaded_at
from analytics_marts.mart_partner_network_health
order by transaction_value desc;
"
"${psql_cmd[@]}" -c "
select
    agent_id,
    agent_name,
    region,
    float_balance,
    cash_balance,
    recent_transaction_volume,
    recent_transaction_value,
    liquidity_risk
from analytics_marts.mart_liquidity_risk
order by
    case liquidity_risk when 'high' then 1 when 'medium' then 2 else 3 end,
    recent_transaction_value desc
limit 10;
"

printf '\nEnd-to-end SQL lineage demo complete.\n'
