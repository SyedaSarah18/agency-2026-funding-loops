"""Pre-compute category/ministry analytics for the Knowledge Base.

Run once from the repo root after any data update:

    PYTHONPATH=agent/src python agent/scripts/precompute_kb.py

Outputs four JSON files to agent/src/vendor_concentration_agent/kb/.
These are committed and baked into the Docker image so the agent can
answer broad "how many vendors compete in X?" questions instantly
without hitting Postgres on every request.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from vendor_concentration_agent.data.postgres import query  # noqa: E402

KB_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "vendor_concentration_agent"
    / "kb"
)
KB_DIR.mkdir(exist_ok=True)

FED_AMOUNT = (
    "(CASE WHEN contract_value ~ '^[-+]?[0-9]+(\\.[0-9]+)?$' "
    "THEN contract_value::numeric ELSE NULL END)"
)


def _save(filename: str, data: dict) -> None:
    path = KB_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    n = data.get("row_count", "?")
    print(f"  {filename}  ({n} rows)")


def _concentration_query(
    table: str,
    group_col: str,
    vendor_col: str,
    amount_expr: str,
    where_extra: str = "",
) -> list[dict]:
    where = f"WHERE {group_col} IS NOT NULL AND {vendor_col} IS NOT NULL AND {amount_expr} IS NOT NULL AND {amount_expr} > 0"
    if where_extra:
        where += f" AND {where_extra}"
    sql = f"""
        WITH per AS (
            SELECT {group_col} AS slice_name,
                   {vendor_col} AS vendor,
                   SUM({amount_expr}) AS vendor_amt
            FROM {table}
            {where}
            GROUP BY {group_col}, {vendor_col}
        ),
        totals AS (
            SELECT slice_name,
                   SUM(vendor_amt)        AS total_spend,
                   COUNT(DISTINCT vendor) AS vendor_count,
                   COUNT(*)               AS contract_count
            FROM per
            GROUP BY slice_name
        ),
        top1 AS (
            SELECT slice_name, vendor AS top_vendor, vendor_amt,
                   ROW_NUMBER() OVER (
                       PARTITION BY slice_name ORDER BY vendor_amt DESC
                   ) AS rk
            FROM per
        )
        SELECT t.slice_name,
               t.total_spend,
               t.vendor_count,
               t.contract_count,
               v.top_vendor,
               ROUND((100.0 * v.vendor_amt / NULLIF(t.total_spend, 0))::numeric, 2)
                   AS top1_share_pct
        FROM totals t
        JOIN top1 v ON v.slice_name = t.slice_name AND v.rk = 1
        ORDER BY top1_share_pct DESC, total_spend DESC
    """
    return query(sql, {})


def compute_ab_sole_source_by_category() -> None:
    print("ab_sole_source → by contract_services category …")
    rows = _concentration_query(
        table="ab.ab_sole_source",
        group_col="contract_services",
        vendor_col="vendor",
        amount_expr="amount",
    )
    _save(
        "ab_sole_source_by_category.json",
        {
            "dataset": "ab_sole_source",
            "slice": "category",
            "column": "contract_services",
            "note": "Every row is sole-source; vendor_count is always 1 by definition — not a concentration signal.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "rows": [
                {
                    "category": r["slice_name"],
                    "total_spend": float(r["total_spend"]),
                    "vendor_count": int(r["vendor_count"]),
                    "contract_count": int(r["contract_count"]),
                    "top_vendor": r["top_vendor"],
                    "top1_share_pct": float(r["top1_share_pct"]),
                }
                for r in rows
            ],
        },
    )


def compute_ab_contracts_by_ministry() -> None:
    print("ab_contracts → by ministry …")
    rows = _concentration_query(
        table="ab.ab_contracts",
        group_col="ministry",
        vendor_col="recipient",
        amount_expr="amount",
    )
    _save(
        "ab_contracts_by_ministry.json",
        {
            "dataset": "ab_contracts",
            "slice": "ministry",
            "column": "ministry",
            "note": "Competitively procured contracts. vendor_count reflects real competition.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "rows": [
                {
                    "ministry": r["slice_name"],
                    "total_spend": float(r["total_spend"]),
                    "vendor_count": int(r["vendor_count"]),
                    "contract_count": int(r["contract_count"]),
                    "top_vendor": r["top_vendor"],
                    "top1_share_pct": float(r["top1_share_pct"]),
                }
                for r in rows
            ],
        },
    )


def compute_fed_contracts_by_category() -> None:
    print("fed_contracts → by economic_object_code (category) …")
    rows = _concentration_query(
        table="public.contracts",
        group_col="economic_object_code",
        vendor_col="vendor_name",
        amount_expr=FED_AMOUNT,
    )
    _save(
        "fed_contracts_by_category.json",
        {
            "dataset": "fed_contracts",
            "slice": "category",
            "column": "economic_object_code",
            "note": "Federal Proactive Disclosure. contract_value is TEXT; non-numeric strings cast to NULL.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "rows": [
                {
                    "category": r["slice_name"],
                    "total_spend": float(r["total_spend"]),
                    "vendor_count": int(r["vendor_count"]),
                    "contract_count": int(r["contract_count"]),
                    "top_vendor": r["top_vendor"],
                    "top1_share_pct": float(r["top1_share_pct"]),
                }
                for r in rows
            ],
        },
    )


def compute_fed_contracts_by_dept() -> None:
    print("fed_contracts → by owner_org_title (department) …")
    rows = _concentration_query(
        table="public.contracts",
        group_col="owner_org_title",
        vendor_col="vendor_name",
        amount_expr=FED_AMOUNT,
    )
    _save(
        "fed_contracts_by_dept.json",
        {
            "dataset": "fed_contracts",
            "slice": "department",
            "column": "owner_org_title",
            "note": "Federal departments / agencies. Same dataset as fed_contracts_by_category but sliced differently.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "rows": [
                {
                    "department": r["slice_name"],
                    "total_spend": float(r["total_spend"]),
                    "vendor_count": int(r["vendor_count"]),
                    "contract_count": int(r["contract_count"]),
                    "top_vendor": r["top_vendor"],
                    "top1_share_pct": float(r["top1_share_pct"]),
                }
                for r in rows
            ],
        },
    )


if __name__ == "__main__":
    print(f"Writing KB files to: {KB_DIR}\n")
    compute_ab_sole_source_by_category()
    compute_ab_contracts_by_ministry()
    compute_fed_contracts_by_category()
    compute_fed_contracts_by_dept()
    print("\nDone.")
