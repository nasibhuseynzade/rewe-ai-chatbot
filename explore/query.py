"""Run SQL against the warehouse and print the results as Markdown tables.

Opens data/warehouse.duckdb read-only, so it is safe to run while other things
are going on. A `bronze` view over the raw Parquet files is available too.

    # a .sql file; sections start with a line "-- ## Title"
    uv run python explore/query.py explore/sql/unit_price_mismatches.sql

    # or a quick inline query
    uv run python explore/query.py "select count(*) from gold.fct_price_interval"

Results of a .sql file are also saved to explore/results/<name>.md, so the file
can be shared as is.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SECTION_RE = re.compile(r"^--\s*##\s*(.+)$", re.MULTILINE)


def to_markdown(columns: list[str], rows: list[tuple], max_rows: int = 200) -> str:
    def cell(v) -> str:
        s = "" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= 120 else s[:117] + "..."

    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"\n_{len(rows) - max_rows} more rows not shown_")
    return "\n".join(lines)


def _has_code(sql: str) -> bool:
    """True if `sql` contains anything besides comments and whitespace."""
    return any(line.strip() and not line.strip().startswith("--") for line in sql.splitlines())


def split_sections(sql: str) -> list[tuple[str, str]]:
    """Split on '-- ## Title' lines; comment-only parts are skipped."""
    parts = SECTION_RE.split(sql)
    sections = []
    if _has_code(parts[0]):
        sections.append(("Query", parts[0]))
    for title, body in zip(parts[1::2], parts[2::2]):
        if _has_code(body):
            sections.append((title.strip(), body))
    return sections


def connect() -> duckdb.DuckDBPyConnection:
    load_dotenv(PROJECT_ROOT / ".env")
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    db = Path(os.getenv("DUCKDB_PATH", data_dir / "warehouse.duckdb"))
    if not db.is_absolute():
        db = PROJECT_ROOT / db
    if not db.exists():
        sys.exit(f"{db} not found. Run dbt build first.")
    con = duckdb.connect(str(db), read_only=True)
    bronze = data_dir / "bronze" / "prices"
    if any(bronze.glob("*.parquet")):
        glob = (bronze / "*.parquet").as_posix().replace("'", "''")
        con.execute(f"CREATE TEMP VIEW bronze AS SELECT * FROM read_parquet('{glob}', union_by_name = true)")
    return con


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    arg = argv[0]
    path = Path(arg)
    is_file = path.suffix == ".sql" and path.exists()
    sql = path.read_text(encoding="utf-8") if is_file else arg

    con = connect()
    out = [f"# {path.stem}\n"] if is_file else []
    for title, body in split_sections(sql):
        try:
            rel = con.sql(body)
            if rel is None:  # statement without a result set
                table = "_ok_"
            else:
                columns, rows = rel.columns, rel.fetchall()
                table = to_markdown(columns, rows) if rows else "_no rows_"
        except duckdb.Error as exc:
            table = f"_query failed: {exc}_"
        section = f"## {title}\n\n{table}\n"
        out.append(section)
        print(section)

    if is_file:
        results = PROJECT_ROOT / "explore" / "results"
        results.mkdir(parents=True, exist_ok=True)
        target = results / f"{path.stem}.md"
        target.write_text("\n".join(out), encoding="utf-8")
        print(f"Saved to {target.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
