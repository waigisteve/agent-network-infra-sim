select
    partners.partner_id,
    partners.partner_code,
    partners.partner_name,
    partners.country,
    count(transactions.transaction_key) as transaction_volume,
    coalesce(sum(transactions.amount), 0) as transaction_value,
    coalesce(sum(transactions.commission), 0) as commission_value,
    count(distinct transactions.agent_id) as active_agents,
    sum(case when transactions.transaction_status = 'FAILED' then 1 else 0 end) as failed_transactions,
    max(transactions.loaded_at) as latest_loaded_at
from {{ ref('dim_partners') }} as partners
left join {{ ref('fact_transactions') }} as transactions
    on partners.partner_id = transactions.partner_id
group by
    partners.partner_id,
    partners.partner_code,
    partners.partner_name,
    partners.country
