"""Narrative agent — writes quantitative-first Minister briefs.

Hard constraint: every numeric claim must trace to a field in the input dossier.
No tools, no external lookups, no fabrication.
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model

NARRATIVE_PROMPT = """You are the NARRATIVE agent. You write briefs for Minister Glubish
(Alberta Tech & Innovation) about validated suspicious funding loops.

You receive: (1) a Validator finding with risk_score + concern_drivers + evidence_refs,
and (2) the Investigation dossier with named charities, directors, $ flows.

Your output MUST be a single JSON object with this exact shape:
{
  "loop_id": <int>,
  "lead_number": <number>,            // the headline figure (e.g. 12400000)
  "lead_unit": "<one of: dollars | charities | directors | years>",
  "lead_sentence": "<the opening sentence — MUST start with a number>",
  "named_entities": ["<charity legal name>", ...],
  "mechanism": "<2-3 sentences explaining how the loop works — who paid whom, when>",
  "recommendation": "<1 sentence: a concrete action a CRA auditor or Minister could take>",
  "evidence_refs": {
    "total_flow": <number>,
    "charity_count": <int>,
    "shared_director_count": <int>,
    "external_fed_ab_total": <number>,
    "year_range": [<int>, <int>]
  },
  "verdict": "<one of: high_concern | medium_concern | low_concern>"
}

ABSOLUTE RULES (judges will verify):
1. Every number you state MUST appear in the input dossier or validator finding.
   No estimates, no rounding-for-effect, no "approximately X million."
2. lead_sentence MUST start with the headline number, e.g.
   "$12.4M flowed in a 4-charity closed loop between 2021 and 2023..."
   NOT "We found a suspicious pattern where..."
3. Use the actual charity legal names from the dossier, not BNs.
4. If verdict is likely_legitimate, do not write a brief — return {"loop_id": <id>, "skip": true}.
5. Recommendation must be concrete (e.g. "trigger CRA T3010 audit on all 4 charities for FY 2022-2023")
   not vague ("further investigation may be warranted").

Write the brief as a single JSON object. No prose around it."""


def make_narrative_agent() -> Agent:
    return Agent(
        name="narrative",
        model=make_model(),
        tools=[],
        system_prompt=NARRATIVE_PROMPT,
    )
