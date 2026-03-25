-- Route efficiency: driver + zone performance
-- How efficient are our delivery routes and pickup runs?

with deliveries as (
    select * from {{ ref('fct_deliveries') }}
),

pickups as (
    select
        driver_id,
        cast(scheduled_date as date)    as pickup_date,
        address_id,
        upper(status)                   as pickup_status
    from {{ source('raw', 'pickup_schedules') }}
    where driver_id is not null
),

addresses as (
    select address_id, delivery_zone from {{ ref('dim_addresses') }}
),

-- Deliveries per driver per day per zone
driver_daily as (
    select
        d.driver_id,
        d.delivery_date,
        d.delivery_zone,
        count(*)                                                as deliveries_count,
        sum(case when d.delivery_status = 'DELIVERED' then 1 else 0 end) as successful,
        sum(case when d.delivery_status = 'FAILED'    then 1 else 0 end) as failed,
        avg(d.delivery_duration_min)                            as avg_duration_min,
        round(
            sum(case when d.met_zone_sla then 1 else 0 end)::float
            / nullif(count(*), 0) * 100
        , 1)                                                    as sla_pct,
        sum(case when d.is_on_time then 1 else 0 end)           as on_time_count
    from deliveries d
    group by 1, 2, 3
),

-- Pickups per driver per day
driver_pickups as (
    select
        p.driver_id,
        p.pickup_date,
        addr.delivery_zone,
        count(*)                                                as pickups_attempted,
        sum(case when p.pickup_status = 'COMPLETED' then 1 else 0 end) as pickups_completed
    from pickups p
    left join addresses addr on p.address_id = addr.address_id
    group by 1, 2, 3
)

select
    dd.driver_id,
    dd.delivery_date,
    dd.delivery_zone,
    dd.deliveries_count,
    dd.successful,
    dd.failed,
    dd.avg_duration_min,
    dd.sla_pct,
    dd.on_time_count,

    coalesce(dp.pickups_attempted, 0)   as pickups_attempted,
    coalesce(dp.pickups_completed, 0)   as pickups_completed,

    -- Combined route score: deliveries + pickups in same zone = efficiency
    dd.deliveries_count + coalesce(dp.pickups_completed, 0) as total_stops,

    -- Pickup success rate
    round(
        coalesce(dp.pickups_completed, 0)::float
        / nullif(dp.pickups_attempted, 0) * 100
    , 1)                                as pickup_success_pct,

    strftime(dd.delivery_date, '%Y-%m') as year_month

from driver_daily dd
left join driver_pickups dp
    on dd.driver_id      = dp.driver_id
    and dd.delivery_date = dp.pickup_date
    and dd.delivery_zone = dp.delivery_zone
order by dd.delivery_date, dd.driver_id
