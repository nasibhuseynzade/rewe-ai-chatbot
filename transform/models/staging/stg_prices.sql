{#
  One row per source row, typed and cleaned. No rows are dropped or merged here.

  - gtin: 11/12-digit codes are GTIN-13s whose leading zeros were lost upstream
    (they pass the check digit once padded), so they are left-padded to 13.
    8-digit codes stay EAN-8.
  - price: cast (not try_cast) on purpose: a bad value should fail loudly.
#}
with source as (
    select * from read_parquet('{{ var("bronze_glob") }}', union_by_name = true)
)

select
    snapshot_date,
    region,
    trim(ean)                                                    as ean_raw,
    case when length(trim(ean)) in (11, 12, 13)
         then lpad(trim(ean), 13, '0')
         else trim(ean) end                                      as gtin,
    trim(name)                                                   as name,
    nullif(nullif(trim(brand), ''), 'NA')                        as brand,
    cast(price as decimal(10, 2))                                as price,
    lower(trim(sale)) = 'true'                                   as on_sale,
    trim(category)                                               as category,
    nullif(nullif(trim(grammage), ''), 'NA')                     as grammage,
    source_file
from source
