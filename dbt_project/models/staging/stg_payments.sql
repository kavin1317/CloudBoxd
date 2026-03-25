with source as (
    select * from {{ source('raw', 'payments') }}
),

renamed as (
    select
        payment_id,
        order_id,
        cast(amount as decimal(10,2))       as amount,
        upper(payment_method)               as payment_method,
        cast(payment_date as timestamp)     as payment_date,
        upper(status)                       as payment_status
    from source
)

select * from renamed
