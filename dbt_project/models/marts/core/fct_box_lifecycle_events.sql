with events as (
    select * from {{ ref('stg_box_lifecycle_events') }}
),

boxes as (
    select box_id, box_type, rfid_tag from {{ ref('stg_hotboxes') }}
)

select
    e.event_id,
    e.box_id,
    b.rfid_tag,
    b.box_type,
    e.event_type,
    e.event_timestamp,
    cast(e.event_timestamp as date)     as event_date,
    e.triggered_by,
    e.previous_status,
    e.new_status,
    e.notes,

    -- Time between this event and previous event for same box
    lag(e.event_timestamp) over (
        partition by e.box_id
        order by e.event_timestamp
    )                                   as prev_event_timestamp,

    datediff('minute',
        lag(e.event_timestamp) over (
            partition by e.box_id
            order by e.event_timestamp
        ),
        e.event_timestamp
    )                                   as minutes_since_prev_event

from events e
left join boxes b on e.box_id = b.box_id
