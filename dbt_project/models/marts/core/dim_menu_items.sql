with menu as (
    select * from {{ ref('stg_menu_items') }}
),

order_stats as (
    select
        oi.menu_item_id,
        count(distinct oi.order_id)     as times_ordered,
        sum(oi.quantity)                as total_units_sold,
        sum(oi.line_total)              as total_revenue,
        avg(oi.item_price)              as avg_selling_price
    from {{ ref('stg_order_items') }} oi
    group by 1
),

feedback_stats as (
    select
        oi.menu_item_id,
        avg(f.food_rating)              as avg_food_rating,
        count(f.feedback_id)            as feedback_count
    from {{ ref('stg_order_items') }} oi
    left join {{ ref('stg_feedback') }} f on oi.order_id = f.order_id
    group by 1
)

select
    m.menu_item_id,
    m.item_name,
    m.description,
    m.cuisine,
    m.category,
    m.price                             as current_price,
    m.is_vegetarian,
    m.is_active,

    coalesce(o.times_ordered, 0)        as times_ordered,
    coalesce(o.total_units_sold, 0)     as total_units_sold,
    coalesce(o.total_revenue, 0)        as total_revenue,
    coalesce(o.avg_selling_price, m.price) as avg_selling_price,

    coalesce(f.avg_food_rating, 0)      as avg_food_rating,
    coalesce(f.feedback_count, 0)       as feedback_count,

    -- Popularity rank within category
    rank() over (
        partition by m.category
        order by coalesce(o.times_ordered, 0) desc
    ) as popularity_rank_in_category

from menu m
left join order_stats   o on m.menu_item_id = o.menu_item_id
left join feedback_stats f on m.menu_item_id = f.menu_item_id
