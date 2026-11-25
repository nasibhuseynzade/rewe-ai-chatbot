"""HTTP API for the website.

    uv run uvicorn app.api:app --reload --port 8000

    GET  /health    data period and status
    GET  /insights  insight cards (no LLM, cached)
    POST /chat      {"question": "...", "history": [{"role": "user"|"assistant", "content": "..."}]}

Protection for the free LLM quotas: per-IP limits per minute and per day, plus a
global daily cap. Logs keep questions, tokens and latency, never IP addresses.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app import config, db
from app.agent import answer
from app.insights import build_cards
from app.llm import LLMError, provider_chain

PER_MINUTE = int(os.getenv("API_LIMIT_PER_MINUTE", "5"))
PER_DAY = int(os.getenv("API_LIMIT_PER_DAY", "40"))
GLOBAL_PER_DAY = int(os.getenv("API_LIMIT_GLOBAL_PER_DAY", "300"))
TRUST_PROXY = os.getenv("API_TRUST_PROXY", "0") == "1"   # behind Caddy: use X-Forwarded-For
ORIGINS = [o.strip() for o in os.getenv(
    "API_ALLOWED_ORIGINS",
    "https://nasib.tech,https://www.nasib.tech,http://localhost:5500,http://127.0.0.1:5500"
).split(",") if o.strip()]
LOG_PATH = config.DATA_DIR / "logs" / "chat.jsonl"

log = logging.getLogger("rewe.api")


class RateLimiter:
    """In-memory sliding windows; enough for one small server process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._minute: dict[str, deque] = defaultdict(deque)
        self._day: dict[str, deque] = defaultdict(deque)
        self._global: deque = deque()

    def check(self, key: str) -> str | None:
        """Record a request; return a reason string if it must be refused."""
        now = time.time()
        with self._lock:
            for q, window in ((self._minute[key], 60), (self._day[key], 86400), (self._global, 86400)):
                while q and q[0] <= now - window:
                    q.popleft()
            if len(self._global) >= GLOBAL_PER_DAY:
                return "The assistant has reached its daily limit. Please come back tomorrow."
            if len(self._day[key]) >= PER_DAY:
                return "You have reached today's question limit. Please come back tomorrow."
            if len(self._minute[key]) >= PER_MINUTE:
                return "Too many questions in a short time. Please wait a minute."
            for q in (self._minute[key], self._day[key], self._global):
                q.append(now)
        return None


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[Message] = Field(default_factory=list, max_length=12)


state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["con"] = db.connect()
    state["chain"] = provider_chain()
    state["limiter"] = RateLimiter()
    state["insights"] = None
    start, end = state["con"].sql("SELECT min(snapshot_date), max(snapshot_date) FROM gold.snapshots").fetchall()[0]
    state["period"] = {"start": str(start), "end": str(end)}
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    yield
    state["con"].close()


app = FastAPI(title="REWE price assistant", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])


def _client_key(request: Request) -> str:
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _log(record: dict) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError as exc:  # logging must never break a request
        log.warning("could not write chat log: %s", exc)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "data_period": state["period"],
            "providers": [p.name for p in state["chain"]]}


@app.get("/insights")
def insights() -> list[dict]:
    if state["insights"] is None:   # the data only changes on redeploy
        state["insights"] = build_cards(state["con"].cursor())
    return state["insights"]


@app.post("/chat")
def chat(req: ChatRequest, request: Request) -> dict:
    refused = state["limiter"].check(_client_key(request))
    if refused:
        raise HTTPException(status_code=429, detail=refused)
    cur = state["con"].cursor()   # own cursor per request thread, same read-only database
    try:
        result = answer(req.question, history=[m.model_dump() for m in req.history],
                        con=cur, chain=state["chain"])
    except LLMError as exc:
        _log({"time": dt.datetime.now().isoformat(timespec="seconds"), "question": req.question,
              "error": str(exc)[:300]})
        raise HTTPException(status_code=503,
                            detail="The assistant is busy right now. Please try again in a minute.") from exc
    finally:
        cur.close()
    _log({"time": dt.datetime.now().isoformat(timespec="seconds"), "question": req.question,
          "tools": [s["tool"] for s in result["steps"]], "provider": result["provider"],
          "llm_calls": result["llm_calls"], "prompt_tokens": result["prompt_tokens"],
          "completion_tokens": result["completion_tokens"], "latency_s": result["latency_s"],
          "guarded": result["guarded"], "fallbacks": len(result["fallbacks"])})
    return {
        "answer": result["answer"],
        "steps": [{k: s.get(k) for k in ("tool", "arguments", "sql", "columns", "rows", "row_count",
                                          "truncated", "chart", "error")}
                  for s in result["steps"] if s["tool"] != "describe_table"],
        "provider": result["provider"],
        "latency_s": result["latency_s"],
    }
