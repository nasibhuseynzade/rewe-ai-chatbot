{#
  One row per product (gtin), described by its most recent observation.

  primary_category: the non-thematic category the product was listed in most
  often (ties broken alphabetically); a thematic one only if nothing else exists.
#}
with latest as (
    select *
    from {{ ref('silver_product_daily') }}
    qualify row_number() over (partition by gtin order by snapshot_date desc, region) = 1
),

history as (
    select
        gtin,
        min(snapshot_date)                                            as first_seen,
        max(snapshot_date)                                            as last_seen,
        list(distinct region order by region)                         as regions,
        count(distinct name)                                          as name_variants,
        count(distinct pack_size)                                     as pack_size_variants,
        arg_max(brand, snapshot_date) filter (where brand is not null) as latest_brand
    from {{ ref('silver_product_daily') }}
    group by gtin
),

category_rank as (
    select
        gtin,
        category,
        row_number() over (
            partition by gtin
            order by is_thematic, sum(snapshots_seen) desc, category
        ) as rnk
    from {{ ref('product_category') }}
    group by gtin, category, is_thematic
)

select
    l.gtin,
    l.ean_raw,
    l.name,
    h.latest_brand                                          as brand,
    c.category                                              as primary_category,
    l.pack_size,
    g.pack_count,
    m.measure_amount,
    m.measure_unit,
    coalesce(m.unit_price_status, 'unverified')             as measure_status,
    g.piece_count,
    g.is_approximate                                        as is_weight_approximate,
    h.first_seen,
    h.last_seen,
    h.regions,
    h.name_variants,
    h.pack_size_variants,
    {{ gtin_check_digit_ok('l.gtin') }}                     as is_valid_gtin,
    -- GS1 restricted circulation numbers (RCN-8): in-store codes, e.g. loose produce
    length(l.gtin) = 8 and left(l.gtin, 1) in ('0', '2')   as is_store_code
from latest as l
join history as h using (gtin)
left join category_rank as c on c.gtin = l.gtin and c.rnk = 1
left join {{ ref('silver_grammage') }} as g on g.grammage = l.grammage
left join {{ ref('silver_pack_measure') }} as m
       on m.grammage = l.grammage and m.name = l.name and m.price = l.price
