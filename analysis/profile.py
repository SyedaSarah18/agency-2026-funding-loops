"""Phase 1b — per-dataset profiling.

Date coverage, NULL rates on key columns, distinct entity counts,
cross-dataset linkage rates, top recipients by $.

Output: analysis/profile.md (human-readable) + analysis/profile.json (raw)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Windows console default encoding (cp1252) chokes on Unicode arrows etc.
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DSN = os.environ["PG_DSN"]

# Statement timeout to keep us from hanging on a hostile query
STMT_TIMEOUT_MS = 60_000


def q(cur, sql: str, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def safe_q(cur, sql: str, label: str, params=None):
    """Run a query; on failure (missing column/table/timeout), return [] + log."""
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    except Exception as e:
        cur.execute("ROLLBACK")  # autocommit=True so this is a no-op, but keep cur alive
        print(f"   [SKIP] {label}: {type(e).__name__}: {str(e)[:120]}")
        return []


def profile_ab(cur, out: dict):
    print("\n[AB] profiling…")
    out["ab"] = {}

    # Date coverage
    rows = safe_q(cur,
        "SELECT MIN(payment_date)::date, MAX(payment_date)::date, COUNT(*) FROM ab.ab_grants",
        "ab_grants date coverage")
    if rows:
        out["ab"]["ab_grants_date_coverage"] = {
            "min": str(rows[0][0]), "max": str(rows[0][1]), "rows": rows[0][2]
        }
        print(f"   ab_grants: {rows[0][0]} → {rows[0][1]}, {rows[0][2]:,} rows")

    # $ volume by fiscal year
    rows = safe_q(cur, """
        SELECT display_fiscal_year, SUM(amount)::bigint AS total, COUNT(*) AS n
        FROM ab.ab_grants
        WHERE display_fiscal_year IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """, "ab_grants by fiscal_year")
    out["ab"]["ab_grants_by_year"] = [
        {"fy": r[0], "total_dollars": r[1], "count": r[2]} for r in rows
    ]
    print(f"   ab_grants: {len(rows)} fiscal years")

    # NULL rates on key columns
    rows = safe_q(cur, """
        SELECT
            COUNT(*) AS n,
            COUNT(*) FILTER (WHERE recipient IS NULL OR recipient = '') AS null_recipient,
            COUNT(*) FILTER (WHERE amount IS NULL) AS null_amount,
            COUNT(*) FILTER (WHERE payment_date IS NULL) AS null_date,
            COUNT(DISTINCT recipient) AS distinct_recipients
        FROM ab.ab_grants
    """, "ab_grants NULL rates")
    if rows:
        n, nr, na, nd, dr = rows[0]
        out["ab"]["ab_grants_quality"] = {
            "rows": n, "null_recipient": nr, "null_amount": na, "null_date": nd,
            "distinct_recipients": dr,
        }
        print(f"   ab_grants: {dr:,} distinct recipients; NULL rates recipient={nr/n:.1%} amount={na/n:.1%} date={nd/n:.1%}")

    # Top 20 AB recipients by $
    rows = safe_q(cur, """
        SELECT recipient, SUM(amount)::bigint AS total, COUNT(*) AS n
        FROM ab.ab_grants
        WHERE recipient IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
    """, "ab_grants top recipients")
    out["ab"]["top_grant_recipients"] = [
        {"recipient": r[0], "total": r[1], "count": r[2]} for r in rows
    ]

    # Contracts
    rows = safe_q(cur, """
        SELECT MIN(display_fiscal_year), MAX(display_fiscal_year), COUNT(*),
               SUM(amount)::bigint, COUNT(DISTINCT recipient)
        FROM ab.ab_contracts
    """, "ab_contracts overview")
    if rows:
        out["ab"]["ab_contracts_overview"] = {
            "min_fy": rows[0][0], "max_fy": rows[0][1], "rows": rows[0][2],
            "total_dollars": rows[0][3], "distinct_recipients": rows[0][4],
        }


def profile_fed(cur, out: dict):
    print("\n[FED] profiling…")
    out["fed"] = {}

    # Date coverage on grants_contributions
    rows = safe_q(cur, """
        SELECT MIN(agreement_start_date)::date, MAX(agreement_start_date)::date,
               COUNT(*), COUNT(DISTINCT recipient_business_number) AS distinct_bn,
               SUM(agreement_value)::bigint AS total_value
        FROM fed.grants_contributions
    """, "fed.grants_contributions overview")
    if rows:
        out["fed"]["grants_contributions_overview"] = {
            "min_date": str(rows[0][0]), "max_date": str(rows[0][1]),
            "rows": rows[0][2], "distinct_bn": rows[0][3],
            "total_value_uncorrected": rows[0][4],
        }
        print(f"   grants_contributions: {rows[0][0]} → {rows[0][1]}, {rows[0][2]:,} rows, {rows[0][3]:,} BNs")

    # $ volume by year
    rows = safe_q(cur, """
        SELECT EXTRACT(YEAR FROM agreement_start_date)::int AS yr,
               SUM(agreement_value)::bigint, COUNT(*)
        FROM fed.grants_contributions
        WHERE agreement_start_date IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """, "fed by year")
    out["fed"]["by_year"] = [{"year": r[0], "total": r[1], "count": r[2]} for r in rows]

    # NULL rates on key columns
    rows = safe_q(cur, """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE recipient_legal_name IS NULL OR recipient_legal_name = '') AS null_name,
               COUNT(*) FILTER (WHERE recipient_business_number IS NULL) AS null_bn,
               COUNT(*) FILTER (WHERE agreement_value IS NULL) AS null_value,
               COUNT(*) FILTER (WHERE agreement_end_date IS NULL) AS null_end
        FROM fed.grants_contributions
    """, "fed NULL rates")
    if rows:
        n, nn, nb, nv, ne = rows[0]
        out["fed"]["quality"] = {
            "rows": n, "null_recipient_name": nn, "null_business_number": nb,
            "null_value": nv, "null_end_date": ne,
        }
        print(f"   NULL: name={nn/n:.1%} bn={nb/n:.1%} value={nv/n:.1%} end_date={ne/n:.1%}")

    # Top 20 federal recipients by $
    rows = safe_q(cur, """
        SELECT recipient_legal_name, SUM(agreement_value)::bigint AS total, COUNT(*) AS n
        FROM fed.grants_contributions
        WHERE recipient_legal_name IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20
    """, "fed top recipients")
    out["fed"]["top_recipients"] = [
        {"recipient": r[0], "total": r[1], "count": r[2]} for r in rows
    ]


def profile_cra(cur, out: dict):
    print("\n[CRA] profiling…")
    out["cra"] = {}

    # cra_identification overview
    rows = safe_q(cur, """
        SELECT COUNT(*) FROM cra.cra_identification
    """, "cra_identification overview")
    if rows:
        out["cra"]["cra_identification_rows"] = rows[0][0]
        print(f"   cra_identification: {rows[0][0]:,} charities")

    # Loop universe — pre-computed circular gifting risk scores
    rows = safe_q(cur, """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE total_score >= 20),
               COUNT(*) FILTER (WHERE total_score >= 25),
               MAX(total_score)
        FROM cra.loop_universe
    """, "loop_universe overview")
    if rows:
        out["cra"]["loop_universe"] = {
            "total_loops": rows[0][0],
            "high_risk_score_20plus": rows[0][1],
            "very_high_risk_25plus": rows[0][2],
            "max_score": rows[0][3],
        }
        print(f"   loop_universe: {rows[0][0]:,} loops; {rows[0][1]:,} score≥20; {rows[0][2]:,} score≥25; max={rows[0][3]}")

    # Qualified donees (charity-to-charity gifts) volume
    rows = safe_q(cur, """
        SELECT COUNT(*), SUM(amount)::bigint, COUNT(DISTINCT donor_bn), COUNT(DISTINCT donee_bn)
        FROM cra.cra_qualified_donees
        WHERE amount IS NOT NULL
    """, "qualified_donees overview")
    if rows:
        out["cra"]["qualified_donees"] = {
            "rows": rows[0][0], "total_dollars": rows[0][1],
            "distinct_donors": rows[0][2], "distinct_donees": rows[0][3],
        }
        print(f"   qualified_donees: {rows[0][0]:,} gifts, ${rows[0][1]:,}, {rows[0][2]:,}→{rows[0][3]:,}")

    # Directors — count & multi-board people
    rows = safe_q(cur, """
        SELECT COUNT(*), COUNT(DISTINCT director_first_name || '|' || director_last_name) AS distinct_people,
               COUNT(DISTINCT bn) AS distinct_charities
        FROM cra.cra_directors
        WHERE director_last_name IS NOT NULL
    """, "directors overview")
    if rows:
        out["cra"]["directors"] = {
            "rows": rows[0][0], "distinct_people": rows[0][1], "distinct_charities": rows[0][2],
        }
        print(f"   directors: {rows[0][0]:,} rows, {rows[0][1]:,} distinct names, {rows[0][2]:,} charities")


def profile_general(cur, out: dict):
    print("\n[GENERAL] profiling…")
    out["general"] = {}

    rows = safe_q(cur, "SELECT COUNT(*) FROM general.entity_golden_records",
                  "entity_golden_records count")
    if rows:
        out["general"]["entity_golden_records"] = rows[0][0]
        print(f"   entity_golden_records: {rows[0][0]:,}")

    rows = safe_q(cur, "SELECT COUNT(*) FROM general.entity_source_links",
                  "entity_source_links count")
    if rows:
        out["general"]["entity_source_links"] = rows[0][0]
        print(f"   entity_source_links: {rows[0][0]:,}")

    # Cross-dataset coverage: for each source, how many distinct entities exist in the linkage table
    rows = safe_q(cur, """
        SELECT source_dataset, COUNT(*) AS link_rows, COUNT(DISTINCT entity_id) AS distinct_entities
        FROM general.entity_source_links
        GROUP BY 1 ORDER BY 1
    """, "entity_source_links by dataset")
    out["general"]["coverage_by_source"] = [
        {"source": r[0], "link_rows": r[1], "distinct_entities": r[2]} for r in rows
    ]


def main():
    print(f"Connecting to: {DSN.split('@')[1].split('/')[0]} ...")
    conn = psycopg2.connect(DSN, connect_timeout=15)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = {STMT_TIMEOUT_MS}")

    out = {}
    profile_ab(cur, out)
    profile_fed(cur, out)
    profile_cra(cur, out)
    profile_general(cur, out)

    out_path = ROOT / "analysis" / "profile.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
