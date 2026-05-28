select
    agents.id as agent_id,
    agents.name as agent_name,
    agents.outlet,
    agents.float_balance,
    agents.cash_balance,
    agents.outstanding_balance,
    agents.latitude,
    agents.longitude,
    field_agents.id as field_agent_id,
    field_agents.name as field_agent_name,
    field_agents.region
from {{ source('app', 'agents') }} as agents
left join {{ source('app', 'field_agents') }} as field_agents
    on agents.field_agent_id = field_agents.id
