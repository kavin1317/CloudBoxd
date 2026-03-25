-- Box maintenance analytics: cost, frequency, downtime per box
-- Feeds fleet health dashboard

with maintenance as (
    select
        maintenance_id,
        box_id,
        upper(maintenance_type)             as maintenance_type,
        cast(start_date as timestamp)       as start_date,
        cast(end_date   as timestamp)       as end_date,
        notes,
        cast(cost as decimal(8,2))          as cost
    from {{ source('raw', 'box_maintenance') }}
),

boxes as (
    select box_id, box_type, rfid_tag, total_assignments from {{ ref('dim_hotboxes') }}
)

select
    m.maintenance_id,
    m.box_id,
    b.rfid_tag,
    b.box_type,
    m.maintenance_type,
    m.start_date,
    m.end_date,
    cast(m.start_date as date)              as maintenance_date,
    strftime(cast(m.start_date as date), '%Y-%m') as year_month,
    m.notes,
    m.cost,

    -- Downtime in hours
    round(
        datediff('minute', m.start_date, m.end_date) / 60.0
    , 1)                                    as downtime_hours,

    -- Running cost per box
    sum(m.cost) over (
        partition by m.box_id
        order by m.start_date
        rows unbounded preceding
    )                                       as cumulative_cost_per_box,

    -- Maintenance count per box
    row_number() over (
        partition by m.box_id
        order by m.start_date
    )                                       as maintenance_sequence,

    b.total_assignments                     as box_total_assignments,

    -- Cost per assignment (efficiency metric)
    round(
        m.cost / nullif(b.total_assignments, 0)
    , 4)                                    as cost_per_assignment

from maintenance m
left join boxes b on m.box_id = b.box_id
order by m.start_date
