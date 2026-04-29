"""Knowledge-base tools — search pre-computed category/ministry analytics.

Four JSON files baked at build time by agent/scripts/precompute_kb.py:
  ab_sole_source_by_category.json   — 4 431 sole-source service categories
  ab_contracts_by_ministry.json     — 64 Alberta competitive ministries
  fed_contracts_by_category.json    — 386 federal economic object codes
  fed_contracts_by_dept.json        — 31 federal departments

These let Discovery answer "how many vendors compete in X?" or
"which categories have the highest concentration?" without hitting
Postgres on every request.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from strands import tool

_KB_DIR = Path(__file__).resolve().parent.parent / "kb"

_FILES = {
    "ab_sole_source_categories": "ab_sole_source_by_category.json",
    "ab_contracts_ministries":   "ab_contracts_by_ministry.json",
    "fed_contracts_categories":  "fed_contracts_by_category.json",
    "fed_contracts_departments": "fed_contracts_by_dept.json",
}

_METHODOLOGY_PATH = _KB_DIR / "methodology.md"


@lru_cache(maxsize=4)
def _load(key: str) -> list[dict]:
    path = _KB_DIR / _FILES[key]
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["rows"]


def _search(rows: list[dict], search: str) -> list[dict]:
    """Case-insensitive substring match across all string fields."""
    term = search.lower()
    return [
        r for r in rows
        if any(term in str(v).lower() for v in r.values())
    ]


@tool
def read_methodology() -> dict[str, Any]:
    """Read the methodology documentation — how HHI, CR_n, Gini, sole-source
    rate, incumbency streak, and vendor footprint are computed, including
    DOJ/FTC thresholds and data caveats per dataset.

    Use this when the user asks HOW a metric is calculated, WHAT a threshold
    means, or WHY a specific formula was chosen.
    """
    if not _METHODOLOGY_PATH.exists():
        return {"error": "methodology.md not found in kb/"}
    return {
        "content": _METHODOLOGY_PATH.read_text(encoding="utf-8"),
        "source": "kb/methodology.md",
    }


@tool
def query_kb_categories(
    dataset: str = "ab_sole_source",
    search: str = "",
    sort_by: str = "top1_share_pct",
    limit: int = 20,
) -> dict[str, Any]:
    """Search pre-computed category-level vendor counts and concentration from
    the Knowledge Base. Use this to answer 'how many vendors are competing in
    X?' or 'which categories have the highest concentration?'

    Covers categories from TWO datasets that have a category column:
      - ab_sole_source  (contract_services — 4 431 rows)
      - fed_contracts   (economic_object_code — 386 rows)

    Each row has: category, total_spend, vendor_count, contract_count,
    top_vendor, top1_share_pct.

    Args:
        dataset: "ab_sole_source" or "fed_contracts".
        search:  optional substring to filter by (matches category name,
                 vendor name, or any field). Empty string = return all.
        sort_by: "top1_share_pct" (default, highest concentration first) |
                 "total_spend" (largest $ first) |
                 "vendor_count" (most competitive first, ascending).
        limit:   max rows to return (default 20).
    """
    key_map = {
        "ab_sole_source": "ab_sole_source_categories",
        "fed_contracts":  "fed_contracts_categories",
    }
    key = key_map.get(dataset)
    if key is None:
        return {"error": f"dataset {dataset!r} has no category KB. Use 'ab_sole_source' or 'fed_contracts'."}

    rows = list(_load(key))
    if search:
        rows = _search(rows, search)

    reverse = sort_by != "vendor_count"
    rows.sort(key=lambda r: r.get(sort_by, 0), reverse=reverse)

    return {
        "dataset": dataset,
        "search": search or "(all)",
        "sort_by": sort_by,
        "total_matching": len(rows),
        "rows": rows[:limit],
    }


@tool
def query_kb_ministries_departments(
    dataset: str = "ab_contracts",
    search: str = "",
    sort_by: str = "top1_share_pct",
    limit: int = 20,
) -> dict[str, Any]:
    """Search pre-computed ministry/department-level vendor counts and
    concentration from the Knowledge Base.

    Covers TWO slices:
      - ab_contracts (ministry — 64 Alberta competitive ministries)
      - fed_contracts (department / owner_org_title — 31 federal departments)

    Each row has: ministry OR department, total_spend, vendor_count,
    contract_count, top_vendor, top1_share_pct.

    Args:
        dataset: "ab_contracts" (Alberta) or "fed_contracts" (Federal).
        search:  optional substring to filter by name or vendor. Empty = all.
        sort_by: "top1_share_pct" | "total_spend" | "vendor_count".
        limit:   max rows to return (default 20).
    """
    key_map = {
        "ab_contracts":  "ab_contracts_ministries",
        "fed_contracts": "fed_contracts_departments",
    }
    key = key_map.get(dataset)
    if key is None:
        return {"error": f"dataset {dataset!r} not supported. Use 'ab_contracts' or 'fed_contracts'."}

    rows = list(_load(key))
    if search:
        rows = _search(rows, search)

    reverse = sort_by != "vendor_count"
    rows.sort(key=lambda r: r.get(sort_by, 0), reverse=reverse)

    return {
        "dataset": dataset,
        "search": search or "(all)",
        "sort_by": sort_by,
        "total_matching": len(rows),
        "rows": rows[:limit],
    }
