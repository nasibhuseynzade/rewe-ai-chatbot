{#
  One row per valid source row, typed and cleaned. Category repeats are kept.

  - Rows without a usable barcode or price are dropped here (in the full data:
    440 rows with ean = 'NA' and price = 'NA'). tests/assert_few_rejected_rows.sql
    keeps an eye on how many rows this filter removes.
  - gtin: 11/12-digit codes are GTIN-13s whose leading zeros were lost upstream
    (they pass the check digit once padded), so they are left-padded to 13.
    8-digit codes stay EAN-8.
#}
with source as (
    select * from read_parquet('{{ var("bronze_glob") }}', union_by_name = true)
),

typed as (
    select
        snapshot_date,
        region,
        trim(ean)                                                as ean_raw,
        trim(name)                                               as name,
        nullif(nullif(trim(brand), ''), 'NA')                    as brand,
        try_cast(price as decimal(10, 2))                        as price,
        lower(trim(sale)) = 'true'                               as on_sale,
        trim(category)                                           as category,
        nullif(nullif(trim(grammage), ''), 'NA')                 as grammage,
        source_file
    from source
)

select
    snapshot_date,
    region,
    ean_raw,
    case when length(ean_raw) in (11, 12, 13)
         then lpad(ean_raw, 13, '0')
         else ean_raw end                                        as gtin,
    name,
    brand,
    price,
    on_sale,
    category,
    grammage,
    source_file
from typed
where regexp_matches(ean_raw, '^[0-9]{8,14}$')
  and price is not null
