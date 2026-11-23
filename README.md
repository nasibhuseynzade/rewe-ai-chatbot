# rewe-ai

Price history of ~20,000 REWE products in two German regions (Bavaria and
Schleswig-Holstein), November 2023 – September 2025: a data pipeline, an
interactive dashboard and an LLM assistant that answers questions about the data.

> Status: ingestion, profiling and the silver/gold layers (dbt) are in place.

## Architecture (planned)

```
rewe.nicoo.org (daily CSV per region)
        │  ingest/download.py
        ▼
raw      gzip copies of the original files
bronze   Parquet, all columns as text + lineage (snapshot_date, region, source_file)
        │  dbt (dbt-duckdb)
        ▼
silver   typed and parsed: prices as DECIMAL, EAN as text, grammage → pack size + unit price
gold     dim_product · product_category · fct_price_interval · snapshots
        │
        ├── dashboard (price trends, regional comparison, sales, shrinkflation)
        └── assistant: tools (SQL on gold views, product search with embeddings),
            read-only DuckDB, evaluated on a fixed question set
```

Design notes:

- **Prices are stored as intervals, not daily rows.** A product's price rarely
  changes, so `fct_price_interval (ean, region, price, on_sale, valid_from, valid_to)`
  replaces tens of millions of repeated daily rows.
- **Missing days are tracked explicitly** (`snapshots`), so a missing source file is
  never mistaken for a delisted product.
- **EANs are text** (leading zeros, EAN-8 and EAN-13), **prices are DECIMAL**, never float.

## What the data profile showed

From a two-week sample (30 files, ~692k rows):

- **17% of rows are repeats**: a product is listed once per category, and
  thematic lists (Monats-Highlights, Regional, Grillsaison, Bewusste Ernährung)
  overlap with departments. Price never differs between repeats, so they collapse
  into one row per product and day; categories become a many-to-many table.
- **Leading zeros were lost upstream**: 11- and 12-digit EANs pass the GS1 check
  digit once left-padded to 13 digits.
- **85% of products kept one price** over two weeks, so storing intervals instead of
  daily rows compresses the fact table by an order of magnitude.
- **28 grammage formats**, from `250g (1 kg = 3,16 €)` to `4x6x0,33l` and
  `1 Stück ca. 300 g`. The parser is validated against the unit price printed in
  the source.
- **Row counts per category are almost always multiples of 40**, which suggests
  the source scraped 40 products per page. A product missing for a day is
  therefore not necessarily delisted; short gaps are bridged.

## Gold tables

| table | grain | use |
|---|---|---|
| `gold.dim_product` | product (gtin) | name, brand, primary category, parsed pack size |
| `gold.fct_price_interval` | product × region × period | price history, sales, unit prices, shrinkflation |
| `gold.product_category` | product × region × category | category membership over time |
| `gold.snapshots` | day × region | which days exist, products per day |

## Quickstart

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                      # create .venv and install dependencies
cp .env.example .env         # Windows PowerShell: copy .env.example .env

# 1. See what is available
uv run python ingest/download.py --list

# 2. Download a two-week sample
uv run python ingest/download.py --start 2025-08-25 --end 2025-09-08

# 3. Profile the data → explore/profile_report.md
uv run python explore/profile.py

# 4. Build silver + gold and run the data tests → data/warehouse.duckdb
uv run dbt build --project-dir transform --profiles-dir transform
```

Run all commands from the project root.

Once the sample looks right, `uv run python ingest/download.py --all` fetches
everything (~1,200 files, ~4 GB uncompressed). The script skips files already in
bronze, so it can be stopped and restarted at any time.

## Project layout

```
ingest/      download + bronze conversion
explore/     profiling queries and reports
transform/   dbt project (staging, silver, gold + tests)
app/         API, dashboard, assistant tools     – later
eval/        assistant evaluation questions      – later
data/        raw / bronze / silver / gold (not in Git)
```

## Roadmap

- [x] Ingestion: download, raw archive, bronze Parquet, manifest
- [x] Profiling report
- [x] Silver: types, grammage parser, data quality tests (dbt)
- [x] Gold: products, categories, price intervals, snapshots
- [ ] Dashboard
- [ ] Assistant: tools, embeddings, evaluation set, model comparison (local vs. API)
- [ ] Deployment (Docker, Oracle Cloud VM)

## Data source

Daily snapshots published at [rewe.nicoo.org](https://rewe.nicoo.org/). The source
states no license; this is a non-commercial portfolio project. Product images
are not downloaded or displayed. Not affiliated with REWE.
