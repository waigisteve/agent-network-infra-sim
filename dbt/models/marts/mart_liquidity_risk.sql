select
    agents.agent_id,
    agents.agent_name,
    agents.region,
    agents.float_balance,
    agents.cash_balance,
    count(transactions.transaction_key) as recent_transaction_volume,
    coalesce(sum(transactions.amount), 0) as recent_transaction_value,
    case
        when agents.float_balance < 5000 and count(transactions.transaction_key) >= 1 then 'high'
        when agents.float_balance < 10000 then 'medium'
        else 'low'
    end as liquidity_risk
from {{ ref('dim_agents') }} as agents
left join {{ ref('fact_transactions') }} as transactions
    on agents.agent_id = transactions.agent_id
group by
    agents.agent_id,
    agents.agent_name,
    agents.region,
    agents.float_balance,
    agents.cash_balance
