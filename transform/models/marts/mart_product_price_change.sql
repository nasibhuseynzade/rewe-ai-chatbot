{#
  Per product and region: regular price in the first and in the last month it
  was seen, and the change. For "biggest price increases" and "how much more
  expensive did X get".

  same_pack_size: the pack size text is identical in both months. Rankings use
  only these rows, so a changed pack (or a typo in the pack size) can't fake a
  price jump; pack changes are covered by mart_shrinkflation.

  unit_price_change_pct compares price per kg / l / m. It is NULL when a pack
  size isn't verified, or when the content differs by more than a factor of 2
  (almost always a pack size typo in the source).
#}
with ranked as (
    select
        *,
        row_number() over (partition by gtin, region order by month)      as rn_first,
        row_number() over (partition by gtin, region order by month desc) as rn_last,
        count(*)     over (partition by gtin, region)                     as months_observed
    from {{ ref('mart_monthly_prices') }}
    where regular_price > 0
)

select
    f.gtin,
    f.region,
    d.name,
    d.brand,
    d.primary_category                                                   as category,
    f.month                                                              as first_month,
    l.month                                                              as last_month,
    f.months_observed,
    f.pack_size                                                          as first_pack_size,
    l.pack_size                                                          as last_pack_size,
    coalesce(f.pack_size = l.pack_size, false)                           as same_pack_size,
    f.regular_price                                                      as first_price,
    l.regular_price                                                      as last_price,
    round(100 * (l.regular_price / f.regular_price - 1), 2)              as price_change_pct,
    f.regular_unit_price                                                 as first_unit_price,
    l.regular_unit_price                                                 as last_unit_price,
    case when f.regular_unit_price > 0 and l.regular_unit_price > 0
              and f.measure_unit = l.measure_unit
              and l.measure_amount between f.measure_amount / 2 and f.measure_amount * 2
         then round(100 * (l.regular_unit_price / f.regular_unit_price - 1), 2)
    end                                                                  as unit_price_change_pct,
    l.measure_unit
from ranked as f
join ranked as l
  on l.gtin = f.gtin and l.region = f.region and l.rn_last = 1
join {{ ref('dim_product') }} as d on d.gtin = f.gtin
where f.rn_first = 1
