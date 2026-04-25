"""Investigation agent — for each candidate concentrated program, builds a dossier.

Pulls the program's full recipient roster, time series, and the dominant vendor's
broader federal funding footprint. Detects whether the vendor is also concentrated
in OTHER programs (a stronger signal than single-program concentration).
"""
from __future__ import annotations

from strands import Agent

from llm.client import make_model
from tools.sql import query_db

INVESTIGATION_PROMPT = """You are the INVESTIGATION agent. The Discovery agent gave you a
single concentrated federal spending program. Build a rich dossier so the
Validator can confirm or rule out concern.

For the candidate program (program + dept + top_vendor) use query_db to gather:

1. **All recipients of this program** since 2020: name, business_number, sum of
   agreement_value, agreement count, year range.
   SQL: GROUP BY recipient_legal_name from fed.grants_contributions
   WHERE prog_name_en = <program> AND owner_org_title = <dept>
     AND agreement_start_date >= '2020-01-01'.

2. **Annual time series** of program spend: total agreement_value per year.
   This shows whether concentration is recent or longstanding.

3. **Top-vendor's broader federal footprint**: sum agreement_value GROUP BY
   prog_name_en, owner_org_title for the top vendor across ALL fed programs
   (not just this one). Surfaces whether the vendor is dependent on this single
   program or has broad federal relationships.

4. **Top-vendor identity check**: look up the top vendor in
   general.entity_golden_records by bn_root or canonical_name to determine if
   it's a charity, government entity, or private corporation. Check
   dataset_sources for which datasets it appears in.

5. **Same-purpose program neighbours**: any other prog_name_en with similar
   text to this program and the same top vendor (use ILIKE for a few keyword
   matches from the program name).

Your final response MUST be a single JSON object with this exact shape:
{
  "program_key": "<key from candidate>",
  "program": "<program name>",
  "dept": "<owner_org_title>",
  "total_spend": <number>,
  "year_range": [<min>, <max>],
  "recipients": [
    {"name": "<legal name>", "bn": "<bn or null>", "amount": <number>,
     "agreement_count": <int>, "share_of_program": <0-1>}, ...
  ],
  "time_series": [
    {"year": <int>, "total_spend": <number>, "top_vendor_share": <0-1>}, ...
  ],
  "top_vendor": {
    "name": "<legal name>",
    "bn": "<bn or null>",
    "entity_type": "<charity | government | private | unknown>",
    "dataset_sources": [<list>],
    "fed_total_all_programs": <number>,
    "other_programs": [
      {"program": "<name>", "dept": "<dept>", "amount": <number>}, ...
    ]
  },
  "similar_programs_same_vendor": [
    {"program": "<name>", "dept": "<dept>", "amount": <number>}, ...
  ]
}

Be thorough but bounded — limit recipients to top 10, time_series to 5 years,
other_programs to top 10. Every number from a query result; do not invent."""


def make_investigation_agent() -> Agent:
    return Agent(
        name="investigation",
        model=make_model(),
        tools=[query_db],
        system_prompt=INVESTIGATION_PROMPT,
    )
