{{ config(severity = 'warn') }}
-- Product-days whose category repeats disagree on the price (see
-- silver_product_daily). Expected to be very rare (< 0.1%).
with s as (
    select count(*) filter (where has_price_conflict) as conflicts, count(*) as product_days
    from {{ ref('silver_product_daily') }}
)
select conflicts, product_days, round(conflicts / product_days, 6) as share
from s
where conflicts > 0.001 * product_days
