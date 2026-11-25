"""Insight cards for the top of the page: computed from the marts, no LLM involved.

Each card has a headline, a small chart, the SQL behind it (shown in the UI, like
for chat answers) and a follow-up question the visitor can send to the chat.

    uv run python -m app.insights      # print the cards as JSON
"""

from __future__ import annotations

import json
import sys

import duckdb

from app import db
from app.db import run_query

REGION_LABEL = {"bavaria": "Bavaria", "schleswig-holstein": "Schleswig-Holstein"}

SQL = {
    "basket": """
        SELECT region, month, price_index
        FROM marts.mart_category_price_index
        WHERE category = 'All categories'
        ORDER BY region, month""",
    "categories": """
        SELECT category, price_index - 100 AS change_pct
        FROM marts.mart_category_price_index
        WHERE region = 'bavaria' AND category <> 'All categories'
        QUALIFY row_number() OVER (PARTITION BY category ORDER BY month DESC) = 1
        ORDER BY change_pct DESC""",
    "risers": """
        SELECT name, max(first_price) AS first_price, max(last_price) AS last_price,
               max(price_change_pct) AS price_change_pct
        FROM marts.mart_product_price_change
        WHERE same_pack_size AND months_observed >= 12 AND first_price >= 1
          AND category <> 'Obst & Gemüse'
        GROUP BY gtin, name
        ORDER BY price_change_pct DESC, name
        LIMIT 5""",
    "direction": """
        SELECT round(100.0 * count(*) FILTER (WHERE last_price > first_price) / count(*), 1) AS pricier_pct,
               round(100.0 * count(*) FILTER (WHERE last_price = first_price) / count(*), 1) AS unchanged_pct,
               round(100.0 * count(*) FILTER (WHERE last_price < first_price) / count(*), 1) AS cheaper_pct,
               count(*) AS products
        FROM marts.mart_product_price_change
        WHERE region = 'bavaria' AND same_pack_size AND months_observed >= 12""",
    "shrinkflation": """
        SELECT name, region, changed_on, old_pack_size, new_pack_size, old_price, new_price,
               unit_price_increase_pct
        FROM marts.mart_shrinkflation
        ORDER BY unit_price_increase_pct DESC""",
    "regions": """
        SELECT count(*) AS products,
               count(*) FILTER (WHERE more_expensive_in = 'same') AS same_price,
               count(*) FILTER (WHERE more_expensive_in = 'bavaria') AS pricier_in_bavaria,
               count(*) FILTER (WHERE more_expensive_in = 'schleswig-holstein') AS pricier_in_sh
        FROM marts.mart_region_compare""",
}


def _q(con: duckdb.DuckDBPyConnection, name: str) -> list[dict]:
    return run_query(con, SQL[name], max_rows=500)["rows"]


def _sql(name: str) -> str:
    return " ".join(SQL[name].split())


def build_cards(con: duckdb.DuckDBPyConnection) -> list[dict]:
    cards = []

    basket = _q(con, "basket")
    latest = {r["region"]: r for r in basket}  # rows are ordered by month
    if latest:
        first_month, last_month = basket[0]["month"], max(r["month"] for r in basket)
        parts = [f"{REGION_LABEL[reg]} {r['price_index'] - 100:+.1f}%" for reg, r in sorted(latest.items())]
        cards.append({
            "id": "basket",
            "title": "Shopping basket",
            "headline": parts[0].split(" ", 1)[1] if len(parts) == 1 else " · ".join(parts),
            "detail": f"Regular prices of all products, {first_month[:7]} to {last_month[:7]} "
                      "(chained price index, first month = 100).",
            "chart": {"type": "line", "x": "month", "y": "price_index", "series": "region", "rows": basket},
            "sql": _sql("basket"),
            "ask": "How much more expensive did groceries get, and which categories drove it?",
        })

    cats = _q(con, "categories")
    if cats:
        top = cats[0]
        cards.append({
            "id": "categories",
            "title": "Biggest movers by category",
            "headline": f"{top['category']} {top['change_pct']:+.1f}%",
            "detail": "Price change since the first month, Bavaria. "
                      f"Smallest: {cats[-1]['category']} ({cats[-1]['change_pct']:+.1f}%, seasonal produce).",
            "chart": {"type": "bar", "x": "category", "y": "change_pct", "series": None, "rows": cats},
            "sql": _sql("categories"),
            "ask": f"Why did {top['category']} get so much more expensive? Show me the products.",
        })

    risers = _q(con, "risers")
    if risers:
        r0 = risers[0]
        cards.append({
            "id": "risers",
            "title": "Steepest price increases",
            "headline": f"{r0['name']}: {r0['first_price']:.2f} € → {r0['last_price']:.2f} €",
            "detail": "Same pack size, sold for at least 12 months. Cocoa and chocolate dominate.",
            "chart": {"type": "bar", "x": "name", "y": "price_change_pct", "series": None, "rows": risers},
            "sql": _sql("risers"),
            "ask": "Which chocolate and cocoa products got more expensive, and by how much?",
        })

    d = _q(con, "direction")
    if d and d[0]["products"]:
        d = d[0]
        cards.append({
            "id": "direction",
            "title": "Up, down or unchanged",
            "headline": f"{d['pricier_pct']:.0f}% pricier · {d['cheaper_pct']:.0f}% cheaper",
            "detail": f"{d['products']:,} products in Bavaria with the same pack size, sold for at "
                      f"least 12 months; {d['unchanged_pct']:.0f}% kept their price.",
            "chart": {"type": "bar", "x": "label", "y": "pct", "series": None, "rows": [
                {"label": "pricier", "pct": d["pricier_pct"]},
                {"label": "unchanged", "pct": d["unchanged_pct"]},
                {"label": "cheaper", "pct": d["cheaper_pct"]}]},
            "sql": _sql("direction"),
            "ask": "Which products got cheaper the most?",
        })

    shrink = _q(con, "shrinkflation")
    if shrink:
        s0 = shrink[0]
        cards.append({
            "id": "shrinkflation",
            "title": "Shrinkflation",
            "headline": f"{len(shrink)} cases found",
            "detail": f"Example: {s0['name']}, {s0['old_pack_size']} → {s0['new_pack_size']}, "
                      f"{s0['old_price']:.2f} € → {s0['new_price']:.2f} € "
                      f"({s0['unit_price_increase_pct']:+.0f}% per kg).",
            "chart": {"type": "table", "rows": shrink[:5]},
            "sql": _sql("shrinkflation"),
            "ask": "Show me all shrinkflation cases.",
        })

    reg = _q(con, "regions")
    if reg and reg[0]["products"]:
        g = reg[0]
        same = 100 * g["same_price"] / g["products"]
        cards.append({
            "id": "regions",
            "title": "Bavaria vs Schleswig-Holstein",
            "headline": f"{same:.0f}% same price",
            "detail": f"Of {g['products']:,} products sold in both regions, {g['pricier_in_bavaria']:,} "
                      f"cost more in Bavaria and {g['pricier_in_sh']:,} in Schleswig-Holstein.",
            "chart": {"type": "bar", "x": "label", "y": "products", "series": None, "rows": [
                {"label": "same price", "products": g["same_price"]},
                {"label": "pricier in Bavaria", "products": g["pricier_in_bavaria"]},
                {"label": "pricier in Schleswig-Holstein", "products": g["pricier_in_sh"]}]},
            "sql": _sql("regions"),
            "ask": "Which products have the biggest price difference between the two regions?",
        })
    return cards


def main() -> int:
    con = db.connect()
    try:
        print(json.dumps(build_cards(con), ensure_ascii=False, indent=2, default=str))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
