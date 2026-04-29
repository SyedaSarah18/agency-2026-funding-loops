"""Strands @tool wrappers for the concentration math functions.

Each tool is a thin adapter: take simple LLM-friendly args, call the
deterministic math, push full audit data to the EventBus, return a lean
summary the LLM can reason about.
"""

from __future__ import annotations

from typing import Any

from strands import tool

from vendor_concentration_agent.math import (
    hhi_by_category,
    cr_n_by_category,
    gini_by_category,
    top_concentrated_categories,
    top_concentrated_ministries,
    vendor_count_per_ministry,
)
from vendor_concentration_agent.tools._wrap import new_call_id, summarize_for_llm


@tool
def list_top_concentrated_categories(
    dataset: str = "ab_sole_source",
    min_total: float = 10_000_000.0,
    limit: int = 10,
) -> dict[str, Any]:
    """List categories ranked by single-vendor share (vendor_count per
    category and CR_1 share). Works on ANY dataset that has a category
    column — `ab_sole_source` (contract_services) and `fed_contracts`
    (economic_object_code). Call it ONCE per dataset to get category-level
    vendor counts across both provincial and federal procurement.

    Returns: ranked list of categories, each with top vendor, vendor count,
    cumulative spend, and CR_1 share.

    ⚠️ NARROW TOOL — call this only when you need a per-category breakdown
    of a SPECIFIC dataset. For broad concentration questions (disproportionate
    share across government, lock-in without an explicit dataset scope) call
    `scan_all_procurement_datasets` instead.

    Args:
        dataset: "ab_sole_source" (category = contract_services) or
                 "fed_contracts" (category = economic_object_code).
        min_total: drop categories below this $ threshold.
        limit: max categories to return.
    """
    result = top_concentrated_categories(dataset=dataset, min_total=min_total, limit=limit)
    return summarize_for_llm(result, new_call_id("top_categories"))


@tool
def list_top_concentrated_ministries(
    dataset: str = "ab_contracts",
    min_total: float = 10_000_000.0,
    limit: int = 10,
) -> dict[str, Any]:
    """List ministries ranked by single-vendor dominance. Works on
    `ab_contracts` (Alberta competitive procurement) and `ab_sole_source`.
    Use this when you want to see which DEPARTMENT is most dependent on
    one vendor — the natural concentration unit when there's no per-
    contract category column.

    Returns: ranked list of ministries, each with top vendor, distinct
    vendor count, cumulative spend, and CR_1 share.

    Args:
        dataset: "ab_contracts" (competitive baseline) or "ab_sole_source".
        min_total: drop ministries below this $ threshold.
        limit: max ministries to return.
    """
    result = top_concentrated_ministries(dataset=dataset, min_total=min_total, limit=limit)
    return summarize_for_llm(result, new_call_id("top_ministries"))


@tool
def list_vendor_counts_by_ministry(
    dataset: str = "ab_contracts",
    min_total: float = 1_000_000.0,
    limit: int = 20,
) -> dict[str, Any]:
    """For each ministry in the dataset, count distinct vendors and total
    spend. Sorted from MOST competition to LEAST. This is the honest
    answer to 'how many vendors are actually competing?' — DO use this
    on `ab_contracts` (the competitive procurement table), NOT on
    `ab_sole_source` (which by definition is single-vendor per row).

    Args:
        dataset: "ab_contracts" recommended.
        min_total: drop ministries below this $ threshold.
        limit: max ministries to return.
    """
    result = vendor_count_per_ministry(dataset=dataset, min_total=min_total, limit=limit)
    return summarize_for_llm(result, new_call_id("vendor_counts"))


def _scan_all_impl(min_total: float, per_dataset_limit: int) -> dict[str, Any]:
    """Underlying implementation of scan_all_procurement_datasets, called
    by both the @tool wrapper and our smoke tests.
    """
    return _scan_all_impl_body(min_total, per_dataset_limit)


@tool
def scan_all_procurement_datasets(
    min_total: float = 10_000_000.0,
    per_dataset_limit: int = 3,
) -> dict[str, Any]:
    """Scan ALL THREE procurement datasets in a single call and return
    the top concentrated findings from each, tagged with which dataset
    they came from. Use this whenever the question is broad (Canadian
    government overall, "any category," competition landscape, etc.) so
    every answer covers federal AND provincial AND sole-source.

    Returns a single unified result whose .findings list contains
    entries from:
      - ab_sole_source (top categories by single-vendor share)
      - ab_contracts   (top ministries by single-vendor share, competitive)
      - fed_contracts  (top federal departments by single-vendor share)

    Args:
        min_total: drop categories/ministries below this $ threshold.
        per_dataset_limit: max items per dataset (default 3 → up to 9 total).
    """
    return _scan_all_impl_body(min_total, per_dataset_limit)


