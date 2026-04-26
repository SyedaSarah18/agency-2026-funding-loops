"""Concentration metrics — pure functions reused by build.py and the agent layer.

All functions accept either a pandas Series of dollar amounts (per group/category)
or a numpy array; they return scalar floats. No DB dependency, no LLM.

Conventions:
- Herfindahl: 0 = perfectly competitive, 1 = monopoly. Sum of squared market shares.
- Gini: 0 = equal distribution across all entities, 1 = one entity gets everything.
- top_n_share: fraction (0.0-1.0) of total accounted for by the top N entities.
- temporal_zscore: how anomalous the latest value is vs. historical baseline; positive
  means above baseline, negative means below. Returns None if <2 historical points.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


def _as_series(amounts) -> pd.Series:
    """Coerce input to a clean float Series with NaN/zero-total guards.

    Returns an empty Series if no positive amounts remain after cleaning.
    """
    s = pd.Series(amounts, dtype="float64").dropna()
    s = s[s > 0]  # negative amounts (refunds, amendments) shouldn't count
    return s


def herfindahl(amounts: Iterable[float]) -> float:
    """Herfindahl-Hirschman Index over a set of vendor amounts.

    Sum of squared market shares. 0 = perfect competition (infinite vendors of equal
    size), 1 = monopoly (one vendor takes 100%).

    Examples:
      herfindahl([100, 100, 100, 100]) == 0.25  (4 equal vendors -> 4 * 0.25^2)
      herfindahl([1000, 1])            ~ 0.998  (one vendor dominates)
      herfindahl([1])                  == 1.0   (single vendor monopoly)
    """
    s = _as_series(amounts)
    if s.empty:
        return 0.0
    shares = s / s.sum()
    return float((shares ** 2).sum())


def gini(amounts: Iterable[float]) -> float:
    """Gini coefficient of inequality across vendors.

    0 = all vendors get equal share. 1 = one vendor gets everything.
    Distinct from Herfindahl: Gini measures inequality of the distribution;
    Herfindahl measures concentration (squared).
    """
    s = _as_series(amounts)
    n = len(s)
    if n == 0:
        return 0.0
    if n == 1:
        return 1.0  # single vendor = maximum inequality
    sorted_amounts = np.sort(s.values)
    cumulative = np.cumsum(sorted_amounts)
    total = cumulative[-1]
    if total == 0:
        return 0.0
    # Standard Gini formula
    return float((2.0 * np.sum((np.arange(1, n + 1)) * sorted_amounts) / (n * total)) - (n + 1.0) / n)


def top_n_share(amounts: Iterable[float], n: int = 1) -> float:
    """Fraction of total accounted for by the top N vendors.

    top_n_share([100, 50, 25, 10], n=1)  == 100/185  ~ 0.541
    top_n_share([100, 50, 25, 10], n=3)  == 175/185  ~ 0.946
    """
    s = _as_series(amounts)
    if s.empty:
        return 0.0
    total = s.sum()
    if total == 0:
        return 0.0
    top = s.nlargest(n).sum()
    return float(top / total)


def vendor_count(amounts: Iterable[float], min_amount: float = 0.0) -> int:
    """Count of distinct vendors with amount > min_amount."""
    s = _as_series(amounts)
    return int((s > min_amount).sum())


def temporal_zscore(yearly_values: Iterable[float]) -> Optional[float]:
    """How many standard deviations the latest value sits from the historical mean.

    Returns None if fewer than 3 points total (not enough history to compute).
    Positive => latest value above baseline; negative => below.
    Useful for detecting "step function" emergence: a vendor that historically
    received $5M/yr and suddenly $50M will have a high z-score.

    Special case: if the historical series is constant (std == 0), zero variance
    means any deviation is anomalous. Returns +/-50.0 (capped) when latest != mean,
    0.0 when latest == mean. Without this we'd return None on the most
    obviously-anomalous case (a vendor that got nothing for years then a windfall).
    """
    arr = np.asarray(list(yearly_values), dtype="float64")
    arr = arr[~np.isnan(arr)]
    if len(arr) < 3:
        return None
    latest = arr[-1]
    historical = arr[:-1]
    h_std = historical.std(ddof=0)
    h_mean = historical.mean()
    if h_std == 0:
        if latest == h_mean:
            return 0.0
        # Constant baseline + any deviation = strongest possible anomaly signal.
        # Cap at +/-50 so it's still finite for downstream arithmetic.
        return 50.0 if latest > h_mean else -50.0
    return float((latest - h_mean) / h_std)


def composite_concentration_risk(
    *,
    total_spend: float,
    top1_share: float,
    n_vendors: int,
    cross_ministry_count: int = 1,
    multi_year_extension: bool = False,
) -> float:
    """Composite risk score 0-100 combining four signals.

    Designed for Atlas ranking — NOT for Validator's per-finding risk score
    (those are LLM-judgment with breakdown). This is a deterministic baseline
    score the data layer assigns; the Validator can override later.

    Components:
      - $ magnitude (0-30): log10(total_spend / 1000) clamped to [0, 30]
      - Top-1 dominance (0-30): linear in top1_share. share=0.50 -> 0; 1.0 -> 30
      - Vendor scarcity (0-20): inverse of vendor count. 1 vendor -> 20; 10+ -> ~2
      - Lock-in breadth (0-15): cross-ministry breadth. 1 ministry -> 0; 10+ -> 15
      - Multi-year extension flag (0-5): boolean flag worth 5 points
    """
    if total_spend <= 0:
        return 0.0

    # Dollar magnitude
    magnitude = max(0.0, min(30.0, np.log10(total_spend / 1000.0) * 3.5))

    # Top-1 dominance
    dominance = max(0.0, min(30.0, (top1_share - 0.5) * 60.0)) if top1_share >= 0.5 else 0.0

    # Vendor scarcity (more vendors = healthier competition)
    scarcity = max(0.0, min(20.0, 20.0 / max(1, n_vendors) * 1.5))

    # Cross-ministry lock-in breadth
    lockin = max(0.0, min(15.0, (cross_ministry_count - 1) * 1.7))

    # Multi-year extension flag
    extension = 5.0 if multi_year_extension else 0.0

    return round(magnitude + dominance + scarcity + lockin + extension, 1)
