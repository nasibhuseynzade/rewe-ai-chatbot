"""Check that each LLM provider in .env answers and can call our tools.

Sends one short question with the real TOOL_SPECS to every provider that has a
key (Ollama: only if it is running) and reports whether the model picked a
tool, which arguments it chose, the token usage and the latency.

    uv run python -m app.llm_ping                 # test all configured providers
    uv run python -m app.llm_ping groq cloudflare # test only these
    uv run python -m app.llm_ping --models gemini # list model names a provider offers

Keys are read from .env and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

from app import config  # noqa: F401  (loads .env)
from app.tools import TOOL_SPECS

QUESTION = "Was kostet Nutella aktuell in Bayern?"
SYSTEM = (
    "You answer questions about REWE supermarket prices in Germany. "
    "Always use a tool to look up data; product names are German."
)


def providers() -> dict[str, dict]:
    cf_account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    return {
        "gemini": {
            "base": "https://generativelanguage.googleapis.com/v1beta/openai",
            "key": os.getenv("GEMINI_API_KEY", ""),
            "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        },
        "groq": {
            "base": "https://api.groq.com/openai/v1",
            "key": os.getenv("GROQ_API_KEY", ""),
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        },
        "cloudflare": {
            "base": f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/v1",
            "key": os.getenv("CLOUDFLARE_API_TOKEN", "") if cf_account else "",
            "model": os.getenv("CLOUDFLARE_MODEL", "@cf/google/gemma-4-26b-a4b-it"),
            "account": cf_account,
        },
        "ollama": {
            "base": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "key": "ollama",  # Ollama ignores the key
            "model": os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
        },
    }


def _short_error(resp: requests.Response) -> str:
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


def ping(name: str, p: dict) -> dict:
    if not p["key"]:
        return {"provider": name, "status": "SKIP", "detail": "no key in .env"}
    payload = {
        "model": p["model"],
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": QUESTION}],
        "tools": TOOL_SPECS,
        "tool_choice": "auto",
        "max_tokens": 2048,
    }
    headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
    start = time.perf_counter()
    try:
        resp = requests.post(f"{p['base']}/chat/completions", json=payload,
                             headers=headers, timeout=90)
    except requests.ConnectionError:
        detail = "not running (start it with: ollama serve)" if name == "ollama" else "connection failed"
        return {"provider": name, "status": "SKIP" if name == "ollama" else "FAIL", "detail": detail}
    except requests.Timeout:
        return {"provider": name, "status": "FAIL", "detail": "timed out after 90 s"}
    latency = time.perf_counter() - start
    if resp.status_code != 200:
        return {"provider": name, "status": "FAIL", "model": p["model"], "detail": _short_error(resp)}

    data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    calls = msg.get("tool_calls") or []
    usage = data.get("usage") or {}
    result = {
        "provider": name, "model": p["model"], "latency_s": round(latency, 2),
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }
    if calls:
        fn = calls[0].get("function", {})
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                pass
        result.update(status="OK", tool=fn.get("name"), arguments=args)
    else:
        result.update(status="NO TOOL CALL", detail=(msg.get("content") or "")[:200])
    return result


def list_models(name: str, p: dict) -> list[str]:
    headers = {"Authorization": f"Bearer {p['key']}"}
    if name == "cloudflare":
        url = (f"https://api.cloudflare.com/client/v4/accounts/{p['account']}"
               "/ai/models/search?task=Text%20Generation&per_page=200")
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return sorted(m["name"] for m in resp.json()["result"])
    resp = requests.get(f"{p['base']}/models", headers=headers, timeout=30)
    resp.raise_for_status()
    return sorted(m["id"].removeprefix("models/") for m in resp.json()["data"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="providers to test (default: all)")
    ap.add_argument("--models", action="store_true", help="list available model names instead")
    args = ap.parse_args(argv)

    all_p = providers()
    names = args.names or list(all_p)
    unknown = [n for n in names if n not in all_p]
    if unknown:
        ap.error(f"unknown provider(s): {', '.join(unknown)}; choose from {', '.join(all_p)}")

    if args.models:
        for n in names:
            p = all_p[n]
            if not p["key"]:
                print(f"\n## {n}: no key in .env")
                continue
            try:
                print(f"\n## {n}\n" + "\n".join(list_models(n, p)))
            except requests.RequestException as exc:
                code = getattr(exc.response, "status_code", "")
                print(f"\n## {n}: failed {code}".rstrip())
        return 0

    tools_chars = len(json.dumps(TOOL_SPECS))
    print(f"Question: {QUESTION}")
    print(f"Tool specs: {len(TOOL_SPECS)} tools, ~{tools_chars // 4} tokens\n")
    failed = False
    for n in names:
        r = ping(n, all_p[n])
        status = r.pop("status")
        provider = r.pop("provider")
        failed |= status == "FAIL"
        print(f"[{status}] {provider}")
        for k, v in r.items():
            if v is not None:
                print(f"    {k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
