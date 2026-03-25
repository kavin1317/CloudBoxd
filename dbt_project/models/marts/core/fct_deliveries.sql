with perf as (
    select * from {{ ref('int_delivery_performance') }}
),

deliveries as (
    select delivery_id, address_id
    from {{ ref('stg_deliveries') }}
)

select
    p.delivery_id,
    p.order_id,
    p.driver_id,
    d.address_id,
    p.delivery_zone,
    p.delivery_status,
    p.scheduled_time,
    cast(p.actual_departure as timestamp) as actual_departure,
    cast(p.actual_delivery  as timestamp) as actual_delivery,
    p.delivery_duration_min,
    p.failure_reason,
    p.is_on_time,
    p.minutes_vs_schedule,
    p.zone_sla_minutes,
    p.met_zone_sla,
    cast(p.scheduled_time as date)        as delivery_date
from perf p
left join deliveries d on p.delivery_id = d.delivery_id
