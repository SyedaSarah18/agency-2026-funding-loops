"""Hour 3 end-to-end smoke — exercise the orchestrator with three
different question shapes so we see Router routing in action and the
specialist(s) running on the routes Router picks.

Run from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe agent/scripts/smoke_hour3.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from vendor_concentration_agent.orchestrator import handle


# ANSI colors so the trace is readable on a dark terminal
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"


async def run_one(question: str) -> None:
    print()
    print("=" * 80)
    print(f"{BOLD}USER:{RESET} {question}")
    print("=" * 80)

    t0 = time.time()
    text_buf = ""
    seen_tools: list[str] = []
    audit_count = 0

    async for event in handle(question):
        kind = event.get("__kind__")
        if kind == "tool":
            name = event["tool"]
            seen_tools.append(name)
            print(f"\n{CYAN}▸ tool:{RESET}      {BOLD}{name}{RESET} ({event.get('label', '')}) — {DIM}{event.get('question','')[:60]}{RESET}")
        elif kind == "tool_done":
            print(f"{GREEN}✓ done:{RESET}      {event['tool_done']}")
        elif kind == "text":
            tok = event["text"]
            text_buf += tok
            sys.stdout.write(tok)
            sys.stdout.flush()
        elif kind == "error":
            print(f"\n{YELLOW}✗ error:{RESET} {event['error']}")
        elif kind == "audit":
            audit_count += 1

    dt = time.time() - t0
    print()
    print(f"\n{MAGENTA}— summary —{RESET}")
    print(f"  duration:   {dt:.1f}s")
    print(f"  tools fired: {seen_tools}")
    print(f"  text length: {len(text_buf):,} chars")


async def main() -> None:
    questions = [
        ("out_of_scope test", "What's the capital of France?"),
        ("discovery test",
         "Which Alberta sole-source procurement categories have the strongest single-vendor dominance? Show me a watchlist of the top 3."),
    ]
    for label, q in questions:
        print(f"\n\n{BOLD}{'#' * 5} {label} {'#' * 5}{RESET}")
        try:
            await run_one(q)
        except Exception as e:
            print(f"\n{YELLOW}EXCEPTION:{RESET} {type(e).__name__}: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
