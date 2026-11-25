{#
  Latest regular price of each product sold in both regions, side by side.
  Only products with a current price in both regions are included.
#}
with current_price as (
    select gtin, region, regular_price, valid_from
    from {{ ref('fct_price_interval') }}
    where is_current and regular_price > 0
    qualify row_number() over (partition by gtin, region order by valid_from desc) = 1
)

select
    b.gtin,
    d.name,
    d.brand,
    d.primary_category                                                  as category,
    b.regular_price                                                     as price_bavaria,
    s.regular_price                                                     as price_schleswig_holstein,
    b.regular_price - s.regular_price                                   as diff_eur,
    round(100 * (b.regular_price / s.regular_price - 1), 2)             as diff_pct,
    case
        when b.regular_price > s.regular_price then 'bavaria'
        when b.regular_price < s.regular_price then 'schleswig-holstein'
        else 'same'
    end                                                                 as more_expensive_in
from current_price as b
join current_price as s on s.gtin = b.gtin
join {{ ref('dim_product') }} as d on d.gtin = b.gtin
where b.region = 'bavaria'
  and s.region = 'schleswig-holstein'
