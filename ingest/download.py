"""Download daily REWE price snapshots and land them as bronze Parquet.

Source: a directory listing of CSV files named ``YYYY-MM-DD_<region>.csv``
(one file per day and region). The CSVs have no date column, so the snapshot
date and region are taken from the file name.

Output layout (under DATA_DIR):

    raw/<region>/<date>_<region>.csv.gz       original bytes, gzip-compressed
    bronze/prices/<date>_<region>.parquet     same rows + lineage columns
    bronze/_manifest.jsonl                    one JSON line per processed file

Bronze rule: every source column is kept as TEXT, exactly as delivered.
Typing and parsing (prices, EANs, grammage) happen later, in silver.

The script is idempotent: files already landed in bronze are skipped, and a
raw file that was downloaded but not yet converted is converted without being
downloaded again.

Examples:
    uv run python ingest/download.py --list
    uv run python ingest/download.py --start 2025-08-25 --end 2025-09-08
    uv run python ingest/download.py --all
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import duckdb
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_COLUMNS = ["name", "brand", "ean", "price", "grammage", "category", "sale", "image"]

# Matches links such as href="2025-09-09_bavaria.csv" or href="./2025-09-09_bavaria.csv"
FILE_LINK_RE = re.compile(
    r'href="(?P<href>[^"]*?(?P<date>\d{4}-\d{2}-\d{2})_(?P<region>[a-z][a-z-]*)\.csv)"'
)


@dataclass(frozen=True)
class SourceFile:
    href: str
    date: dt.date
    region: str

    @property
    def stem(self) -> str:
        return f"{self.date.isoformat()}_{self.region}"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    base_url: str
    sleep_seconds: float
    user_agent: str


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    base_url = os.getenv("SOURCE_BASE_URL", "https://rewe.nicoo.org/")
    if not base_url.endswith("/"):
        base_url += "/"
    return Settings(
        data_dir=data_dir,
        base_url=base_url,
        sleep_seconds=float(os.getenv("DOWNLOAD_SLEEP_SECONDS", "1.5")),
        user_agent=os.getenv("USER_AGENT", "rewe-ai-portfolio-project"),
    )


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def list_source_files(session: requests.Session, base_url: str) -> list[SourceFile]:
    """Parse the directory listing and return all CSV snapshots, oldest first."""
    resp = session.get(base_url, timeout=30)
    resp.raise_for_status()
    files: dict[str, SourceFile] = {}
    for m in FILE_LINK_RE.finditer(resp.text):
        try:
            date = dt.date.fromisoformat(m["date"])
        except ValueError:
            continue
        f = SourceFile(href=m["href"], date=date, region=m["region"])
        files[f.stem] = f  # de-duplicate (a listing may link a file twice)
    return sorted(files.values(), key=lambda f: (f.date, f.region))


def print_summary(files: list[SourceFile]) -> None:
    if not files:
        print("No CSV files found in the listing.")
        return
    print(f"{len(files)} files from {files[0].date} to {files[-1].date}")
    for region, n in sorted(Counter(f.region for f in files).items()):
        dates = [f.date for f in files if f.region == region]
        span = (max(dates) - min(dates)).days + 1
        print(f"  {region:<22} {n:>4} files, {min(dates)} .. {max(dates)} "
              f"({span - n} days missing in that span)")


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #
def download_to_gzip(session: requests.Session, url: str, dest: Path,
                     retries: int = 4) -> tuple[str, int]:
    """Stream `url` into a gzip file at `dest`. Returns (sha256 of raw bytes, raw size).

    Writes to a temporary file first so an interrupted run never leaves a
    half-written file behind.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=(10, 120)) as resp:
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                resp.raise_for_status()
                sha, size = hashlib.sha256(), 0
                with gzip.open(tmp, "wb") as out:
                    for chunk in resp.iter_content(chunk_size=1 << 16):
                        out.write(chunk)
                        sha.update(chunk)
                        size += len(chunk)
            tmp.replace(dest)
            return sha.hexdigest(), size
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            tmp.unlink(missing_ok=True)
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if attempt == retries or (status is not None and status < 500 and status != 429):
                raise
            wait = 2 ** attempt
            print(f"    retry {attempt}/{retries - 1} in {wait}s ({exc})")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def sha256_of_gzip(path: Path) -> tuple[str, int]:
    sha, size = hashlib.sha256(), 0
    with gzip.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            sha.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), size


