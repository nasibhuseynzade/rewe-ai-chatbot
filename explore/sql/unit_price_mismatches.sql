-- How reliable are the unit prices?
-- Every price interval's pack measure is reconciled in silver_pack_measure
-- against the product name and the unit price printed in the source.
-- This file shows how that came out, and what is left as 'conflict'.

-- ## Unit price status
select
    unit_price_status,
    count(*)                                            as intervals,
    round(100.0 * count(*) / sum(count(*)) over (), 2)  as pct,
    count(distinct gtin)                                as products
from gold.fct_price_interval
group by all
order by intervals desc

-- ## Multipacks read as total (sample)
select d.name, f.grammage, f.price, f.measure_amount, f.measure_unit,
       f.unit_price, f.source_unit_price
from gold.fct_price_interval f
join gold.dim_product d using (gtin)
where f.unit_price_status = 'multipack_total'
qualify row_number() over (partition by f.gtin order by f.valid_from desc) = 1
order by d.name
limit 25

-- ## Size taken from the name (sample)
select d.name, f.grammage, f.price, f.measure_amount, f.measure_unit,
       f.unit_price, f.source_unit_price
from gold.fct_price_interval f
join gold.dim_product d using (gtin)
where f.unit_price_status = 'from_name'
qualify row_number() over (partition by f.gtin order by f.valid_from desc) = 1
order by d.name
limit 25

-- ## Remaining conflicts by category
select d.primary_category, count(*) as intervals, count(distinct gtin) as products
from gold.fct_price_interval f
join gold.dim_product d using (gtin)
where f.unit_price_status = 'conflict'
group by all
order by intervals desc

-- ## Remaining conflicts (one row per product)
select
    d.name,
    d.primary_category,
    f.price,
    f.on_sale,
    f.grammage,
    f.unit_price,
    f.source_unit_price,
    round(f.unit_price / f.source_unit_price, 3) as ratio
from gold.fct_price_interval f
join gold.dim_product d using (gtin)
where f.unit_price_status = 'conflict'
qualify row_number() over (partition by f.gtin order by f.valid_from desc) = 1
order by abs(1 - f.unit_price / f.source_unit_price) desc
limit 60
