select
    partner_id,
    partner_code,
    partner_name,
    partner_type,
    country,
    integration_mode,
    data_freshness_sla_minutes,
    is_active
from {{ ref('stg_partners') }}
