-- Demand vs inventory gap: are we running out of boxes on high-demand days?
-- Feeds the forecasting dashboard and operations planning

with demand as (
    select * from {{ ref('int_demand_signals') }}
),

dates as (
    select
        date_day,
        day_name,
        day_type,
        week_of_year,
        year_month
    from {{ ref('dim_dates') }}
)

select
    d.order_day,
    dt.day_name,
    dt.day_type,
    dt.week_of_year,
    dt.year_month,

    d.total_orders,
    d.total_revenue,
    d.avg_order_value,
    d.boxes_assigned,
    d.unique_boxes_used,
    d.small_boxes_used,
    d.medium_boxes_used,
    d.large_boxes_used,
    d.available_boxes_eod,
    d.demand_pressure_ratio,
    d.rolling_7d_avg_orders,

    -- Inventory gap: how many more boxes would we have needed?
    -- (assumes avg 1.1 boxes per order based on our data)
    round(d.total_orders * 1.1)                         as boxes_needed_estimate,
    round(d.total_orders * 1.1) - d.boxes_assigned      as inventory_gap,

    -- Stockout risk classification
    case
        when d.demand_pressure_ratio > 0.8  then 'HIGH_RISK'
        when d.demand_pressure_ratio > 0.6  then 'MEDIUM_RISK'
        else                                     'LOW_RISK'
    end                                         as stockout_risk,

    -- Week-over-week order growth
    d.total_orders - lag(d.total_orders, 7) over (
        order by d.order_day
    )                                           as wow_order_delta,

    round(
        (d.total_orders - lag(d.total_orders, 7) over (order by d.order_day))::float
        / nullif(lag(d.total_orders, 7) over (order by d.order_day), 0) * 100
    , 1)                                        as wow_growth_pct

from demand d
left join dates dt on d.order_day = dt.date_day
order by d.order_day
