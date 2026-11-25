{#
  Monthly price index per category and region (first month = 100), plus an
  'All categories' line.

  Method: chained Jevons index, as statistics offices use for elementary price
  indices. For every pair of consecutive months, take the products present in
  both, compute each one's price ratio, and average the ratios geometrically.
  Chaining these monthly links copes with products entering and leaving the
  assortment.

  - Regular prices (not sale prices), so promotions don't move the index.
  - Ratios use the unit price when the pack size is known in both months, so
    shrinkflation counts as a price increase.
  - Ratios beyond index_max_monthly_ratio are dropped as data errors.
  - Categories averaging fewer than index_min_products products per monthly
    comparison are left out: too few products for a stable index.
#}
with prices as (
    select
        p.gtin,
        p.region,
        p.month,
        p.regular_price,
        p.regular_unit_price,
        p.measure_unit,
        d.primary_category as category
    from {{ ref('mart_monthly_prices') }} as p
    join {{ ref('dim_product') }} as d using (gtin)
    where p.regular_price > 0
),

months as (
    select
        region,
        month,
        row_number() over (partition by region order by month) as month_seq
    from (select distinct region, month from prices)
),

with_seq as (
    select p.*, m.month_seq
    from prices as p
    join months as m using (region, month)
),

ratios as (
    select
        cur.region,
        cur.category,
        cur.month,
        cur.month_seq,
        case
            when cur.regular_unit_price > 0 and prev.regular_unit_price > 0
                 and cur.measure_unit = prev.measure_unit
            then cur.regular_unit_price / prev.regular_unit_price
            else cur.regular_price / prev.regular_price
        end as ratio
    from with_seq as cur
    join with_seq as prev
      on prev.gtin = cur.gtin
     and prev.region = cur.region
     and prev.month_seq = cur.month_seq - 1
),

clean as (
    select *
    from ratios
    where ratio between 1.0 / {{ var('index_max_monthly_ratio') }} and {{ var('index_max_monthly_ratio') }}
),

links as (
    select region, category, month, month_seq,
           exp(avg(ln(ratio))) as link, count(*) as products_compared
    from clean
    group by region, category, month, month_seq
    union all
    select region, 'All categories', month, month_seq,
           exp(avg(ln(ratio))), count(*)
    from clean
    group by region, month, month_seq
),

kept as (
    select region, category
    from links
    group by all
    having avg(products_compared) >= {{ var('index_min_products') }}
),

kept_links as (
    select l.*
    from links as l
    join kept using (region, category)
),

base as (
    -- the first month of each region is the base (100) for every category
    select distinct l.region, l.category, m.month, m.month_seq
    from kept_links as l
    join months as m on m.region = l.region and m.month_seq = 1
)

select
    region,
    category,
    month,
    month_seq,
    round(100 * exp(sum(ln(link)) over (
        partition by region, category order by month_seq
        rows between unbounded preceding and current row)), 2)          as price_index,
    round(100 * (link - 1), 2)                                           as pct_change_vs_prev_month,
    products_compared
from kept_links
union all
select region, category, month, month_seq, 100.0, null, null
from base
