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
    """List categories ranked by single-vendor share. ONLY works on
    `ab_sole_source` (the only dataset with a category column).
    Use this to find sole-source LOCK-IN by service category.

    Returns: ranked list of categories, each with top vendor, vendor count,
    cumulative spend, and CR_1 share.

    Args:
        dataset: must be "ab_sole_source".
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
