-- RFM segmentation: Recency, Frequency, Monetary
-- Used by customer analytics marts and recommendation system

with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

loyalty as (
    select * from {{ ref('stg_loyalty') }}
),

rfm_base as (
    select
        o.customer_id,
        max(cast(o.order_date as date))             as last_order_date,
        count(distinct o.order_id)                  as order_count,
        sum(o.order_amount)                         as total_spend,
        avg(o.order_amount)                         as avg_order_value,
        min(cast(o.order_date as date))             as first_order_date,
        datediff('day',
            min(cast(o.order_date as date)),
            max(cast(o.order_date as date))
        )                                           as customer_lifespan_days
    from orders o
    group by 1
),

rfm_scored as (
    select
        r.*,
        c.plan_id,
        c.is_active,
        c.signup_date,
        l.tier                                      as loyalty_tier,
        l.points                                    as loyalty_points,

        -- Recency score (days since last order → lower = better)
        datediff('day', r.last_order_date, current_date) as days_since_last_order,

        -- Quintile scores (1=worst, 5=best)
        ntile(5) over (order by datediff('day', r.last_order_date, current_date) desc) as recency_score,
        ntile(5) over (order by r.order_count asc)      as frequency_score,
        ntile(5) over (order by r.total_spend asc)      as monetary_score

    from rfm_base r
    left join customers c on r.customer_id = c.customer_id
    left join loyalty   l on r.customer_id = l.customer_id
),

segmented as (
    select
        *,
        (recency_score + frequency_score + monetary_score) as rfm_total,

        case
            when recency_score >= 4 and frequency_score >= 4 and monetary_score >= 4
                then 'CHAMPION'
            when recency_score >= 3 and frequency_score >= 3 and monetary_score >= 3
                then 'LOYAL'
            when recency_score >= 4 and frequency_score <= 2
                then 'NEW_CUSTOMER'
            when recency_score <= 2 and frequency_score >= 3
                then 'AT_RISK'
            when recency_score <= 2 and frequency_score <= 2
                then 'CHURNED'
            else
                'POTENTIAL'
        end as rfm_segment
    from rfm_scored
)

select * from segmented
