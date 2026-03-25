with addresses as (
    select * from {{ source('raw', 'addresses') }}
),

delivery_stats as (
    select
        d.address_id,
        count(*)                                                as total_deliveries,
        avg(p.delivery_duration_min)                            as avg_delivery_minutes,
        round(
            sum(case when p.met_zone_sla then 1 else 0 end)::float
            / nullif(count(*), 0) * 100
        , 1)                                                    as zone_sla_pct
    from {{ ref('stg_deliveries') }} d
    left join {{ ref('int_delivery_performance') }} p on d.delivery_id = p.delivery_id
    group by 1
)

select
    a.address_id,
    a.street,
    a.city,
    a.state,
    a.zipcode,
    a.delivery_zone,
    coalesce(ds.total_deliveries, 0)    as total_deliveries,
    coalesce(ds.avg_delivery_minutes, 0) as avg_delivery_minutes,
    coalesce(ds.zone_sla_pct, 0)        as zone_sla_pct
from addresses a
left join delivery_stats ds on a.address_id = ds.address_id
