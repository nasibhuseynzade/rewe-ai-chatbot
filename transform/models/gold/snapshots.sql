{#
  Which (date, region) snapshots exist. snapshot_seq numbers them per region,
  so "consecutive" means consecutive *files*, and a missing source file never
  looks like a product disappearing.
#}
select
    snapshot_date,
    region,
    row_number() over (partition by region order by snapshot_date)  as snapshot_seq,
    count(*)                                                         as products,
    sum(source_rows)                                                 as source_rows,
    count(*) filter (where on_sale)                                  as products_on_sale
from {{ ref('silver_product_daily') }}
group by snapshot_date, region
