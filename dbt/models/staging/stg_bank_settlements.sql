select
    id as settlement_id,
    partner_id,
    settled_partner_id,
    integration_run_id,
    settlement_reference,
    settlement_date,
    transaction_count,
    gross_amount,
    commission_amount,
    currency,
    loaded_at
from {{ source('app', 'bank_settlements') }}
