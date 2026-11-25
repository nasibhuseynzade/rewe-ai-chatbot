"""Ask the assistant from the terminal.

    uv run python -m app.ask "Welche Kategorie ist am teuersten geworden?"
    uv run python -m app.ask --providers groq "Wo ist Butter billiger?"
    uv run python -m app.ask                  # interactive, keeps the conversation
    uv run python -m app.ask --sql "..."      # also print the SQL of each step
    uv run python -m app.ask --json "..."     # full result as JSON
"""

from __future__ import annotations

import argparse
import json
import sys

from app import db
from app.agent import answer
from app.llm import LLMError, provider_chain


def _print(result: dict, show_sql: bool) -> None:
    print(f"\n{result['answer']}\n")
    for i, s in enumerate(result["steps"], 1):
        status = f"error: {s['error']}" if "error" in s else f"{s.get('row_count', 0)} rows"
        print(f"  [{i}] {s['tool']}({json.dumps(s['arguments'], ensure_ascii=False)}) -> {status}")
        if show_sql and s.get("sql"):
            print(f"      SQL: {s['sql']}")
    fb = "; ".join(f"{a['provider']} failed ({a['error'][:60]})" for a in result["fallbacks"])
    print(f"  -- {result['provider']} | {result['llm_calls']} LLM calls | "
          f"{result['prompt_tokens']}+{result['completion_tokens']} tokens | {result['latency_s']} s"
          + (f" | {fb}" if fb else ""))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="*")
    ap.add_argument("--providers", help="fallback order, e.g. 'groq,cloudflare' (default: LLM_PROVIDERS)")
    ap.add_argument("--sql", action="store_true", help="print the SQL of each step")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = ap.parse_args(argv)

    chain = provider_chain(args.providers)
    con = db.connect()
    history: list[dict] = []
    question = " ".join(args.question)
    try:
        while True:
            if not question:
                try:
                    question = input("\n? ").strip()
                except (EOFError, KeyboardInterrupt):
                    return 0
                if question.lower() in ("", "q", "quit", "exit"):
                    return 0
            try:
                result = answer(question, history=history, con=con, chain=chain)
            except LLMError as exc:
                print(f"LLM error: {exc}", file=sys.stderr)
                return 1
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                _print(result, args.sql)
            if args.question:
                return 0
            history += [{"role": "user", "content": question},
                        {"role": "assistant", "content": result["answer"]}]
            question = ""
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
