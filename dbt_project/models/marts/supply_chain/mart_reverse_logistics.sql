-- Reverse logistics performance: pickup success rates, overdue rates,
-- zone-level return patterns — the supply chain "returns" dashboard

with pickups as (
    select
        pickup_id,
        customer_id,
        address_id,
        box_id,
        cast(scheduled_date as date)        as scheduled_date,
        nullif(cast(actual_pickup as varchar), '') as actual_pickup,
        upper(status)                       as pickup_status,
        driver_id
    from {{ source('raw', 'pickup_schedules') }}
),

addresses as (
    select address_id, delivery_zone, zipcode from {{ ref('dim_addresses') }}
),

boxes as (
    select box_id, box_type, rfid_tag from {{ ref('dim_hotboxes') }}
),

assignments as (
    select
        box_id,
        assignment_id,
        sla_status,
        turnaround_hours,
        return_condition
    from {{ ref('fct_box_assignments') }}
)

select
    p.pickup_id,
    p.customer_id,
    p.box_id,
    b.rfid_tag,
    b.box_type,
    p.scheduled_date,
    cast(p.actual_pickup as timestamp)      as actual_pickup_ts,
    p.pickup_status,
    p.driver_id,
    a.delivery_zone,
    a.zipcode,

    -- Days between scheduled and actual pickup
    case
        when p.actual_pickup is not null
        then datediff('day',
            p.scheduled_date,
            cast(p.actual_pickup as date)
        )
    end                                     as pickup_delay_days,

    -- SLA from assignment perspective
    ass.sla_status,
    ass.turnaround_hours,
    ass.return_condition,

    -- Pickup outcome classification
    case
        when p.pickup_status = 'COMPLETED' and
             datediff('day', p.scheduled_date,
                cast(p.actual_pickup as date)) <= 0
        then 'ON_SCHEDULE'
        when p.pickup_status = 'COMPLETED'
        then 'DELAYED_RETURN'
        when p.pickup_status = 'MISSED'
        then 'MISSED_PICKUP'
        else 'CANCELLED'
    end                                     as return_outcome,

    strftime(p.scheduled_date, '%Y-%m')     as year_month

from pickups p
left join addresses  a   on p.address_id  = a.address_id
left join boxes      b   on p.box_id      = b.box_id
left join assignments ass on p.box_id     = ass.box_id
