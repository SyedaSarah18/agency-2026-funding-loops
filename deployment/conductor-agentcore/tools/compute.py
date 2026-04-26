"""Constrained code-compute tool for the Conductor agent.

Lets the Conductor write arbitrary pandas method-chain expressions against
pre-loaded Atlas DataFrames in a sandbox — without exposing full Python
execution. Covers ~80% of likely "compute me a novel metric" demo questions
with ~20% of the security/reliability risk of a full code interpreter.

Available DataFrames in the eval sandbox:
  - atlas_categories          (atlas_categories.parquet)
  - atlas_vendor_dependency   (atlas_vendor_dependency.parquet)
  - atlas_incumbency          (atlas_incumbency.parquet)
  - pd                        (pandas)
  - np                        (numpy)
  - metrics                   (analysis/atlas/metrics.py functions:
                               herfindahl, gini, top_n_share, temporal_zscore)

Available builtins:
  - len, min, max, sum, abs, round, sorted, list, dict, tuple, set,
    str, int, float, bool, range, enumerate, zip, map, filter

NOT available: open, exec, eval, __import__, file IO, network, os, sys, etc.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from strands import tool

# Deployment-flat layout: parquets at <package_root>/atlas_data/.
ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = ROOT / "atlas_data"

# Inline a tiny metrics shim so we don't have to ship analysis/atlas/metrics.py.
class _MetricsShim:
    @staticmethod
    def herfindahl(amounts):
        s = pd.Series(amounts, dtype="float64").dropna()
        s = s[s > 0]
        if s.empty:
            return 0.0
        shares = s / s.sum()
        return float((shares ** 2).sum())

    @staticmethod
    def gini(amounts):
        import numpy as _np
        s = pd.Series(amounts, dtype="float64").dropna()
        s = s[s > 0]
        n = len(s)
        if n == 0:
            return 0.0
        if n == 1:
            return 1.0
        sorted_a = _np.sort(s.values)
        cumulative = _np.cumsum(sorted_a)
        total = cumulative[-1]
        if total == 0:
            return 0.0
        return float(
            (2.0 * _np.sum((_np.arange(1, n + 1)) * sorted_a) / (n * total))
            - (n + 1.0) / n
        )

    @staticmethod
    def top_n_share(amounts, n=1):
        s = pd.Series(amounts, dtype="float64").dropna()
        s = s[s > 0]
        if s.empty:
            return 0.0
        return float(s.nlargest(n).sum() / s.sum())

    @staticmethod
    def temporal_zscore(yearly_values):
        import numpy as _np
        arr = _np.asarray(list(yearly_values), dtype="float64")
        arr = arr[~_np.isnan(arr)]
        if len(arr) < 3:
            return None
        latest = arr[-1]
        historical = arr[:-1]
        if historical.std(ddof=0) == 0:
            return 0.0 if latest == historical.mean() else (
                50.0 if latest > historical.mean() else -50.0
            )
        return float((latest - historical.mean()) / historical.std(ddof=0))


_metrics = _MetricsShim()

_SAFE_BUILTINS = {
    "len": len, "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
    "sorted": sorted, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "str": str, "int": int, "float": float, "bool": bool,
    "range": range, "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "any": any, "all": all,
}

_BANNED_TOKENS = (
    "__", "import", "exec", "eval", "open(", "compile", "globals", "locals",
    "getattr", "setattr", "delattr", "vars", "dir", "type(",
)


@lru_cache(maxsize=1)
def _atlas_dfs() -> dict:
    return {
        "atlas_categories": pd.read_parquet(ATLAS_DIR / "atlas_categories.parquet"),
        "atlas_vendor_dependency": pd.read_parquet(ATLAS_DIR / "atlas_vendor_dependency.parquet"),
        "atlas_incumbency": pd.read_parquet(ATLAS_DIR / "atlas_incumbency.parquet"),
    }


@tool
def code_compute(expression: str, max_rows: int = 30) -> str:
    """Evaluate a single pandas method-chain expression against the Atlas DataFrames.

    Use this when the user asks for a novel metric or filter that the
    pre-built atlas_* tools don't directly answer (e.g. "what's the median
    Herfindahl in IT services?" or "how many vendors have lockin >= 50?").

    Available variables in the expression:
      atlas_categories        — DataFrame
      atlas_vendor_dependency — DataFrame
      atlas_incumbency        — DataFrame
      pd, np                  — pandas, numpy
      metrics                 — module with herfindahl, gini, top_n_share, temporal_zscore

    Examples:
      atlas_categories[atlas_categories.total_spend >= 50_000_000].sort_values('top1_share', ascending=False).head(10)
      atlas_vendor_dependency.query('lockin_score >= 60')[['vendor','n_ministries','total_spend','lockin_score']]
      atlas_categories['top1_share'].describe()
      metrics.herfindahl(atlas_categories[atlas_categories.ministry == 'Service Alberta'].top1_amount)

    Args:
        expression: A single Python expression (NOT a statement — no assignments,
            no imports, no semicolons). Pandas method-chain style works best.
        max_rows: If the result is a DataFrame, return at most this many rows.

    Returns:
        JSON object: {result_type, result, shape (if DataFrame), truncated (bool)}.
        On error, returns {error: ...} with the exception message.
    """
    expr = (expression or "").strip()
    if not expr:
        return json.dumps({"error": "empty expression"})

    # Guardrails — block obviously dangerous tokens
    lower = expr.lower()
    for banned in _BANNED_TOKENS:
        if banned in lower:
            return json.dumps({
                "error": f"banned token in expression: {banned!r}. "
                         "code_compute only allows safe pandas/numpy expressions."
            })

    if "=" in expr and not any(op in expr for op in ("==", ">=", "<=", "!=")):
        return json.dumps({"error": "assignments not allowed; only single expressions"})

    sandbox = _atlas_dfs() | {"pd": pd, "np": np, "metrics": _metrics}
    try:
        result = eval(expr, {"__builtins__": _SAFE_BUILTINS}, sandbox)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}"})

    # Format the result
    if isinstance(result, pd.DataFrame):
        truncated = len(result) > max_rows
        head = result.head(max_rows).copy()
        for col in head.columns:
            if head[col].dtype == "object":
                head[col] = head[col].astype(str).where(head[col].notna(), None)
        rows = json.loads(head.to_json(orient="records", date_format="iso"))
        return json.dumps({
            "result_type": "DataFrame",
            "shape": list(result.shape),
            "truncated": truncated,
            "rows": rows,
        }, default=str)
    if isinstance(result, pd.Series):
        truncated = len(result) > max_rows
        head = result.head(max_rows)
        return json.dumps({
            "result_type": "Series",
            "length": len(result),
            "truncated": truncated,
            "values": json.loads(head.to_json(orient="index", date_format="iso")),
        }, default=str)
    if isinstance(result, (int, float, str, bool, type(None))):
        return json.dumps({"result_type": type(result).__name__, "value": result})
    if isinstance(result, (list, tuple)):
        return json.dumps({
            "result_type": type(result).__name__,
            "length": len(result),
            "values": list(result)[:max_rows],
            "truncated": len(result) > max_rows,
        }, default=str)
    if isinstance(result, dict):
        return json.dumps({"result_type": "dict", "value": result}, default=str)
    # Fallback: stringify
    return json.dumps({"result_type": type(result).__name__, "value_str": str(result)[:500]})
