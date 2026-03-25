with drivers as (
    select * from {{ source('raw', 'drivers') }}
),

delivery_stats as (
    select
        d.driver_id,
        count(*)                                                as total_deliveries,
        sum(case when d.delivery_status = 'DELIVERED' then 1 else 0 end) as successful_deliveries,
        sum(case when d.delivery_status = 'FAILED'    then 1 else 0 end) as failed_deliveries,
        avg(d.delivery_duration_min)                            as avg_delivery_minutes,
        round(
            sum(case when p.met_zone_sla then 1 else 0 end)::float
            / nullif(count(*), 0) * 100
        , 1)                                                    as sla_compliance_pct
    from {{ ref('stg_deliveries') }} d
    left join {{ ref('int_delivery_performance') }} p on d.delivery_id = p.delivery_id
    group by 1
),

pickup_stats as (
    select
        driver_id,
        count(*)                                                as total_pickups,
        sum(case when status = 'COMPLETED' then 1 else 0 end)  as completed_pickups
    from {{ source('raw', 'pickup_schedules') }}
    group by 1
)

select
    dr.driver_id,
    dr.driver_name,
    dr.phone,
    dr.vehicle_number,
    dr.is_active,

    coalesce(ds.total_deliveries, 0)        as total_deliveries,
    coalesce(ds.successful_deliveries, 0)   as successful_deliveries,
    coalesce(ds.failed_deliveries, 0)       as failed_deliveries,
    coalesce(ds.avg_delivery_minutes, 0)    as avg_delivery_minutes,
    coalesce(ds.sla_compliance_pct, 0)      as sla_compliance_pct,

    coalesce(ps.total_pickups, 0)           as total_pickups,
    coalesce(ps.completed_pickups, 0)       as completed_pickups,

    round(
        coalesce(ds.successful_deliveries, 0)::float
        / nullif(ds.total_deliveries, 0) * 100
    , 1) as delivery_success_rate

from drivers dr
left join delivery_stats ds on dr.driver_id = ds.driver_id
left join pickup_stats   ps on dr.driver_id = ps.driver_id
