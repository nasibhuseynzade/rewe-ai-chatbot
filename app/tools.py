"""Tools the LLM can call. Each one is a fixed, parameterised SQL query on the
serving database, except run_sql, which runs the LLM's own SELECT after the
guard (app/sql_guard.py) has checked it.

Every tool returns the same shape, so the frontend can show any result:
    {
      "tool": name, "sql": the SQL that ran, "params": its parameters,
      "columns": [...], "rows": [{...}], "row_count": n, "truncated": bool,
      "chart": {"type": "line" | "step" | "bar", "x": col, "y": col,
                "series": col | None, "title": str} | None
    }

TOOL_SPECS describes the tools in the OpenAI-compatible function-calling format
(also understood by Gemini's and Groq's OpenAI-compatible endpoints).
"""

from __future__ import annotations

from typing import Any, Callable

import duckdb

from app import config
from app.db import run_query
from app.sql_guard import check_sql

ALL_CATEGORIES = "All categories"


def _result(tool: str, sql: str, params: dict, data: dict, chart: dict | None = None) -> dict:
    return {"tool": tool, "sql": " ".join(sql.split()), "params": params, **data,
            "chart": chart if data["row_count"] else None}


_REGION_ALIASES = {
    "bavaria": "bavaria", "bayern": "bavaria", "by": "bavaria",
    "schleswig-holstein": "schleswig-holstein", "schleswigholstein": "schleswig-holstein",
    "sh": "schleswig-holstein",
}


def _region(region: str | None) -> str | None:
    """Normalise a region name; models sometimes send 'Bavaria' or 'Bayern'."""
    key = (region or "").strip().lower().replace(" ", "-").replace("_", "-")
    if key in ("", "all", "both", "none", "null"):
        return None
    key = _REGION_ALIASES.get(key) or _REGION_ALIASES.get(key.replace("-", ""))
    if key is None:
        raise ValueError(f"region must be one of {config.REGIONS} or null")
    return key


_NULL_WORDS = {"", "null", "none", "nil", "all", "any", "alle", "all categories", "*"}


def _category(con: duckdb.DuckDBPyConnection, category: str | None) -> str | None:
    """Normalise a category argument.

    Models sometimes send the string "null" / "None" instead of JSON null, or the
    right name in the wrong case; both used to return zero rows silently. Unknown
    names raise with the list of valid ones, so the model can correct itself.
    """
    if category is None or str(category).strip().lower() in _NULL_WORDS:
        return None
    names = {c.lower(): c for c in list_categories(con)}  # a few ms; no cache to go stale
    found = names.get(str(category).strip().lower())
    if found is None:
        raise ValueError(f"unknown category '{category}'; use one of: {', '.join(sorted(names.values()))}")
    return found


