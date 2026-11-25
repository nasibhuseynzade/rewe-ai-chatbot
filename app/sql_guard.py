"""Checks SQL written by the LLM before it runs (the run_sql tool).

Allowed: exactly one SELECT (CTEs and UNIONs included) that reads only from
schema-qualified tables in the allowed schemas (gold, marts) or from its own
CTEs, and calls no file-, system- or metadata functions. A LIMIT is enforced.

This is the first line of defence. The second is the database connection
itself (read-only, no external access, locked config; see app/db.py), so
even SQL that slipped past this check couldn't change or read anything else.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from app import config


class SqlNotAllowed(ValueError):
    """Raised with a message the LLM can use to fix its query."""


FORBIDDEN_STATEMENTS = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
    exp.Alter, exp.Command, exp.Set, exp.Pragma, exp.Copy, exp.Use,
)

# Function names (lowercase) or prefixes that are never allowed.
FORBIDDEN_FUNCTION_PREFIXES = (
    "read_", "glob", "parquet_", "sniff_", "query", "duckdb_", "pragma_",
    "getenv", "current_setting", "load", "install", "attach", "detach",
    "export", "import", "copy", "system", "which_secret", "iceberg_",
    "delta_", "scan_", "http", "sqlite_", "postgres_", "mysql_", "json_execute",
    "checkpoint", "force_checkpoint", "enable_", "disable_",
)


def _function_name(func: exp.Func) -> str:
    if isinstance(func, exp.Anonymous):
        return str(func.this).lower()
    return (func.sql_name() or func.key).lower()


def check_sql(sql: str, max_rows: int | None = None) -> str:
    """Return a safe version of `sql` (with LIMIT) or raise SqlNotAllowed."""
    max_rows = max_rows or config.MAX_ROWS
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SqlNotAllowed(f"Could not parse the SQL: {exc}") from exc

    if len(statements) != 1:
        raise SqlNotAllowed("Send exactly one SQL statement.")
    tree = statements[0]

    if not isinstance(tree, exp.Query):
        raise SqlNotAllowed("Only SELECT queries are allowed.")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_STATEMENTS):
            raise SqlNotAllowed("Only SELECT queries are allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = (table.name or "").lower()
        schema = (table.db or "").lower()
        if table.catalog:
            raise SqlNotAllowed("Don't reference other databases.")
        if not schema:
            if name in cte_names:
                continue
            raise SqlNotAllowed(
                f"Table '{table.sql(dialect='duckdb')}' must be schema-qualified, "
                f"e.g. gold.dim_product or marts.mart_category_price_index."
            )
        if schema not in config.SERVING_SCHEMAS:
            raise SqlNotAllowed(
                f"Schema '{schema}' is not available. Use: {', '.join(config.SERVING_SCHEMAS)}."
            )

    for func in tree.find_all(exp.Func):
        fname = _function_name(func)
        if fname.startswith(FORBIDDEN_FUNCTION_PREFIXES):
            raise SqlNotAllowed(f"Function '{fname}' is not allowed.")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(max_rows)
    else:
        value = limit.expression if isinstance(limit, exp.Limit) else limit
        try:
            n = int(value.name)
        except (AttributeError, ValueError):
            n = max_rows + 1
        if n > max_rows:
            tree = tree.limit(max_rows)

    return tree.sql(dialect="duckdb")