# --------------------------------------------------------------------------- #
# Bronze
# --------------------------------------------------------------------------- #
def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def raw_to_bronze(raw_gz: Path, bronze_file: Path, src: SourceFile) -> tuple[int, list[str]]:
    """Convert one raw CSV (gzipped) to Parquet, all columns as text.

    Adds lineage columns: snapshot_date, region, source_file, ingested_at.
    Returns (row count, source column names).
    """
    bronze_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = bronze_file.with_name(bronze_file.name + ".part")
    con = duckdb.connect()
    try:
        source = (
            f"read_csv({_sql_str(raw_gz.as_posix())}, header = true, all_varchar = true, "
            f"compression = 'gzip')"
        )
        columns = [row[0] for row in con.sql(f"DESCRIBE SELECT * FROM {source}").fetchall()]
        con.execute(f"""
            COPY (
                SELECT
                    *,
                    DATE {_sql_str(src.date.isoformat())}     AS snapshot_date,
                    {_sql_str(src.region)}                    AS region,
                    {_sql_str(src.stem + '.csv')}             AS source_file,
                    now()::TIMESTAMP                          AS ingested_at
                FROM {source}
            ) TO {_sql_str(tmp.as_posix())} (FORMAT parquet, COMPRESSION zstd)
        """)
        # fetchall() works on DuckDB 1.x and 2.x (2.x removed Relation.fetchone()).
        rows = con.sql(f"SELECT count(*) FROM read_parquet({_sql_str(tmp.as_posix())})").fetchall()[0][0]
    finally:
        con.close()
    tmp.replace(bronze_file)
    return rows, columns


def append_manifest(manifest: Path, record: dict) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true", help="only show which files are available")
    p.add_argument("--start", type=dt.date.fromisoformat, help="first snapshot date (YYYY-MM-DD)")
    p.add_argument("--end", type=dt.date.fromisoformat, help="last snapshot date (YYYY-MM-DD)")
    p.add_argument("--all", action="store_true", help="download every available file")
    p.add_argument("--regions", nargs="+", help="limit to these regions, e.g. bavaria")
    p.add_argument("--limit", type=int, help="process at most N files (useful for testing)")
    p.add_argument("--force", action="store_true", help="re-process files already in bronze")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_settings()

    session = requests.Session()
    session.headers["User-Agent"] = cfg.user_agent

    print(f"Listing {cfg.base_url} ...")
    files = list_source_files(session, cfg.base_url)
    print_summary(files)

    if args.list:
        return 0
    if not (args.all or args.start or args.end):
        print("\nNothing selected. Use --start/--end for a date range, or --all.")
        return 0

    selected = [
        f for f in files
        if (args.start is None or f.date >= args.start)
        and (args.end is None or f.date <= args.end)
        and (args.regions is None or f.region in args.regions)
    ]
    if args.limit:
        selected = selected[: args.limit]
    print(f"\nSelected {len(selected)} files.\n")

    raw_dir = cfg.data_dir / "raw"
    bronze_dir = cfg.data_dir / "bronze" / "prices"
    manifest = cfg.data_dir / "bronze" / "_manifest.jsonl"

    done = skipped = failed = 0
    for i, src in enumerate(selected, 1):
        raw_gz = raw_dir / src.region / f"{src.stem}.csv.gz"
        bronze_file = bronze_dir / f"{src.stem}.parquet"
        prefix = f"[{i}/{len(selected)}] {src.stem}"

        if bronze_file.exists() and not args.force:
            skipped += 1
            continue

        url = urljoin(cfg.base_url, src.href)
        record = {"file": src.stem + ".csv", "snapshot_date": src.date.isoformat(),
                  "region": src.region, "url": url}
        try:
            if raw_gz.exists() and not args.force:
                sha, size = sha256_of_gzip(raw_gz)
                record["downloaded"] = False
            else:
                sha, size = download_to_gzip(session, url, raw_gz)
                record["downloaded"] = True
            rows, columns = raw_to_bronze(raw_gz, bronze_file, src)

            drift = columns != EXPECTED_COLUMNS
            record.update(status="ok", raw_sha256=sha, raw_bytes=size, rows=rows,
                          columns=columns, schema_drift=drift)
            note = "  (!) unexpected columns" if drift else ""
            print(f"{prefix}: {rows:,} rows, {size / 1e6:.1f} MB{note}")
            done += 1
        except Exception as exc:  # keep going; the manifest records what failed
            record.update(status="error", error=f"{type(exc).__name__}: {exc}")
            print(f"{prefix}: FAILED - {record['error']}")
            failed += 1
        record["processed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        append_manifest(manifest, record)

        if record.get("downloaded") and i < len(selected):
            time.sleep(cfg.sleep_seconds)

    print(f"\nDone: {done} landed, {skipped} already in bronze, {failed} failed.")
    print(f"Bronze files: {bronze_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
