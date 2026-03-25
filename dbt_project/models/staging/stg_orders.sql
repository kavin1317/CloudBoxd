with source as (
    select * from {{ source('raw', 'orders') }}
),

renamed as (
    select
        order_id,
        customer_id,
        cast(order_date as timestamp)   as order_date,
        cast(order_amount as decimal(10,2)) as order_amount,
        upper(status)                   as order_status,
        address_id,
        nullif(notes, '')               as notes,
        cast(created_at as timestamp)   as created_at
    from source
)

select * from renamed
