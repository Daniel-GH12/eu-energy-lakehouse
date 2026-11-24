with spot_hourly as (
    select
        date_trunc('hour', timestamp_utc) as hour_utc,
        avg(price_eur_mwh) as spot_avg_eur_mwh,
        min(price_eur_mwh) as spot_min_eur_mwh,
        max(price_eur_mwh) as spot_max_eur_mwh,
        count(*) as spot_intervals_count
    from {{ ref('stg_ree_prices') }}
    where market_type = 'spot'
    group by 1
),

pvpc_hourly as (
    select
        date_trunc('hour', timestamp_utc) as hour_utc,
        price_eur_mwh as pvpc_eur_mwh
    from {{ ref('stg_ree_prices') }}
    where market_type = 'pvpc'
)

select
    p.hour_utc,
    p.pvpc_eur_mwh,
    s.spot_avg_eur_mwh,
    s.spot_min_eur_mwh,
    s.spot_max_eur_mwh,
    s.spot_intervals_count,
    p.pvpc_eur_mwh - s.spot_avg_eur_mwh as pvpc_spot_spread_eur_mwh,
    s.spot_max_eur_mwh - s.spot_min_eur_mwh as spot_intraday_range_eur_mwh
from pvpc_hourly as p
inner join spot_hourly as s
    on p.hour_utc = s.hour_utc
order by p.hour_utc
