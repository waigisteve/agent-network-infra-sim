select
    raw_transaction_id as transaction_key,
    partner_id,
    provider_reference,
    agent_id,
    customer_msisdn_hash,
    transaction_type,
    amount,
    commission,
    transaction_status,
    transaction_created_at,
    loaded_at
from {{ ref('int_transactions_deduped') }}
