-- Date dimension: spine for all time-series analysis

with date_spine as (
    select
        range::date as date_day
    from range(date '2025-06-01', date '2026-02-01', interval '1' day)
)

select
    date_day,
    year(date_day)                                          as year,
    month(date_day)                                         as month_number,
    strftime(date_day, '%B')                                as month_name,
    quarter(date_day)                                       as quarter_number,
    'Q' || quarter(date_day)::varchar                       as quarter_name,
    dayofmonth(date_day)                                    as day_of_month,
    dayofweek(date_day)                                     as day_of_week,
    strftime(date_day, '%A')                                as day_name,
    case when dayofweek(date_day) in (0, 6) then true else false end as is_weekend,
    case when dayofweek(date_day) in (0, 6) then 'WEEKEND' else 'WEEKDAY' end as day_type,
    weekofyear(date_day)                                    as week_of_year,
    yearweek(date_day)                                      as year_week,
    date_trunc('week', date_day)                            as week_start_date,
    date_trunc('month', date_day)                           as month_start_date,
    strftime(date_day, '%Y-%m')                             as year_month
from date_spine
