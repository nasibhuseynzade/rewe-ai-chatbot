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

Full data: 970 files, 20.2M rows, 57,320 products (28,097 sold in both regions).

- **14% of rows are repeats**: a product is listed once per category, and
  thematic lists (Monats-Highlights, Regional, Grillsaison, Bewusste Ernährung)
  overlap with departments. Repeats collapse into one row per product and day;
  categories become a many-to-many table. In 864 of 17.4M product-days the
  repeats disagree on the price (changed mid-scrape); the lower price is kept
  and the row flagged.
- **Leading zeros were lost upstream**: 11- and 12-digit EANs pass the GS1 check
  digit once left-padded to 13 digits. 440 rows with `NA` as barcode and price
  are rejected in staging (a test watches the reject rate).
- **Half of all products never changed price** in 22 months, so storing intervals
  instead of daily rows shrinks the fact table from ~17M rows to a fraction.
- **40+ grammage formats**, from `250g (1 kg = 3,16 €)` to `4x6x0,33l`,
  `1 Stück ca. 300 g`, `84x1mm` and `0,01m3`. Every parsed size is cross-checked against two
  independent sources: the unit price printed by the source and the size in the
  product name. This caught an upstream quirk: `6x480g` often means 6 items
  totalling 480 g (the name says `6x80g`), while `6x1,50l` really is 9 litres.
  The size is reconciled accordingly, and each price row carries a
  `unit_price_status` (match / multipack_total / from_name / conflict / unverified).
  In the two-week sample only 0.2% of rows disagreed before reconciliation.
- **The source was scraped 40 products per page.** 99.5% of row counts per
  category and day are multiples of 40, and ~27k times a product appeared twice
  in the same category (overlapping pages). So a product missing for a day is
  not necessarily delisted: 97.2% of reappearances are on the next snapshot,
  and gaps of up to 3 missed snapshots are bridged. Product counts per category
  should be read as approximate.
- **Some scrapes are partial**: Bavaria's last file (2025-09-09) stops after
  "Küche & Haushalt". Snapshots well below the surrounding median are flagged
  `is_partial`, and "current price" tolerates a few missing snapshots.
- **About 27% of days have no file** (970 files for 665 days × 2 regions).
  Consecutive *snapshots*, not calendar days, define continuity.

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
everything (970 files, Nov 2023 – Sep 2025). The script skips files already in
bronze, so it can be stopped and restarted at any time.

Ad-hoc questions go through the query helper (read-only, prints Markdown):

```bash
uv run python explore/query.py "select region, count(*) from gold.snapshots group by all"
uv run python explore/query.py explore/sql/unit_price_mismatches.sql
```

## Project layout

```
ingest/      download + bronze conversion
explore/     profiling, query helper, analysis SQL (explore/sql)
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
