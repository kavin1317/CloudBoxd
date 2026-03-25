-- Fleet Utilization: daily snapshot of how many boxes are in use vs available
-- This is the #1 supply chain KPI for hotbox fleet management

with assignments as (
    select * from {{ ref('fct_box_assignments') }}
),

boxes as (
    select * from {{ ref('dim_hotboxes') }}
),

dates as (
    select date_day from {{ ref('dim_dates') }}
),

-- For each date, count boxes that were assigned (not yet returned) on that day
daily_in_use as (
    select
        d.date_day,
        b.box_type,
        count(distinct case
            when a.assignment_date <= d.date_day
             and (a.returned_at is null or cast(a.returned_at as date) > d.date_day)
            then a.box_id
        end) as boxes_in_use
    from dates d
    cross join (select distinct box_type from boxes) bt
    left join boxes b on b.box_type = bt.box_type
    left join assignments a on a.box_id = b.box_id
    group by 1, 2
),

fleet_totals as (
    select
        box_type,
        count(*)            as total_boxes,
        sum(box_capacity)   as total_capacity
    from boxes
    group by 1
)

select
    d.date_day,
    f.box_type,
    f.total_boxes,
    f.total_capacity,
    coalesce(u.boxes_in_use, 0)                             as boxes_in_use,
    f.total_boxes - coalesce(u.boxes_in_use, 0)             as boxes_available,
    round(
        coalesce(u.boxes_in_use, 0)::float
        / nullif(f.total_boxes, 0) * 100
    , 1)                                                    as utilization_pct,

    -- 7-day rolling utilization
    round(avg(
        coalesce(u.boxes_in_use, 0)::float / nullif(f.total_boxes, 0) * 100
    ) over (
        partition by f.box_type
        order by d.date_day
        rows between 6 preceding and current row
    ), 1)                                                   as rolling_7d_utilization_pct,

    -- Flag critically low availability (< 20% available)
    case
        when (f.total_boxes - coalesce(u.boxes_in_use, 0))::float
             / nullif(f.total_boxes, 0) < 0.20
        then true else false
    end                                                     as is_low_availability

from dates d
cross join fleet_totals f
left join daily_in_use u
    on d.date_day = u.date_day
    and f.box_type = u.box_type
where d.date_day between '2025-06-01' and '2026-01-31'
order by d.date_day, f.box_type
