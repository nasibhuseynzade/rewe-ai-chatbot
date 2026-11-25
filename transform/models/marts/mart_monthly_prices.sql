{#
  One price per product, region and month: the price valid on the month's last
  complete (non-partial) snapshot. The building block for the price index and
  for "how did the price develop" questions.

  regular_unit_price: regular price per kg / l / m when the pack size is known
  and verified, so pack size changes can be compared like for like.
#}
with month_end as (
    select
        region,
        cast(date_trunc('month', snapshot_date) as date)  as month,
        max(snapshot_date)                                 as snapshot_date
    from {{ ref('snapshots') }}
    where not is_partial
    group by all
)

select
    f.gtin,
    f.region,
    m.month,
    m.snapshot_date,
    f.price,
    f.on_sale,
    f.regular_price,
    f.pack_size,
    f.unit_price_status,
    f.measure_amount,
    f.measure_unit,
    case
        when f.unit_price_status in ('match', 'unit_scale_fixed', 'multipack_total', 'from_name')
             and f.measure_amount > 0 and f.regular_price > 0
        then round(f.regular_price / f.measure_amount, 4)
    end                                                    as regular_unit_price
from month_end as m
join {{ ref('fct_price_interval') }} as f
  on f.region = m.region
 and m.snapshot_date between f.valid_from and f.valid_to
