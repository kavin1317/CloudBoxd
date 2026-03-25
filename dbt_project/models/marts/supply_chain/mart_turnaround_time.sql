-- Box turnaround time analysis: how long does each box take to complete
-- a full dispatch → deliver → pickup → return cycle?
-- This is the core reverse logistics KPI.

with assignments as (
    select * from {{ ref('fct_box_assignments') }}
),

boxes as (
    select box_id, box_type, rfid_tag from {{ ref('dim_hotboxes') }}
),

addresses as (
    select address_id, delivery_zone from {{ ref('dim_addresses') }}
),

orders as (
    select order_id, address_id from {{ ref('fct_orders') }}
),

enriched as (
    select
        a.assignment_id,
        a.box_id,
        b.rfid_tag,
        b.box_type,
        a.order_id,
        addr.delivery_zone,
        a.assignment_date,

        a.turnaround_hours,
        a.dwell_hours,
        a.dispatch_lag_minutes,
        a.sla_status,
        a.return_condition,
        a.is_returned,
        a.days_since_assigned,

        -- Turnaround buckets for distribution analysis
        case
            when a.turnaround_hours <= 12  then '0-12h'
            when a.turnaround_hours <= 24  then '12-24h'
            when a.turnaround_hours <= 48  then '24-48h'
            when a.turnaround_hours <= 72  then '48-72h'
            when a.turnaround_hours is not null then '72h+'
            else 'OUTSTANDING'
        end                                             as turnaround_bucket,

        -- Month for trend analysis
        strftime(a.assignment_date, '%Y-%m')            as year_month

    from assignments a
    left join boxes   b    on a.box_id   = b.box_id
    left join orders  o    on a.order_id = o.order_id
    left join addresses addr on o.address_id = addr.address_id
)

select * from enriched
