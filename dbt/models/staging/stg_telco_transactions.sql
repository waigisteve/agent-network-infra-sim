select
    id as raw_transaction_id,
    partner_id,
    integration_run_id,
    provider_reference,
    agent_id,
    customer_msisdn_hash,
    upper(transaction_type) as transaction_type,
    amount,
    commission,
    upper(status) as transaction_status,
    transaction_created_at,
    loaded_at
from {{ source('app', 'raw_partner_transactions') }}
