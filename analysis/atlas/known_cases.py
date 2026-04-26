"""Eval suite — asserts the Atlas flags known true-positive monopolies.

Run: python analysis/atlas/known_cases.py
Exits 0 if all assertions pass; non-zero with a diff if any fail.

Treat as a regression test. After ANY change to the build pipeline,
agent prompts, or scoring formulas, run this to confirm we still
catch the things we already know are real.

Why this exists separately from the Validator agent:
  Validator is an LLM agent making subjective judgments at runtime
  on one finding at a time. This eval is a deterministic test
  asserting specific risk-score ranges over the WHOLE Atlas. It runs
  only when we change agent code.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.stdout.reconfigure(encoding="utf-8")

ATLAS_DIR = ROOT / "analysis" / "atlas_data"

# (vendor_substr, category_substr, min_total_spend, min_headline_risk)
# Each tuple is a "known true positive" — a real Alberta procurement
# concentration we expect the Atlas to flag. If the Atlas misses any of these,
# the methodology has a gap.
KNOWN_CASES = [
    # The headline scandal-shaped cases
    ("MICROSOFT CANADA",     "Azure",                       50_000_000, 60),
    ("IBM CANADA",            "Enterprise License",          50_000_000, 60),
    ("IBM CANADA",            "Mainframe",                   30_000_000, 60),
    ("IBM CANADA",            "IMAGIS",                      30_000_000, 60),
    ("Telus Health",          "Personal Health Record",      30_000_000, 60),
    ("Alberta Blue Cross",    "benefit programs",            1_000_000_000, 60),

    # Vendor-level lock-in (atlas_vendor_dependency)
    # tuple shape: (vendor_substr, None, min_total_spend, min_lockin_score)
    # marker '__VENDOR__' tells the runner to look in the vendor table not categories
    ("__VENDOR__IBM CANADA",   None,                          200_000_000, 60),
    ("__VENDOR__Catholic Social Services", None,             400_000_000, 60),
]


def assert_category_case(cats: pd.DataFrame, vendor_substr: str, category_substr: str,
                         min_spend: int, min_risk: float) -> tuple[bool, str]:
    matches = cats[
        cats["top1_vendor"].str.contains(vendor_substr, case=False, na=False)
        & cats["category"].str.contains(category_substr, case=False, na=False)
        & (cats["total_spend"] >= min_spend)
    ]
    if matches.empty:
        return False, f"NO MATCH for vendor={vendor_substr!r} category~{category_substr!r} spend>={min_spend:,}"
    best = matches.sort_values("headline_risk_score", ascending=False).iloc[0]
    if best["headline_risk_score"] < min_risk:
        return False, (
            f"FOUND but risk too low ({best['headline_risk_score']:.1f} < {min_risk}) "
            f"for {vendor_substr} / {category_substr}"
        )
    return True, (
        f"OK risk={best['headline_risk_score']:.1f} ${best['total_spend']:,.0f} "
        f"share={best['top1_share']:.0%} {best['category'][:40]}"
    )


def assert_vendor_case(vendors: pd.DataFrame, vendor_substr: str,
                       min_spend: int, min_lockin: float) -> tuple[bool, str]:
    matches = vendors[
        vendors["vendor"].str.contains(vendor_substr, case=False, na=False)
        & (vendors["total_spend"] >= min_spend)
    ]
    if matches.empty:
        return False, f"NO VENDOR MATCH for {vendor_substr!r} spend>={min_spend:,}"
    best = matches.sort_values("lockin_score", ascending=False).iloc[0]
    if best["lockin_score"] < min_lockin:
        return False, (
            f"FOUND but lockin too low ({best['lockin_score']:.1f} < {min_lockin}) for {vendor_substr}"
        )
    return True, (
        f"OK lockin={best['lockin_score']:.1f} {int(best['n_ministries']):>2d} ministries "
        f"${best['total_spend']:,.0f}"
    )


def main() -> int:
    cats = pd.read_parquet(ATLAS_DIR / "atlas_categories.parquet")
    vendors = pd.read_parquet(ATLAS_DIR / "atlas_vendor_dependency.parquet")

    print("=" * 90)
    print("KNOWN CASES EVAL — does the Atlas flag the things we already know are true?")
    print("=" * 90)
    failures = []
    for case in KNOWN_CASES:
        v, c, spend, threshold = case
        if v.startswith("__VENDOR__"):
            ok, msg = assert_vendor_case(vendors, v.replace("__VENDOR__", ""), spend, threshold)
            label = f"VENDOR {v.replace('__VENDOR__','')}"
        else:
            ok, msg = assert_category_case(cats, v, c, spend, threshold)
            label = f"CATEGORY {v} / {c}"
        marker = "[PASS]" if ok else "[FAIL]"
        print(f"  {marker} {label:<60s} {msg}")
        if not ok:
            failures.append((label, msg))

    print()
    if failures:
        print(f"FAILED: {len(failures)} of {len(KNOWN_CASES)} known cases not flagged correctly.")
        return 1
    print(f"PASSED: all {len(KNOWN_CASES)} known cases flagged at expected thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