def _limit(limit: int | None, default: int, maximum: int = 50) -> int:
    return max(1, min(int(limit or default), maximum))


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def search_products(con: duckdb.DuckDBPyConnection, query: str,
                    region: str | None = None, limit: int = 10) -> dict:
    """Find products by name.

    Prices are the latest known per region with their date, so products that left
    the assortment before the last snapshot still show a price (still_sold tells
    them apart). Ranking: name match first, then products still sold and products
    with a long price history, so "Tomate" finds the everyday tomatoes before a
    sandwich that was listed for two weeks. Words: German compounds carry their
    meaning in the last part, so "Rispentomaten" is a full match for "Tomate" and
    "Tomatenmark" only half. Full matches share the result slots between
    categories in proportion to their number of matches.
    """
    sql = """
        WITH q AS (
            SELECT list_filter(string_split(regexp_replace(lower(strip_accents($query)), '[^a-z0-9]+', ' ', 'g'), ' '),
                               lambda t: length(t) >= 2) AS tokens
        ),
        latest AS (
            SELECT gtin, region, price, valid_to, is_current
            FROM gold.fct_price_interval
            QUALIFY row_number() OVER (PARTITION BY gtin, region ORDER BY valid_to DESC, valid_from DESC) = 1
        ),
        scored AS (
            SELECT
                d.gtin, d.name, d.brand, d.primary_category AS category, d.pack_size,
                d.first_seen, d.last_seen,
                -- German compounds carry their meaning in the last part: a word that
                -- equals or ends with the search word (Butter, Rispen-tomaten) counts fully,
                -- one that only starts with or contains it (Butter-kaese, Tomaten-mark) half.
                list_sum(list_transform(q.tokens, lambda t:
                    CASE
                        WHEN list_bool_or(list_transform(w.words, lambda x:
                                 x = t OR suffix(x, t) OR suffix(x, t || 'n') OR suffix(x, t || 'en')
                                 OR suffix(x, t || 'e') OR suffix(x, t || 's'))) THEN 1.0
                        WHEN contains(w.text, t) THEN 0.5
                        ELSE 0.0
                    END)) / greatest(len(q.tokens), 1)                    AS token_share,
                jaro_winkler_similarity(lower(strip_accents(d.name)),
                                        lower(strip_accents($query)))     AS similarity,
                least(date_diff('day', d.first_seen, d.last_seen) / 365.0, 1) AS history_share,
                -- short names are the generic products ("ja! Frische Vollmilch" before
                -- "Milkana mit Blauschimmel & Allgaeuer Milch")
                least(3.0 / greatest(len(list_filter(w.words, lambda x: regexp_matches(x, '^[a-z-]{2,}$'))), 1), 1) AS short_name
            FROM gold.dim_product AS d, q,
                 LATERAL (SELECT regexp_replace(lower(strip_accents(d.name || ' ' || coalesce(d.brand, ''))),
                                                '[^a-z0-9-]+', ' ', 'g') AS text) AS n,
                 LATERAL (SELECT n.text AS text, string_split(n.text, ' ') AS words) AS w
            WHERE $region IS NULL OR list_contains(d.regions, $region)
        ),
        joined AS (
            SELECT
                s.*,
                b.price  AS price_bavaria,
                sh.price AS price_schleswig_holstein,
                coalesce(b.is_current, false) OR coalesce(sh.is_current, false) AS still_sold,
                greatest(coalesce(b.valid_to, sh.valid_to), coalesce(sh.valid_to, b.valid_to)) AS price_date
            FROM scored AS s
            LEFT JOIN latest AS b  ON b.gtin = s.gtin  AND b.region = 'bavaria'
            LEFT JOIN latest AS sh ON sh.gtin = s.gtin AND sh.region = 'schleswig-holstein'
            WHERE s.token_share > 0 OR s.similarity > 0.88
        ),
        ranked AS (
            SELECT *,
                   round(token_share + 0.15 * similarity + 0.2 * still_sold::int + 0.2 * history_share
                         + 0.3 * short_name, 3) AS score
            FROM joined
        ),
        -- Full matches share the result slots between categories in proportion to how
        -- many matches each has (D'Hondt: priority = matches / rank). "Butter" mostly
        -- returns dairy, with the best bakery item further down; "Tomate" alternates
        -- fresh and canned. The model then picks what the question is about.
        diverse AS (
            SELECT *,
                   token_share >= 0.99 AS full_match,
                   count(*) OVER (PARTITION BY token_share >= 0.99, category)
                     / row_number() OVER (PARTITION BY token_share >= 0.99, category
                                          ORDER BY score DESC, last_seen DESC) AS priority
            FROM ranked
        )
        SELECT
            gtin, name, brand, category, pack_size,
            price_bavaria, price_schleswig_holstein, price_date, still_sold,
            first_seen, last_seen, score
        FROM diverse
        ORDER BY full_match DESC,
                 CASE WHEN full_match THEN priority END DESC,
                 score DESC, last_seen DESC
        LIMIT $limit
    """
    # at least 8 results: a product type ("tomatoes") needs several candidates
    params = {"query": query, "region": _region(region), "limit": _limit(max(limit or 10, 8), 10, 30)}
    return _result("search_products", sql, params, run_query(con, sql, params))


def get_price_history(con: duckdb.DuckDBPyConnection, gtins: list[str],
                      region: str | None = None) -> dict:
    sql = """
        SELECT d.name, f.gtin, f.region, f.valid_from, f.valid_to, f.price, f.on_sale,
               f.regular_price, f.discount_pct, f.pack_size, f.unit_price, f.measure_unit,
               f.unit_price_status
        FROM gold.fct_price_interval AS f
        JOIN gold.dim_product AS d USING (gtin)
        WHERE f.gtin IN (SELECT unnest($gtins))
          AND ($region IS NULL OR f.region = $region)
        ORDER BY d.name, f.region, f.valid_from
    """
    params = {"gtins": list(gtins)[:5], "region": _region(region)}
    chart = {"type": "step", "x": "valid_from", "y": "price", "series": "name",
             "title": "Price history"}
    return _result("get_price_history", sql, params, run_query(con, sql, params), chart)


