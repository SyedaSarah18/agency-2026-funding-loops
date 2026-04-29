"""Procurement-specific metrics: sole-source rate, incumbency streak, etc.

Hour 1 ships sole_source_rate. Remaining functions land in Hour 2.
"""

from __future__ import annotations

from vendor_concentration_agent.data.postgres import query
from vendor_concentration_agent.math.types import MathResult


# ---------------------------------------------------------------------------
# Sole-source rate — share of procurement dollars not subject to competition
# ---------------------------------------------------------------------------

def sole_source_rate(
    ministry: str | None = None,
    fiscal_year: str | None = None,
) -> MathResult:
    """Sole-source rate = $ sole-source / ($ sole-source + $ contracts), as
    a percentage 0–100. Computed by summing both Alberta procurement tables
    (`ab.ab_sole_source` and `ab.ab_contracts`) under the same scope filters.

    A simple ratio — no external citation. The interpretation we attach: a
    high sole-source share signals that competitive procurement is the
    exception rather than the rule for that scope.
    """
    where: list[str] = ["amount IS NOT NULL", "amount > 0"]
    params: dict = {}
    if ministry is not None:
        where.append("ministry = %(ministry)s")
        params["ministry"] = ministry
    if fiscal_year is not None:
        where.append("display_fiscal_year = %(fy)s")
        params["fy"] = fiscal_year
    where_sql = " AND ".join(where)

    sql = f"""
        SELECT 'sole_source' AS source, COALESCE(SUM(amount), 0)::numeric AS total
        FROM ab.ab_sole_source
        WHERE {where_sql}
        UNION ALL
        SELECT 'contracts' AS source, COALESCE(SUM(amount), 0)::numeric AS total
        FROM ab.ab_contracts
        WHERE {where_sql}
    """
    rows = query(sql, params)
    by_source = {r["source"]: float(r["total"]) for r in rows}
    sole = by_source.get("sole_source", 0.0)
    comp = by_source.get("contracts", 0.0)
    total = sole + comp
    rate = 100.0 * sole / total if total else 0.0

    return MathResult(
        value=round(rate, 4),
        formula_id="sole_source_rate",
        sql=sql.strip(),
        source_rows=[{"source": k, "total": v} for k, v in by_source.items()],
        trace_steps=[
            {"step": "sole_source_total", "value": sole},
            {"step": "contracts_total", "value": comp},
            {"step": "denominator (sum)", "value": total},
            {"step": "numerator / denominator * 100", "value": round(rate, 4)},
        ],
        references=[],
        inputs={"ministry": ministry, "fiscal_year": fiscal_year},
    )
