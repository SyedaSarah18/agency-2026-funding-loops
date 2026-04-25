"""Phase 1c — signal probes for all 10 challenges.

For each challenge, run ONE targeted SQL probe and capture:
  - candidate_count: how many rows match the suspicion pattern
  - dollar_magnitude: total $ exposed
  - named_entities: a few real names (Minister demo needs faces)
  - data_risk_notes: known-data-issues we hit
  - agent_4fit: short note on whether the 4-agent pipeline has real work

Output: analysis/triage_results.json + analysis/scorecard.md
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")
DSN = os.environ["PG_DSN"]
STMT_TIMEOUT_MS = 90_000


def run(cur, label, sql, params=None):
    """Run a single probe; return rows + elapsed seconds + error if any."""
    t0 = time.time()
    try:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return {"rows": rows, "elapsed": time.time() - t0, "error": None}
    except Exception as e:
        return {"rows": [], "elapsed": time.time() - t0, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def probe_ch1_zombies(cur):
    """Ch.1 Zombies: orgs with big govt funding then no recent CRA filings (proxy for inactive).

    Logic: a charity is 'zombie' if:
      - received >$500K combined FED+AB funding in a year, AND
      - has no cra filing (most recent fiscal_year) within 2 years after that funding
    Proxy uses cra_identification.fiscal_year as the most recent reporting year.
    """
    return run(cur, "ch1_zombies", """
        WITH cra_last AS (
            SELECT bn, MAX(fiscal_year) AS last_fy, MAX(legal_name) AS legal_name
            FROM cra.cra_identification
            GROUP BY bn
        ),
        ab_funded AS (
            SELECT esl.entity_id, SUM(g.amount) AS total
            FROM ab.ab_grants g
            JOIN general.entity_source_links esl
              ON esl.source_schema = 'ab' AND esl.source_table = 'ab_grants'
             AND esl.source_pk = jsonb_build_object('id', g.id)
            WHERE EXTRACT(YEAR FROM g.payment_date)::int <= 2022
            GROUP BY esl.entity_id
            HAVING SUM(g.amount) >= 500000
        )
        SELECT COUNT(DISTINCT egr.id) AS candidates,
               COALESCE(SUM(af.total),0)::bigint AS exposed_dollars,
               (array_agg(egr.canonical_name ORDER BY af.total DESC))[1:5] AS sample_names
        FROM ab_funded af
        JOIN general.entity_golden_records egr ON egr.id = af.entity_id
        LEFT JOIN cra_last cl ON cl.bn = egr.bn_root
        WHERE cl.last_fy IS NULL OR cl.last_fy < 2023
    """)


def probe_ch2_ghost(cur):
    """Ch.2 Ghost Capacity: charities with 0 employees AND received govt $.

    field_300 in T3010 = number of permanent, full-time compensated positions.
    """
    return run(cur, "ch2_ghost", """
        WITH zero_emp AS (
            SELECT bn, MAX(fpe) AS last_filing
            FROM cra.cra_compensation
            WHERE field_300 = 0 OR field_300 IS NULL
            GROUP BY bn
            HAVING COUNT(*) >= 3  -- 3+ years of zero-employee filings
        ),
        funded AS (
            SELECT esl.entity_id, SUM(g.amount) AS ab_total
            FROM ab.ab_grants g
            JOIN general.entity_source_links esl
              ON esl.source_schema = 'ab' AND esl.source_table = 'ab_grants'
             AND esl.source_pk = jsonb_build_object('id', g.id)
            GROUP BY esl.entity_id
            HAVING SUM(g.amount) >= 100000
        )
        SELECT COUNT(DISTINCT egr.id) AS candidates,
               SUM(funded.ab_total)::bigint AS exposed_dollars,
               (array_agg(egr.canonical_name ORDER BY funded.ab_total DESC))[1:5] AS sample_names
        FROM zero_emp ze
        JOIN general.entity_golden_records egr ON egr.bn_root = ze.bn
        JOIN funded ON funded.entity_id = egr.id
    """)


def probe_ch3_loops(cur):
    """Ch.3 Funding Loops: pre-built loops table has 5,808 detected cycles."""
    return run(cur, "ch3_loops", """
        SELECT COUNT(*) AS candidates,
               COALESCE(SUM(total_flow),0)::bigint AS exposed_dollars,
               (SELECT array_agg(path_display ORDER BY total_flow DESC)
                FROM (SELECT path_display, total_flow FROM cra.loops
                      ORDER BY total_flow DESC LIMIT 5) s) AS sample_names
        FROM cra.loops
        WHERE total_flow >= 100000
    """)


def probe_ch4_amendment_creep(cur):
    """Ch.4 Amendment Creep: FED grants with amendments that significantly increased value.

    Group by ref_number (which collides per known issue F-1 but still useful for amendment lineage).
    """
    return run(cur, "ch4_creep", """
        WITH lineage AS (
            SELECT ref_number,
                   MIN(agreement_value) FILTER (WHERE COALESCE(amendment_number, '0') = '0' OR is_amendment = false) AS original,
                   MAX(agreement_value) AS final_val,
                   COUNT(*) AS amendment_count,
                   MAX(recipient_legal_name) AS recipient
            FROM fed.grants_contributions
            WHERE ref_number IS NOT NULL AND agreement_value IS NOT NULL
            GROUP BY ref_number
            HAVING COUNT(*) >= 3
        )
        SELECT COUNT(*) AS candidates,
               SUM(final_val - COALESCE(original, 0))::bigint AS exposed_dollars,
               (array_agg(recipient ORDER BY (final_val - COALESCE(original,0)) DESC))[1:5] AS sample_names
        FROM lineage
        WHERE final_val > COALESCE(original, 0) * 2 AND COALESCE(original,0) > 50000
    """)


def probe_ch5_vendor_concentration(cur):
    """Ch.5 Vendor Concentration: ministries where top-3 vendors control >75% of contract spend.

    Higher concentration = more likely incumbency / dependency.
    """
    return run(cur, "ch5_concentration", """
        WITH ministry_total AS (
            SELECT ministry, SUM(amount) AS m_total
            FROM ab.ab_contracts
            WHERE amount IS NOT NULL AND ministry IS NOT NULL
            GROUP BY ministry
        ),
        top3 AS (
            SELECT ministry, recipient, SUM(amount) AS r_total,
                   ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY SUM(amount) DESC) AS rn
            FROM ab.ab_contracts
            WHERE amount IS NOT NULL AND recipient IS NOT NULL
            GROUP BY ministry, recipient
        ),
        concentrated AS (
            SELECT t.ministry, mt.m_total,
                   SUM(t.r_total) AS top3_total,
                   SUM(t.r_total) / NULLIF(mt.m_total, 0) AS share
            FROM top3 t JOIN ministry_total mt USING (ministry)
            WHERE t.rn <= 3
            GROUP BY t.ministry, mt.m_total
        )
        SELECT COUNT(*) AS candidates,
               SUM(m_total)::bigint AS exposed_dollars,
               (array_agg(ministry ORDER BY share DESC))[1:5] AS sample_names
        FROM concentrated
        WHERE share >= 0.75
    """)


def probe_ch6_director_networks(cur):
    """Ch.6 Director Networks: people sitting on >=4 distinct charity boards.

    Use first_name + last_name as crude key (will have John-Smith collisions; validator must filter).
    """
    return run(cur, "ch6_directors", """
        WITH multi_board AS (
            SELECT lower(trim(first_name)) || '|' || lower(trim(last_name)) AS person_key,
                   first_name, last_name,
                   COUNT(DISTINCT bn) AS board_count,
                   array_agg(DISTINCT bn) AS bns
            FROM cra.cra_directors
            WHERE last_name IS NOT NULL AND first_name IS NOT NULL
              AND length(trim(last_name)) >= 3
            GROUP BY 1, first_name, last_name
            HAVING COUNT(DISTINCT bn) >= 4
        )
        SELECT COUNT(*) AS candidates,
               0::bigint AS exposed_dollars,  -- needs join to funding; defer to investigation phase
               (array_agg(first_name || ' ' || last_name ORDER BY board_count DESC))[1:5] AS sample_names
        FROM multi_board
    """)


def probe_ch7_policy_spend_signal(cur):
    """Ch.7 Policy Misalignment: spend-side only (we lack policy docs today).

    Top federal program areas by total $ over last 5 years -- gives us the universe
    to compare against policy commitments later.
    """
    return run(cur, "ch7_policy_spend", """
        SELECT COUNT(DISTINCT prog_name_en) AS candidates,
               SUM(agreement_value)::bigint AS exposed_dollars,
               (SELECT array_agg(prog_name_en ORDER BY total DESC)
                FROM (SELECT prog_name_en, SUM(agreement_value) AS total
                      FROM fed.grants_contributions
                      WHERE prog_name_en IS NOT NULL
                        AND agreement_start_date >= '2020-01-01'
                      GROUP BY prog_name_en
                      ORDER BY 2 DESC LIMIT 5) s) AS sample_names
        FROM fed.grants_contributions
        WHERE prog_name_en IS NOT NULL AND agreement_start_date >= '2020-01-01'
    """)


def probe_ch8_duplicative(cur):
    """Ch.8 Duplicative Funding: orgs receiving from multiple datasets in the same period."""
    return run(cur, "ch8_duplicative", """
        SELECT COUNT(*) AS candidates,
               0::bigint AS exposed_dollars,  -- requires deeper join; flag count only
               (array_agg(canonical_name ORDER BY source_link_count DESC))[1:5] AS sample_names
        FROM general.entity_golden_records
        WHERE array_length(dataset_sources, 1) >= 2
          AND source_link_count >= 5  -- meaningful funding history across both
    """)


def probe_ch9_contract_intel(cur):
    """Ch.9 Contract Intelligence: top YoY growth in spend categories.

    Use FED program names; compute simple year-over-year delta.
    """
    return run(cur, "ch9_contract_intel", """
        WITH yearly AS (
            SELECT prog_name_en,
                   EXTRACT(YEAR FROM agreement_start_date)::int AS yr,
                   SUM(agreement_value) AS total
            FROM fed.grants_contributions
            WHERE prog_name_en IS NOT NULL
              AND agreement_start_date BETWEEN '2020-01-01' AND '2024-12-31'
            GROUP BY 1, 2
        ),
        growth AS (
            SELECT prog_name_en,
                   SUM(total) FILTER (WHERE yr = 2024) AS y24,
                   SUM(total) FILTER (WHERE yr = 2020) AS y20
            FROM yearly GROUP BY 1
        )
        SELECT COUNT(*) AS candidates,
               SUM(y24 - COALESCE(y20,0))::bigint AS exposed_dollars,
               (array_agg(prog_name_en ORDER BY (y24 - COALESCE(y20,0)) DESC))[1:5] AS sample_names
        FROM growth
        WHERE y24 > 0 AND y24 > COALESCE(y20, 0) * 3 AND y24 > 1000000
    """)


def probe_ch10_adverse_media(cur):
    """Ch.10 Adverse Media: top funded entities are the universe to cross-check vs news.

    Probe just measures: do we have enough big-name recipients to make adverse-media matching feasible?
    """
    return run(cur, "ch10_adverse_media", """
        SELECT COUNT(*) AS candidates,
               SUM(total)::bigint AS exposed_dollars,
               (array_agg(recipient_legal_name ORDER BY total DESC))[1:5] AS sample_names
        FROM (
            SELECT recipient_legal_name, SUM(agreement_value) AS total
            FROM fed.grants_contributions
            WHERE recipient_legal_name IS NOT NULL AND agreement_value IS NOT NULL
            GROUP BY 1
            HAVING SUM(agreement_value) >= 10000000
        ) big
    """)


PROBES = [
    ("Ch.1  Zombie Recipients", probe_ch1_zombies, "Inactive orgs that received big govt funding before going silent"),
    ("Ch.2  Ghost Capacity", probe_ch2_ghost, "Charities with 0 employees for 3+ years still receiving govt $"),
    ("Ch.3  Funding Loops", probe_ch3_loops, "Circular gifting cycles (pre-detected in cra.loops)"),
    ("Ch.4  Amendment Creep", probe_ch4_amendment_creep, "FED contracts that 2x+ via amendments after $50K start"),
    ("Ch.5  Vendor Concentration", probe_ch5_vendor_concentration, "Ministries where top-3 vendors hold >=75% of contract $"),
    ("Ch.6  Director Networks", probe_ch6_director_networks, "Individuals sitting on 4+ distinct charity boards"),
    ("Ch.7  Policy Misalignment", probe_ch7_policy_spend_signal, "Spend-side only -- top fed programs since 2020 (need policy docs to compare)"),
    ("Ch.8  Duplicative Funding", probe_ch8_duplicative, "Orgs in 2+ datasets with substantial funding history"),
    ("Ch.9  Contract Intelligence", probe_ch9_contract_intel, "FED programs with 3x+ growth 2020->2024 over $1M"),
    ("Ch.10 Adverse Media", probe_ch10_adverse_media, "FED recipients with >=$10M lifetime -- universe for news matching"),
]


def main():
    print(f"Connecting to: {DSN.split('@')[1].split('/')[0]} ...")
    conn = psycopg2.connect(DSN, connect_timeout=15)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = {STMT_TIMEOUT_MS}")

    results = []
    for label, probe_fn, desc in PROBES:
        print(f"\n>> {label}")
        print(f"   {desc}")
        r = probe_fn(cur)
        if r["error"]:
            print(f"   [ERROR after {r['elapsed']:.1f}s] {r['error']}")
            results.append({"challenge": label, "desc": desc, "error": r["error"], "elapsed": r["elapsed"]})
            continue
        if not r["rows"]:
            print(f"   [no rows] ({r['elapsed']:.1f}s)")
            results.append({"challenge": label, "desc": desc, "candidates": 0, "elapsed": r["elapsed"]})
            continue
        row = r["rows"][0]
        candidates = row[0] or 0
        dollars = row[1] or 0
        sample = list(row[2]) if row[2] else []
        results.append({
            "challenge": label,
            "desc": desc,
            "candidates": candidates,
            "exposed_dollars": dollars,
            "sample_names": sample[:5],
            "elapsed": r["elapsed"],
        })
        print(f"   candidates={candidates:>10,}   $exposed={dollars:>17,}   ({r['elapsed']:.1f}s)")
        for n in sample[:3]:
            if n:
                print(f"      - {str(n)[:100]}")

    out = ROOT / "analysis" / "triage_results.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
