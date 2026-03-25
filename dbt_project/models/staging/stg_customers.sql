with source as (
    select * from {{ source('raw', 'customers') }}
),

renamed as (
    select
        customer_id,
        customer_name,
        lower(email)                    as email,
        phone,
        plan_id,
        cast(signup_date as date)       as signup_date,
        cast(is_active as boolean)      as is_active,
        cast(created_at as timestamp)   as created_at,
        cast(updated_at as timestamp)   as updated_at
    from source
)

select * from renamed
