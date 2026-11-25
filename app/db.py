"""Read-only access to the serving database.

Every connection is locked down:
  - opened read_only: no writes of any kind
  - enable_external_access = false: no reading files, no ATTACH, no extensions
  - lock_configuration: the settings above can't be changed by a query
  - memory and thread limits
Every query has a timeout and a row limit.
"""

from __future__ import annotations

import datetime as dt
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from app import config


class QueryTimeout(Exception):
    pass


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    path = path or config.SERVING_PATH
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: uv run python -m app.build_serving")
    con = duckdb.connect(
        str(path),
        read_only=True,
        config={
            "enable_external_access": False,
            "memory_limit": config.DB_MEMORY_LIMIT,
            "threads": config.DB_THREADS,
        },
    )
    con.execute("SET lock_configuration = true")
    return con


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def run_query(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    params: dict[str, Any] | None = None,
    max_rows: int | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Run a query with a timeout; return columns, rows (as dicts) and truncation info."""
    max_rows = max_rows or config.MAX_ROWS
    timeout_s = timeout_s or config.QUERY_TIMEOUT_S
    timed_out = threading.Event()

    def _interrupt() -> None:
        timed_out.set()
        con.interrupt()

    timer = threading.Timer(timeout_s, _interrupt)
    timer.start()
    try:
        cur = con.execute(sql, params or {})
        columns = [d[0] for d in cur.description]
        raw = cur.fetchmany(max_rows + 1)
    except duckdb.InterruptException as exc:
        raise QueryTimeout(f"query took longer than {timeout_s:.0f}s") from exc
    except duckdb.Error:
        if timed_out.is_set():
            raise QueryTimeout(f"query took longer than {timeout_s:.0f}s")
        raise
    finally:
        timer.cancel()

    truncated = len(raw) > max_rows
    rows = [dict(zip(columns, (_jsonable(v) for v in r))) for r in raw[:max_rows]]
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}
