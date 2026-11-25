"""Try the chatbot's tools from the terminal, without an LLM.

    uv run python -m app.cli tools                                   # list tools
    uv run python -m app.cli call search_products '{"query": "Butter"}'
    uv run python -m app.cli sql "select count(*) from gold.dim_product"
    uv run python -m app.cli demo                                    # a few sample calls
"""

from __future__ import annotations

import json
import sys

from app import db
from app.tools import TOOL_SPECS, call_tool


def to_markdown(columns: list[str], rows: list[dict], max_rows: int = 30) -> str:
    def cell(v) -> str:
        s = "" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= 60 else s[:57] + "..."

    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(cell(r.get(c)) for c in columns) + " |" for r in rows[:max_rows]]
    if len(rows) > max_rows:
        lines.append(f"_{len(rows) - max_rows} more rows_")
    return "\n".join(lines)


def show(result: dict) -> None:
    print(f"\n### {result.get('tool')}")
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    print(f"SQL: {result['sql'][:300]}{'...' if len(result['sql']) > 300 else ''}")
    if result.get("params"):
        print(f"params: {json.dumps(result['params'], ensure_ascii=False)}")
    print(f"rows: {result['row_count']}{' (truncated)' if result['truncated'] else ''}"
          f"   chart: {json.dumps(result['chart'], ensure_ascii=False) if result['chart'] else '-'}\n")
    if result["rows"]:
        print(to_markdown(result["columns"], result["rows"]))


DEMO = [
    ("search_products", {"query": "Haferdrink"}),
    ("get_category_index", {"region": "bavaria"}),
    ("rank_categories_by_inflation", {"region": "bavaria"}),
    ("rank_price_changes", {"direction": "increase", "limit": 5, "min_months": 3}),
    ("find_shrinkflation", {}),
    ("compare_regions", {"limit": 5}),
    ("get_sales_stats", {"region": "bavaria"}),
    ("run_sql", {"sql": "select primary_category, count(*) as products from gold.dim_product "
                        "group by 1 order by 2 desc"}),
]


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "tools":
        for spec in TOOL_SPECS:
            f = spec["function"]
            params = ", ".join(f["parameters"]["properties"])
            print(f"- {f['name']}({params})\n    {f['description']}")
        return 0

    con = db.connect()
    if cmd == "call" and len(argv) >= 2:
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        show(call_tool(con, argv[1], args))
    elif cmd == "sql" and len(argv) == 2:
        show(call_tool(con, "run_sql", {"sql": argv[1]}))
    elif cmd == "demo":
        for name, args in DEMO:
            show(call_tool(con, name, args))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
