with source as (
    select * from {{ source('raw', 'menu_items') }}
),

renamed as (
    select
        menu_item_id,
        item_name,
        description,
        cuisine,
        upper(category)                 as category,
        cast(price as decimal(8,2))     as price,
        cast(is_vegetarian as boolean)  as is_vegetarian,
        cast(is_active as boolean)      as is_active
    from source
)

select * from renamed
