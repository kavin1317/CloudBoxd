with customers as (
    select * from {{ ref('stg_customers') }}
),

segments as (
    select * from {{ ref('int_customer_segments') }}
),

loyalty as (
    select * from {{ ref('stg_loyalty') }}
),

plans as (
    select * from {{ source('raw', 'subscription_plans') }}
)

select
    c.customer_id,
    c.customer_name,
    c.email,
    c.phone,
    c.plan_id,
    p.plan_name,
    p.plan_price,
    p.meals_per_day,
    c.signup_date,
    c.is_active,

    -- Loyalty
    coalesce(l.tier, 'BRONZE')              as loyalty_tier,
    coalesce(l.points, 0)                   as loyalty_points,
    coalesce(l.lifetime_points, 0)          as lifetime_loyalty_points,

    -- RFM Segmentation
    coalesce(s.rfm_segment, 'NEW_CUSTOMER') as rfm_segment,
    coalesce(s.recency_score, 1)            as recency_score,
    coalesce(s.frequency_score, 1)          as frequency_score,
    coalesce(s.monetary_score, 1)           as monetary_score,
    coalesce(s.order_count, 0)              as total_orders,
    coalesce(s.total_spend, 0)              as total_spend,
    s.last_order_date,
    s.days_since_last_order,
    s.customer_lifespan_days

from customers c
left join plans    p on c.plan_id     = p.plan_id
left join loyalty  l on c.customer_id = l.customer_id
left join segments s on c.customer_id = s.customer_id
