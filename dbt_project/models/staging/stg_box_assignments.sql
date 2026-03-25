with source as (
    select * from {{ source('raw', 'box_assignments') }}
),

renamed as (
    select
        assignment_id,
        order_id,
        box_id,
        sequence_number,
        subsequence,
        cast(assigned_at as timestamp)                  as assigned_at,
        nullif(cast(dispatched_at as varchar), '')      as dispatched_at,
        nullif(cast(delivered_at as varchar), '')       as delivered_at,
        nullif(cast(picked_up_at as varchar), '')       as picked_up_at,
        nullif(cast(returned_at as varchar), '')        as returned_at,
        nullif(return_condition, '')                    as return_condition,
        cast(nullif(cast(turnaround_hours as varchar), '') as decimal(8,2)) as turnaround_hours,
        cast(is_returned as boolean)                    as is_returned
    from source
)

select * from renamed
