"""Hour 2 smoke — exercises gini, incumbency_streak, vendor_footprint,
competition_count, cross_dataset_lookup, divergence_check, and the
explainer registry.

Run from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe agent/scripts/smoke_hour2.py
"""

from __future__ import annotations

from vendor_concentration_agent.math import (
    hhi_by_category,
    cr_n_by_category,
    gini_by_category,
    top_concentrated_categories,
    sole_source_rate,
    incumbency_streak,
    vendor_footprint,
    competition_count,
    cross_dataset_lookup,
    divergence_check,
    EXPLAINERS,
    get_explainer,
)


def line(s: str = "") -> None:
    print(s)


def section(title: str) -> None:
    line()
    line("=" * 80)
    line(title)
    line("=" * 80)


def main() -> None:
    section("Discovery: top 3 concentrated AB categories")
    top = top_concentrated_categories("ab_sole_source", min_total=10_000_000, limit=3)
    for c in top.value:
        line(f"  {c['top1_share_pct']:>5.1f}%  ${c['cat_total']:>14,.0f}  {c['top_vendor'][:40]:<40}  {c['category'][:50]}")

    pick = top.value[2]  # third entry — Microsoft Azure single-vendor monopoly
    cat = pick["category"]
    vendor = pick["top_vendor"]

    section(f"Concentration trio for: {cat[:60]}")
    h = hhi_by_category("ab_sole_source", cat)
    cr1 = cr_n_by_category("ab_sole_source", cat, n=1)
    g = gini_by_category("ab_sole_source", cat)
    line(f"  HHI   = {h.value:>10,.2f}   refs={h.references}")
    line(f"  CR_1  = {cr1.value:>6.2f}%      refs={cr1.references}")
    line(f"  Gini  = {g.value:>6.4f}       refs={g.references}")

    section(f"Incumbency streak: {vendor[:40]} in {cat[:30]}")
    inc = incumbency_streak("ab_sole_source", vendor, cat)
    line(f"  streak = {inc.value} consecutive fiscal year(s)")
    for step in inc.trace_steps:
        line(f"    {step['step']}: {step['value']}")

    section(f"Vendor footprint: {vendor[:50]}")
    fp = vendor_footprint(vendor)
    line(f"  contracts: {fp.value['contract_count']}   total $: {fp.value['total_amount']:,.0f}")
    line(f"  ministries ({fp.value['ministry_count']}): {fp.value['ministries'][:5]}{' …' if fp.value['ministry_count'] > 5 else ''}")
    line(f"  year range: {fp.value['first_year']} → {fp.value['last_year']}")

    section(f"Competition count for: {cat[:60]}")
    comp = competition_count("ab_sole_source", cat)
    line(f"  distinct vendors ever in this category = {comp.value}")
    band_lo = next((b for b in get_explainer("competition_count")["interpretation_bands"] if b["severity"] == "high"), None)
    if comp.value <= 2 and band_lo:
        line(f"  → flagged: {band_lo['label']} ({band_lo['range']}) — capacity-gap signal")

    section("Cross-dataset lookup: IBM Canada")
    xd = cross_dataset_lookup("IBM Canada")
    line(f"  matched = {xd.value.get('matched')}")
    if xd.value.get("matched"):
        line(f"  canonical_name = {xd.value['canonical_name']}")
        line(f"  dataset_sources = {xd.value['dataset_sources']}")
        line(f"  appears in: cra={xd.value['appears_in_cra']}  fed={xd.value['appears_in_fed']}  ab={xd.value['appears_in_ab']}")
        line(f"  source_link_count = {xd.value['source_link_count']}")

    section("Divergence check (planted: 100% vs 99.7%, then 100% vs 60%)")
    d1 = divergence_check(100.0, 99.7)
    d2 = divergence_check(100.0, 60.0)
    line(f"  100% vs 99.7%  -> {d1.value['verdict']}  delta_pct={d1.value['delta_pct']}")
    line(f"  100% vs 60%    -> {d2.value['verdict']}  delta_pct={d2.value['delta_pct']}")

    section("Explainer registry coverage")
    line(f"  formula_ids registered: {len(EXPLAINERS)}")
    needed = {
        "hhi", "cr_n", "gini",
        "sole_source_rate", "incumbency_streak", "vendor_footprint", "competition_count",
        "cross_dataset_lookup", "divergence_check", "top_concentrated_categories",
    }
    missing = needed - set(EXPLAINERS.keys())
    if missing:
        line(f"  MISSING: {missing}")
    else:
        line(f"  all {len(needed)} expected ids present")

    line()
    line("Hour 2 smoke: OK")


if __name__ == "__main__":
    main()
