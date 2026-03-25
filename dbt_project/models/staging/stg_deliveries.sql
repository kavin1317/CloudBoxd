with source as (
    select * from {{ source('raw', 'deliveries') }}
),

renamed as (
    select
        delivery_id,
        order_id,
        driver_id,
        address_id,
        cast(scheduled_time as timestamp)                       as scheduled_time,
        nullif(cast(actual_departure as varchar), '')           as actual_departure,
        nullif(cast(actual_delivery as varchar), '')            as actual_delivery,
        upper(delivery_status)                                  as delivery_status,
        cast(nullif(cast(delivery_duration_min as varchar), '') as integer) as delivery_duration_min,
        nullif(failure_reason, '')                              as failure_reason
    from source
)

select * from renamed