def get_price_change(con: duckdb.DuckDBPyConnection, gtins: list[str],
                     region: str | None = None) -> dict:
    sql = """
        SELECT name, gtin, region, first_month, last_month, months_observed,
               first_price, last_price, price_change_pct, unit_price_change_pct
        FROM marts.mart_product_price_change
        WHERE gtin IN (SELECT unnest($gtins))
          AND ($region IS NULL OR region = $region)
        ORDER BY name, region
    """
    params = {"gtins": list(gtins)[:20], "region": _region(region)}
    return _result("get_price_change", sql, params, run_query(con, sql, params))


def get_category_index(con: duckdb.DuckDBPyConnection, category: str | None = None,
                       region: str | None = None) -> dict:
    category = _category(con, category)
    sql = """
        SELECT region, category, month, price_index, pct_change_vs_prev_month, products_compared
        FROM marts.mart_category_price_index
        WHERE category = coalesce($category, $all)
          AND ($region IS NULL OR region = $region)
        ORDER BY region, month
    """
    params = {"category": category, "all": ALL_CATEGORIES, "region": _region(region)}
    chart = {"type": "line", "x": "month", "y": "price_index", "series": "region",
             "title": f"Price index: {category or ALL_CATEGORIES} (first month = 100)"}
    return _result("get_category_index", sql, params, run_query(con, sql, params), chart)


def rank_categories_by_inflation(con: duckdb.DuckDBPyConnection,
                                 region: str | None = None) -> dict:
    sql = """
        SELECT region, category, price_index AS latest_index,
               round(price_index - 100, 2) AS change_since_start_pct, month AS latest_month
        FROM marts.mart_category_price_index
        WHERE category <> $all AND ($region IS NULL OR region = $region)
        QUALIFY row_number() OVER (PARTITION BY region, category ORDER BY month DESC) = 1
        ORDER BY region, latest_index DESC
    """
    params = {"all": ALL_CATEGORIES, "region": _region(region)}
    chart = {"type": "bar", "x": "category", "y": "change_since_start_pct", "series": "region",
             "title": "Price change since the first month, by category (%)"}
    return _result("rank_categories_by_inflation", sql, params, run_query(con, sql, params), chart)


def rank_price_changes(con: duckdb.DuckDBPyConnection, direction: str = "increase",
                       category: str | None = None, region: str | None = None,
                       min_months: int = 6, limit: int = 10) -> dict:
    category = _category(con, category)
    order = "DESC" if direction != "decrease" else "ASC"
    sql = f"""
        SELECT name, brand, category, region, first_month, last_month, first_price, last_price,
               last_pack_size AS pack_size, price_change_pct
        FROM marts.mart_product_price_change
        WHERE months_observed >= $min_months
          AND same_pack_size
          AND ($category IS NULL OR category = $category)
          AND ($region IS NULL OR region = $region)
        ORDER BY price_change_pct {order}
        LIMIT $limit
    """
    params = {"min_months": max(1, int(min_months)), "category": category,
              "region": _region(region), "limit": _limit(limit, 10)}
    chart = {"type": "bar", "x": "name", "y": "price_change_pct", "series": None,
             "title": "Biggest price " + ("decreases" if order == "ASC" else "increases") + " (%)"}
    return _result("rank_price_changes", sql, params, run_query(con, sql, params), chart)


def find_shrinkflation(con: duckdb.DuckDBPyConnection, category: str | None = None,
                       region: str | None = None, limit: int = 20) -> dict:
    category = _category(con, category)
    sql = """
        SELECT name, brand, category, region, changed_on, old_pack_size, new_pack_size,
               old_price, new_price, content_drop_pct, unit_price_increase_pct
        FROM marts.mart_shrinkflation
        WHERE ($category IS NULL OR category = $category)
          AND ($region IS NULL OR region = $region)
        ORDER BY unit_price_increase_pct DESC
        LIMIT $limit
    """
    params = {"category": category, "region": _region(region), "limit": _limit(limit, 20)}
    chart = {"type": "bar", "x": "name", "y": "unit_price_increase_pct", "series": None,
             "title": "Shrinkflation: hidden price increase per kg / l (%)"}
    return _result("find_shrinkflation", sql, params, run_query(con, sql, params), chart)


