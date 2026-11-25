{#
  How common and how deep promotions were, per category, region and month.

  share_on_sale: share of product-days flagged on sale (partial snapshots left out).
  avg_discount_pct: average discount of sale intervals starting that month.
#}
with daily as (
    select
        d.region,
        cast(date_trunc('month', d.snapshot_date) as date) as month,
        p.primary_category                                 as category,
        d.on_sale
    from {{ ref('silver_product_daily') }} as d
    join {{ ref('snapshots') }} as s using (snapshot_date, region)
    join {{ ref('dim_product') }} as p using (gtin)
    where not s.is_partial
),

share as (
    select region, month, category,
           count(*) as product_days,
           count(*) filter (where on_sale) as sale_days
    from daily
    group by all
    union all
    select region, month, 'All categories', count(*), count(*) filter (where on_sale)
    from daily
    group by region, month
),

discounts as (
    select
        f.region,
        cast(date_trunc('month', f.valid_from) as date) as month,
        p.primary_category                              as category,
        f.discount_pct
    from {{ ref('fct_price_interval') }} as f
    join {{ ref('dim_product') }} as p using (gtin)
    where f.on_sale and f.discount_pct > 0
),

depth as (
    select region, month, category, avg(discount_pct) as avg_discount, count(*) as sale_intervals
    from discounts group by all
    union all
    select region, month, 'All categories', avg(discount_pct), count(*)
    from discounts group by region, month
)

select
    s.region,
    s.month,
    s.category,
    s.product_days,
    s.sale_days,
    round(100.0 * s.sale_days / s.product_days, 2)  as share_on_sale_pct,
    round(100 * d.avg_discount, 2)                   as avg_discount_pct,
    coalesce(d.sale_intervals, 0)                    as sale_intervals_started
from share as s
left join depth as d using (region, month, category)
