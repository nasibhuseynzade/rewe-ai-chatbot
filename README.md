# rewe-ai

Price history of ~20,000 REWE products in two German regions (Bavaria and
Schleswig-Holstein), November 2023 – September 2025: a data pipeline, an
interactive dashboard and an LLM assistant that answers questions about the data.

> Status: step 1 of the roadmap: ingestion and profiling.

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
```

Once the sample looks right, `uv run python ingest/download.py --all` fetches
everything (~1,200 files, ~4 GB uncompressed). The script skips files already in
bronze, so it can be stopped and restarted at any time.

## Project layout

```
ingest/      download + bronze conversion
explore/     profiling queries and reports
transform/   dbt project (silver, gold)          – next
app/         API, dashboard, assistant tools     – later
eval/        assistant evaluation questions      – later
data/        raw / bronze / silver / gold (not in Git)
```

## Roadmap

- [x] Ingestion: download, raw archive, bronze Parquet, manifest
- [x] Profiling report
- [ ] Silver: types, grammage parser, data quality tests (dbt)
- [ ] Gold: products, categories, price intervals, snapshots
- [ ] Dashboard
- [ ] Assistant: tools, embeddings, evaluation set, model comparison (local vs. API)
- [ ] Deployment (Docker, Oracle Cloud VM)

## Data source

Daily snapshots published at [rewe.nicoo.org](https://rewe.nicoo.org/). The source
states no license; this is a non-commercial portfolio project. Product images
are not downloaded or displayed. Not affiliated with REWE.
