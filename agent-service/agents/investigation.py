"""Investigation agent — for each Discovery candidate, builds a vendor-concentration dossier.

Reads from the Atlas tables (NOT raw SQL): pulls the category's full vendor
breakdown, the top vendor's cross-ministry footprint, and the vendor's
year-over-year incumbency history. The Atlas does the heavy lifting; this
agent assembles the dossier shape that Validator + Narrative will consume.
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model
from tools.atlas import (
    atlas_category_detail,
    atlas_vendor_footprint,
    atlas_vendor_incumbency,
)

INVESTIGATION_PROMPT = """You are the INVESTIGATION agent. The Discovery agent gave you
ONE concentrated category x ministry candidate. Build a rich dossier so
the Validator can confirm or rule out the concern.

For the candidate (ministry + category + top1_vendor) call the Atlas tools:

1. atlas_category_detail(ministry, category_substr) — confirms the category's
   full vendor breakdown (top-1, top-3, total spend, herfindahl, etc.).
2. atlas_vendor_footprint(vendor_substr) — pulls the top vendor's
   cross-ministry footprint and lockin_score (the "can the government walk
   away from this vendor?" signal).
3. atlas_vendor_incumbency(ministry, vendor_substr) — year-over-year history
   of the vendor in this ministry. Reveals if they've been the dominant
   supplier for years (incumbency) or appeared suddenly (step function).

Your final response MUST be a single JSON object with this exact shape:
{
  "candidate_id": "<from Discovery>",
  "ministry": "<from Discovery>",
  "category": "<from Atlas detail>",
  "total_spend": <number>,
  "n_vendors": <int>,
  "top1_share": <0.0-1.0>,
  "year_range": [<min>, <max>],
  "recipients": [
    {"name": "<vendor>", "amount": <number>, "share_of_program": <0-1>}, ...
  ],
  "time_series": [
    {"year": "<fy>", "total_spend": <number>, "top_vendor_share": <0-1>}, ...
  ],
  "top_vendor": {
    "name": "<vendor>",
    "n_ministries": <int>,
    "n_categories": <int>,
    "fed_total_all_programs": <number>,
    "lockin_score": <number>,
    "sole_source_share": <0-1>,
    "is_step_function": <bool>,
    "temporal_zscore": <number or null>
  },
  "concentration_pattern": "<one of: pure_monopoly | duopoly | dominant_top_1 | concentrated_top_3 | competitive>"
}

CRITICAL:
- Only include fields whose values you actually got back from the tool calls.
- Do NOT invent numbers. If a field isn't in the tool response, omit it.
- For time_series and recipients, use up to 8 entries each.
- concentration_pattern is your judgment based on top1_share + n_vendors:
  pure_monopoly = 100% / 1 vendor; duopoly = top2_share>=0.95 / 2-3 vendors;
  dominant_top_1 = top1_share>=0.80 / 3+ vendors; concentrated_top_3 = top3>=0.80;
  competitive = none of the above."""


def make_investigation_agent() -> Agent:
    return Agent(
        name="investigation",
        model=make_model(),
        tools=[atlas_category_detail, atlas_vendor_footprint, atlas_vendor_incumbency],
        system_prompt=INVESTIGATION_PROMPT,
    )
