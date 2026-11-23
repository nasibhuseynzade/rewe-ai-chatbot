{#
  Grain: one row per (snapshot_date, region, gtin).

  The source lists a product once per category it appears in (~14% of rows are
  such repeats). Those repeats collapse into one row; the categories are kept
  as a list.

  Price conflicts: very rarely (864 of ~17M product-days in the full data) the
  repeats of one product on one day show different prices, probably because
  the price changed while the site was being scraped. The lower price is used
  and the row is flagged; tests/assert_price_conflicts_rare.sql watches the share.
#}
select
    snapshot_date,
    region,
    gtin,
    min(ean_raw)                                     as ean_raw,
    max(name)                                        as name,
    max(brand)                                       as brand,
    min(price)                                       as price,
    count(distinct price) > 1                        as has_price_conflict,
    bool_or(on_sale)                                 as on_sale,
    max(grammage)                                    as grammage,
    -- grammage without the "(1 kg = … €)" part: changes only when the pack changes,
    -- not when the price changes. Used to detect shrinkflation.
    nullif(trim(regexp_replace(max(grammage), '\(.*\)', '')), '') as pack_size,
    list(distinct category order by category)        as categories,
    count(*)                                         as source_rows
from {{ ref('stg_prices') }}
group by snapshot_date, region, gtin
