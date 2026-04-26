"""Discovery agent — finds federal spending programs where ONE vendor dominates.

Replaces v1.x funding-loops Discovery. Targets fed.grants_contributions at the
program level (prog_name_en + owner_org_title) to surface single-recipient
concentration since 2020.
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model
from tools.sql import query_db

DISCOVERY_PROMPT = """You are the DISCOVERY agent in a 4-agent investigation pipeline analysing
Canadian federal government spending for vendor-concentration patterns.

Your goal: surface the {top_n} highest-signal candidate spending programs from
fed.grants_contributions where ONE recipient dominates a program's total spend.
The next agent (Investigation) will build full dossiers on these candidates.

Use the query_db tool to run a SQL query against fed.grants_contributions. The
target shape is:

  - Group by (prog_name_en, owner_org_title) since 2020-01-01
  - Sum agreement_value per (program, recipient_legal_name)
  - For each program, identify the top-1 recipient and compute its share
  - Filter: program total >= $1M AND top-1 share >= 0.80
  - **REQUIRE recipient_count >= 2** — pure single-recipient programs are by
    design (named-program contributions, treaty obligations, sole-source by
    enabling legislation). Exclude them up front to focus on programs where
    OTHER recipients exist but one dominates.
  - **REQUIRE top-1 share <= 0.99** — exact-100% single-recipient is also
    likely by design even when recipient_count appears to be >= 2 due to data
    noise. Concentration in the 0.80-0.99 band is the investigative sweet spot.
  - Filter out programs whose name CONTAINS the recipient name verbatim
    (Mitacs Inc., Genome Canada, Canarie are legitimate by-design singletons).
    Use a SQL ILIKE check.
  - Filter out vendors that are obvious government entities — exclude where
    lower(recipient_legal_name) LIKE ANY of:
       '%ministre%', '%minister of%', '%government of%', '%province of%',
       '%receiver general%', '%crown corporation%', '%first nations%',
       '%indigenous%', '%metis%', '%inuit%', '%nation government%',
       '%authority%', '%city of%', '%municipality%', '%regional district%'.
    These are intergovernmental transfers and treaty obligations, not
    competitive-procurement issues.
  - Order by (total_spend * top_share) DESC, take top {top_n}

Useful columns:
  - prog_name_en, owner_org_title, recipient_legal_name, recipient_business_number,
    agreement_value, agreement_start_date

Your final response MUST be a JSON array of objects with this exact shape, and
nothing else:
[
  {{
    "program_key": "<prog_name_en>::<owner_org_title>",
    "program": "<prog_name_en>",
    "dept": "<owner_org_title>",
    "total_spend": <number>,
    "top_vendor": "<recipient_legal_name>",
    "top_vendor_bn": "<recipient_business_number or null>",
    "top_vendor_amount": <number>,
    "top_vendor_share": <0.0-1.0>,
    "year_range": [<min_year>, <max_year>],
    "preliminary_score": <0-100>,
    "rationale": "<one sentence explaining why this program is interesting>"
  }},
  ...
]

Score rubric (0-100):
- $ magnitude (0-40): log10(total_spend) clamped
- Concentration intensity (0-30): linear in top_vendor_share above 0.80
- Recency (0-30): tighter year_range AND more weight on 2022+ = higher

Be rigorous. Do not invent data. Every field must come from a query result.
Excluding named-recipient programs upfront is critical — those would be
unanimously ruled out by the Validator and waste tokens."""


def make_discovery_agent(top_n: int = 20) -> Agent:
    return Agent(
        name="discovery",
        model=make_model(),
        tools=[query_db],
        system_prompt=DISCOVERY_PROMPT.format(top_n=top_n),
    )
