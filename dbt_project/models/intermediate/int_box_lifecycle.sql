-- Computes per-assignment lifecycle metrics:
-- turnaround time, SLA status, days outstanding, current phase

with assignments as (
    select * from {{ ref('stg_box_assignments') }}
),

boxes as (
    select * from {{ ref('stg_hotboxes') }}
),

enriched as (
    select
        a.assignment_id,
        a.order_id,
        a.box_id,
        a.sequence_number,
        a.subsequence,
        b.box_type,
        b.rfid_tag,
        b.box_capacity,

        a.assigned_at,
        cast(a.dispatched_at as timestamp)  as dispatched_at,
        cast(a.delivered_at  as timestamp)  as delivered_at,
        cast(a.picked_up_at  as timestamp)  as picked_up_at,
        cast(a.returned_at   as timestamp)  as returned_at,
        a.return_condition,
        a.turnaround_hours,
        a.is_returned,

        -- Time-to-dispatch (minutes from assignment to leaving warehouse)
        case
            when a.dispatched_at is not null and a.dispatched_at != ''
            then datediff('minute', a.assigned_at, cast(a.dispatched_at as timestamp))
        end as dispatch_lag_minutes,

        -- Time-at-customer (hours box sat with customer before pickup)
        case
            when a.delivered_at is not null and a.delivered_at != ''
              and a.picked_up_at is not null and a.picked_up_at != ''
            then round(
                datediff('minute', cast(a.delivered_at as timestamp), cast(a.picked_up_at as timestamp)) / 60.0
            , 2)
        end as dwell_hours,

        -- SLA classification (based on architecture: next-day return = green)
        case
            when not a.is_returned                               then 'OUTSTANDING'
            when a.turnaround_hours <= 24                        then 'ON_TIME'
            when a.turnaround_hours <= 72                        then 'LATE'
            else                                                      'OVERDUE'
        end as sla_status,

        -- Days since assignment (for overdue alerting)
        datediff('day', a.assigned_at, current_timestamp) as days_since_assigned,

        -- Box utilization flag
        case
            when a.is_returned then 'COMPLETED'
            when a.delivered_at is not null and a.delivered_at != '' then 'AWAITING_RETURN'
            when a.dispatched_at is not null and a.dispatched_at != '' then 'IN_TRANSIT'
            else 'PREPARING'
        end as lifecycle_phase

    from assignments a
    left join boxes b on a.box_id = b.box_id
)

select * from enriched
