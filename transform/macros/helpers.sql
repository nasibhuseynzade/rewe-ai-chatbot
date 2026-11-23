{# German number text ("4.990,00", "0,79", "1,5") -> DECIMAL. Dots are thousands separators. #}
{% macro de_decimal(expr, precision=14, scale=4) -%}
    try_cast(replace(replace({{ expr }}, '.', ''), ',', '.') as decimal({{ precision }}, {{ scale }}))
{%- endmacro %}


{#
  GS1 check digit for GTIN-8/12/13/14 given as text.
  From the right, payload digits are weighted 3,1,3,1,...; the check digit
  makes the weighted sum a multiple of 10.
#}
{% macro gtin_check_digit_ok(code) -%}
    (case
        when not coalesce(regexp_matches({{ code }}, '^[0-9]{8,14}$'), false) then false
        else (
            10 - list_sum([
                try_cast(reverse(left({{ code }}, length({{ code }}) - 1))[i] as integer)
                * case when i % 2 = 1 then 3 else 1 end
                for i in range(1, length({{ code }}))
            ]) % 10
        ) % 10 = try_cast(right({{ code }}, 1) as integer)
    end)
{%- endmacro %}


{# SQL list literal from a dbt list var, e.g. ['a', 'b'] -> ('a', 'b') #}
{% macro sql_in_list(values) -%}
    ({% for v in values %}'{{ v | replace("'", "''") }}'{% if not loop.last %}, {% endif %}{% endfor %})
{%- endmacro %}
