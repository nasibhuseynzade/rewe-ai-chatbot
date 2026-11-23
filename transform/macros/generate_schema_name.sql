{#
  Use the configured schema name as-is (staging / silver / gold) instead of
  dbt's default "<target_schema>_<custom_schema>" (main_silver, ...).
  Clean schema names matter later: the assistant only sees the gold schema.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}
