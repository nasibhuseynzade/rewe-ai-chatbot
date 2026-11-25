"""Paths and limits, read from .env (see .env.example)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _path(env: str, default: str) -> Path:
    p = Path(os.getenv(env, default))
    return p if p.is_absolute() else PROJECT_ROOT / p


DATA_DIR = _path("DATA_DIR", "./data")
WAREHOUSE_PATH = _path("DUCKDB_PATH", str(DATA_DIR / "warehouse.duckdb"))
SERVING_PATH = _path("SERVING_PATH", str(DATA_DIR / "serving.duckdb"))
DBT_MANIFEST = PROJECT_ROOT / "transform" / "target" / "manifest.json"

# Schemas copied into the serving database and visible to the assistant.
SERVING_SCHEMAS = ("gold", "marts")

# Limits for every query the assistant triggers.
MAX_ROWS = int(os.getenv("QUERY_MAX_ROWS", "200"))
QUERY_TIMEOUT_S = float(os.getenv("QUERY_TIMEOUT_SECONDS", "10"))
DB_MEMORY_LIMIT = os.getenv("DB_MEMORY_LIMIT", "1GB")
DB_THREADS = int(os.getenv("DB_THREADS", "2"))

REGIONS = ("bavaria", "schleswig-holstein")
