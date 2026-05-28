select
    agent_id,
    agent_name,
    outlet,
    field_agent_id,
    field_agent_name,
    region,
    latitude,
    longitude,
    float_balance,
    cash_balance,
    outstanding_balance
from {{ ref('stg_agents') }}
