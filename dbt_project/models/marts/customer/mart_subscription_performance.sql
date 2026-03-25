-- Subscription plan performance: revenue, retention, churn by plan type

with customers as (
    select * from {{ ref('dim_customers') }}
),

orders as (
    select * from {{ ref('fct_orders') }}
),

plan_customers as (
    select
        c.plan_id,
        c.plan_name,
        c.plan_price,
        count(distinct c.customer_id)                       as total_customers,
        sum(case when c.is_active then 1 else 0 end)        as active_customers,
        sum(case when not c.is_active then 1 else 0 end)    as churned_customers,
        avg(c.total_spend)                                  as avg_customer_ltv,
        avg(c.total_orders)                                 as avg_orders_per_customer,
        avg(c.customer_lifespan_days)                       as avg_lifespan_days
    from customers c
    group by 1, 2, 3
),

plan_revenue as (
    select
        c.plan_id,
        strftime(o.order_date, '%Y-%m')                     as year_month,
        count(distinct o.order_id)                          as monthly_orders,
        sum(o.order_amount)                                 as monthly_revenue,
        count(distinct o.customer_id)                       as active_ordering_customers
    from orders o
    left join customers c on o.customer_id = c.customer_id
    group by 1, 2
)

select
    pc.plan_id,
    pc.plan_name,
    pc.plan_price,
    pc.total_customers,
    pc.active_customers,
    pc.churned_customers,
    round(
        pc.churned_customers::float / nullif(pc.total_customers, 0) * 100
    , 1)                                                    as churn_rate_pct,
    round(pc.avg_customer_ltv, 2)                           as avg_customer_ltv,
    round(pc.avg_orders_per_customer, 1)                    as avg_orders_per_customer,
    round(pc.avg_lifespan_days, 0)                          as avg_lifespan_days,

    -- Monthly recurring revenue estimate
    round(pc.active_customers * pc.plan_price, 2)           as estimated_mrr,

    -- Revenue per plan as % of total
    round(
        (pc.active_customers * pc.plan_price)::float
        / sum(pc.active_customers * pc.plan_price) over () * 100
    , 1)                                                    as mrr_share_pct

from plan_customers pc
order by pc.plan_price desc
