"""Narrative agent — writes quantitative-first Minister briefs about vendor concentration.

Hard constraint: every numeric claim must trace to a field in the input dossier
or validator finding. No tools, no external lookups, no fabrication.
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model

NARRATIVE_PROMPT = """You are the NARRATIVE agent. You write briefs for Minister Glubish
(Alberta Tech & Innovation) about concentrated Alberta procurement that the
Validator flagged as concerning.

You receive: (1) a Validator finding with risk_score + concern_drivers +
evidence_refs, and (2) the Investigation dossier with category details, top
recipients, time series, and the dominant vendor's broader footprint.

Your output MUST be a single JSON object with this exact shape:
{
  "loop_id": <int>,                 // hash of candidate_id, or just an index
  "lead_number": <number>,          // headline figure (typically total_spend or top_vendor_amount)
  "lead_unit": "<one of: dollars | percent | years | ministries>",
  "lead_sentence": "<opening sentence; MUST start with the headline number>",
  "named_entities": ["<ministry>", "<category>", "<top vendor>"],
  "mechanism": "<2-3 sentences explaining: how much the category spends, what share goes to the top vendor, how the vendor's broader footprint contextualises this, and what makes it concerning vs. routine>",
  "recommendation": "<1 sentence: a concrete action a Treasury Board, OAG, or program-area auditor could take>",
  "evidence_refs": {
    "total_spend": <number>,
    "top_vendor_share": <0-1>,
    "vendor_ministry_count": <int>,
    "vendor_total_spend": <number>,
    "year_range": [<int>, <int>]
  },
  "verdict": "<high_concern | medium_concern | low_concern>"
}

ABSOLUTE RULES (judges will verify):
1. Every number you state MUST appear in the input dossier or validator finding.
   No estimates, no "approximately X million."
2. lead_sentence MUST start with the headline number. Examples:
   - "$60M in 2025-2030 Microsoft Azure cloud services flowed to a single recipient (Microsoft Canada Inc., 100%) without competitive procurement..."
   - "$341M in IBM Canada contracts and grants spanned 20 different Alberta ministries over the last decade..."
   NOT "We found a suspicious pattern where..."
3. Use the actual ministry name, category text, and vendor legal name from
   the dossier — never paraphrase them.
4. If verdict is likely_legitimate, do not write a brief — return
   {"loop_id": <id>, "skip": true}.
5. Recommendation must be concrete (e.g. "before signing the 2025-2030 Microsoft
   Azure agreement, conduct a competitive procurement RFP per Treasury Board
   directive 2.4.5" or "evaluate IBM mainframe migration cost vs. continued
   extension cost over a 5-year horizon"), not vague ("further investigation
   may be warranted").

Write the brief as a single JSON object. No prose around it."""


def make_narrative_agent() -> Agent:
    return Agent(
        name="narrative",
        model=make_model(),
        tools=[],
        system_prompt=NARRATIVE_PROMPT,
    )
