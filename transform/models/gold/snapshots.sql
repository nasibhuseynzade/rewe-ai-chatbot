{#
  Which (date, region) snapshots exist. snapshot_seq numbers them per region,
  so "consecutive" means consecutive *files*, and a missing source file never
  looks like a product disappearing.

  is_partial: the scrape was incomplete that day (fewer products than
  `partial_snapshot_threshold` x the median of the surrounding snapshots).
  Exclude such days from day-level counts; prices from them are still valid.
#}
with per_day as (
    select
        snapshot_date,
        region,
        count(*)                                  as products,
        sum(source_rows)                          as source_rows,
        count(*) filter (where on_sale)           as products_on_sale
    from {{ ref('silver_product_daily') }}
    group by snapshot_date, region
)

select
    snapshot_date,
    region,
    row_number() over w                                            as snapshot_seq,
    products,
    source_rows,
    products_on_sale,
    median(products) over (w rows between 7 preceding and 7 following) as typical_products,
    products < {{ var('partial_snapshot_threshold') }}
               * median(products) over (w rows between 7 preceding and 7 following)
                                                                   as is_partial
from per_day
window w as (partition by region order by snapshot_date)
