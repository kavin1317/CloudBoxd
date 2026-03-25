with accounts as (
    select * from {{ source('raw', 'loyalty_accounts') }}
),

transactions as (
    select * from {{ source('raw', 'loyalty_transactions') }}
),

accounts_cleaned as (
    select
        account_id,
        customer_id,
        upper(tier)                         as tier,
        cast(points as integer)             as points,
        cast(lifetime_points as integer)    as lifetime_points,
        cast(tier_updated_at as timestamp)  as tier_updated_at
    from accounts
),

transactions_cleaned as (
    select
        transaction_id,
        account_id,
        cast(points_change as integer)      as points_change,
        upper(transaction_type)             as transaction_type,
        cast(transaction_date as timestamp) as transaction_date,
        nullif(reference_id, '')            as reference_id
    from transactions
)

select
    a.account_id,
    a.customer_id,
    a.tier,
    a.points,
    a.lifetime_points,
    a.tier_updated_at,
    count(t.transaction_id)                             as total_transactions,
    sum(case when t.points_change > 0 then t.points_change else 0 end) as total_earned,
    sum(case when t.points_change < 0 then abs(t.points_change) else 0 end) as total_redeemed
from accounts_cleaned a
left join transactions_cleaned t on a.account_id = t.account_id
group by 1,2,3,4,5,6
