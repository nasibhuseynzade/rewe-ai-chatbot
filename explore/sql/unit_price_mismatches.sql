-- Why do some intervals fail tests/assert_unit_price_matches_source.sql?
-- (Same condition as the dbt test; keep the two in sync.)
--
-- Possible causes to tell apart:
--   * parser bug           -> concentrated in one grammage pattern
--   * drained weight       -> canned / jarred food; source unit price is per
--                             Abtropfgewicht, so our price/kg looks too LOW (ratio < 1)
--   * stale unit price     -> source text not updated after a price change;
--                             often on_sale intervals
--   * approximate weights  -> "1 Stück ca. N g" items

-- ## Size of the problem
with m as (
    select f.*
    from gold.fct_price_interval f
    join silver.silver_grammage g on g.grammage = f.grammage
    where g.source_unit_price is not null
      and g.source_unit_price_basis = f.measure_unit
      and abs(f.unit_price - g.source_unit_price) > greatest(0.03 * g.source_unit_price, 0.006)
)
select
    (select count(*) from m)                                   as mismatching_intervals,
    (select count(*) from gold.fct_price_interval)             as all_intervals,
    round(100.0 * (select count(*) from m)
          / (select count(*) from gold.fct_price_interval), 2) as pct,
    (select count(distinct gtin) from m)                       as products,
    (select count(*) from m where on_sale)                     as on_sale_intervals

-- ## By grammage pattern and sale flag
with m as (
    select f.on_sale, f.grammage,
           f.unit_price / g.source_unit_price as ratio
    from gold.fct_price_interval f
    join silver.silver_grammage g on g.grammage = f.grammage
    where g.source_unit_price is not null
      and g.source_unit_price_basis = f.measure_unit
      and abs(f.unit_price - g.source_unit_price) > greatest(0.03 * g.source_unit_price, 0.006)
)
select
    regexp_replace(grammage, '[0-9]+([.,][0-9]+)?', 'N', 'g') as pattern,
    on_sale,
    count(*)                       as intervals,
    round(median(ratio), 3)        as median_ratio,
    round(min(ratio), 3)           as min_ratio,
    round(max(ratio), 3)           as max_ratio,
    any_value(grammage)            as example
from m
group by all
order by intervals desc

-- ## Ratio buckets (our unit price / source unit price)
with m as (
    select f.unit_price / g.source_unit_price as ratio
    from gold.fct_price_interval f
    join silver.silver_grammage g on g.grammage = f.grammage
    where g.source_unit_price is not null
      and g.source_unit_price_basis = f.measure_unit
      and abs(f.unit_price - g.source_unit_price) > greatest(0.03 * g.source_unit_price, 0.006)
)
select
    case
        when ratio < 0.5  then 'a) < 0.5'
        when ratio < 0.9  then 'b) 0.5 - 0.9'
        when ratio < 1.0  then 'c) 0.9 - 1.0'
        when ratio < 1.1  then 'd) 1.0 - 1.1'
        when ratio < 2.0  then 'e) 1.1 - 2.0'
        else                   'f) >= 2.0'
    end as ratio_bucket,
    count(*) as intervals
from m
group by all
order by ratio_bucket

-- ## By primary category
with m as (
    select f.gtin
    from gold.fct_price_interval f
    join silver.silver_grammage g on g.grammage = f.grammage
    where g.source_unit_price is not null
      and g.source_unit_price_basis = f.measure_unit
      and abs(f.unit_price - g.source_unit_price) > greatest(0.03 * g.source_unit_price, 0.006)
)
select d.primary_category, count(*) as intervals
from m join gold.dim_product d using (gtin)
group by all
order by intervals desc

-- ## Examples
select
    d.name,
    d.primary_category,
    f.region,
    f.valid_from,
    f.price,
    f.on_sale,
    f.grammage,
    f.unit_price           as our_unit_price,
    g.source_unit_price,
    round(f.unit_price / g.source_unit_price, 3) as ratio
from gold.fct_price_interval f
join silver.silver_grammage g on g.grammage = f.grammage
join gold.dim_product d using (gtin)
where g.source_unit_price is not null
  and g.source_unit_price_basis = f.measure_unit
  and abs(f.unit_price - g.source_unit_price) > greatest(0.03 * g.source_unit_price, 0.006)
order by abs(1 - f.unit_price / g.source_unit_price) desc
limit 40
