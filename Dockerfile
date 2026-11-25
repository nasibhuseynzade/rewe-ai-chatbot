# API image: FastAPI + DuckDB, reading a read-only serving.duckdb mounted at runtime.
# The data pipeline (download, dbt) runs elsewhere; only its output is mounted.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/var \
    SERVING_PATH=/app/serving/serving.duckdb

WORKDIR /app
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY app/ app/

# unprivileged user; /app/var holds the chat log
RUN useradd --create-home --uid 10001 api \
    && mkdir -p /app/var/logs /app/serving \
    && chown -R api /app/var
USER api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

# one worker: the rate limiter keeps its counters in memory
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
