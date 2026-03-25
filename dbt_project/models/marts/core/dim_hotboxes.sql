with boxes as (
    select * from {{ ref('stg_hotboxes') }}
),

assignment_stats as (
    select
        box_id,
        count(*)                                        as total_assignments,
        sum(case when is_returned then 1 else 0 end)    as completed_assignments,
        avg(turnaround_hours)                           as avg_turnaround_hours,
        sum(case when return_condition = 'DAMAGED'      then 1 else 0 end) as damage_count,
        sum(case when return_condition = 'NEEDS_CLEANING' then 1 else 0 end) as cleaning_count,
        max(cast(assigned_at as date))                  as last_assigned_date
    from {{ ref('stg_box_assignments') }}
    group by 1
),

maintenance_stats as (
    select
        box_id,
        count(*)                                        as total_maintenance_events,
        sum(cast(cost as decimal(8,2)))                 as total_maintenance_cost,
        max(cast(start_date as date))                   as last_maintenance_date
    from {{ source('raw', 'box_maintenance') }}
    group by 1
)

select
    b.box_id,
    b.rfid_tag,
    b.box_type,
    b.box_capacity,
    b.current_status,
    b.first_deployed,

    coalesce(a.total_assignments, 0)        as total_assignments,
    coalesce(a.completed_assignments, 0)    as completed_assignments,
    coalesce(a.avg_turnaround_hours, 0)     as avg_turnaround_hours,
    coalesce(a.damage_count, 0)             as damage_count,
    coalesce(a.cleaning_count, 0)           as cleaning_count,
    a.last_assigned_date,

    coalesce(m.total_maintenance_events, 0) as total_maintenance_events,
    coalesce(m.total_maintenance_cost, 0)   as total_maintenance_cost,
    m.last_maintenance_date,

    -- Health score: 100 - (damage % * 50) - (avg_turnaround deviation penalty)
    round(
        100
        - (coalesce(a.damage_count, 0)::float / nullif(a.total_assignments, 0) * 50)
        - (coalesce(m.total_maintenance_events, 0)::float / nullif(a.total_assignments, 0) * 10)
    , 1) as health_score,

    case b.current_status
        when 'LOST'        then 'INACTIVE'
        when 'RETIRED'     then 'INACTIVE'
        when 'MAINTENANCE' then 'MAINTENANCE'
        else                    'ACTIVE'
    end as operational_status

from boxes b
left join assignment_stats  a on b.box_id = a.box_id
left join maintenance_stats m on b.box_id = m.box_id
