with ranked as (
    select
        *,
        row_number() over (
            partition by partner_id, provider_reference
            order by loaded_at desc, raw_transaction_id desc
        ) as row_num
    from {{ ref('stg_telco_transactions') }}
)

select
    raw_transaction_id,
    partner_id,
    integration_run_id,
    provider_reference,
    agent_id,
    customer_msisdn_hash,
    transaction_type,
    amount,
    commission,
    transaction_status,
    transaction_created_at,
    loaded_at
from ranked
where row_num = 1
