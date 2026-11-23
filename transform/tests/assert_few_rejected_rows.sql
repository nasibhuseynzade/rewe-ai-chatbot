{{ config(severity = 'warn') }}
-- stg_prices drops source rows without a usable barcode or price.
-- That should stay a tiny fraction (0.1%); more means the source format changed.
with b as (
    select ean, price
    from read_parquet('{{ var("bronze_glob") }}', union_by_name = true)
),
s as (
    select
        count(*) as source_rows,
        count(*) filter (
            where not coalesce(regexp_matches(trim(ean), '^[0-9]{8,14}$'), false)
               or try_cast(price as decimal(10, 2)) is null
        ) as rejected_rows
    from b
)
select source_rows, rejected_rows, round(rejected_rows / source_rows, 6) as share
from s
where rejected_rows > 0.001 * source_rows
