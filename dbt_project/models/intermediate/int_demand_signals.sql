-- Daily demand aggregation used by forecasting mart and inventory gap analysis

with orders as (
    select * from {{ ref('stg_orders') }}
),

assignments as (
    select * from {{ ref('stg_box_assignments') }}
),

boxes as (
    select * from {{ ref('stg_hotboxes') }}
),

daily_orders as (
    select
        cast(order_date as date)                    as order_day,
        dayofweek(cast(order_date as date))         as day_of_week,
        case
            when dayofweek(cast(order_date as date)) in (0, 6) then 'WEEKEND'
            else 'WEEKDAY'
        end                                         as day_type,
        count(distinct order_id)                    as total_orders,
        sum(order_amount)                           as total_revenue,
        avg(order_amount)                           as avg_order_value
    from orders
    group by 1, 2, 3
),

daily_boxes as (
    select
        cast(a.assigned_at as date)                 as assignment_day,
        count(distinct a.assignment_id)             as boxes_assigned,
        count(distinct a.box_id)                    as unique_boxes_used,
        sum(case when b.box_type = 'SMALL'  then 1 else 0 end) as small_boxes_used,
        sum(case when b.box_type = 'MEDIUM' then 1 else 0 end) as medium_boxes_used,
        sum(case when b.box_type = 'LARGE'  then 1 else 0 end) as large_boxes_used
    from assignments a
    left join boxes b on a.box_id = b.box_id
    group by 1
),

-- Fleet availability snapshot per day
fleet_snapshot as (
    select
        assignment_day,
        80 as total_fleet_size,          -- static fleet of 80 boxes
        (80 - unique_boxes_used)         as available_boxes_eod
    from daily_boxes
)

select
    o.order_day,
    o.day_of_week,
    o.day_type,
    o.total_orders,
    o.total_revenue,
    o.avg_order_value,
    coalesce(b.boxes_assigned, 0)       as boxes_assigned,
    coalesce(b.unique_boxes_used, 0)    as unique_boxes_used,
    coalesce(b.small_boxes_used, 0)     as small_boxes_used,
    coalesce(b.medium_boxes_used, 0)    as medium_boxes_used,
    coalesce(b.large_boxes_used, 0)     as large_boxes_used,
    coalesce(f.available_boxes_eod, 80) as available_boxes_eod,

    -- Demand pressure: orders per available box
    round(
        o.total_orders::float / nullif(coalesce(f.available_boxes_eod, 80), 0)
    , 2) as demand_pressure_ratio,

    -- 7-day rolling average orders
    avg(o.total_orders) over (
        order by o.order_day
        rows between 6 preceding and current row
    ) as rolling_7d_avg_orders

from daily_orders o
left join daily_boxes  b on o.order_day = b.assignment_day
left join fleet_snapshot f on o.order_day = f.assignment_day
order by o.order_day
