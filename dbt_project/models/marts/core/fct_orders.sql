with orders as (
    select * from {{ ref('stg_orders') }}
),

order_items_agg as (
    select
        order_id,
        count(distinct menu_item_id)    as distinct_items,
        sum(quantity)                   as total_quantity,
        sum(line_total)                 as items_total
    from {{ ref('stg_order_items') }}
    group by 1
),

payments as (
    select
        order_id,
        payment_status,
        payment_method,
        amount                          as payment_amount
    from {{ ref('stg_payments') }}
),

assignments_agg as (
    select
        order_id,
        count(*)                        as boxes_used,
        max(subsequence::integer)       as max_subsequence
    from {{ ref('stg_box_assignments') }}
    group by 1
),

feedback as (
    select
        order_id,
        rating                          as overall_rating,
        food_rating,
        delivery_rating,
        box_condition_rating
    from {{ ref('stg_feedback') }}
)

select
    o.order_id,
    o.customer_id,
    o.address_id,
    cast(o.order_date as date)          as order_date,
    o.order_date                        as order_timestamp,
    hour(o.order_date)                  as order_hour,
    o.order_status,
    o.order_amount,

    coalesce(oi.distinct_items, 0)      as distinct_items,
    coalesce(oi.total_quantity, 0)      as total_quantity,

    coalesce(a.boxes_used, 0)           as boxes_used,
    coalesce(a.max_subsequence, 0)      as ctt_max_subsequence,
    case when coalesce(a.boxes_used, 1) > 1
        then true else false
    end                                 as is_multi_box_order,

    p.payment_status,
    p.payment_method,
    p.payment_amount,

    f.overall_rating,
    f.food_rating,
    f.delivery_rating,
    f.box_condition_rating,
    case when f.overall_rating is not null then true else false end as has_feedback

from orders o
left join order_items_agg  oi on o.order_id = oi.order_id
left join assignments_agg   a on o.order_id  = a.order_id
left join payments          p on o.order_id  = p.order_id
left join feedback          f on o.order_id  = f.order_id
