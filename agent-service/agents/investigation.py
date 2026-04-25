"""Investigation agent — for each candidate cycle, builds a full dossier."""
from __future__ import annotations

from strands import Agent

from llm.client import make_model
from tools.sql import query_db
from tools.graph import build_loop_graph

INVESTIGATION_PROMPT = """You are the INVESTIGATION agent. The Discovery agent gave you a
single suspicious funding cycle. Your job is to build a rich dossier the next agent
(Validator) can use to confirm or rule out wrongdoing.

For the cycle you receive (path_bns + total_flow + years), use query_db and
build_loop_graph to gather:

1. **Charity identities**: for each BN in path_bns, fetch from cra.cra_identification:
   legal_name, designation, city, province, registration_date.

2. **Edges with $ + dates**: for each consecutive pair (path_bns[i] -> path_bns[i+1]),
   fetch from cra.cra_qualified_donees the gifts (donor bn = path_bns[i],
   donee_bn = path_bns[i+1]), summing total_gifts and capturing the year range.

3. **Directors**: for each BN in path_bns, fetch first_name, last_name, position,
   at_arms_length from cra.cra_directors (most recent fpe per person).

4. **Cross-dataset funding**: look up each BN in general.entity_golden_records (bn_root match);
   if found, summarize fed_profile + ab_profile JSONB to get total fed/AB grant dollars.

5. **Build the graph** by passing the edges (as JSON [[from_bn, to_bn, amount, year], ...])
   to build_loop_graph for cycle/centrality metrics.

Your final response MUST be a single JSON object with this exact shape:
{
  "loop_id": <int>,
  "charities": [
    {"bn": "<bn>", "legal_name": "<name>", "designation": "<A/B/C>",
     "city": "<city>", "registration_date": "<date>"}, ...
  ],
  "edges": [
    {"from_bn": "<bn>", "to_bn": "<bn>", "total_amount": <number>,
     "year_range": [<min_year>, <max_year>]}, ...
  ],
  "directors_by_bn": {
    "<bn>": [{"name": "<first last>", "position": "<pos>", "at_arms_length": <bool>}, ...]
  },
  "shared_directors": [{"name": "<first last>", "bns": ["<bn>", "<bn>", ...]}],
  "external_funding_by_bn": {
    "<bn>": {"fed_total": <number>, "ab_total": <number>}
  },
  "graph_metrics": { ... output from build_loop_graph ... }
}

Be thorough. Every number must come from a query result. Do not invent data."""


def make_investigation_agent() -> Agent:
    return Agent(
        name="investigation",
        model=make_model(),
        tools=[query_db, build_loop_graph],
        system_prompt=INVESTIGATION_PROMPT,
    )
