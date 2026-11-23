{{ config(severity = 'warn') }}
-- Parser check: our unit price (price / parsed size) should match the unit price
-- printed in the source, when both use the same base unit. The source rounds to
-- cents, so differences under half a cent are ignored.
-- Rows returned here point at grammage formats the parser gets wrong.
select
    f.gtin, f.region, f.valid_from, f.price, f.grammage,
    f.unit_price, g.source_unit_price, g.source_unit_price_basis
from {{ ref('fct_price_interval') }} as f
join {{ ref('silver_grammage') }} as g on g.grammage = f.grammage
where g.source_unit_price is not null
  and g.source_unit_price_basis = f.measure_unit
  and abs(f.unit_price - g.source_unit_price)
      > greatest({{ var('unit_price_tolerance') }} * g.source_unit_price, 0.006)
