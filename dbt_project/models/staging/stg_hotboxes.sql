with source as (
    select * from {{ source('raw', 'hotboxes') }}
),

renamed as (
    select
        box_id,
        rfid_tag,
        upper(box_type)                 as box_type,
        box_capacity,
        upper(current_status)           as current_status,
        cast(first_deployed as date)    as first_deployed,
        coalesce(total_assignments, 0)  as total_assignments,
        cast(created_at as timestamp)   as created_at,
        cast(updated_at as timestamp)   as updated_at
    from source
)

select * from renamed
