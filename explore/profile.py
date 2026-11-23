"""First look at the bronze data: what does it really contain?

Runs a set of profiling queries over data/bronze/prices/*.parquet and writes
the results to explore/profile_report.md (and prints them).

The answers decide how the silver layer is built: how to parse grammage,
whether EANs repeat inside one file, which days are missing, and so on.

    uv run python explore/profile.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT = PROJECT_ROOT / "explore" / "profile_report.md"

# (title, explanation, SQL). Every query reads from the `bronze` view.
CHECKS: list[tuple[str, str, str]] = [
    (
        "Overview per region",
        "Files, rows and date range. Big swings in rows per file can mean partial scrapes.",
        """
        SELECT region,
               count(DISTINCT snapshot_date)              AS files,
               count(*)                                   AS rows,
               min(snapshot_date)                         AS first_day,
               max(snapshot_date)                         AS last_day,
               round(count(*) / count(DISTINCT snapshot_date)) AS avg_rows_per_file
        FROM bronze GROUP BY region ORDER BY region
        """,
    ),
    (
        "Smallest and largest files",
        "Outliers in row count. A file far below the average is probably incomplete.",
        """
        WITH f AS (SELECT region, snapshot_date, count(*) AS rows FROM bronze GROUP BY ALL),
             s AS (SELECT *, avg(rows) OVER (PARTITION BY region) AS region_avg FROM f)
        (SELECT 'smallest' AS kind, region, snapshot_date, rows,
                round(100.0 * rows / region_avg) AS pct_of_avg
         FROM s ORDER BY rows ASC LIMIT 5)
        UNION ALL
        (SELECT 'largest', region, snapshot_date, rows, round(100.0 * rows / region_avg)
         FROM s ORDER BY rows DESC LIMIT 5)
        """,
    ),
    (
        "Missing days",
        "Days without a file between a region's first and last day. "
        "A product absent on these days is unknown, not delisted.",
        """
        WITH bounds AS (SELECT region, min(snapshot_date) AS lo, max(snapshot_date) AS hi
                        FROM bronze GROUP BY region),
             calendar AS (SELECT region, unnest(generate_series(lo, hi, INTERVAL 1 DAY))::DATE AS d
                          FROM bounds),
             present AS (SELECT DISTINCT region, snapshot_date AS d FROM bronze)
        SELECT c.region,
               count(*)                                   AS missing_days,
               string_agg(strftime(c.d, '%Y-%m-%d'), ', ' ORDER BY c.d)
                   FILTER (WHERE c.d IS NOT NULL)         AS dates
        FROM calendar c ANTI JOIN present p USING (region, d)
        GROUP BY c.region ORDER BY c.region
        """,
    ),
    (
        "Duplicate EANs inside one file",
        "If one EAN appears several times in the same day/region, the product is probably "
        "listed in more than one category (then category is many-to-many).",
        """
        WITH d AS (
            SELECT region, snapshot_date, ean, count(*) AS n,
                   count(DISTINCT category) AS categories,
                   count(DISTINCT price)    AS prices,
                   count(DISTINCT name)     AS names
            FROM bronze GROUP BY ALL HAVING count(*) > 1
        )
        SELECT count(*)                         AS duplicate_groups,
               sum(n - 1)                       AS extra_rows,
               count(*) FILTER (categories > 1) AS differ_in_category,
               count(*) FILTER (prices > 1)     AS differ_in_price,
               count(*) FILTER (names > 1)      AS differ_in_name
        FROM d
        """,
    ),
    (
        "Duplicate EAN examples",
        "A few concrete cases, latest snapshot first.",
        """
        SELECT region, snapshot_date, ean,
               string_agg(DISTINCT category, ' | ') AS categories,
               string_agg(DISTINCT price, ' | ')    AS prices,
               any_value(name)                      AS name
        FROM bronze
        GROUP BY region, snapshot_date, ean HAVING count(*) > 1
        ORDER BY snapshot_date DESC, region LIMIT 10
        """,
    ),
    (
        "EAN shape",
        "EANs must be stored as text. Length 8 and 13 are normal (EAN-8 / EAN-13); "
        "anything else, or non-digits, needs a look.",
        """
        SELECT length(ean) AS ean_length,
               regexp_matches(ean, '^[0-9]+$') AS only_digits,
               count(*) AS rows,
               count(DISTINCT ean) AS distinct_eans,
               any_value(ean) AS example
        FROM bronze GROUP BY ALL ORDER BY rows DESC
        """,
    ),
    (
        "Distinct products",
        "How many products exist, and how many appear in both regions.",
        """
        WITH per_ean AS (SELECT ean, count(DISTINCT region) AS regions FROM bronze GROUP BY ean)
        SELECT count(*)                          AS distinct_eans,
               count(*) FILTER (regions > 1)     AS in_both_regions,
               count(*) FILTER (regions = 1)     AS in_one_region
        FROM per_ean
        """,
    ),
    (
        "Price column",
        "Prices are text in bronze. Values that fail to parse as a number need handling.",
        """
        SELECT count(*)                                                AS rows,
               count(*) FILTER (price IS NULL OR trim(price) = '')     AS empty,
               count(*) FILTER (try_cast(price AS DECIMAL(10,2)) IS NULL
                                AND price IS NOT NULL AND trim(price) <> '') AS unparseable,
               min(try_cast(price AS DECIMAL(10,2)))                   AS min_price,
               max(try_cast(price AS DECIMAL(10,2)))                   AS max_price,
               any_value(price) FILTER (try_cast(price AS DECIMAL(10,2)) IS NULL) AS bad_example
        FROM bronze
        """,
    ),
    (
        "How often prices change",
        "Per product and region: number of distinct prices over the whole period. "
        "This shows how much the price-interval model will compress the data.",
        """
        WITH p AS (SELECT ean, region, count(DISTINCT price) AS distinct_prices
                   FROM bronze GROUP BY ALL)
        SELECT distinct_prices, count(*) AS products,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
        FROM p GROUP BY ALL ORDER BY distinct_prices LIMIT 15
        """,
    ),
    (
        "Same EAN, different names",
        "Products renamed over time. Decides whether dim_product needs name history.",
        """
        WITH n AS (SELECT ean, count(DISTINCT name) AS names, string_agg(DISTINCT name, ' | ') AS all_names
                   FROM bronze GROUP BY ean)
        SELECT count(*) FILTER (names > 1) AS eans_with_several_names,
               any_value(all_names) FILTER (names > 1) AS example
        FROM n
        """,
    ),
    (
        "Sale column",
        "Expected values: True / False.",
        "SELECT sale, count(*) AS rows FROM bronze GROUP BY ALL ORDER BY rows DESC",
    ),
    (
        "Brand column",
        "'NA' (and empty) should become NULL in silver.",
        """
        SELECT CASE WHEN brand IS NULL THEN '<null>'
                    WHEN trim(brand) = '' THEN '<empty>'
                    WHEN brand = 'NA' THEN 'NA'
                    ELSE 'real brand' END AS brand_kind,
               count(*) AS rows
        FROM bronze GROUP BY ALL ORDER BY rows DESC
        """,
    ),
    (
        "Top brands",
        "Most frequent brands on the latest snapshot.",
        """
        SELECT brand, count(*) AS products
        FROM bronze WHERE snapshot_date = (SELECT max(snapshot_date) FROM bronze)
        GROUP BY ALL ORDER BY products DESC LIMIT 15
        """,
    ),
    (
        "Categories",
        "Products per category on each region's latest snapshot.",
        """
        WITH latest AS (SELECT region, max(snapshot_date) AS d FROM bronze GROUP BY region)
        SELECT b.category, b.region, count(*) AS products
        FROM bronze b JOIN latest l ON b.region = l.region AND b.snapshot_date = l.d
        GROUP BY ALL ORDER BY b.category, b.region
        """,
    ),
    (
        "Grammage patterns",
        "Numbers replaced by N, so we can see which formats the parser must handle.",
        r"""
        SELECT regexp_replace(grammage, '[0-9]+([.,][0-9]+)?', 'N', 'g') AS pattern,
               count(*) AS rows,
               any_value(grammage) AS example
        FROM bronze GROUP BY ALL ORDER BY rows DESC LIMIT 40
        """,
    ),
    (
        "Unit price inside grammage",
        "Share of rows with a '(1 kg = 3,96 €)'-style unit price, by base unit.",
        r"""
        SELECT coalesce(nullif(regexp_extract(grammage, '\(\s*1\s*([^=\s]+)\s*=', 1), ''), '<none>') AS base_unit,
               count(*) AS rows,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct,
               any_value(grammage) AS example
        FROM bronze GROUP BY ALL ORDER BY rows DESC
        """,
    ),
    (
        "Image column",
        "Only checked, not used: we won't hotlink product images on a public site.",
        """
        SELECT count(*) FILTER (image IS NULL OR trim(image) = '') AS empty_images,
               count(DISTINCT regexp_extract(image, '^(https?://[^/]+)', 1)) AS image_hosts
        FROM bronze
        """,
    ),
]


def to_markdown(columns: list[str], rows: list[tuple]) -> str:
    def cell(v) -> str:
        s = "" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= 120 else s[:117] + "..."

    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    files = sorted((data_dir / "bronze" / "prices").glob("*.parquet"))
    if not files:
        print("No bronze files yet. Run ingest/download.py first.")
        return 1

    con = duckdb.connect()
    glob = (data_dir / "bronze" / "prices" / "*.parquet").as_posix().replace("'", "''")
    con.execute(f"CREATE VIEW bronze AS SELECT * FROM read_parquet('{glob}', union_by_name = true)")

    out = [f"# Bronze profile\n\n{len(files)} files in `data/bronze/prices`.\n"]
    for title, why, sql in CHECKS:
        try:
            rel = con.sql(sql)
            columns, rows = rel.columns, rel.fetchall()
            body = to_markdown(columns, rows) if rows else "_no rows_"
        except duckdb.Error as exc:
            body = f"_query failed: {exc}_"
        section = f"## {title}\n\n{why}\n\n{body}\n"
        out.append(section)
        print(section)

    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"Report written to {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
