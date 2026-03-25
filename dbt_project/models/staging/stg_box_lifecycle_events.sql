with source as (
    select * from {{ source('raw', 'box_lifecycle_events') }}
),

renamed as (
    select
        event_id,
        box_id,
        upper(event_type)                   as event_type,
        cast(event_timestamp as timestamp)  as event_timestamp,
        nullif(triggered_by, '')            as triggered_by,
        upper(previous_status)              as previous_status,
        upper(new_status)                   as new_status,
        nullif(notes, '')                   as notes
    from source
)

select * from renamed
