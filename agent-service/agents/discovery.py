"""Discovery agent — picks top-N candidates from the pre-computed Atlas.

Replaces v1.x funding-loops + v2.x raw-SQL Discovery. The data layer
(analysis/atlas/build.py) has already pre-computed the Watchlist of
concentrated category x ministry rows ranked by composite_risk_score.
Discovery's only job is to call atlas_top_categories() and rank the
results, then optionally drill into specific candidates if needed.

This is data-first discipline: the heavy analysis happens once at
build time, not on every agent run. The Validator and known_cases.py
eval already proved the Atlas methodology is sound.
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model
from tools.atlas import atlas_top_categories, atlas_category_detail

DISCOVERY_PROMPT = """You are the DISCOVERY agent. Your job is to surface
the {top_n} highest-signal vendor-concentration candidates from the pre-computed
Procurement Concentration Atlas for the next agent (Investigation) to dig into.

The Atlas is already ranked by composite_risk_score combining dollar magnitude,
top-1 vendor share, vendor scarcity, and cross-ministry lock-in breadth. You do
NOT need to write SQL or compute concentration — just call the tool.

Steps:
1. Call atlas_top_categories(top_n={top_n}) to get the Watchlist.
2. (Optional) Call atlas_category_detail(ministry, category_substr) to drill
   into any candidate whose details you want to confirm before passing on.
3. Return the {top_n} candidates as a JSON array. Use the EXACT data the
   Atlas returned — do not invent fields or modify numbers.

Your final response MUST be a JSON array of objects with this exact shape:
[
  {{
    "candidate_id": "<ministry>::<category short label>",
    "ministry": "<ministry>",
    "category": "<category from the Atlas>",
    "total_spend": <number>,
    "n_vendors": <int>,
    "top1_vendor": "<vendor name>",
    "top1_amount": <number>,
    "top1_share": <0.0-1.0>,
    "headline_risk_score": <number>,
    "rationale": "<one sentence: why this is the next agent's priority>"
  }},
  ...
]

Be selective and rigorous — only pass through the {top_n} STRONGEST signals.
Skip any row whose top1_vendor name suggests an obvious by-design singleton
(an Indigenous government, a Crown corporation, a named-recipient program where
the program name and vendor name match) — the Validator will catch these too,
but Discovery should pre-filter to save downstream work."""


def make_discovery_agent(top_n: int = 5) -> Agent:
    return Agent(
        name="discovery",
        model=make_model(),
        tools=[atlas_top_categories, atlas_category_detail],
        system_prompt=DISCOVERY_PROMPT.format(top_n=top_n),
    )
