"""Build data/serving.duckdb: the small database the chatbot reads.

Copies the gold and marts schemas out of the warehouse (silver and staging stay
behind) and stores the dbt documentation next to them (meta.tables,
meta.columns), so the assistant's schema description travels with the data.

    uv run python -m app.build_serving

Run it after every `dbt build`. The file is written to a temporary name first
and swapped in at the end, so a running app never sees a half-built database.
"""

from __future__ import annotations

import json
import sys

import duckdb

from app import config


def load_dbt_docs() -> tuple[list[tuple], dict[tuple[str, str, str], str]]:
    """(schema, table, description) rows and {(schema, table, column): description}."""
    if not config.DBT_MANIFEST.exists():
        print(f"Warning: {config.DBT_MANIFEST} not found; tables will have no descriptions.")
        return [], {}
    manifest = json.loads(config.DBT_MANIFEST.read_text(encoding="utf-8"))
    tables, columns = [], {}
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        schema, name = node.get("schema"), node.get("alias") or node.get("name")
        if schema not in config.SERVING_SCHEMAS:
            continue
        tables.append((schema, name, " ".join((node.get("description") or "").split())))
        for col_name, col in (node.get("columns") or {}).items():
            columns[(schema, name, col_name)] = " ".join((col.get("description") or "").split())
    return tables, columns


def main() -> int:
    if not config.WAREHOUSE_PATH.exists():
        print(f"{config.WAREHOUSE_PATH} not found. Run dbt build first.")
        return 1

    target = config.SERVING_PATH
    tmp = target.with_name(target.name + ".tmp")
    tmp.unlink(missing_ok=True)

    con = duckdb.connect(str(tmp))
    wh = config.WAREHOUSE_PATH.as_posix().replace("'", "''")
    con.execute(f"ATTACH '{wh}' AS wh (READ_ONLY)")

    schemas = ", ".join(f"'{s}'" for s in config.SERVING_SCHEMAS)
    tables = con.sql(f"""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_catalog = 'wh' AND table_schema IN ({schemas}) AND table_type = 'BASE TABLE'
        ORDER BY 1, 2
    """).fetchall()
    if not tables:
        print("No gold/marts tables found in the warehouse. Run dbt build first.")
        return 1

    for schema in config.SERVING_SCHEMAS:
        con.execute(f"CREATE SCHEMA {schema}")
    for schema, table in tables:
        con.execute(f'CREATE TABLE {schema}."{table}" AS SELECT * FROM wh.{schema}."{table}"')

    # documentation from dbt
    table_docs, column_docs = load_dbt_docs()
    con.execute("CREATE SCHEMA meta")
    con.execute("CREATE TABLE meta.tables (table_schema VARCHAR, table_name VARCHAR, description VARCHAR)")
    con.executemany("INSERT INTO meta.tables VALUES (?, ?, ?)",
                    [t for t in table_docs if (t[0], t[1]) in set(tables)])
    cols = con.sql(f"""
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_catalog = 'wh' AND table_schema IN ({schemas})
        ORDER BY 1, 2, 5
    """).fetchall()
    con.execute("""CREATE TABLE meta.columns (
        table_schema VARCHAR, table_name VARCHAR, column_name VARCHAR,
        data_type VARCHAR, ordinal_position INTEGER, description VARCHAR)""")
    con.executemany(
        "INSERT INTO meta.columns VALUES (?, ?, ?, ?, ?, ?)",
        [(s, t, c, dtype, pos, column_docs.get((s, t, c), "")) for s, t, c, dtype, pos in cols
         if (s, t) in set(tables)],
    )

    con.execute("DETACH wh")
    con.execute("CHECKPOINT")
    summary = con.sql("""
        SELECT schema_name || '.' || table_name AS "table", estimated_size AS rows
        FROM duckdb_tables() ORDER BY schema_name, table_name
    """).fetchall()
    con.close()
    tmp.replace(target)

    print(f"Built {target.relative_to(config.PROJECT_ROOT)} "
          f"({target.stat().st_size / 1e6:.1f} MB)")
    for name, rows in summary:
        print(f"  {name:<40} {rows:>10,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
