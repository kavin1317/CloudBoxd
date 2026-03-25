-- Customer-level order analytics: LTV, order cadence, subscription value
-- Primary mart for customer analytics dashboard

with customers as (
    select * from {{ ref('dim_customers') }}
),

orders as (
    select * from {{ ref('fct_orders') }}
),

monthly as (
    select
        customer_id,
        strftime(order_date, '%Y-%m')       as year_month,
        count(distinct order_id)            as monthly_orders,
        sum(order_amount)                   as monthly_revenue
    from orders
    group by 1, 2
),

order_gaps as (
    select
        customer_id,
        order_date,
        lag(order_date) over (
            partition by customer_id
            order by order_date
        )                                   as prev_order_date,
        datediff('day',
            lag(order_date) over (
                partition by customer_id
                order by order_date
            ),
            order_date
        )                                   as days_between_orders
    from orders
)

select
    c.customer_id,
    c.customer_name,
    c.plan_id,
    c.plan_name,
    c.plan_price,
    c.signup_date,
    c.is_active,
    c.loyalty_tier,
    c.loyalty_points,
    c.rfm_segment,
    c.total_orders,
    c.total_spend,
    c.last_order_date,
    c.days_since_last_order,
    c.customer_lifespan_days,

    -- Average order value
    round(
        c.total_spend / nullif(c.total_orders, 0)
    , 2)                                    as avg_order_value,

    -- Monthly order cadence
    round(
        c.total_orders::float
        / nullif(c.customer_lifespan_days / 30.0, 0)
    , 2)                                    as avg_orders_per_month,

    -- Avg days between orders
    round(avg(og.days_between_orders), 1)   as avg_days_between_orders,

    -- Estimated annual LTV (simple: monthly cadence × AOV × 12)
    round(
        (c.total_orders::float / nullif(c.customer_lifespan_days / 30.0, 0))
        * (c.total_spend / nullif(c.total_orders, 0))
        * 12
    , 2)                                    as estimated_annual_ltv,

    -- Multi-box order rate
    round(
        sum(case when o.is_multi_box_order then 1 else 0 end)::float
        / nullif(c.total_orders, 0) * 100
    , 1)                                    as multi_box_order_pct,

    -- Feedback rate
    round(
        sum(case when o.has_feedback then 1 else 0 end)::float
        / nullif(c.total_orders, 0) * 100
    , 1)                                    as feedback_rate_pct,

    -- Avg overall rating
    round(avg(o.overall_rating), 2)         as avg_rating

from customers c
left join orders o       on c.customer_id = o.customer_id
left join order_gaps og  on c.customer_id = og.customer_id
group by
    c.customer_id, c.customer_name, c.plan_id, c.plan_name,
    c.plan_price, c.signup_date, c.is_active, c.loyalty_tier,
    c.loyalty_points, c.rfm_segment, c.total_orders, c.total_spend,
    c.last_order_date, c.days_since_last_order, c.customer_lifespan_days