def compare_regions(con: duckdb.DuckDBPyConnection, gtins: list[str] | None = None,
                    category: str | None = None, limit: int = 20) -> dict:
    category = _category(con, category)
    if isinstance(gtins, str):
        gtins = None if gtins.strip().lower() in _NULL_WORDS else [gtins]
    sql = """
        WITH filtered AS (
            SELECT * FROM marts.mart_region_compare
            WHERE ($gtins IS NULL OR gtin IN (SELECT unnest($gtins)))
              AND ($category IS NULL OR category = $category)
        )
        SELECT 'summary' AS row_type, NULL AS name, NULL AS category,
               count(*) AS products,
               count(*) FILTER (WHERE more_expensive_in = 'bavaria') AS pricier_in_bavaria,
               count(*) FILTER (WHERE more_expensive_in = 'schleswig-holstein') AS pricier_in_sh,
               round(avg(diff_pct), 2) AS avg_diff_pct,
               NULL AS price_bavaria, NULL AS price_schleswig_holstein
        FROM filtered
        UNION ALL
        SELECT * FROM (
            SELECT 'product', name, category, NULL, NULL, NULL, diff_pct,
                   price_bavaria, price_schleswig_holstein
            FROM filtered
            WHERE more_expensive_in <> 'same'
            ORDER BY abs(diff_pct) DESC
            LIMIT $limit
        )
    """
    params = {"gtins": list(gtins)[:50] if gtins else None, "category": category,
              "limit": _limit(limit, 20)}
    return _result("compare_regions", sql, params, run_query(con, sql, params))


def rank_promotions(con: duckdb.DuckDBPyConnection, mode: str = "most",
                    year: int | None = None, category: str | None = None,
                    region: str | None = None, min_days: int = 180, limit: int = 10) -> dict:
    """Products ranked by promotions: most often on sale, deepest discount, or never on sale."""
    category = _category(con, category)
    mode = (mode or "most").strip().lower()
    if mode not in ("most", "deepest", "never"):
        raise ValueError("mode must be 'most', 'deepest' or 'never'")
    order = {
        "most": "promotions DESC, days_on_sale DESC",
        "deepest": "max_discount_pct DESC NULLS LAST, promotions DESC",
        "never": "days_listed DESC",
    }[mode]
    having = {
        "most": "sum(promotions) > 0",
        "deepest": "max(max_discount_pct) IS NOT NULL",
        "never": "sum(promotions) = 0 AND sum(days_listed) >= $min_days",
    }[mode]
    sql = f"""
        SELECT name, brand, category, region,
               sum(promotions)                                         AS promotions,
               sum(days_on_sale)                                       AS days_on_sale,
               sum(days_listed)                                        AS days_listed,
               round(100.0 * sum(days_on_sale) / nullif(sum(days_listed), 0), 1) AS share_on_sale_pct,
               max(max_discount_pct)                                   AS max_discount_pct,
               round(avg(avg_discount_pct), 1)                         AS avg_discount_pct
        FROM marts.mart_product_promotions
        WHERE ($year IS NULL OR year = $year)
          AND ($category IS NULL OR category = $category)
          AND ($region IS NULL OR region = $region)
        GROUP BY gtin, name, brand, category, region
        HAVING {having}
        ORDER BY {order}, name
        LIMIT $limit
    """
    params = {"year": int(year) if year not in (None, "") else None, "category": category,
              "region": _region(region), "limit": _limit(limit, 10)}
    if mode == "never":  # DuckDB rejects parameters the query doesn't use
        params["min_days"] = max(1, int(min_days or 180))
    y = {"most": "promotions", "deepest": "max_discount_pct", "never": None}[mode]
    title = {"most": "Times on sale", "deepest": "Deepest discount (%)", "never": None}[mode]
    chart = {"type": "bar", "x": "name", "y": y, "series": None, "title": title} if y else None
    return _result("rank_promotions", sql, params, run_query(con, sql, params), chart)


