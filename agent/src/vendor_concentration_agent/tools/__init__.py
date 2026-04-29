"""Strands @tool wrappers around the deterministic math layer.

Discovery agent tools:
  list_top_concentrated_categories

Investigation agent tools:
  hhi_for_category
  cr_n_for_category
  gini_for_category
  sole_source_share
  how_long_has_vendor_held_category
  vendor_full_footprint
  how_many_distinct_vendors_in_category

Validator agent tools:
  cross_dataset_lookup_for_vendor
  compare_two_computations
  (plus the Investigation tools, so it can re-run a number on a sibling table)
"""

from vendor_concentration_agent.tools.concentration import (
    list_top_concentrated_categories,
    hhi_for_category,
    cr_n_for_category,
    gini_for_category,
)
from vendor_concentration_agent.tools.procurement import (
    sole_source_share,
    how_long_has_vendor_held_category,
    vendor_full_footprint,
    how_many_distinct_vendors_in_category,
)
from vendor_concentration_agent.tools.crosscheck import (
    cross_dataset_lookup_for_vendor,
    compare_two_computations,
)

DISCOVERY_TOOLS = [
    list_top_concentrated_categories,
]

INVESTIGATION_TOOLS = [
    hhi_for_category,
    cr_n_for_category,
    gini_for_category,
    sole_source_share,
    how_long_has_vendor_held_category,
    vendor_full_footprint,
    how_many_distinct_vendors_in_category,
]

VALIDATOR_TOOLS = [
    cross_dataset_lookup_for_vendor,
    compare_two_computations,
    # Validator may re-run any investigation tool on a sibling slice
    hhi_for_category,
    cr_n_for_category,
    sole_source_share,
    vendor_full_footprint,
    how_many_distinct_vendors_in_category,
]

NARRATIVE_TOOLS: list = []  # writing only — no tools

__all__ = [
    "DISCOVERY_TOOLS",
    "INVESTIGATION_TOOLS",
    "VALIDATOR_TOOLS",
    "NARRATIVE_TOOLS",
]
