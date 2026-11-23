-- Price intervals of one product in one region must not overlap and must be ordered.
select a.gtin, a.region, a.interval_no, a.valid_from, a.valid_to, b.interval_no as next_no, b.valid_from as next_from
from {{ ref('fct_price_interval') }} as a
join {{ ref('fct_price_interval') }} as b
  on a.gtin = b.gtin and a.region = b.region and b.interval_no = a.interval_no + 1
where b.valid_from <= a.valid_to
   or a.valid_from > a.valid_to
