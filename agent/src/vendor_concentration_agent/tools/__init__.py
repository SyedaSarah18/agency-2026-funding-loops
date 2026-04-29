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
    list_top_concentrated_ministries,
    list_vendor_counts_by_ministry,
    scan_all_procurement_datasets,
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
from vendor_concentration_agent.tools.kb import (
    query_kb_categories,
    query_kb_ministries_departments,
    read_methodology,
)

DISCOVERY_TOOLS = [
    # Primary live tools — always try these first
    scan_all_procurement_datasets,        # broad: all 3 datasets in one call
    list_top_concentrated_categories,     # narrow: one dataset by category
    list_top_concentrated_ministries,     # narrow: one dataset by ministry
    list_vendor_counts_by_ministry,       # narrow: competition count by ministry
    # KB fallback — pre-computed full coverage; use only when live query
    # returns empty / insufficient results or the question requires ALL rows
    query_kb_categories,              # all categories with vendor counts
    query_kb_ministries_departments,  # all ministries/depts with vendor counts
    read_methodology,                 # how metrics are computed (HHI, Gini, etc.)
]

INVESTIGATION_TOOLS = [
    hhi_for_category,
    cr_n_for_category,
    gini_for_category,
    sole_source_share,
    how_long_has_vendor_held_category,
    vendor_full_footprint,
    how_many_distinct_vendors_in_category,
    read_methodology,  # for explaining how a metric was computed
]

VALIDATOR_TOOLS = [
    # Validator's job is to cross-check — NOT to re-run the same metric on
    # the same inputs. Tool access is restricted to:
    cross_dataset_lookup_for_vendor,    # cross-jurisdiction confirm
    compare_two_computations,           # arithmetic delta verdict
    sole_source_share,                   # sibling-table comparison vs sole-source rate
    # Deliberately NOT exposed: hhi_for_category, cr_n_for_category,
    # vendor_full_footprint, how_many_distinct_vendors_in_category, gini —
    # those would let the Validator "re-run with slightly wrong inputs"
    # and produce false DIVERGE verdicts.
]

NARRATIVE_TOOLS: list = []  # writing only — no tools

__all__ = [
    "DISCOVERY_TOOLS",
    "INVESTIGATION_TOOLS",
    "VALIDATOR_TOOLS",
    "NARRATIVE_TOOLS",
]
