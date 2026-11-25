{#
  One price per product, region and month: the price valid on the month's
  reference date, i.e. its last complete (non-partial) snapshot. Months without
  any snapshot (May-July 2024) use their last day; fct_price_interval carries
  prices through those data gaps. The building block for the price index and
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
),

calendar as (
    select region, cast(unnest(generate_series(min(month), max(month), interval 1 month)) as date) as month
    from month_end
    group by region
),

reference as (
    select
        c.region,
        c.month,
        coalesce(m.snapshot_date, cast(last_day(c.month) as date)) as snapshot_date
    from calendar as c
    left join month_end as m using (region, month)
)

select
    f.gtin,
    f.region,
    r.month,
    r.snapshot_date,
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
from reference as r
join {{ ref('fct_price_interval') }} as f
  on f.region = r.region
 and r.snapshot_date between f.valid_from and f.valid_to