def get_sales_stats(con: duckdb.DuckDBPyConnection, category: str | None = None,
                    region: str | None = None) -> dict:
    category = _category(con, category)
    sql = """
        SELECT region, month, category, share_on_sale_pct, avg_discount_pct, sale_intervals_started
        FROM marts.mart_sales_monthly
        WHERE category = coalesce($category, $all)
          AND ($region IS NULL OR region = $region)
        ORDER BY region, month
    """
    params = {"category": category, "all": ALL_CATEGORIES, "region": _region(region)}
    chart = {"type": "line", "x": "month", "y": "share_on_sale_pct", "series": "region",
             "title": f"Share of products on sale: {category or ALL_CATEGORIES} (%)"}
    return _result("get_sales_stats", sql, params, run_query(con, sql, params), chart)


def run_sql(con: duckdb.DuckDBPyConnection, sql: str) -> dict:
    safe = check_sql(sql)
    return _result("run_sql", safe, {}, run_query(con, safe))


# --------------------------------------------------------------------------- #
# Registry and specs for the LLM
# --------------------------------------------------------------------------- #
def describe_table(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    """Columns, types and descriptions of one gold/marts table (schema on demand)."""
    schema, _, name = table.strip().lower().partition(".")
    if not name:
        schema, name = "", schema
    sql = """
        SELECT c.table_schema || '.' || c.table_name AS "table", c.column_name, c.data_type,
               c.description
        FROM meta.columns AS c
        WHERE c.table_name = $name AND ($schema = '' OR c.table_schema = $schema)
        ORDER BY c.table_schema, c.ordinal_position
    """
    params = {"schema": schema, "name": name}
    data = run_query(con, sql, params, max_rows=200)
    if not data["row_count"]:
        tables = [r[0] for r in con.sql(
            "SELECT table_schema || '.' || table_name FROM meta.tables ORDER BY 1").fetchall()]
        raise ValueError(f"unknown table '{table}'; available: {', '.join(tables)}")
    return _result("describe_table", sql, params, data)


def list_tables(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    """(schema.table, description) pairs, for the system prompt."""
    return con.sql("SELECT table_schema || '.' || table_name, description "
                   "FROM meta.tables ORDER BY 1").fetchall()


TOOLS: dict[str, Callable[..., dict]] = {
    f.__name__: f for f in (
        search_products, get_price_history, get_price_change, get_category_index,
        rank_categories_by_inflation, rank_price_changes, find_shrinkflation,
        compare_regions, get_sales_stats, rank_promotions, describe_table, run_sql,
    )
}

_REGION = {"type": ["string", "null"], "enum": ["bavaria", "schleswig-holstein", None],
           "description": "Region filter; null for both regions."}
_CATEGORY = {"type": ["string", "null"],
             "description": "Exact category name (German, see the category list); null for all."}
_GTINS = {"type": "array", "items": {"type": "string"},
          "description": "Product gtins, taken from search_products results."}


def _spec(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


TOOL_SPECS: list[dict] = [
    _spec("search_products",
          "Find products by name. Product names are German: translate the user's words to "
          "German product terms first (e.g. 'oat milk' -> 'Haferdrink'). Returns gtins, the "
          "latest known price per region with its date (price_date), and still_sold (false = "
          "no longer listed at the end of the data). Call this before any tool that needs gtins.",
          {"query": {"type": "string", "description": "German search words, e.g. 'Butter' or 'Kerrygold Butter'."},
           "region": _REGION,
           "limit": {"type": "integer", "description": "Max results (default 10)."}},
          ["query"]),
    _spec("get_price_history",
          "Every price period of up to 5 products: price, sale flag, regular price, pack size, "
          "unit price. For 'how did the price of X develop'.",
          {"gtins": _GTINS, "region": _REGION}, ["gtins"]),
    _spec("get_price_change",
          "Overall change of products' regular price between the first and last month they "
          "were seen (shelf price and price per kg/l).",
          {"gtins": _GTINS, "region": _REGION}, ["gtins"]),
    _spec("get_category_index",
          "Monthly price index (first month = 100) for one category, or for all categories "
          "together (the shopping basket) when category is null. For 'how much more expensive "
          "did food / dairy / ... get over time'. Each region is measured against its own "
          "first month, so the index can't tell which region is cheaper: use compare_regions.",
          {"category": _CATEGORY, "region": _REGION}, []),
    _spec("rank_categories_by_inflation",
          "All categories ranked by how much their prices rose since the first month.",
          {"region": _REGION}, []),
    _spec("rank_price_changes",
          "Products with the biggest regular-price increases or decreases between their first "
          "and last month, same pack size only (pack size changes: use find_shrinkflation).",
          {"direction": {"type": "string", "enum": ["increase", "decrease"]},
           "category": _CATEGORY, "region": _REGION,
           "min_months": {"type": "integer", "description": "Only products seen at least this many months (default 6)."},
           "limit": {"type": "integer", "description": "Max results (default 10)."}},
          []),
    _spec("find_shrinkflation",
          "Products whose pack got smaller while the price stayed the same or rose.",
          {"category": _CATEGORY, "region": _REGION,
           "limit": {"type": "integer", "description": "Max results (default 20)."}},
          []),
    _spec("compare_regions",
          "Which region is cheaper or more expensive: compares current regular prices of the "
          "same products in Bavaria and Schleswig-Holstein. Returns a summary row (how many "
          "products are pricier in each region) plus the largest differences. Filter by gtins "
          "or category.",
          {"gtins": {**_GTINS, "type": ["array", "null"]}, "category": _CATEGORY,
           "limit": {"type": "integer", "description": "Max product rows (default 20)."}},
          []),
    _spec("get_sales_stats",
          "Monthly promotions for one category or all categories together (category null): "
          "share_on_sale_pct = share of products on sale, avg_discount_pct = average discount "
          "of those on sale. To rank categories in one month, use run_sql on "
          "marts.mart_sales_monthly.",
          {"category": _CATEGORY, "region": _REGION}, []),
    _spec("rank_promotions",
          "Products ranked by their promotions (sale periods). mode 'most' = on sale most often, "
          "'deepest' = biggest discount, 'never' = never on sale although listed at least "
          "min_days. Per product and region; optional year (2023 = Nov-Dec only, 2025 = until "
          "September), category and region.",
          {"mode": {"type": "string", "enum": ["most", "deepest", "never"]},
           "year": {"type": ["integer", "null"], "description": "Calendar year, e.g. 2024; null for the whole period."},
           "category": _CATEGORY, "region": _REGION,
           "min_days": {"type": "integer", "description": "For mode 'never': listed at least this many days (default 180)."},
           "limit": {"type": "integer", "description": "Max results (default 10)."}},
          []),
    _spec("describe_table",
          "Columns and their meaning for one table. Call before writing SQL for run_sql.",
          {"table": {"type": "string", "description": "e.g. 'gold.fct_price_interval' or 'marts.mart_monthly_prices'."}},
          ["table"]),
    _spec("run_sql",
          "Run your own read-only SQL (DuckDB dialect) when no other tool fits; check columns "
          "with describe_table first. Only SELECT, "
          "only schema-qualified tables in gold.* and marts.*, at most "
          f"{config.MAX_ROWS} rows.",
          {"sql": {"type": "string", "description": "One SELECT statement."}},
          ["sql"]),
]


def call_tool(con: duckdb.DuckDBPyConnection, name: str, arguments: dict[str, Any]) -> dict:
    """Run a tool by name. Errors come back as {'error': ...} so the LLM can react."""
    func = TOOLS.get(name)
    if func is None:
        return {"tool": name, "error": f"Unknown tool '{name}'."}
    try:
        return func(con, **arguments)
    except TypeError as exc:
        return {"tool": name, "error": f"Bad arguments: {exc}"}
    except Exception as exc:  # SqlNotAllowed, QueryTimeout, duckdb errors, ValueError
        return {"tool": name, "error": f"{type(exc).__name__}: {exc}"}


def list_categories(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Primary categories, for the assistant's system prompt."""
    return [r[0] for r in con.sql(
        "SELECT DISTINCT primary_category FROM gold.dim_product "
        "WHERE primary_category IS NOT NULL ORDER BY 1").fetchall()]
