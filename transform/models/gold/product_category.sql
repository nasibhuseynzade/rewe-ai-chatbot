{#
  Which categories a product was listed in, per region, and when.
  Many-to-many: a product can sit in its department *and* in thematic lists
  (Monats-Highlights, Regional, ...). Never sum products across categories
  without deduplicating.
#}
select
    d.gtin,
    d.region,
    c.category,
    c.category in {{ sql_in_list(var('thematic_categories')) }}   as is_thematic,
    min(d.snapshot_date)                                         as first_seen,
    max(d.snapshot_date)                                         as last_seen,
    count(*)                                                     as snapshots_seen
from {{ ref('silver_product_daily') }} as d
cross join unnest(d.categories) as c(category)
group by d.gtin, d.region, c.category
