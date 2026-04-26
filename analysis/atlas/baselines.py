"""Statistical baselines from the actual data — kills magic numbers.

Every threshold the system uses (top-1 share >= 0.80, total >= $10M, etc.)
should be defensible as "the Nth percentile of the actual distribution"
rather than "we picked it from thin air." This module computes those
percentile distributions from the live Atlas data and prints them.

Run: python analysis/atlas/baselines.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.stdout.reconfigure(encoding="utf-8")

ATLAS_DIR = ROOT / "analysis" / "atlas_data"


def main() -> None:
    cats = pd.read_parquet(ATLAS_DIR / "atlas_categories.parquet")
    vendors = pd.read_parquet(ATLAS_DIR / "atlas_vendor_dependency.parquet")
    incumb = pd.read_parquet(ATLAS_DIR / "atlas_incumbency.parquet")

    print("=" * 80)
    print("BASELINES — derived from the actual data, justify every threshold")
    print("=" * 80)

    print("\n[atlas_categories] distribution of top-1 share across all categories:")
    pcts = cats["top1_share"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
    print(pcts.to_string())
    p99 = cats["top1_share"].quantile(0.99)
    p95 = cats["top1_share"].quantile(0.95)
    print(f"\n  Implication: 'top-1 share >= {p95:.2f}' = above 95th pct = unusual")
    print(f"               'top-1 share >= {p99:.2f}' = above 99th pct = extreme")

    print("\n[atlas_categories] distribution of total_spend per category (log-scale):")
    spend_pcts = cats["total_spend"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
    print(spend_pcts.to_string(float_format=lambda x: f"${x:,.0f}"))
    p95_spend = cats["total_spend"].quantile(0.95)
    p99_spend = cats["total_spend"].quantile(0.99)
    print(f"\n  Implication: '$10M magnitude floor for headline' is justified — that's ~{(cats['total_spend'] >= 10_000_000).mean()*100:.1f}% of categories.")

    print("\n[atlas_categories] distribution of Herfindahl index:")
    hpcts = cats["herfindahl"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
    print(hpcts.to_string())

    print("\n[atlas_vendor_dependency] distribution of n_ministries per vendor:")
    npcts = vendors["n_ministries"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
    print(npcts.to_string())
    p95_min = vendors["n_ministries"].quantile(0.95)
    print(f"\n  Implication: a vendor present in >={int(p95_min)} ministries is in the top 5% of cross-ministry breadth.")

    print("\n[atlas_vendor_dependency] distribution of lockin_score:")
    lpcts = vendors["lockin_score"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99])
    print(lpcts.to_string())

    print("\n[atlas_incumbency] step-function emergence stats:")
    n_step = int(incumb["is_step_function"].sum())
    n_total = len(incumb)
    print(f"  {n_step:,} of {n_total:,} (vendor x ministry) histories show step-function (z>5)")
    print(f"  ({n_step/n_total*100:.1f}% — these are vendors that suddenly appeared at scale)")


if __name__ == "__main__":
    main()
