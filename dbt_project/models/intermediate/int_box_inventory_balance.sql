-- Daily inventory balance: how many boxes of each type are
-- available, in-use, in-maintenance, lost — for gap analysis

with assignments as (
    select * from {{ ref('stg_box_assignments') }}
),

boxes as (
    select * from {{ ref('stg_hotboxes') }}
),

maintenance as (
    select
        box_id,
        cast(start_date as date) as maint_start,
        cast(end_date   as date) as maint_end
    from {{ source('raw', 'box_maintenance') }}
),

-- Boxes in-use per day (assigned but not yet returned)
daily_in_use as (
    select
        cast(a.assigned_at as date)     as snapshot_date,
        b.box_type,
        count(distinct a.box_id)        as boxes_in_use
    from assignments a
    left join boxes b on a.box_id = b.box_id
    where not a.is_returned
    group by 1, 2
),

-- Total fleet by type (static)
fleet_by_type as (
    select
        box_type,
        count(*)    as total_boxes,
        sum(box_capacity) as total_capacity
    from boxes
    group by 1
)

select
    d.snapshot_date,
    f.box_type,
    f.total_boxes,
    f.total_capacity,
    coalesce(d.boxes_in_use, 0)             as boxes_in_use,
    f.total_boxes - coalesce(d.boxes_in_use, 0) as boxes_available,
    round(
        coalesce(d.boxes_in_use, 0)::float / f.total_boxes * 100
    , 1)                                    as utilization_pct

from fleet_by_type f
cross join (select distinct cast(assigned_at as date) as snapshot_date from assignments) d
left join daily_in_use d2
    on d.snapshot_date = d2.snapshot_date
    and f.box_type = d2.box_type
order by d.snapshot_date, f.box_type
