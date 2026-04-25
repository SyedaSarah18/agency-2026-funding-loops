"""Phase 1a — connect to organizer's PostgreSQL, dump schemas/tables/columns/row-counts.

Output: analysis/schema.json (full inventory) + console summary.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DSN = os.environ["PG_DSN"]
TARGET_SCHEMAS = ("cra", "fed", "ab", "general")


def fetch_inventory(conn):
    cur = conn.cursor()

    # All target-schema tables + columns
    cur.execute(
        """
        SELECT table_schema, table_name, column_name, data_type, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (list(TARGET_SCHEMAS),),
    )
    cols = cur.fetchall()

    schema = defaultdict(lambda: defaultdict(list))
    for schema_name, table, col, dtype, pos in cols:
        schema[schema_name][table].append({"name": col, "type": dtype, "pos": pos})

    # Row count per table (uses pg_class reltuples for speed; approximate but huge tables make COUNT(*) too slow)
    cur.execute(
        """
        SELECT n.nspname, c.relname, c.reltuples::bigint
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p')
        """,
        (list(TARGET_SCHEMAS),),
    )
    counts = {(s, t): n for s, t, n in cur.fetchall()}

    inventory = {}
    grand_total = 0
    for schema_name, tables in schema.items():
        inventory[schema_name] = {}
        schema_total = 0
        for table, columns in tables.items():
            n = counts.get((schema_name, table), 0)
            inventory[schema_name][table] = {
                "approx_row_count": n,
                "column_count": len(columns),
                "columns": columns,
            }
            schema_total += n
        inventory[schema_name]["__schema_total_approx_rows__"] = schema_total
        grand_total += schema_total

    inventory["__grand_total_approx_rows__"] = grand_total
    return inventory


def print_summary(inventory):
    print(f"\n{'='*70}")
    print(f"SCHEMA INVENTORY — Agency 2026 Hackathon DB")
    print(f"{'='*70}\n")
    for schema_name in TARGET_SCHEMAS:
        if schema_name not in inventory:
            print(f"  [MISSING] schema '{schema_name}' not found")
            continue
        s = inventory[schema_name]
        total = s.get("__schema_total_approx_rows__", 0)
        table_names = [t for t in s.keys() if not t.startswith("__")]
        print(f"  {schema_name.upper():<8} {len(table_names):>3} tables  ~{total:>12,} rows (approx)")
    print(f"\n  {'GRAND TOTAL':<12} ~{inventory['__grand_total_approx_rows__']:>12,} rows")
    print(f"  {'TARGET (brief)':<12} ~  23,000,000 rows")
    print(f"\nFull inventory written to analysis/schema.json")


def main():
    print(f"Connecting to: {DSN.split('@')[1].split('/')[0]} ...", flush=True)
    try:
        conn = psycopg2.connect(DSN, connect_timeout=15)
    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] DB connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    conn.set_session(readonly=True, autocommit=True)
    print(f"Connected. Server: {conn.server_version}", flush=True)

    inventory = fetch_inventory(conn)
    out = ROOT / "analysis" / "schema.json"
    out.write_text(json.dumps(inventory, indent=2, default=str))
    print_summary(inventory)


if __name__ == "__main__":
    main()
