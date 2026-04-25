"""Targeted verification tools for the Validator agent.

Each tool checks ONE specific factual claim from the Investigation dossier
against source rows in the DB and returns a structured pass/fail result. The
Validator chains these into its risk-score reasoning and the Narrative agent
references the verification status in evidence_refs.

Why these exist as separate tools rather than letting the Validator write SQL:
- Forces explicit, auditable verification per claim — every numeric assertion
  in a Minister brief can be traced back to a specific verify_* call.
- Standardises the pass/fail shape so the Narrative agent can include
  verification status without ambiguity.
- Constrains the Validator's reasoning loop: prompt requires it to verify the
  top numerical claims before raising verdict to high_concern.

Strands convention notes (from .venv/.../strands/tools/decorator.py):
- The first line of the docstring becomes the tool description shown to the LLM.
- The Args block is parsed by docstring_parser to populate per-param descriptions.
- Type hints drive the JSON-schema input validator.
- Returning a JSON string passes through verbatim into the tool result.
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

import psycopg2
from strands import tool

from config import PG_DSN

STMT_TIMEOUT_MS = 30_000


def _conn():
    c = psycopg2.connect(PG_DSN, connect_timeout=10)
    c.set_session(readonly=True, autocommit=True)
    cur = c.cursor()
    cur.execute(f"SET statement_timeout = {STMT_TIMEOUT_MS}")
    return c, cur


def _f(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _delta_pct(claimed: float, actual: Optional[float]) -> Optional[float]:
    if actual is None or claimed == 0:
        return None
    return round((actual - claimed) / claimed * 100, 2)


@tool
def verify_gift(donor_bn: str, donee_bn: str, year: int, claimed_amount: float,
                tolerance_pct: float = 5.0) -> str:
    """Verify a single charity-to-charity gift claim against cra.cra_qualified_donees.

    Args:
        donor_bn: Business number of the donor charity (e.g. "132171679RR0001").
        donee_bn: Business number of the recipient charity.
        year: Fiscal-period-end year to match (uses fpe column).
        claimed_amount: The dollar amount the Investigation agent reported.
        tolerance_pct: Allowed difference in percent (default 5%).

    Returns:
        JSON string with keys: verified (bool), claimed, actual, delta_pct,
        row_count, donee_name. verified=True iff actual is within tolerance_pct
        of claimed.
    """
    conn, cur = _conn()
    try:
        cur.execute("""
            SELECT SUM(total_gifts), COUNT(*), MAX(donee_name)
            FROM cra.cra_qualified_donees
            WHERE bn = %s
              AND donee_bn = %s
              AND EXTRACT(YEAR FROM fpe)::int = %s
        """, (donor_bn, donee_bn, year))
        actual, row_count, donee_name = cur.fetchone()
        actual_f = _f(actual)
        delta = _delta_pct(claimed_amount, actual_f)
        verified = (
            actual_f is not None and delta is not None
            and abs(delta) <= tolerance_pct
        )
        return json.dumps({
            "verified": verified,
            "claimed": claimed_amount,
            "actual": actual_f,
            "delta_pct": delta,
            "row_count": row_count or 0,
            "donee_name_in_source": donee_name,
        })
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})
    finally:
        conn.close()


@tool
def verify_director(bn: str, last_name: str, first_name: Optional[str] = None) -> str:
    """Verify whether a person serves as a director of a charity.

    Returns the actual position, at_arms_length flag, tenure dates, and most
    recent fiscal period end from cra.cra_directors.

    Args:
        bn: Charity business number.
        last_name: Director's last name (case-insensitive partial match).
        first_name: Director's first name (case-insensitive partial match,
            optional — omit to match all directors with the given last name).

    Returns:
        JSON string with keys: found (bool), count (int), directors (list of
        up to 10 dicts with first_name, last_name, position, at_arms_length,
        start_date, end_date, fpe).
    """
    conn, cur = _conn()
    try:
        params = [bn, last_name.lower()]
        sql = """
            SELECT first_name, last_name, position, at_arms_length,
                   start_date, end_date, fpe
            FROM cra.cra_directors
            WHERE bn = %s
              AND lower(last_name) LIKE '%%' || %s || '%%'
        """
        if first_name:
            sql += " AND lower(first_name) LIKE '%%' || %s || '%%'"
            params.append(first_name.lower())
        sql += " ORDER BY fpe DESC LIMIT 10"
        cur.execute(sql, params)
        rows = cur.fetchall()
        directors = [
            {
                "first_name": r[0],
                "last_name": r[1],
                "position": r[2],
                "at_arms_length": r[3],
                "start_date": str(r[4]) if r[4] else None,
                "end_date": str(r[5]) if r[5] else None,
                "fpe": str(r[6]) if r[6] else None,
            }
            for r in rows
        ]
        return json.dumps({
            "found": len(directors) > 0,
            "count": len(directors),
            "directors": directors,
        })
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})
    finally:
        conn.close()


@tool
def verify_charity_revenue(bn: str, year: int, claimed_revenue: float,
                           tolerance_pct: float = 5.0) -> str:
    """Verify a charity's annual revenue claim against cra.cra_financial_details.

    Prefers field_4700 (total revenue, T3010 Section D) and falls back to
    field_4500 if 4700 is null.

    Args:
        bn: Charity business number.
        year: Fiscal period end year.
        claimed_revenue: The dollar amount Investigation reported.
        tolerance_pct: Allowed difference in percent (default 5%).

    Returns:
        JSON string with keys: verified (bool), claimed, actual, delta_pct,
        field_used ("4700" or "4500" or null), fpe.
    """
    conn, cur = _conn()
    try:
        cur.execute("""
            SELECT field_4700, field_4500, fpe
            FROM cra.cra_financial_details
            WHERE bn = %s
              AND EXTRACT(YEAR FROM fpe)::int = %s
            ORDER BY fpe DESC
            LIMIT 1
        """, (bn, year))
        r = cur.fetchone()
        if not r:
            return json.dumps({
                "verified": False, "claimed": claimed_revenue, "actual": None,
                "delta_pct": None, "field_used": None, "fpe": None,
                "note": "no T3010 filing found for that BN+year",
            })
        actual_4700, actual_4500, fpe = r
        actual = _f(actual_4700) if actual_4700 is not None else _f(actual_4500)
        field = "4700" if actual_4700 is not None else ("4500" if actual_4500 is not None else None)
        delta = _delta_pct(claimed_revenue, actual)
        verified = (
            actual is not None and delta is not None
            and abs(delta) <= tolerance_pct
        )
        return json.dumps({
            "verified": verified,
            "claimed": claimed_revenue,
            "actual": actual,
            "delta_pct": delta,
            "field_used": field,
            "fpe": str(fpe) if fpe else None,
        })
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})
    finally:
        conn.close()


@tool
def verify_external_funding(bn: str, source: str, claimed_total: float,
                            legal_name: Optional[str] = None,
                            min_year: Optional[int] = None,
                            max_year: Optional[int] = None,
                            tolerance_pct: float = 10.0) -> str:
    """Verify a charity's federal or Alberta government funding receipt.

    For source='fed': sums fed.grants_contributions.agreement_value matching
    BN first; if zero rows hit, falls back to recipient_legal_name match
    (case-insensitive exact). The fallback exists because KNOWN-DATA-ISSUE F-6
    leaves ~55% of fed rows with NULL recipient_business_number.

    For source='ab': sums ab.ab_grants.amount via general.entity_source_links.

    Args:
        bn: Charity business number (full 15-char format).
        source: Either 'fed' or 'ab'.
        claimed_total: The dollar amount Investigation reported.
        legal_name: Optional charity legal name. If provided, used as fallback
            when BN match returns 0 rows (only for source='fed').
        min_year: Optional lower bound on agreement_start_date (fed) or
            payment_date (ab) year.
        max_year: Optional upper bound, inclusive.
        tolerance_pct: Allowed difference in percent. Default 10% because
            FED amendment double-counting (KNOWN-DATA-ISSUE F-3) inflates
            agreement_value by ~73% on average — so exact matching is unfair.

    Returns:
        JSON string with keys: verified (bool), claimed, actual, delta_pct,
        row_count, year_range, match_method ("bn" | "legal_name" | "none").
    """
    if source not in ("fed", "ab"):
        return json.dumps({"error": "source must be 'fed' or 'ab'"})

    conn, cur = _conn()
    try:
        match_method = "none"
        if source == "fed":
            sql = """
                SELECT SUM(agreement_value), COUNT(*),
                       MIN(EXTRACT(YEAR FROM agreement_start_date)::int),
                       MAX(EXTRACT(YEAR FROM agreement_start_date)::int)
                FROM fed.grants_contributions
                WHERE recipient_business_number = %s
            """
            params = [bn]
            if min_year is not None:
                sql += " AND EXTRACT(YEAR FROM agreement_start_date) >= %s"
                params.append(min_year)
            if max_year is not None:
                sql += " AND EXTRACT(YEAR FROM agreement_start_date) <= %s"
                params.append(max_year)
            cur.execute(sql, params)
            row = cur.fetchone()
            actual, row_count, yr_min, yr_max = row
            if row_count and row_count > 0:
                match_method = "bn"
            elif legal_name:
                # FED-6 fallback: try legal-name match (case-insensitive exact)
                sql_n = """
                    SELECT SUM(agreement_value), COUNT(*),
                           MIN(EXTRACT(YEAR FROM agreement_start_date)::int),
                           MAX(EXTRACT(YEAR FROM agreement_start_date)::int)
                    FROM fed.grants_contributions
                    WHERE lower(recipient_legal_name) = lower(%s)
                """
                params_n = [legal_name]
                if min_year is not None:
                    sql_n += " AND EXTRACT(YEAR FROM agreement_start_date) >= %s"
                    params_n.append(min_year)
                if max_year is not None:
                    sql_n += " AND EXTRACT(YEAR FROM agreement_start_date) <= %s"
                    params_n.append(max_year)
                cur.execute(sql_n, params_n)
                actual, row_count, yr_min, yr_max = cur.fetchone()
                if row_count and row_count > 0:
                    match_method = "legal_name"

            actual_f = _f(actual)
            delta = _delta_pct(claimed_total, actual_f)
            verified = (
                actual_f is not None and delta is not None
                and abs(delta) <= tolerance_pct
            )
            return json.dumps({
                "verified": verified,
                "claimed": claimed_total,
                "actual": actual_f,
                "delta_pct": delta,
                "row_count": row_count or 0,
                "year_range": [yr_min, yr_max],
                "match_method": match_method,
                "tolerance_used": tolerance_pct,
            })
        else:
            sql = """
                SELECT SUM(g.amount), COUNT(*),
                       MIN(EXTRACT(YEAR FROM g.payment_date)::int),
                       MAX(EXTRACT(YEAR FROM g.payment_date)::int)
                FROM ab.ab_grants g
                JOIN general.entity_source_links esl
                  ON esl.source_schema = 'ab' AND esl.source_table = 'ab_grants'
                 AND esl.source_pk = jsonb_build_object('id', g.id)
                JOIN general.entity_golden_records egr
                  ON egr.id = esl.entity_id
                WHERE egr.bn_root = substring(%s FROM 1 FOR 9)
            """
            params = [bn]
            if min_year is not None:
                sql += " AND EXTRACT(YEAR FROM g.payment_date) >= %s"
                params.append(min_year)
            if max_year is not None:
                sql += " AND EXTRACT(YEAR FROM g.payment_date) <= %s"
                params.append(max_year)

        cur.execute(sql, params)
        actual, row_count, yr_min, yr_max = cur.fetchone()
        actual_f = _f(actual)
        delta = _delta_pct(claimed_total, actual_f)
        verified = (
            actual_f is not None and delta is not None
            and abs(delta) <= tolerance_pct
        )
        return json.dumps({
            "verified": verified,
            "claimed": claimed_total,
            "actual": actual_f,
            "delta_pct": delta,
            "row_count": row_count or 0,
            "year_range": [yr_min, yr_max],
            "tolerance_used": tolerance_pct,
        })
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"})
    finally:
        conn.close()
