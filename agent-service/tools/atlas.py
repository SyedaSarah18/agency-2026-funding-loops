"""Atlas read tools for the agent layer.

Agents read pre-computed concentration metrics from
analysis/atlas_data/*.parquet via these tools — they do NOT run analytical
SQL against the raw procurement tables. This keeps the data layer's
methodology defensible (statistical baselines + percentile thresholds)
and the agent layer focused on synthesis + reasoning.

Tools exposed:
- atlas_top_categories(top_n, min_total_spend): ranked Watchlist of
  most-concentrated category x ministry rows by headline_risk_score.
- atlas_category_detail(ministry, category): full row + all-vendor
  breakdown for a specific category (used by Investigation).
- atlas_vendor_footprint(vendor_substr): cross-ministry breakdown +
  lockin score for a vendor (used by Investigation + Conductor chat).
- atlas_vendor_incumbency(ministry, vendor): year-over-year history +
  step-function detection.

Strands convention: docstring first line = tool description; Args
block describes parameters; type hints drive JSON schema.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from strands import tool

ROOT = Path(__file__).resolve().parent.parent.parent
ATLAS_DIR = ROOT / "analysis" / "atlas_data"


@lru_cache(maxsize=1)
def _categories() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_categories.parquet")


@lru_cache(maxsize=1)
def _vendor_dep() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_vendor_dependency.parquet")


@lru_cache(maxsize=1)
def _incumbency() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_incumbency.parquet")


@lru_cache(maxsize=1)
def _regions_headline() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_regions_headline.parquet")


@lru_cache(maxsize=1)
def _regions_cities() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_regions_cities.parquet")


@lru_cache(maxsize=1)
def _regions_oop() -> pd.DataFrame:
    return pd.read_parquet(ATLAS_DIR / "atlas_regions_out_of_province.parquet")


def _serialize(df: pd.DataFrame, max_rows: int = 50) -> list[dict]:
    """Convert DataFrame to JSON-safe list of dicts, capped."""
    safe = df.head(max_rows).copy()
    for col in safe.columns:
        if safe[col].dtype == "object":
            safe[col] = safe[col].astype(str).where(safe[col].notna(), None)
    return json.loads(safe.to_json(orient="records", date_format="iso"))


@tool
def atlas_top_categories(top_n: int = 10, min_total_spend: float = 10_000_000) -> str:
    """Return the top-N most-concentrated category x ministry rows from
    atlas_categories.parquet, ranked by headline_risk_score descending.

    Use this when you want the Watchlist of "where should an auditor look first?"
    — the Atlas already pre-ranks these using a composite score combining
    dollar magnitude, top-1 share, vendor scarcity, and cross-ministry lock-in.

    Args:
        top_n: How many rows to return (default 10, max 50).
        min_total_spend: Minimum category total spend to include (default $10M
            — that's the 92nd percentile of the actual distribution, so this
            is the "headline" filter for politically-resonant findings).

    Returns:
        JSON list of objects: {ministry, category, total_spend, n_vendors,
        top1_vendor, top1_amount, top1_share, top3_share, herfindahl,
        top1_vendor_cross_ministry_count, composite_risk_score,
        headline_risk_score}
    """
    df = _categories()
    df = df[df["total_spend"] >= min_total_spend]
    df = df.sort_values("headline_risk_score", ascending=False).head(min(top_n, 50))
    return json.dumps({
        "row_count": len(df),
        "rows": _serialize(df, max_rows=50),
    }, default=str)


@tool
def atlas_category_detail(ministry: str, category_substr: str) -> str:
    """Return detail for a specific category x ministry: full row + the
    raw vendor breakdown.

    Used by Investigation to build a dossier for one Discovery candidate.

    Args:
        ministry: Exact ministry name (e.g. "Service Alberta",
            "Technology and Innovation").
        category_substr: Substring of the category name (case-insensitive).
            For exact match, pass the full category name.

    Returns:
        JSON object: {match_count, candidates: [...]} where each candidate
        has all atlas_categories fields. If multiple categories match the
        substring, all are returned ranked by headline_risk_score.
    """
    df = _categories()
    df = df[
        df["ministry"].str.lower().eq(ministry.lower())
        & df["category"].str.contains(category_substr, case=False, na=False)
    ]
    df = df.sort_values("headline_risk_score", ascending=False)
    return json.dumps({
        "match_count": len(df),
        "candidates": _serialize(df, max_rows=10),
    }, default=str)


@tool
def atlas_vendor_footprint(vendor_substr: str, top_n: int = 10) -> str:
    """Return a vendor's cross-ministry footprint and lockin score from
    atlas_vendor_dependency.parquet.

    This answers "the government has become dependent on a vendor it can no
    longer walk away from" — the lockin_score combines cross-ministry
    breadth, total spend, sole-source share, and category breadth.

    Args:
        vendor_substr: Substring of the vendor's legal name (case-insensitive).
            Returns up to top_n matches sorted by lockin_score descending.
        top_n: How many vendor matches to return (default 10).

    Returns:
        JSON list of {vendor, n_ministries, n_categories, total_spend,
        n_contracts, sole_source_spend, sole_source_count, sole_source_share,
        lockin_score}.
    """
    df = _vendor_dep()
    df = df[df["vendor"].str.contains(vendor_substr, case=False, na=False)]
    df = df.sort_values("lockin_score", ascending=False).head(top_n)
    return json.dumps({
        "match_count": len(df),
        "vendors": _serialize(df, max_rows=10),
    }, default=str)


@tool
def atlas_region_breakdown(view: str = "out_of_province",
                           ministry: Optional[str] = None,
                           city: Optional[str] = None,
                           top_n: int = 15) -> str:
    """Regional breakdown of Alberta sole-source procurement.

    Three views answer the challenge's "concentration by region" requirement:
    - 'headline': per ministry, the Alberta-based vs Out-of-province vs Unknown
      spend split. Surfaces which ministries depend most on out-of-province
      vendors.
    - 'cities': within Alberta, per (city x ministry), top vendor + concentration.
      Surfaces small-town concentration patterns (e.g. one Lethbridge vendor
      dominating Lethbridge-issued contracts).
    - 'out_of_province': categories where >50% of spend leaves Alberta. Names
      the top out-of-province vendor and their province (typically ON for
      tech giants like Microsoft/IBM Canada Inc).

    Args:
        view: 'headline' | 'cities' | 'out_of_province' (default).
        ministry: Optional exact ministry name to filter by (used for headline + cities views).
        city: Optional substring of city name (used for 'cities' view only).
        top_n: Max rows to return (default 15).

    Returns:
        JSON list of rows. Schema depends on view:
          headline: {ministry, region_bucket, spend, n_contracts, n_vendors}
          cities:   {province, city, ministry, total_spend, n_vendors,
                     top1_vendor, top1_amount, top1_share}
          out_of_province: {category, total_spend, out_of_province_spend,
                            out_of_province_share, top_out_of_province_vendor,
                            top_out_of_province_province, top_out_of_province_amount}
    """
    if view == "headline":
        df = _regions_headline()
        if ministry:
            df = df[df["ministry"].str.lower().eq(ministry.lower())]
        df = df.sort_values("spend", ascending=False).head(top_n)
    elif view == "cities":
        df = _regions_cities()
        if ministry:
            df = df[df["ministry"].str.lower().eq(ministry.lower())]
        if city:
            df = df[df["city"].str.contains(city, case=False, na=False)]
        df = df.sort_values("total_spend", ascending=False).head(top_n)
    elif view == "out_of_province":
        df = _regions_oop()
        df = df.sort_values("out_of_province_spend", ascending=False).head(top_n)
    else:
        return json.dumps({"error": f"unknown view {view!r}; expected headline|cities|out_of_province"})
    return json.dumps({
        "view": view,
        "row_count": len(df),
        "rows": _serialize(df, max_rows=top_n),
    }, default=str)


@tool
def atlas_vendor_incumbency(ministry: Optional[str] = None,
                            vendor_substr: Optional[str] = None,
                            step_function_only: bool = False,
                            top_n: int = 20) -> str:
    """Return per (ministry x vendor) year-over-year history with temporal_zscore
    + step-function emergence detection from atlas_incumbency.parquet.

    Use this when you want to know "did this vendor appear suddenly?" or "has
    this vendor been the dominant supplier year after year?"

    Args:
        ministry: Optional exact ministry name to filter.
        vendor_substr: Optional substring of vendor name to filter.
        step_function_only: If True, only return rows where is_step_function=true
            (vendors that appeared with z>5 standard deviations above their
            historical baseline — the "GC Strategies pattern").
        top_n: Max rows to return.

    Returns:
        JSON list of {ministry, vendor, years_active, fy_min, fy_max,
        total_spend, latest_year_spend, temporal_zscore, is_step_function}.
    """
    df = _incumbency()
    if ministry:
        df = df[df["ministry"].str.lower().eq(ministry.lower())]
    if vendor_substr:
        df = df[df["vendor"].str.contains(vendor_substr, case=False, na=False)]
    if step_function_only:
        df = df[df["is_step_function"]]
    df = df.sort_values("total_spend", ascending=False).head(top_n)
    return json.dumps({
        "match_count": len(df),
        "histories": _serialize(df, max_rows=20),
    }, default=str)
