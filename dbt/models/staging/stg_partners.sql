select
    id as partner_id,
    code as partner_code,
    name as partner_name,
    partner_type,
    country,
    integration_mode,
    data_freshness_sla_minutes,
    is_active,
    created_at
from {{ source('app', 'partners') }}
