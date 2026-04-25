"""Phase 6d — deep probe of Challenge 5 (Vendor Concentration).

Original triage probe was narrow:
  - AB only (no federal contracts)
  - Ministry-level only (no program / business_unit / category cut)
  - top-3 >= 75% threshold (no Herfindahl, no top-1, no other thresholds)
  - No recency filter (mixes 2014 with 2024)
  - No minimum spend floor (a $50K ministry counts the same as a $500M one)

This probe runs 6 cuts across AB + FED and prints them all so we can decide
whether Ch.5 has more signal than the 12-candidate top-line implied.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")
DSN = os.environ["PG_DSN"]


def section(title: str):
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)


def run_query(cur, sql, params=()):
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def print_rows(cols, rows, money_cols=("total", "category_total", "vendor_total"), limit=15):
    if not rows:
        print("  (no rows)")
        return
    widths = [max(len(c), 12) for c in cols]
    for r in rows[:limit]:
        for i, v in enumerate(r):
            s = ""
            if v is None:
                s = "-"
            elif cols[i] in money_cols and isinstance(v, (int, float)):
                s = f"${v:,.0f}"
            elif isinstance(v, float):
                s = f"{v:.3f}"
            else:
                s = str(v)
            widths[i] = max(widths[i], len(s))
    fmt = "  " + "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*cols))
    print("  " + "  ".join("-" * w for w in widths))
    for r in rows[:limit]:
        cells = []
        for i, v in enumerate(r):
            if v is None:
                cells.append("-")
            elif cols[i] in money_cols and isinstance(v, (int, float)):
                cells.append(f"${v:,.0f}")
            elif isinstance(v, float):
                cells.append(f"{v:.3f}")
            else:
                cells.append(str(v))
        print(fmt.format(*cells))
    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more rows")


def main():
    print(f"Connecting to: {DSN.split('@')[1].split('/')[0]}")
    conn = psycopg2.connect(DSN, connect_timeout=15)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    cur.execute("SET statement_timeout = 90000")

    # ============== Cut 1: AB ministry-level (original probe, expanded) ==============
    section("Cut 1: AB MINISTRIES — top-3 vendor concentration, all years")
    cols, rows = run_query(cur, """
        WITH per_ministry AS (
            SELECT ministry, recipient, SUM(amount) AS r_total
            FROM ab.ab_contracts
            WHERE amount IS NOT NULL AND ministry IS NOT NULL AND recipient IS NOT NULL
            GROUP BY 1, 2
        ),
        ranked AS (
            SELECT ministry, recipient, r_total,
                   SUM(r_total) OVER (PARTITION BY ministry) AS m_total,
                   ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY r_total DESC) AS rn
            FROM per_ministry
        )
        SELECT ministry,
               m_total,
               SUM(r_total) FILTER (WHERE rn = 1) AS top1,
               SUM(r_total) FILTER (WHERE rn <= 3) AS top3,
               (SUM(r_total) FILTER (WHERE rn = 1)) / NULLIF(m_total, 0) AS top1_share,
               (SUM(r_total) FILTER (WHERE rn <= 3)) / NULLIF(m_total, 0) AS top3_share
        FROM ranked
        GROUP BY ministry, m_total
        HAVING m_total >= 1000000
        ORDER BY top3_share DESC
        LIMIT 25
    """)
    print_rows(cols, rows, money_cols=("m_total", "top1", "top3"))

    # ============== Cut 2: AB ministries with HIGH top-1 share (single-vendor dominance) ==============
    section("Cut 2: AB MINISTRIES where the SINGLE TOP vendor controls >=50% of ministry spend")
    cols, rows = run_query(cur, """
        WITH per_ministry AS (
            SELECT ministry, recipient, SUM(amount) AS r_total
            FROM ab.ab_contracts
            WHERE amount IS NOT NULL AND ministry IS NOT NULL AND recipient IS NOT NULL
            GROUP BY 1, 2
        ),
        ranked AS (
            SELECT ministry, recipient, r_total,
                   SUM(r_total) OVER (PARTITION BY ministry) AS m_total,
                   ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY r_total DESC) AS rn
            FROM per_ministry
        )
        SELECT ministry, recipient AS top_vendor, r_total AS top1,
               m_total, (r_total / NULLIF(m_total, 0)) AS top1_share
        FROM ranked
        WHERE rn = 1 AND m_total >= 1000000
          AND (r_total / NULLIF(m_total, 0)) >= 0.50
        ORDER BY top1_share DESC
        LIMIT 25
    """)
    print_rows(cols, rows, money_cols=("top1", "m_total"))

    # ============== Cut 3: AB recent (last 3 fiscal years) ==============
    section("Cut 3: AB RECENT (FY 2022-25 only) — top-3 share by ministry")
    cols, rows = run_query(cur, """
        WITH per_ministry AS (
            SELECT ministry, recipient, SUM(amount) AS r_total
            FROM ab.ab_contracts
            WHERE amount IS NOT NULL AND ministry IS NOT NULL AND recipient IS NOT NULL
              AND display_fiscal_year IN ('2022-23', '2023-24', '2024-25')
            GROUP BY 1, 2
        ),
        ranked AS (
            SELECT ministry, recipient, r_total,
                   SUM(r_total) OVER (PARTITION BY ministry) AS m_total,
                   ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY r_total DESC) AS rn
            FROM per_ministry
        )
        SELECT ministry, m_total,
               SUM(r_total) FILTER (WHERE rn <= 3) AS top3,
               (SUM(r_total) FILTER (WHERE rn <= 3)) / NULLIF(m_total, 0) AS top3_share
        FROM ranked
        GROUP BY ministry, m_total
        HAVING m_total >= 500000
        ORDER BY top3_share DESC
        LIMIT 20
    """)
    print_rows(cols, rows, money_cols=("m_total", "top3"))

    # ============== Cut 4: FED department-level concentration ==============
    section("Cut 4: FED DEPARTMENTS — top-3 recipient concentration, agreement_value >= $1M each")
    cols, rows = run_query(cur, """
        WITH per_dept AS (
            SELECT owner_org_title AS dept, recipient_legal_name AS recipient,
                   SUM(agreement_value) AS r_total
            FROM fed.grants_contributions
            WHERE agreement_value IS NOT NULL AND owner_org_title IS NOT NULL
              AND recipient_legal_name IS NOT NULL
              AND agreement_start_date >= '2020-01-01'
            GROUP BY 1, 2
        ),
        ranked AS (
            SELECT dept, recipient, r_total,
                   SUM(r_total) OVER (PARTITION BY dept) AS d_total,
                   ROW_NUMBER() OVER (PARTITION BY dept ORDER BY r_total DESC) AS rn
            FROM per_dept
        )
        SELECT dept, d_total,
               SUM(r_total) FILTER (WHERE rn <= 3) AS top3,
               (SUM(r_total) FILTER (WHERE rn <= 3)) / NULLIF(d_total, 0) AS top3_share
        FROM ranked
        GROUP BY dept, d_total
        HAVING d_total >= 50000000
        ORDER BY top3_share DESC
        LIMIT 25
    """)
    print_rows(cols, rows, money_cols=("d_total", "top3"))

    # ============== Cut 5: FED program-level (much more granular than dept) ==============
    section("Cut 5: FED PROGRAMS — top-1 recipient concentration since 2020 (>= $1M total)")
    cols, rows = run_query(cur, """
        WITH per_prog AS (
            SELECT prog_name_en AS program, owner_org_title AS dept,
                   recipient_legal_name AS recipient,
                   SUM(agreement_value) AS r_total
            FROM fed.grants_contributions
            WHERE agreement_value IS NOT NULL AND prog_name_en IS NOT NULL
              AND recipient_legal_name IS NOT NULL
              AND agreement_start_date >= '2020-01-01'
            GROUP BY 1, 2, 3
        ),
        ranked AS (
            SELECT program, dept, recipient, r_total,
                   SUM(r_total) OVER (PARTITION BY program) AS p_total,
                   ROW_NUMBER() OVER (PARTITION BY program ORDER BY r_total DESC) AS rn
            FROM per_prog
        )
        SELECT program, dept, p_total, recipient AS top_vendor, r_total AS top1,
               (r_total / NULLIF(p_total, 0)) AS top1_share
        FROM ranked
        WHERE rn = 1 AND p_total >= 1000000
          AND (r_total / NULLIF(p_total, 0)) >= 0.80
        ORDER BY p_total DESC
        LIMIT 30
    """)
    print_rows(cols, rows, money_cols=("p_total", "top1"))

    # ============== Cut 6: Vendor-level — vendors dominating across MANY ministries/depts ==============
    section("Cut 6: VENDOR-LEVEL — single recipients receiving >$10M from 5+ ministries/departments")
    cols, rows = run_query(cur, """
        WITH ab_recv AS (
            SELECT recipient, ministry, SUM(amount) AS amt
            FROM ab.ab_contracts
            WHERE recipient IS NOT NULL AND ministry IS NOT NULL AND amount IS NOT NULL
            GROUP BY 1, 2
        ),
        fed_recv AS (
            SELECT recipient_legal_name AS recipient, owner_org_title AS ministry,
                   SUM(agreement_value) AS amt
            FROM fed.grants_contributions
            WHERE recipient_legal_name IS NOT NULL AND owner_org_title IS NOT NULL
              AND agreement_value IS NOT NULL
              AND agreement_start_date >= '2020-01-01'
            GROUP BY 1, 2
        ),
        unioned AS (SELECT * FROM ab_recv UNION ALL SELECT * FROM fed_recv),
        per_recipient AS (
            SELECT recipient, COUNT(DISTINCT ministry) AS ministries_n, SUM(amt) AS vendor_total
            FROM unioned
            GROUP BY 1
        )
        SELECT recipient, ministries_n, vendor_total
        FROM per_recipient
        WHERE ministries_n >= 5 AND vendor_total >= 10000000
        ORDER BY vendor_total DESC
        LIMIT 25
    """)
    print_rows(cols, rows)

    # ============== Summary counts ==============
    section("HEADLINE COUNTS — how many candidates exist across each cut?")
    queries = [
        ("Ch5 (orig): AB ministries top-3 >= 75%",
         """SELECT COUNT(*) FROM (
                WITH p AS (SELECT ministry, recipient, SUM(amount) AS r FROM ab.ab_contracts
                           WHERE amount IS NOT NULL AND ministry IS NOT NULL GROUP BY 1,2),
                     r AS (SELECT ministry, recipient, r,
                                  SUM(r) OVER (PARTITION BY ministry) AS m,
                                  ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY r DESC) AS rn FROM p)
                SELECT ministry FROM r GROUP BY ministry, m
                HAVING (SUM(r) FILTER (WHERE rn<=3)) / NULLIF(m,0) >= 0.75
            ) x"""),
        ("AB ministries top-1 >= 50% (≥$1M)",
         """SELECT COUNT(*) FROM (
                WITH p AS (SELECT ministry, recipient, SUM(amount) AS r FROM ab.ab_contracts
                           WHERE amount IS NOT NULL AND ministry IS NOT NULL GROUP BY 1,2),
                     r AS (SELECT ministry, recipient, r,
                                  SUM(r) OVER (PARTITION BY ministry) AS m,
                                  ROW_NUMBER() OVER (PARTITION BY ministry ORDER BY r DESC) AS rn FROM p)
                SELECT ministry FROM r WHERE rn=1 AND m>=1000000 AND r/NULLIF(m,0)>=0.5
            ) x"""),
        ("FED departments top-3 >= 75% (since 2020, ≥$50M)",
         """SELECT COUNT(*) FROM (
                WITH p AS (SELECT owner_org_title AS d, recipient_legal_name AS r, SUM(agreement_value) AS amt
                           FROM fed.grants_contributions
                           WHERE agreement_value IS NOT NULL AND owner_org_title IS NOT NULL
                             AND agreement_start_date >= '2020-01-01' GROUP BY 1,2),
                     ranked AS (SELECT d, r, amt,
                                       SUM(amt) OVER (PARTITION BY d) AS d_t,
                                       ROW_NUMBER() OVER (PARTITION BY d ORDER BY amt DESC) AS rn FROM p)
                SELECT d FROM ranked GROUP BY d, d_t
                HAVING d_t>=50000000 AND (SUM(amt) FILTER (WHERE rn<=3))/NULLIF(d_t,0)>=0.75
            ) x"""),
        ("FED programs top-1 >= 80% (since 2020, ≥$1M)",
         """SELECT COUNT(*) FROM (
                WITH p AS (SELECT prog_name_en AS prog, recipient_legal_name AS r, SUM(agreement_value) AS amt
                           FROM fed.grants_contributions
                           WHERE agreement_value IS NOT NULL AND prog_name_en IS NOT NULL
                             AND agreement_start_date >= '2020-01-01' GROUP BY 1,2),
                     ranked AS (SELECT prog, r, amt,
                                       SUM(amt) OVER (PARTITION BY prog) AS p_t,
                                       ROW_NUMBER() OVER (PARTITION BY prog ORDER BY amt DESC) AS rn FROM p)
                SELECT prog FROM ranked WHERE rn=1 AND p_t>=1000000 AND amt/NULLIF(p_t,0)>=0.8
            ) x"""),
        ("Cross-ministry vendors (≥5 ministries/depts, ≥$10M)",
         """SELECT COUNT(*) FROM (
                WITH u AS (
                    SELECT recipient, ministry, SUM(amount) AS amt FROM ab.ab_contracts
                    WHERE recipient IS NOT NULL AND ministry IS NOT NULL AND amount IS NOT NULL
                    GROUP BY 1,2
                    UNION ALL
                    SELECT recipient_legal_name, owner_org_title, SUM(agreement_value) FROM fed.grants_contributions
                    WHERE recipient_legal_name IS NOT NULL AND owner_org_title IS NOT NULL
                      AND agreement_value IS NOT NULL AND agreement_start_date >= '2020-01-01'
                    GROUP BY 1,2)
                SELECT recipient FROM u GROUP BY 1
                HAVING COUNT(DISTINCT ministry)>=5 AND SUM(amt)>=10000000
            ) x"""),
    ]
    for label, q in queries:
        try:
            cur.execute(q)
            n = cur.fetchone()[0]
            print(f"  {label:<60s}  {n:>6,}")
        except Exception as e:
            print(f"  {label:<60s}  ERROR: {str(e)[:60]}")


if __name__ == "__main__":
    main()
