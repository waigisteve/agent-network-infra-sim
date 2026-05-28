with transaction_totals as (
    select
        partner_id,
        count(*) as raw_transaction_count,
        coalesce(sum(amount), 0) as raw_gross_amount,
        coalesce(sum(commission), 0) as raw_commission_amount
    from {{ ref('int_transactions_deduped') }}
    where transaction_status = 'SUCCESS'
    group by partner_id
)

select
    settlements.settlement_id,
    settlements.partner_id,
    settlements.settlement_reference,
    settlements.settlement_date,
    settlements.transaction_count as settlement_transaction_count,
    coalesce(transaction_totals.raw_transaction_count, 0) as raw_transaction_count,
    settlements.gross_amount as settlement_gross_amount,
    coalesce(transaction_totals.raw_gross_amount, 0) as raw_gross_amount,
    settlements.commission_amount as settlement_commission_amount,
    coalesce(transaction_totals.raw_commission_amount, 0) as raw_commission_amount,
    case
        when settlements.transaction_count = coalesce(transaction_totals.raw_transaction_count, 0)
         and settlements.gross_amount = coalesce(transaction_totals.raw_gross_amount, 0)
            then 'matched'
        else 'exception'
    end as reconciliation_status
from {{ ref('stg_bank_settlements') }} as settlements
left join transaction_totals
    on settlements.partner_id = transaction_totals.partner_id
