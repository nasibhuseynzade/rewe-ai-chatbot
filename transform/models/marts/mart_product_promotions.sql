{#
  Promotions per product, region and calendar year: how often a product went on
  sale, for how many days, and how deep the discounts were. For "which product
  was on sale most often", "deepest discounts" and "which products were never on
  sale".

  - promotions: number of sale episodes that started in the year. Sale intervals
    count as one episode unless an observed non-sale interval or more than a week
    lies between them (a sale price that changes during the promotion is still one
    promotion, and rows that only fill data gaps don't split a promotion).
  - days_listed / days_on_sale: calendar days inside the year covered by the
    product's price intervals, and the part of them on sale.
  - discounts are in percent (31.5 = 31.5% off the regular price).
#}
with intervals as (
    select
        gtin, region, interval_no, valid_from, valid_to, on_sale, observed_snapshots,
        100 * discount_pct as discount_pct
    from {{ ref('fct_price_interval') }}
),

observed as (
    -- episodes are decided on observed rows only
    select
        *,
        lag(on_sale)  over w as prev_on_sale,
        lag(valid_to) over w as prev_valid_to
    from intervals
    where observed_snapshots > 0
    window w as (partition by gtin, region order by interval_no)
),

episodes as (
    select
        *,
        sum(case when on_sale and (not coalesce(prev_on_sale, false)
                                   or date_diff('day', prev_valid_to, valid_from) > 7)
                 then 1 else 0 end)
            over (partition by gtin, region order by interval_no) as episode_no
    from observed
),

sale_episodes as (
    select
        gtin,
        region,
        episode_no,
        min(valid_from)     as started_on,
        max(discount_pct)   as max_discount_pct,
        avg(discount_pct)   as avg_discount_pct
    from episodes
    where on_sale
    group by all
),

years as (
    select unnest(range(year(min(valid_from)), year(max(valid_to)) + 1)) as year
    from intervals
),

listed as (
    -- days of each interval that fall into each calendar year
    select
        i.gtin,
        i.region,
        y.year,
        sum(date_diff('day', greatest(i.valid_from, make_date(y.year, 1, 1)),
                             least(i.valid_to, make_date(y.year, 12, 31))) + 1)          as days_listed,
        sum(case when i.on_sale
                 then date_diff('day', greatest(i.valid_from, make_date(y.year, 1, 1)),
                                       least(i.valid_to, make_date(y.year, 12, 31))) + 1
                 else 0 end)                                                           as days_on_sale
    from intervals as i
    join years as y
      on i.valid_from <= make_date(y.year, 12, 31)
     and i.valid_to   >= make_date(y.year, 1, 1)
    group by all
),

promo as (
    select
        gtin,
        region,
        year(started_on)                  as year,
        count(*)                          as promotions,
        max(max_discount_pct)             as max_discount_pct,
        avg(avg_discount_pct)             as avg_discount_pct
    from sale_episodes
    group by all
)

select
    l.gtin,
    l.region,
    l.year,
    d.name,
    d.brand,
    d.primary_category                                           as category,
    l.days_listed,
    l.days_on_sale,
    round(100.0 * l.days_on_sale / nullif(l.days_listed, 0), 1)  as share_on_sale_pct,
    coalesce(p.promotions, 0)                                    as promotions,
    round(p.max_discount_pct, 1)                                 as max_discount_pct,
    round(p.avg_discount_pct, 1)                                 as avg_discount_pct
from listed as l
left join promo as p using (gtin, region, year)
join {{ ref('dim_product') }} as d on d.gtin = l.gtin
