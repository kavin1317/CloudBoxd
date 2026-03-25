-- Per-delivery performance metrics with zone context

with deliveries as (
    select * from {{ ref('stg_deliveries') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
),

addresses as (
    select
        address_id,
        delivery_zone,
        zipcode,
        city
    from {{ source('raw', 'addresses') }}
),

joined as (
    select
        d.delivery_id,
        d.order_id,
        d.driver_id,
        d.delivery_status,
        d.scheduled_time,
        cast(d.actual_departure as timestamp)   as actual_departure,
        cast(d.actual_delivery  as timestamp)   as actual_delivery,
        d.delivery_duration_min,
        d.failure_reason,

        a.delivery_zone,
        a.zipcode,

        o.order_amount,
        o.customer_id,

        -- On-time flag: delivered within scheduled_time + 15 min buffer
        case
            when d.delivery_status = 'DELIVERED'
             and cast(d.actual_delivery as timestamp) <= d.scheduled_time + interval '15' minute
            then true
            else false
        end as is_on_time,

        -- Late by how many minutes
        case
            when d.delivery_status = 'DELIVERED'
            then datediff(
                'minute',
                d.scheduled_time,
                cast(d.actual_delivery as timestamp)
            )
        end as minutes_vs_schedule,

        -- Zone SLA benchmark (from architecture doc)
        case a.delivery_zone
            when 'ZONE-A' then 30
            when 'ZONE-B' then 43
            when 'ZONE-C' then 55
            when 'ZONE-D' then 67
        end as zone_sla_minutes,

        -- Met zone SLA?
        case
            when d.delivery_status = 'DELIVERED'
             and d.delivery_duration_min is not null
             and d.delivery_duration_min <= (
                case a.delivery_zone
                    when 'ZONE-A' then 30
                    when 'ZONE-B' then 43
                    when 'ZONE-C' then 55
                    when 'ZONE-D' then 67
                end
             )
            then true
            else false
        end as met_zone_sla

    from deliveries d
    left join orders  o on d.order_id   = o.order_id
    left join addresses a on d.address_id = a.address_id
)

select * from joined
