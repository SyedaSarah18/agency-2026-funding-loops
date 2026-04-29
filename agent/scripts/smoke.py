"""Smoke test — exercises hhi, cr_n, top_concentrated_categories, and
sole_source_rate against the live organizer Postgres.

Run from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe agent/scripts/smoke.py
"""

from __future__ import annotations

from vendor_concentration_agent.math import (
    hhi_by_category,
    cr_n_by_category,
    top_concentrated_categories,
    sole_source_rate,
)


def _line(s: str = "") -> None:
    print(s)


def main() -> None:
    _line("=" * 80)
    _line("TOP 5 CONCENTRATED AB SOLE-SOURCE CATEGORIES (>= $10M, by CR_1)")
    _line("=" * 80)
    res = top_concentrated_categories("ab_sole_source", min_total=10_000_000, limit=5)
    for row in res.value:
        _line(
            f"  {row['top1_share_pct']:>5.1f}%  "
            f"${row['cat_total']:>14,.0f}  "
            f"{row['vendor_count']:>3} vendors  "
            f"top: {row['top_vendor'][:40]:<40}  "
            f"{row['category'][:45]}"
        )

    pick = res.value[2]
    cat = pick["category"]
    _line()
    _line("=" * 80)
    _line(f"DEEP DIVE: {cat[:70]}")
    _line("=" * 80)

    h = hhi_by_category("ab_sole_source", cat)
    _line(f"HHI         = {h.value:>10,.2f}   (DOJ band: "
          f"{'highly concentrated' if h.value > 2500 else 'moderate' if h.value > 1500 else 'competitive'})")
    _line(f"  vendors   = {h.inputs['vendor_count']}")
    _line(f"  total $   = {h.inputs['category_total']:,.0f}")
    _line(f"  refs      = {h.references}")

    cr1 = cr_n_by_category("ab_sole_source", cat, n=1)
    cr4 = cr_n_by_category("ab_sole_source", cat, n=4)
    _line(f"CR_1        = {cr1.value:>6.2f}%")
    _line(f"CR_4        = {cr4.value:>6.2f}%")

    _line()
    _line("trace_steps for HHI (top 5):")
    for step in h.trace_steps[:5]:
        _line(f"  {step['vendor'][:40]:<40}  share={step['share_pct']:>6.2f}%  squared={step['share_pct_squared']:>10,.2f}")

    _line()
    _line("=" * 80)
    _line("SOLE-SOURCE RATE — overall, all years")
    _line("=" * 80)
    ssr = sole_source_rate()
    _line(f"  rate      = {ssr.value:>6.2f}%")
    for step in ssr.trace_steps:
        _line(f"  {step['step']:<35} = {step['value']:>14,.2f}")

    _line()
    _line("=" * 80)
    _line("SOLE-SOURCE RATE — Service Alberta")
    _line("=" * 80)
    try:
        ssr_sa = sole_source_rate(ministry="Service Alberta")
        _line(f"  rate      = {ssr_sa.value:>6.2f}%")
        for step in ssr_sa.trace_steps:
            _line(f"  {step['step']:<35} = {step['value']:>14,.2f}")
    except Exception as e:
        _line(f"  (skipped: {e})")

    _line()
    _line("Hour 1 smoke: OK")


if __name__ == "__main__":
    main()
