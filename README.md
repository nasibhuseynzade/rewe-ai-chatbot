# Rewe AI Chatbot

Price history of about 57,000 REWE online-shop products in two German regions
(Bavaria and Schleswig-Holstein), November 2023 to September 2025, and a chatbot
that answers questions about it. Every answer comes with the table, chart and SQL
it is based on.

Live: [nasib.tech/projects/rewe](https://nasib.tech/projects/rewe/)

Unofficial project, not affiliated with REWE. Data from [rewe.nicoo.org](https://rewe.nicoo.org/).

## Architecture

```
rewe.nicoo.org (daily CSV per region)
   |  ingest/download.py
   v
raw       gzip copies of the original files
bronze    Parquet, all columns as text + lineage (snapshot_date, region, source_file)
   |  dbt (dbt-duckdb), data/warehouse.duckdb
   v
staging   typed views, GTIN normalisation and check digit
silver    one row per product and day, parsed pack sizes, pack size reconciliation
gold      dim_product, product_category, fct_price_interval, snapshots
marts     price index, monthly prices, price changes, promotions, shrinkflation, regions
   |  app/build_serving.py
   v
serving.duckdb   gold + marts + column docs, read-only
   |
FastAPI (Docker, Oracle Cloud VM, behind Caddy)
   |  agent loop with 12 tools, SQL guard
   |  LLM: Cloudflare Workers AI (Gemma 4), falling back to Groq and Gemini
   v
nasib.tech (GitHub Pages): insight cards + chat
```

Design notes:

- **Prices are stored as intervals, not daily rows.** A price rarely changes, so
  `fct_price_interval (gtin, region, price, on_sale, valid_from, valid_to)` replaces
  17 million repeated daily rows with about 632,000 intervals.
- **Missing days are tracked explicitly** (`snapshots`), so a missing source file is
  never mistaken for a delisted product. Days without any data are bridged with the
  previous regular price (see below).
- **GTINs are text** (leading zeros, EAN-8 and EAN-13), **prices are DECIMAL**, never float.

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
- **Half of all products never changed price** in 22 months.
- **40+ grammage formats**, from `250g (1 kg = 3,16 €)` to `4x6x0,33l`,
  `1 Stück ca. 300 g`, `84x1mm` and `0,01m3`. Every parsed size is cross-checked against two
  independent sources: the unit price printed by the source and the size in the
  product name. This caught an upstream quirk: `6x480g` often means 6 items
  totalling 480 g (the name says `6x80g`), while `6x1,50l` really is 9 litres.
  The size is reconciled accordingly, and each price row carries a
  `unit_price_status` (match / unit_scale_fixed / multipack_total / from_name / conflict / unverified).
- **Pack sizes contain typos** such as `1000kg` for `1000g` or `1ml` for `1l`.
  Shrinkflation only counts verified pack sizes and content drops between 3% and 50%,
  which cut 66 raw candidates to 14 real cases.
- **The source was scraped 40 products per page.** 99.5% of row counts per
  category and day are multiples of 40, and about 27k times a product appeared twice
  in the same category (overlapping pages). So a product missing for a day is
  not necessarily delisted: 97.2% of reappearances are on the next snapshot,
  and gaps of up to 3 missed snapshots are bridged.
- **Some scrapes are partial**: Bavaria's last file (2025-09-09) stops after
  "Küche & Haushalt". Snapshots well below the surrounding median are flagged
  `is_partial`.
- **There are no files from 13 April to 23 August 2024** and none for two weeks in
  August 2025. A product listed on both sides of such a gap keeps its previous
  regular price, not on sale, for the missing days (`filled_days` in
  `fct_price_interval` counts them). Products that were really absent while
  snapshots exist are not filled.

## Gold tables

| table | grain | use |
|---|---|---|
| `gold.dim_product` | product (gtin) | name, brand, primary category, parsed pack size |
| `gold.fct_price_interval` | product × region × period | price history, sales, unit prices |
| `gold.product_category` | product × region × category | category membership over time |
| `gold.snapshots` | day × region | which days exist, products per day |

## Marts (pre-computed answers)

| table | use |
|---|---|
| `marts.mart_monthly_prices` | one regular price per product, region and month |
| `marts.mart_category_price_index` | monthly price index per category (chained Jevons, first month = 100) |
| `marts.mart_product_price_change` | first vs. last price per product, same pack size flag |
| `marts.mart_product_promotions` | promotions per product and year: count, days on sale, deepest discount |
| `marts.mart_shrinkflation` | smaller pack, same or higher price |
| `marts.mart_region_compare` | Bavaria vs. Schleswig-Holstein, same product |
| `marts.mart_sales_monthly` | share of products on sale, average discount, per category |

## Chatbot backend

The model never touches the database directly. It calls **tools**
(`app/tools.py`): parameterised queries for the common questions (product search,
price history and change, price index, rankings, promotions, shrinkflation, regions),
plus `describe_table` and `run_sql` for everything else. All of them run against
`data/serving.duckdb`.

Two layers of protection for model-written SQL:

1. `app/sql_guard.py` (sqlglot): one SELECT only, only `gold.*` / `marts.*`
   tables, no file / system / metadata functions, LIMIT enforced.
2. The connection itself (`app/db.py`): read-only, external access disabled,
   configuration locked, memory / thread limits, query timeout.

Other parts:

- `app/llm.py`: one client for OpenAI-compatible APIs. Providers are tried in the
  order of `LLM_PROVIDERS`; one that fails with a rate limit, outage or timeout rests
  for two minutes.
- `app/agent.py`: the tool loop. The model sees the first 20 rows of each result,
  the page gets all of them. Answers that used no tool and run long are replaced,
  so the bot stays on topic.
- `app/prompt.py`: the system prompt, built from the serving database (data period,
  categories, table descriptions).
- `app/api.py`: FastAPI with `/chat`, `/insights` and `/health`, per-IP and daily
  limits, CORS for the website. The log keeps questions, tokens and latency, no IPs.
- `eval/cases.toml` + `app/evaluate.py`: 45 questions in English, German and Turkish.
  Each run scores tool choice and quoted numbers per model and writes a scorecard to
  `eval/results/`.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). Run all commands from the project root.

```bash
uv sync                      # create .venv and install dependencies
cp .env.example .env         # add at least one LLM key

# 1. Download a two-week sample (or --all for everything, about 970 files)
uv run python ingest/download.py --start 2025-08-25 --end 2025-09-08

# 2. Profile the raw data, written to explore/profile_report.md
uv run python explore/profile.py

# 3. Build staging, silver, gold and marts and run the data tests
uv run dbt build --project-dir transform --profiles-dir transform

# 4. Build the read-only database the chatbot uses
uv run python -m app.build_serving

# 5. Check the LLM keys, then ask questions in the terminal
uv run python -m app.llm_ping
uv run python -m app.ask "Which category got the most expensive?"

# 6. Run the API locally (open http://localhost:8000/docs)
uv run uvicorn app.api:app --port 8000

# 7. Score a model on the evaluation set
uv run python -m app.evaluate --providers cloudflare
```

The download script skips files already in bronze, so it can be stopped and
restarted at any time. Ad-hoc questions go through the query helper:

```bash
uv run python explore/query.py "select region, count(*) from gold.snapshots group by all"
uv run python explore/query.py explore/sql/unit_price_mismatches.sql
```

## Deployment

The API runs as one Docker container next to an existing Caddy reverse proxy. The
data pipeline runs on a laptop, and only its output, `data/serving.duckdb`, is
copied to the server and mounted read-only.

```bash
# on the server
git clone https://github.com/nasibhuseynzade/rewe-ai-chatbot.git && cd rewe-ai-chatbot
mkdir -p data                   # then copy serving.duckdb here, e.g. with scp from the laptop
cp .env.example .env            # LLM keys, LLM_PROVIDERS=cloudflare,groq,gemini, CADDY_NETWORK
docker compose up -d --build
# add deploy/Caddyfile.snippet to the Caddyfile and reload Caddy
```

The image contains only the API dependencies (`requirements-api.txt`, no dbt) and
runs as an unprivileged user with one worker, because the rate limiter keeps its
counters in memory. After copying a new `serving.duckdb`: `docker compose restart rewe-api`.

## Project layout

```
ingest/      download + bronze conversion
explore/     profiling, query helper, analysis SQL (explore/sql)
transform/   dbt project: staging, silver, gold, marts, tests
app/         backend: serving DB, tools, SQL guard, LLM client, agent, API
eval/        evaluation questions and scorecards
deploy/      Caddy config for the server
data/        raw, bronze and DuckDB files (not in Git)
```

## Data source

Daily snapshots published at [rewe.nicoo.org](https://rewe.nicoo.org/). The source
states no license; this is a non-commercial portfolio project. Product images
are not downloaded or displayed. Not affiliated with REWE.
