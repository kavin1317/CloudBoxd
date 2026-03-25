with source as (
    select * from {{ source('raw', 'feedback') }}
),

renamed as (
    select
        feedback_id,
        order_id,
        customer_id,
        cast(rating as integer)                 as rating,
        cast(food_rating as integer)            as food_rating,
        cast(delivery_rating as integer)        as delivery_rating,
        cast(box_condition_rating as integer)   as box_condition_rating,
        nullif(comments, '')                    as comments,
        cast(created_at as timestamp)           as created_at
    from source
)

select * from renamed
