"""One client for every OpenAI-compatible provider, with a fallback chain.

LLM_PROVIDERS in .env sets the order, e.g. "gemini,groq,cloudflare" for local
development or "cloudflare,groq,gemini" in production. A provider without a key
is skipped; on rate limits (429), server errors (5xx), timeouts or connection
errors the next provider is tried, and the failed one rests for
LLM_COOLDOWN_SECONDS (or the Retry-After it sent) before it is tried first again.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field

import requests

from app import config  # noqa: F401  (loads .env)

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Connect fast or move on; a chat user won't wait a minute for a stuck provider.
CONNECT_TIMEOUT_S = 5.0
TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1500"))
COOLDOWN_S = float(os.getenv("LLM_COOLDOWN_SECONDS", "120"))

# provider name -> time.monotonic() until which it is skipped after an outage or
# rate limit, so later questions don't wait for a provider that is known to be down
_cooldown_until: dict[str, float] = {}


def _cool_down(name: str, resp: requests.Response | None = None) -> None:
    seconds = COOLDOWN_S
    if resp is not None:
        try:
            seconds = min(max(float(resp.headers.get("Retry-After", "")), 1.0), 600.0)
        except ValueError:
            pass
    _cooldown_until[name] = time.monotonic() + seconds


def _ready_first(chain: list["Provider"]) -> list["Provider"]:
    """Providers not cooling down, in order; cooling ones only as a last resort."""
    now = time.monotonic()
    ready = [p for p in chain if _cooldown_until.get(p.name, 0) <= now]
    return ready + [p for p in chain if p not in ready]


@dataclass
class Provider:
    name: str
    base_url: str
    api_key: str
    model: str

    @property
    def available(self) -> bool:
        return bool(self.api_key)


def all_providers() -> dict[str, Provider]:
    cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    return {
        "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                           os.getenv("GEMINI_API_KEY", ""),
                           os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")),
        "groq": Provider("groq", "https://api.groq.com/openai/v1",
                         os.getenv("GROQ_API_KEY", ""),
                         os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")),
        "cloudflare": Provider("cloudflare",
                               f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/v1",
                               os.getenv("CLOUDFLARE_API_TOKEN", "") if cf_account else "",
                               os.getenv("CLOUDFLARE_MODEL", "@cf/google/gemma-4-26b-a4b-it")),
        "ollama": Provider("ollama", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                           "ollama" if os.getenv("OLLAMA_MODEL") else "",
                           os.getenv("OLLAMA_MODEL", "qwen3.5:4b")),
    }


def provider_chain(names: str | list[str] | None = None) -> list[Provider]:
    """Providers in fallback order, only those with a key."""
    if names is None:
        names = os.getenv("LLM_PROVIDERS", "gemini,groq,cloudflare")
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]
    known = all_providers()
    unknown = [n for n in names if n not in known]
    if unknown:
        raise ValueError(f"unknown provider(s): {', '.join(unknown)}")
    chain = [known[n] for n in names if known[n].available]
    if not chain:
        raise RuntimeError(f"no API key set for any of: {', '.join(names)} (see .env)")
    return chain


@dataclass
class Completion:
    message: dict            # canonical assistant message (role, content, tool_calls)
    provider: str
    model: str
    latency_s: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    attempts: list[dict] = field(default_factory=list)  # failed providers before this one


class LLMError(RuntimeError):
    def __init__(self, message: str, attempts: list[dict]):
        super().__init__(message)
        self.attempts = attempts


def _canonical(msg: dict, provider: str) -> dict:
    """Keep only standard fields, so the history can go to any provider.

    Groq rejects unknown message fields (like 'reasoning'); Gemini needs the
    'extra_content' of its own tool calls back (thought signatures), so that is
    kept and tagged with the provider that produced it.
    """
    out: dict = {"role": "assistant", "content": msg.get("content") or ""}
    calls = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        args = fn.get("arguments", "{}")
        if not isinstance(args, str):
            args = json.dumps(args, ensure_ascii=False)
        call = {"id": c.get("id") or f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                "function": {"name": fn.get("name", ""), "arguments": args or "{}"}}
        if c.get("extra_content"):
            call["extra_content"] = c["extra_content"]
            call["_provider"] = provider
        calls.append(call)
    if calls:
        out["tool_calls"] = calls
    return out


def _for_provider(messages: list[dict], provider: str) -> list[dict]:
    """Drop provider-specific extras that the target provider didn't produce."""
    clean = []
    for m in messages:
        if m.get("role") != "assistant" or "tool_calls" not in m:
            clean.append(m)
            continue
        calls = []
        for c in m["tool_calls"]:
            c = dict(c)
            if c.pop("_provider", None) != provider:
                c.pop("extra_content", None)
            calls.append(c)
        clean.append({**m, "tool_calls": calls})
    return clean


def _error_text(resp: requests.Response) -> str:
    try:
        body = resp.json()
        if isinstance(body, list) and body:
            body = body[0]
        err = body.get("error") or body.get("errors") or body
        if isinstance(err, list) and err:
            err = err[0]
        msg = err.get("message", err) if isinstance(err, dict) else err
    except ValueError:
        msg = resp.text
    return f"HTTP {resp.status_code}: {str(msg)[:300]}"


def chat(messages: list[dict], tools: list[dict] | None = None,
         chain: list[Provider] | None = None) -> Completion:
    """Send messages to the first provider in the chain that answers."""
    chain = _ready_first(chain or provider_chain())
    attempts: list[dict] = []
    for p in chain:
        payload: dict = {"model": p.model, "messages": _for_provider(messages, p.name),
                         "max_tokens": MAX_TOKENS}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        start = time.perf_counter()
        try:
            resp = requests.post(f"{p.base_url}/chat/completions", json=payload,
                                 timeout=(CONNECT_TIMEOUT_S, TIMEOUT_S),
                                 headers={"Authorization": f"Bearer {p.api_key}"})
        except (requests.ConnectionError, requests.Timeout) as exc:
            attempts.append({"provider": p.name, "error": type(exc).__name__})
            _cool_down(p.name)
            continue
        latency = time.perf_counter() - start
        if resp.status_code in RETRY_STATUS:
            attempts.append({"provider": p.name, "error": _error_text(resp)})
            _cool_down(p.name, resp)
            continue
        if resp.status_code != 200:
            # A 400 means our request is wrong for this provider; another one may still accept it.
            attempts.append({"provider": p.name, "error": _error_text(resp)})
            continue
        _cooldown_until.pop(p.name, None)
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return Completion(
            message=_canonical(choice.get("message") or {}, p.name),
            provider=p.name, model=p.model, latency_s=round(latency, 2),
            prompt_tokens=usage.get("prompt_tokens") or 0,
            completion_tokens=usage.get("completion_tokens") or 0,
            attempts=attempts,
        )
    raise LLMError("all providers failed: " + "; ".join(
        f"{a['provider']}: {a['error']}" for a in attempts), attempts)
