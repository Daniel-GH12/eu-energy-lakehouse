select
    timestamp_utc,
    market_type,
    price_eur_mwh,
    cast(date as date) as ingestion_date
from read_parquet('data/silver/ree_prices/date=*/prices.parquet', hive_partitioning=true)
