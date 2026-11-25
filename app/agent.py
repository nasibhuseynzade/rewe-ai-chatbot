"""The tool loop: question in, answer plus the data behind it out.

    result = answer("Wie teuer ist Butter geworden?")
    result["answer"]  # text for the chat bubble
    result["steps"]   # every tool call with its SQL, rows and chart, for the UI

The LLM sees a compact version of each tool result (first rows only); the full
result goes back to the caller.
"""

from __future__ import annotations

import json
import time
from typing import Any

import duckdb

from app import db
from app.llm import Provider, chat, provider_chain
from app.prompt import build_system_prompt
from app.tools import TOOL_SPECS, call_tool

MAX_ROUNDS = 5           # tool-calling rounds before we force an answer
LLM_ROWS = 20            # rows of each tool result the model gets to see
LLM_RESULT_CHARS = 6000  # hard cap per tool result sent to the model
HISTORY_TURNS = 6        # earlier user/assistant messages kept for follow-ups

# Safety net for the scope rule: an answer that used no tool can only be a short
# refusal or a note about the data's limits. A long one means the prompt was
# talked around (poem, code, essay), so it is replaced.
OFF_TOPIC_MAX_CHARS = 700
OFF_TOPIC_REPLY = ("I can only answer questions about REWE prices in this dataset, for example: "
                   "\"Which category got the most expensive?\"")


def _compact(result: dict) -> str:
    """Tool result as the model sees it: the first rows, each with its column names.

    Rows as plain value lists would save tokens, but models then mix up columns
    (e.g. old and new price), so every row keeps its keys; empty values are dropped.
    """
    if "error" in result:
        return json.dumps({"error": result["error"]}, ensure_ascii=False)
    rows = [{k: v for k, v in r.items() if v is not None} for r in result.get("rows", [])]
    n = LLM_ROWS
    while True:
        out = {"rows": rows[:n], "row_count": result.get("row_count", 0)}
        if result.get("truncated") or len(rows) > n:
            out["note"] = f"showing {min(n, len(rows))} rows; more exist"
        text = json.dumps(out, ensure_ascii=False, default=str)
        if len(text) <= LLM_RESULT_CHARS or n <= 3:
            return text[:LLM_RESULT_CHARS]
        n = max(3, n // 2)


def _parse_args(raw: str) -> dict[str, Any]:
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"arguments are not valid JSON: {exc}") from exc
    if not isinstance(args, dict):
        raise ValueError("arguments must be a JSON object")
    return args


def answer(question: str, history: list[dict] | None = None,
           con: duckdb.DuckDBPyConnection | None = None,
           chain: list[Provider] | None = None) -> dict:
    own_con = con is None
    con = con or db.connect()
    chain = chain or provider_chain()
    started = time.perf_counter()
    try:
        messages: list[dict] = [{"role": "system", "content": build_system_prompt(con)}]
        for m in (history or [])[-HISTORY_TURNS:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": question})

        steps: list[dict] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        fallbacks: list[dict] = []
        providers_used: list[str] = []
        text = ""

        for round_no in range(MAX_ROUNDS + 1):
            last_round = round_no == MAX_ROUNDS
            if last_round:
                messages.append({"role": "user", "content":
                                 "Answer now with the data you already have; no more tool calls."})
            comp = chat(messages, None if last_round else TOOL_SPECS, chain)
            usage["prompt_tokens"] += comp.prompt_tokens
            usage["completion_tokens"] += comp.completion_tokens
            fallbacks += comp.attempts
            if comp.attempts:  # don't retry providers that just failed, for the rest of this answer
                chain = chain[[p.name for p in chain].index(comp.provider):]
            providers_used.append(f"{comp.provider}:{comp.model}")
            msg = comp.message
            messages.append(msg)

            calls = msg.get("tool_calls") or []
            if not calls or last_round:
                text = msg.get("content", "").strip()
                break

            for call in calls:
                name = call["function"]["name"]
                try:
                    args = _parse_args(call["function"]["arguments"])
                    result = call_tool(con, name, args)
                except ValueError as exc:
                    args, result = {}, {"tool": name, "error": str(exc)}
                    # providers reject history with broken JSON arguments (HTTP 400)
                    call["function"]["arguments"] = "{}"
                steps.append({"tool": name, "arguments": args,
                              **{k: v for k, v in result.items() if k != "tool"}})
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": _compact(result)})

        guarded = False
        if not text:
            text = "Sorry, I couldn't put an answer together. Please try rephrasing the question."
        elif not steps and len(text) > OFF_TOPIC_MAX_CHARS:
            text, guarded = OFF_TOPIC_REPLY, True
        return {
            "question": question,
            "answer": text,
            "steps": steps,
            "provider": providers_used[-1] if providers_used else None,
            "llm_calls": len(providers_used),
            "providers_used": providers_used,
            "fallbacks": fallbacks,
            "guarded": guarded,
            **usage,
            "latency_s": round(time.perf_counter() - started, 2),
        }
    finally:
        if own_con:
            con.close()
