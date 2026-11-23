{{ config(severity = 'warn') }}
-- Grammage strings the parser could not read at all. Each one is a format to add.
select grammage
from {{ ref('silver_grammage') }}
where not is_parsed
