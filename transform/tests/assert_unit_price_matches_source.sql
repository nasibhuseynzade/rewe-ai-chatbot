{{ config(severity = 'warn') }}
-- After reconciliation (silver_pack_measure) a few intervals still disagree with
-- the unit price printed in the source: mostly jarred food whose printed unit
-- price uses a different weight than the label. That is expected, as long as it
-- stays rare. A jump in this share means a parser or reconciliation regression.
-- Details: uv run python explore/query.py explore/sql/unit_price_mismatches.sql
with s as (
    select
        count(*) filter (where unit_price_status = 'conflict') as conflicts,
        count(*)                                                as intervals
    from {{ ref('fct_price_interval') }}
)
select conflicts, intervals, round(conflicts / intervals, 4) as share
from s
where intervals > 0
  and conflicts / intervals > {{ var('unit_price_conflict_max_share') }}
