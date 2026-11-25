"""Run the evaluation set against one provider and score the answers.

    uv run python -m app.evaluate --providers groq
    uv run python -m app.evaluate --providers cloudflare --cases shrink_any_tr,region_overall_en
    uv run python -m app.evaluate --providers gemini --sleep 5

Writes eval/results/<time>_<provider>.jsonl (every answer, for inspection) and
eval/results/<time>_<provider>.md (the scorecard), and prints the scorecard.
Use one provider per run (no fallback), so the score belongs to that model.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import tomllib
import unicodedata
from pathlib import Path

from app import config, db
from app.agent import answer
from app.llm import LLMError, provider_chain
from app.tools import _region

CASES_FILE = config.PROJECT_ROOT / "eval" / "cases.toml"
RESULTS_DIR = config.PROJECT_ROOT / "eval" / "results"

_NUM = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)*")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def numbers_in(text: str) -> list[float]:
    """All numbers in a text, reading both 3,40 and 3.40 (and 10,511 / 1.234,5)."""
    found: list[float] = []
    for tok in _NUM.findall(text.replace("−", "-")):
        sign = -1 if tok.startswith("-") else 1
        tok = tok.lstrip("-")
        seps = [c for c in tok if c in ".,"]
        candidates = []
        if not seps:
            candidates.append(tok)
        elif len(set(seps)) == 2:                      # 1.234,56 or 1,234.56
            dec = tok[max(tok.rfind("."), tok.rfind(","))]
            thou = "," if dec == "." else "."
            candidates.append(tok.replace(thou, "").replace(dec, "."))
        else:
            sep = seps[0]
            parts = tok.split(sep)
            if len(parts) == 2:                         # 3,40 / 3.40, maybe 10,511
                candidates.append(f"{parts[0]}.{parts[1]}")
            if all(len(p) == 3 for p in parts[1:]):     # thousands separator
                candidates.append(tok.replace(sep, ""))
        for c in candidates:
            try:
                found.append(sign * float(c))
            except ValueError:
                pass
    return found


def _has_number(found: list[float], expected: float) -> bool:
    """Sign is ignored: "-12.76 %" and "fell 12.76 %" both match 12.76."""
    tol = max(0.011, 0.006 * abs(expected))
    return any(abs(abs(f) - abs(expected)) <= tol for f in found)


def _same(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return _norm(a).strip() == _norm(b).strip()
    return a == b


def score(case: dict, result: dict) -> dict:
    """Check one answer; returns {check_name: (passed, detail)}."""
    text = result.get("answer", "")
    steps = result.get("steps", [])
    called = [s["tool"] for s in steps]
    checks: dict[str, tuple[bool, str]] = {}

    if case.get("no_tools"):
        checks["no_tools"] = (not called, f"called {called}" if called else "")
    if case.get("tools"):
        ok = any(t in called for t in case["tools"])
        checks["tools"] = (ok, "" if ok else f"called {called or 'nothing'}, wanted one of {case['tools']}")
    for tool, expected in (case.get("args") or {}).items():
        step = next((s for s in steps if s["tool"] == tool), None)
        if step is None:
            checks[f"args:{tool}"] = (False, "tool not called")
            continue
        got = step.get("arguments", {})
        bad = []
        for k, v in expected.items():
            g = got.get(k)
            if k == "region":
                try:
                    g, v = _region(g), _region(v)
                except ValueError:
                    pass
            if not _same(g, v):
                bad.append(f"{k}={g!r} (want {v!r})")
        checks[f"args:{tool}"] = (not bad, ", ".join(bad))
    if case.get("numbers"):
        found = numbers_in(text)
        missing = []
        for n in case["numbers"]:
            options = n if isinstance(n, list) else [n]
            if not any(_has_number(found, o) for o in options):
                missing.append("/".join(str(o) for o in options))
        checks["numbers"] = (not missing, f"missing {', '.join(missing)}" if missing else "")
    if case.get("mentions"):
        missing = [m for m in case["mentions"] if _norm(m) not in _norm(text)]
        checks["mentions"] = (not missing, f"missing {missing}" if missing else "")
    if case.get("not_mentions"):
        found = [m for m in case["not_mentions"] if _norm(m) in _norm(text)]
        checks["not_mentions"] = (not found, f"contains {found}" if found else "")
    if case.get("max_chars"):
        ok = len(text) <= case["max_chars"]
        checks["max_chars"] = (ok, "" if ok else f"{len(text)} chars > {case['max_chars']}")
    if case.get("mentions_any"):
        ok = any(_norm(m) in _norm(text) for m in case["mentions_any"])
        checks["mentions_any"] = (ok, "" if ok else f"none of {case['mentions_any']}")
    return checks


def _scorecard(provider: str, rows: list[dict]) -> str:
    n = len(rows)
    passed = sum(r["passed"] for r in rows)
    ok_runs = [r for r in rows if not r.get("error")]
    tool_rows = [r for r in rows if "tools" in r["checks"]]
    num_rows = [r for r in rows if "numbers" in r["checks"]]

    def share(sub, key):
        return f"{sum(r['checks'][key][0] for r in sub)}/{len(sub)}" if sub else "-"

    def avg(key):
        vals = [r[key] for r in ok_runs if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0

    lines = [
        f"# Evaluation: {provider}",
        "",
        f"- Date: {dt.datetime.now():%Y-%m-%d %H:%M}",
        f"- Passed: **{passed}/{n}** ({100 * passed / n:.0f}%)",
        f"- Right tool: {share(tool_rows, 'tools')} · Right numbers: {share(num_rows, 'numbers')}",
        f"- Errors (provider failed): {n - len(ok_runs)}",
        f"- Average latency: {avg('latency_s'):.1f} s · Average tokens per question: "
        f"{avg('prompt_tokens'):.0f} in + {avg('completion_tokens'):.0f} out",
        "",
        "| case | result | tools called | problem |",
        "|---|---|---|---|",
    ]
    for r in rows:
        problems = "; ".join(f"{k}: {d}" for k, (ok, d) in r["checks"].items() if not ok)
        lines.append(f"| {r['id']} | {'PASS' if r['passed'] else 'FAIL'} | "
                     f"{', '.join(r['tools_called']) or '-'} | {(r.get('error') or problems).replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--providers", required=True, help="one provider, e.g. groq (no fallback)")
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--sleep", type=float, default=3.0, help="pause between cases, seconds (rate limits)")
    args = ap.parse_args(argv)

    cases = tomllib.loads(CASES_FILE.read_text(encoding="utf-8"))["case"]
    if args.cases:
        wanted = {c.strip() for c in args.cases.split(",")}
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            ap.error(f"unknown case(s): {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in wanted]

    chain = provider_chain(args.providers)
    label = "+".join(f"{p.name}-{p.model.split('/')[-1]}" for p in chain)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = RESULTS_DIR / f"{dt.datetime.now():%Y%m%d-%H%M}_{re.sub(r'[^A-Za-z0-9.+-]', '_', label)}"
    con = db.connect()
    rows: list[dict] = []
    try:
        with open(f"{stem}.jsonl", "w", encoding="utf-8") as log:
            for i, case in enumerate(cases, 1):
                try:
                    result = answer(case["question"], con=con, chain=chain)
                    error = None
                except LLMError as exc:
                    result, error = {"answer": "", "steps": []}, str(exc)[:200]
                checks = score(case, result) if not error else {"run": (False, error)}
                row = {
                    "id": case["id"], "question": case["question"], "passed": all(ok for ok, _ in checks.values()),
                    "checks": checks, "error": error, "answer": result.get("answer"),
                    "tools_called": [s["tool"] for s in result.get("steps", [])],
                    "steps": [{k: s.get(k) for k in ("tool", "arguments", "sql", "row_count", "error")}
                              for s in result.get("steps", [])],
                    **{k: result.get(k) for k in ("provider", "latency_s", "prompt_tokens",
                                                   "completion_tokens", "llm_calls")},
                }
                rows.append(row)
                log.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                print(f"[{i}/{len(cases)}] {'PASS' if row['passed'] else 'FAIL'} {case['id']}", flush=True)
                if i < len(cases):
                    time.sleep(args.sleep)
    finally:
        con.close()

    card = _scorecard(label, rows)
    Path(f"{stem}.md").write_text(card, encoding="utf-8")
    print("\n" + card)
    print(f"Saved {stem}.md and .jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
