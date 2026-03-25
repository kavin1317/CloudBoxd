with source as (
    select * from {{ source('raw', 'order_items') }}
),

renamed as (
    select
        order_id,
        menu_item_id,
        cast(quantity as integer)           as quantity,
        cast(item_price as decimal(8,2))    as item_price,
        quantity * item_price               as line_total
    from source
)

select * from renamed
