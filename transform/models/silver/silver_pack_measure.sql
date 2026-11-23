{#
  Final pack measure per (grammage, name, price), checked against two
  independent pieces of evidence:

    1. the unit price printed in the source   "(1 kg = 4,98 €)"
    2. the size written in the product name   "Harry Goldkrüstchen 6x80g"

  Why: multipack notation is inconsistent upstream. "6x480g" usually means
  6 x 80 g = 480 g in total, but "6x1,50l" really is 6 bottles of 1.5 l.
  And for some jarred food the printed unit price uses a different weight
  than the one on the label.

  Candidates (all in kg / l / m):
    total_product   N x M as written            (6x480g -> 2.88 kg)
    total_given     M alone, for multipacks     (6x480g -> 0.48 kg)
    name_total      size found in the name      ("6x80g" -> 0.48 kg)

  unit_price_status, in order of evaluation:
    match            printed unit price agrees with N x M
    conflict         the name confirms N x M but the printed unit price
                     disagrees (e.g. drained vs. filled weight); N x M kept
    multipack_total  name or printed unit price say M is the total; M used
    from_name        the grammage field is off, but name and printed unit
                     price agree with each other; name size used
    unverified       nothing to check against (no printed unit price)
    conflict         (fallback) nothing agrees; N x M kept
#}
with triples as (
    select distinct grammage, name, price
    from {{ ref('silver_product_daily') }}
    where grammage is not null
),

name_size as (
    select
        *,
        -- the last size mentioned in the name, e.g. '6x80g', '1,5l', '85g'
        regexp_extract_all(
            name, '(?:[0-9]+\s*x\s*)?[0-9]+(?:[.,][0-9]+)?\s*(?:kg|g|ml|l)\b'
        )[-1] as name_size_text
    from triples
),

name_parsed as (
    select
        *,
        regexp_extract(
            name_size_text,
            '^(?:([0-9]+)\s*x\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(kg|g|ml|l)$',
            ['n', 'amount', 'unit']
        ) as ns
    from name_size
),

candidates as (
    select
        n.grammage,
        n.name,
        n.price,
        g.measure_unit,
        g.is_approximate,
        g.measure_amount                                                     as total_product,
        case when g.pack_count > 1 then g.item_measure end                   as total_given,
        cast(
            coalesce(try_cast(nullif(n.ns.n, '') as integer), 1)
            * {{ de_decimal("nullif(n.ns.amount, '')") }}
            * case n.ns.unit when 'g' then 0.001 when 'ml' then 0.001 else 1 end
        as decimal(14, 6))                                                   as name_total,
        case n.ns.unit when 'g' then 'kg' when 'kg' then 'kg'
                       when 'ml' then 'l' when 'l' then 'l' end              as name_unit,
        case when g.source_unit_price_basis = g.measure_unit
             then g.source_unit_price end                                    as src_unit_price,
        case when g.is_approximate then 0.10
             else {{ var('unit_price_tolerance') }} end                     as tol
    from name_parsed as n
    join {{ ref('silver_grammage') }} as g using (grammage)
),

checks as (
    select
        *,
        -- printed unit price agrees with a candidate total?
        src_unit_price is not null and total_product > 0
          and abs(price / total_product - src_unit_price)
              <= greatest(tol * src_unit_price, 0.006)                       as src_ok_product,
        src_unit_price is not null and total_given > 0
          and abs(price / total_given - src_unit_price)
              <= greatest(tol * src_unit_price, 0.006)                       as src_ok_given,
        src_unit_price is not null and name_total > 0 and name_unit = measure_unit
          and abs(price / name_total - src_unit_price)
              <= greatest(tol * src_unit_price, 0.006)                       as src_ok_name,
        -- name size equals a candidate total (within 2%)?
        name_unit = measure_unit and total_product > 0
          and abs(name_total - total_product) <= 0.02 * total_product        as name_ok_product,
        name_unit = measure_unit and total_given > 0
          and abs(name_total - total_given) <= 0.02 * total_given            as name_ok_given
    from candidates
),

decided as (
    select
        *,
        case
            when total_product is null                       then 'unverified'
            when coalesce(src_ok_product, false)             then 'match'
            when coalesce(name_ok_product, false)            then
                case when src_unit_price is null then 'unverified' else 'conflict' end
            when total_given is not null
                 and (coalesce(src_ok_given, false) or coalesce(name_ok_given, false))
                                                             then 'multipack_total'
            when coalesce(src_ok_name, false)                then 'from_name'
            when src_unit_price is null                      then 'unverified'
            else 'conflict'
        end as unit_price_status
    from checks
)

select
    grammage,
    name,
    price,
    case unit_price_status
        when 'multipack_total' then total_given
        when 'from_name'       then name_total
        else total_product
    end                                                   as measure_amount,
    measure_unit,
    unit_price_status,
    src_unit_price                                        as source_unit_price,
    total_product                                         as parsed_measure_amount,
    name_total                                            as name_measure_amount
from decided