def _scan_all_impl_body(min_total: float, per_dataset_limit: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    # Pull from each dataset; tolerate any one failure rather than
    # bailing on the whole scan.
    try:
        r1 = top_concentrated_categories(
            dataset="ab_sole_source",
            min_total=min_total,
            limit=per_dataset_limit,
        )
        for c in r1.value:
            findings.append({
                "dataset": "ab_sole_source",
                "slice_type": "category",
                "slice_label": "Service category",
                "name": c["category"],
                "top_vendor": c["top_vendor"],
                "total_spend": c["cat_total"],
                "vendor_count": c["vendor_count"],
                "top1_share_pct": c["top1_share_pct"],
                "call_id": new_call_id("scan_ab_ss"),
            })
    except Exception as e:
        findings.append({"dataset": "ab_sole_source", "error": str(e)})

    try:
        r2 = top_concentrated_ministries(
            dataset="ab_contracts",
            min_total=min_total,
            limit=per_dataset_limit,
        )
        for c in r2.value:
            findings.append({
                "dataset": "ab_contracts",
                "slice_type": "ministry",
                "slice_label": "Alberta ministry",
                "name": c["ministry"],
                "top_vendor": c["top_vendor"],
                "total_spend": c["ministry_total"],
                "vendor_count": c["vendor_count"],
                "top1_share_pct": c["top1_share_pct"],
                "call_id": new_call_id("scan_ab_c"),
            })
    except Exception as e:
        findings.append({"dataset": "ab_contracts", "error": str(e)})

    try:
        r3 = top_concentrated_ministries(
            dataset="fed_contracts",
            min_total=min_total,
            limit=per_dataset_limit,
        )
        for c in r3.value:
            findings.append({
                "dataset": "fed_contracts",
                "slice_type": "ministry",
                "slice_label": "Federal department",
                "name": c["ministry"],
                "top_vendor": c["top_vendor"],
                "total_spend": c["ministry_total"],
                "vendor_count": c["vendor_count"],
                "top1_share_pct": c["top1_share_pct"],
                "call_id": new_call_id("scan_fed"),
            })
    except Exception as e:
        findings.append({"dataset": "fed_contracts", "error": str(e)})

    # Emit one consolidated tool_result so the chat thread shows ONE
    # multi-dataset card instead of three single-dataset cards.
    from vendor_concentration_agent.trace.events import current_bus
    import asyncio as _asyncio
    bus = current_bus()
    if bus is not None:
        try:
            loop = _asyncio.get_running_loop()
            loop.create_task(bus.emit_tool_result(
                "multi_dataset_scan",
                {"findings": findings, "min_total": min_total},
                call_id=new_call_id("scan_all"),
            ))
        except RuntimeError:
            pass

    return {
        "findings": findings,
        "datasets_scanned": ["ab_sole_source", "ab_contracts", "fed_contracts"],
        "min_total": min_total,
        "instruction_for_agent": (
            "Use these findings as your candidate list. Every candidate has a "
            "'dataset' field — preserve it through your plan so the user can "
            "see which jurisdiction each finding came from."
        ),
    }


@tool
def hhi_for_category(dataset: str, category: str) -> dict[str, Any]:
    """Compute the Herfindahl-Hirschman Index (HHI) for a specific category
    in a specific dataset.

    HHI is the sum of (vendor_share_percent)^2. Range 0–10,000. DOJ/FTC bands:
    below 1500 = competitive, 1500–2500 = moderately concentrated, above
    2500 = highly concentrated. A category with a single vendor returns
    HHI = 10,000.

    Args:
        dataset: "ab_sole_source".
        category: exact category text from the procurement table.
    """
    result = hhi_by_category(dataset=dataset, category=category)
    return summarize_for_llm(result, new_call_id("hhi"))


@tool
def cr_n_for_category(dataset: str, category: str, n: int = 4) -> dict[str, Any]:
    """Compute the top-n concentration ratio (CR_n) for a category. CR_1 is
    the single largest vendor's share; CR_4 is the four-firm concentration
    ratio used in industrial-organization economics.

    Args:
        dataset: "ab_sole_source".
        category: exact category text.
        n: how many top vendors to combine. Default 4.
    """
    result = cr_n_by_category(dataset=dataset, category=category, n=n)
    return summarize_for_llm(result, new_call_id(f"cr{n}"))


@tool
def gini_for_category(dataset: str, category: str) -> dict[str, Any]:
    """Compute the Gini coefficient of contract-value distribution across
    vendors in a category. 0 = perfect equality (all vendors win equal $);
    closer to 1 = one vendor takes everything.

    Args:
        dataset: "ab_sole_source".
        category: exact category text.
    """
    result = gini_by_category(dataset=dataset, category=category)
    return summarize_for_llm(result, new_call_id("gini"))
