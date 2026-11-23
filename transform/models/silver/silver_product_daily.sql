{#
  Grain: one row per (snapshot_date, region, gtin).

  The source lists a product once per category it appears in (~17% of rows are
  such repeats). Price never differs between those repeats, so they collapse
  into one row; the categories are kept as a list.
#}
select
    snapshot_date,
    region,
    gtin,
    min(ean_raw)                                     as ean_raw,
    max(name)                                        as name,
    max(brand)                                       as brand,
    max(price)                                       as price,
    count(distinct price)                            as distinct_prices,   -- tested: must be 1
    bool_or(on_sale)                                 as on_sale,
    max(grammage)                                    as grammage,
    -- grammage without the "(1 kg = … €)" part: changes only when the pack changes,
    -- not when the price changes. Used to detect shrinkflation.
    nullif(trim(regexp_replace(max(grammage), '\(.*\)', '')), '') as pack_size,
    list(distinct category order by category)        as categories,
    count(*)                                         as source_rows
from {{ ref('stg_prices') }}
group by snapshot_date, region, gtin
