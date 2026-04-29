"""Validate the references registry — fetch every URL, optionally check the
excerpt sentinel, stamp accessed_date.

HARD FAIL (build broken):
  - missing or empty excerpt file
  - URL returns network error or HTTP 4xx/5xx
SOFT WARN (excerpt may be stale, but build still passes):
  - URL returned 200 OK but sentinel string was not in the response body.
    This is common for JS-rendered pages where the static HTML is a shell
    that loads content client-side. We treat the *excerpt file* on disk as
    the canonical quote; the live page is just a liveness check.

Run from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe agent/scripts/build_references.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "references" / "references.json"
EXCERPTS_DIR = REPO_ROOT / "references"

# A real-browser User-Agent — many government sites return different
# content (or 4xx) for non-browser clients.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}


def main() -> int:
    if not REGISTRY.exists():
        print(f"FATAL: registry not found: {REGISTRY}", file=sys.stderr)
        return 2

    registry: dict = json.loads(REGISTRY.read_text(encoding="utf-8"))
    hard_failures: list[str] = []

    for ref_id, entry in registry.items():
        url = entry["url"]
        sentinel = entry.get("excerpt_must_contain", "")
        excerpt_path = EXCERPTS_DIR / entry["excerpt_file"]

        print(f"\n[{ref_id}] {url}")

        # HARD: excerpt file must exist and be non-empty
        if not excerpt_path.exists() or excerpt_path.stat().st_size == 0:
            hard_failures.append(f"{ref_id}: missing or empty excerpt file {excerpt_path}")
            print("  FAIL  excerpt file missing or empty")
            continue

        # HARD: URL must respond
        try:
            r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20.0)
        except httpx.HTTPError as e:
            hard_failures.append(f"{ref_id}: network error {e}")
            print(f"  FAIL  network: {e}")
            continue

        if r.status_code >= 400:
            hard_failures.append(f"{ref_id}: HTTP {r.status_code}")
            print(f"  FAIL  HTTP {r.status_code}")
            continue

        # SOFT: sentinel check
        sentinel_in_page = bool(sentinel) and (sentinel.lower() in r.text.lower())
        if sentinel and not sentinel_in_page:
            print(f"  WARN  sentinel {sentinel!r} not in static HTML "
                  f"(likely JS-rendered; excerpt file is canonical)")
            entry["last_check_status"] = "ok_sentinel_missing"
        else:
            print(f"  OK    {r.status_code} · "
                  f"{'sentinel matched · ' if sentinel_in_page else ''}{len(r.text):,} chars")
            entry["last_check_status"] = "ok"

        entry["accessed_date"] = date.today().isoformat()

    REGISTRY.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if hard_failures:
        print("\nBUILD FAILED:")
        for f in hard_failures:
            print(f"  - {f}")
        return 1

    print(f"\nbuild_references: OK · {len(registry)} entries validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
