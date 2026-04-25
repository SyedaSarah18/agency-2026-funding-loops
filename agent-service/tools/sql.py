"""Read-only SQL tool exposed to Strands agents.

Wraps a single connection-per-call psycopg2 query against the organizer's hosted PG.
Returns rows as plain dict lists (JSON-serializable) so the LLM can reason over them.
"""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from strands import tool

from config import PG_DSN

# Cap how much we ever return to the LLM in one call.
MAX_ROWS_RETURNED = 200
STMT_TIMEOUT_MS = 60_000


def _normalize(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items()}
    return v


@tool
def query_db(sql: str) -> str:
    """Run a read-only SQL query against the Agency 2026 PostgreSQL database
    and return the result rows as a JSON string.

    Schemas you can query: cra, fed, ab, general.

    Useful tables:
      - cra.loops (5808 rows): id, hops, path_bns (text[]), path_display, total_flow, min_year, max_year
      - cra.loop_universe (1501 rows): bn, legal_name, total_loops, score, total_circular_amt
      - cra.cra_identification (421K): bn, fiscal_year, legal_name, designation, registration_date, city, province
      - cra.cra_qualified_donees (1.66M): bn (donor), donee_bn, donee_name, total_gifts, fpe (date)
      - cra.cra_directors (2.87M): bn, first_name, last_name, position, at_arms_length, start_date, end_date
      - cra.cra_compensation (216K): bn, fpe, field_300 (FT employees), field_310 (PT employees)
      - cra.cra_financial_details (420K): bn, fpe, field_4500 (total revenue), field_5100 (total expenses)
      - fed.grants_contributions (1.28M): recipient_legal_name, recipient_business_number, agreement_value, agreement_start_date, prog_name_en, owner_org, is_amendment, amendment_number
      - ab.ab_grants (1.99M): recipient, ministry, program, amount, payment_date, fiscal_year
      - ab.ab_contracts (67K): recipient, ministry, amount, display_fiscal_year
      - ab.ab_sole_source (15K): vendor, ministry, amount, start_date, end_date
      - general.entity_golden_records (851K): id, canonical_name, bn_root, dataset_sources (text[]), cra_profile/fed_profile/ab_profile (jsonb)
      - general.entity_source_links (5.16M): entity_id, source_schema, source_table, source_pk (jsonb), source_name

    Constraints:
      - Read-only. The connection rejects writes.
      - Limited to 200 rows per call. Use LIMIT explicitly when you expect many.
      - 60-second statement timeout.
    """
    sql = sql.strip().rstrip(";")
    # Hard guard against accidental writes (psycopg2 readonly already blocks them, but fail fast).
    forbidden = ("insert ", "update ", "delete ", "drop ", "truncate ",
                 "alter ", "create ", "grant ", "revoke ")
    lower = sql.lower()
    if any(f in lower for f in forbidden):
        return json.dumps({"error": "write statements not allowed; this tool is read-only"})

    try:
        conn = psycopg2.connect(PG_DSN, connect_timeout=10)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SET statement_timeout = {STMT_TIMEOUT_MS}")
        cur.execute(sql)
        rows = cur.fetchmany(MAX_ROWS_RETURNED + 1)
        truncated = len(rows) > MAX_ROWS_RETURNED
        rows = rows[:MAX_ROWS_RETURNED]
        out = {
            "row_count": len(rows),
            "truncated": truncated,
            "rows": [{k: _normalize(v) for k, v in r.items()} for r in rows],
        }
        return json.dumps(out, default=str)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}"})
    finally:
        try:
            conn.close()
        except Exception:
            pass
