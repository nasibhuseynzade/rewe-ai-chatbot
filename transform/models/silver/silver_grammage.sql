{#
  Parses each *distinct* grammage string once (a few thousand strings instead of
  millions of rows). Formats seen in the data, e.g.:

    250g (1 kg = 3,16 €)        1,50kg (1 kg = 0,79 €)     130g
    6x0,33l (1 l = 2,52 €)      4x6x0,33l (1 l = 2,37 €)   3x48 Stück
    1 Stück ca. 300 g (1 kg = 1,59 €)                      20x6cm (1 m = 0,66 €)
    50m (1 m  = 0,04 €)         1g (1 kg = 4.990,00 €)

  Output:
    pack_count       product of the "N x" multipliers (1 if none)
    unit_amount      amount per item, in the original unit
    measure_amount   total amount in the base unit (kg / l / m), or kg for
                     "Stück ca. N g" items; NULL for plain piece counts
    measure_unit     kg | l | m
    source_unit_price / source_unit_price_basis   as printed in "(1 kg = … €)"
#}
with strings as (
    select distinct grammage
    from {{ ref('stg_prices') }}
    where grammage is not null
),

extracted as (
    select
        grammage,
        trim(regexp_replace(grammage, '\(.*\)', ''))                     as size_text,
        regexp_extract(
            grammage,
            '\(\s*1\s*(kg|l|m)\s*=\s*([0-9.,]+)\s*€\s*\)',
            ['basis', 'value']
        )                                                                as up,
        regexp_extract(
            trim(regexp_replace(grammage, '\(.*\)', '')),
            '^(?:([0-9]+)\s*x\s*)?(?:([0-9]+)\s*x\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(g|kg|ml|l|cm|m|Stück)\b',
            ['n1', 'n2', 'amount', 'unit']
        )                                                                as s,
        regexp_extract(
            grammage,
            'ca\.\s*([0-9]+(?:[.,][0-9]+)?)\s*(g|kg)\b',
            ['amount', 'unit']
        )                                                                as approx
    from strings
),

typed as (
    select
        grammage,
        size_text,
        coalesce(try_cast(nullif(s.n1, '') as integer), 1)
          * coalesce(try_cast(nullif(s.n2, '') as integer), 1)           as pack_count,
        {{ de_decimal("nullif(s.amount, '')") }}                         as unit_amount,
        nullif(s.unit, '')                                               as unit,
        {{ de_decimal("nullif(approx.amount, '')") }}
          * case approx.unit when 'g' then 0.001 else 1 end              as approx_weight_kg,
        {{ de_decimal("nullif(up.value, '')") }}                         as source_unit_price,
        nullif(up.basis, '')                                             as source_unit_price_basis
    from extracted
)

select
    grammage,
    size_text,
    pack_count,
    unit_amount,
    unit,
    case unit
        when 'g' then 'kg' when 'kg' then 'kg'
        when 'ml' then 'l' when 'l' then 'l'
        when 'cm' then 'm' when 'm' then 'm'
        when 'Stück' then 'piece'
    end                                                                  as base_unit,
    approx_weight_kg,
    approx_weight_kg is not null                                         as is_approximate,
    cast(case
        when unit in ('g', 'ml') then pack_count * unit_amount * 0.001
        when unit = 'cm'         then pack_count * unit_amount * 0.01
        when unit in ('kg', 'l', 'm') then pack_count * unit_amount
        when unit = 'Stück' and approx_weight_kg is not null
                                 then pack_count * unit_amount * approx_weight_kg
    end as decimal(14, 6))                                               as measure_amount,
    case
        when unit in ('g', 'kg') then 'kg'
        when unit in ('ml', 'l') then 'l'
        when unit in ('cm', 'm') then 'm'
        when unit = 'Stück' and approx_weight_kg is not null then 'kg'
    end                                                                  as measure_unit,
    case when unit = 'Stück' then pack_count * unit_amount end           as piece_count,
    source_unit_price,
    source_unit_price_basis,
    unit is not null                                                     as is_parsed
from typed
