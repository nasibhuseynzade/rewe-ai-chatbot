{#
  Price history as intervals: one row per period in which a product had the
  same price, sale flag and pack size in a region.

  A new interval starts when price, on_sale or pack size changes, or when the
  product was missing for more than `max_gap_snapshots` consecutive snapshots.
  Shorter gaps are bridged (the source scrapes page by page and sometimes
  misses a product for a day).

  valid_from / valid_to are the first and last *observed* snapshot dates
  (inclusive). To get the price on date X:  X between valid_from and valid_to.

  regular_price: the price outside promotions. For an on_sale interval it is
  the previous non-sale price (or the next one if the product started on sale).

  Data gaps: when a product is listed on both sides of days without data (no
  snapshot at all, like 13 April - 23 August 2024, or the product missed at most
  max_gap_snapshots scrapes) and its price changed in between, the dates between
  the two intervals are filled with the previous regular price, not on sale.
  A non-sale interval is extended; after a sale interval a non-sale interval is
  added. Products that were really absent (snapshots exist, product not listed
  for longer) are not filled. filled_days counts the days added to a row.
#}
with daily as (
    select
        d.gtin,
        d.region,
        d.snapshot_date,
        s.snapshot_seq,
        d.price,
        d.on_sale,
        coalesce(d.pack_size, '')       as pack_key,
        d.pack_size,
        d.grammage,
        d.name
    from {{ ref('silver_product_daily') }} as d
    join {{ ref('snapshots') }} as s using (snapshot_date, region)
),

flagged as (
    select
        *,
        case
            when lag(snapshot_seq) over w is null then 1
            when price        <> lag(price) over w then 1
            when on_sale      <> lag(on_sale) over w then 1
            when pack_key     <> lag(pack_key) over w then 1
            when snapshot_seq - lag(snapshot_seq) over w > {{ var('max_gap_snapshots') }} + 1 then 1
            else 0
        end as starts_interval
    from daily
    window w as (partition by gtin, region order by snapshot_seq)
),

numbered as (
    select
        *,
        cast(sum(starts_interval) over (
            partition by gtin, region order by snapshot_seq
            rows between unbounded preceding and current row
        ) as integer) as interval_no
    from flagged
),

intervals as (
    select
        gtin,
        region,
        interval_no,
        any_value(price)                          as price,
        any_value(on_sale)                        as on_sale,
        any_value(pack_size)                      as pack_size,
        arg_max(grammage, snapshot_date)          as grammage,
        arg_max(name, snapshot_date)              as name,
        min(snapshot_date)                        as valid_from,
        max(snapshot_date)                        as valid_to,
        count(*)                                  as observed_snapshots,
        max(snapshot_seq) - min(snapshot_seq) + 1 as spanned_snapshots,
        min(snapshot_seq)                         as first_seq,
        max(snapshot_seq)                         as last_seq
    from numbered
    group by gtin, region, interval_no
),

with_regular as (
    select
        *,
        case when not on_sale then price
             else coalesce(
                 last_value(case when not on_sale then price end ignore nulls) over (
                     partition by gtin, region order by interval_no
                     rows between unbounded preceding and 1 preceding),
                 first_value(case when not on_sale then price end ignore nulls) over (
                     partition by gtin, region order by interval_no
                     rows between 1 following and unbounded following)
             )
        end as regular_price
    from intervals
),

gaps as (
    select
        *,
        lead(valid_from) over w   as next_from,
        lead(first_seq)  over w   as next_first_seq
    from with_regular
    window w as (partition by gtin, region order by interval_no)
),

with_gap as (
    select
        *,
        next_from is not null
          and next_first_seq - last_seq <= {{ var('max_gap_snapshots') }} + 1
          and date_diff('day', valid_to, next_from) > 1                    as gap_after
    from gaps
),

filled as (
    -- non-sale intervals run on until the next interval starts
    select
        gtin, region, price, on_sale, pack_size, grammage, name, valid_from,
        case when gap_after and not on_sale then next_from - 1 else valid_to end      as valid_to,
        observed_snapshots, spanned_snapshots, last_seq, regular_price,
        case when gap_after and not on_sale then date_diff('day', valid_to, next_from) - 1
             else 0 end                                                             as filled_days
    from with_gap
    union all
    -- after a sale interval, the gap gets the regular price, not on sale
    select
        gtin, region, regular_price, false, pack_size, grammage, name,
        valid_to + 1, next_from - 1,
        0, 0, last_seq, regular_price,
        date_diff('day', valid_to, next_from) - 1
    from with_gap
    where gap_after and on_sale and regular_price is not null
),

renumbered as (
    select
        *,
        cast(row_number() over (partition by gtin, region order by valid_from) as integer) as interval_no
    from filled
),

region_last as (
    select region, max(snapshot_seq) as last_seq
    from {{ ref('snapshots') }}
    group by region
)

select
    i.gtin,
    i.region,
    i.interval_no,
    i.valid_from,
    i.valid_to,
    i.price,
    i.on_sale,
    i.regular_price,
    case when i.on_sale and i.regular_price > 0
         then round(1 - i.price / i.regular_price, 4) end           as discount_pct,
    i.pack_size,
    i.grammage,
    m.measure_amount,
    m.measure_unit,
    case when m.measure_amount > 0
         then round(i.price / m.measure_amount, 4) end              as unit_price,
    m.source_unit_price,
    coalesce(m.unit_price_status, 'unverified')                     as unit_price_status,
    case when g.piece_count > 0
         then round(i.price / g.piece_count, 4) end                 as price_per_piece,
    i.observed_snapshots,
    i.spanned_snapshots,
    i.filled_days,
    -- seen in one of the region's last (max_gap_snapshots + 1) snapshots; the
    -- same tolerance as gap bridging, so a partial last scrape doesn't matter
    i.last_seq >= r.last_seq - {{ var('max_gap_snapshots') }}       as is_current
from renumbered as i
join region_last as r using (region)
left join {{ ref('silver_grammage') }} as g on g.grammage = i.grammage
left join {{ ref('silver_pack_measure') }} as m
       on m.grammage = i.grammage and m.name = i.name and m.price = i.price
