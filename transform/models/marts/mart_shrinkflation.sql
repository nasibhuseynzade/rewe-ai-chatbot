{#
  Shrinkflation events: the pack got smaller while the regular price stayed the
  same or went up. Compared between consecutive *non-sale* intervals, so
  promotions don't create false events.

  Guards against data errors (the source has typos like 1000kg for 1000g):
  - both packs must be verified against the printed unit price or the product
    name (unit_price_status not 'unverified' or 'conflict'),
  - the pack size text must actually change,
  - the content drop must lie between shrinkflation_min_content_drop and
    shrinkflation_max_content_drop.
#}
with regular as (
    select
        gtin, region, interval_no, valid_from, regular_price,
        pack_size, measure_amount, measure_unit
    from {{ ref('fct_price_interval') }}
    where not on_sale
      and unit_price_status in ('match', 'unit_scale_fixed', 'multipack_total', 'from_name')
      and measure_amount > 0
),

pairs as (
    select
        *,
        lag(regular_price)  over w as prev_price,
        lag(pack_size)      over w as prev_pack_size,
        lag(measure_amount) over w as prev_measure_amount,
        lag(measure_unit)   over w as prev_measure_unit
    from regular
    window w as (partition by gtin, region order by interval_no)
)

select
    p.gtin,
    p.region,
    d.name,
    d.brand,
    d.primary_category                                                  as category,
    p.valid_from                                                        as changed_on,
    p.prev_pack_size                                                    as old_pack_size,
    p.pack_size                                                         as new_pack_size,
    p.prev_price                                                        as old_price,
    p.regular_price                                                     as new_price,
    round(100 * (1 - p.measure_amount / p.prev_measure_amount), 2)      as content_drop_pct,
    round(100 * ((p.regular_price / p.measure_amount)
               / (p.prev_price / p.prev_measure_amount) - 1), 2)        as unit_price_increase_pct,
    p.measure_unit
from pairs as p
join {{ ref('dim_product') }} as d using (gtin)
where p.prev_measure_amount is not null
  and p.measure_unit = p.prev_measure_unit
  and p.pack_size <> p.prev_pack_size
  and p.measure_amount <= (1 - {{ var('shrinkflation_min_content_drop') }}) * p.prev_measure_amount
  and p.measure_amount >= (1 - {{ var('shrinkflation_max_content_drop') }}) * p.prev_measure_amount
  and p.regular_price >= p.prev_price
