"""Build the Procurement Concentration Atlas.

Pulls Alberta procurement data from the organizer's hosted PostgreSQL into
a local DuckDB, computes 3 ranked Atlas tables, and writes parquet outputs
to atlas_data/. The agent layer reads from these parquet files; it never
runs analytical SQL.

Outputs:
- atlas_data/atlas_categories.parquet      — per (category x ministry): concentration metrics
- atlas_data/atlas_vendor_dependency.parquet — per vendor: cross-ministry footprint
- atlas_data/atlas_incumbency.parquet      — per (ministry x vendor): year-over-year dominance

Usage:  python analysis/atlas/build.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.stdout.reconfigure(encoding="utf-8")

from atlas.metrics import (
    composite_concentration_risk,
    gini,
    herfindahl,
    temporal_zscore,
    top_n_share,
    vendor_count,
)

load_dotenv(ROOT / ".env")

PG_DSN = os.environ["PG_DSN"]
ATLAS_DIR = ROOT / "analysis" / "atlas_data"
ATLAS_DIR.mkdir(parents=True, exist_ok=True)
DUCKDB_PATH = ATLAS_DIR / "atlas.duckdb"

# ---- Step 1: pull source tables from Postgres into DuckDB once -------------

def pull_source_tables(force: bool = False) -> duckdb.DuckDBPyConnection:
    """Pull ab.ab_sole_source + ab.ab_contracts into local DuckDB.

    Idempotent unless force=True. Round-trips Postgres -> pandas -> DuckDB.
    Round-trip cost is paid once; subsequent Atlas builds re-read from DuckDB
    (much faster than the hosted PG).
    """
    print(f"[1/4] Pulling source tables -> {DUCKDB_PATH}")
    con = duckdb.connect(str(DUCKDB_PATH))

    if not force:
        existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if {"ab_sole_source", "ab_contracts"}.issubset(existing):
            n_ss = con.execute("SELECT COUNT(*) FROM ab_sole_source").fetchone()[0]
            n_c = con.execute("SELECT COUNT(*) FROM ab_contracts").fetchone()[0]
            print(f"  cached: ab_sole_source={n_ss:,}  ab_contracts={n_c:,}  (use force=True to refresh)")
            return con

    pg = psycopg2.connect(PG_DSN, connect_timeout=15)
    pg.set_session(readonly=True, autocommit=True)

    print("  pulling ab.ab_sole_source ...")
    t0 = time.time()
    df_ss = pd.read_sql(
        """
        SELECT id, ministry, vendor,
               vendor_city, vendor_province, vendor_postal_code, vendor_country,
               start_date, end_date, amount, contract_number,
               contract_services, permitted_situations,
               display_fiscal_year, special
        FROM ab.ab_sole_source
        """,
        pg,
    )
    print(f"  ab_sole_source: {len(df_ss):,} rows in {time.time()-t0:.1f}s")

    print("  pulling ab.ab_contracts ...")
    t0 = time.time()
    df_c = pd.read_sql(
        """
        SELECT id, display_fiscal_year, recipient, amount, ministry
        FROM ab.ab_contracts
        """,
        pg,
    )
    print(f"  ab_contracts: {len(df_c):,} rows in {time.time()-t0:.1f}s")

    pg.close()

    con.execute("DROP TABLE IF EXISTS ab_sole_source")
    con.execute("DROP TABLE IF EXISTS ab_contracts")
    con.register("df_ss", df_ss)
    con.register("df_c", df_c)
    con.execute("CREATE TABLE ab_sole_source AS SELECT * FROM df_ss")
    con.execute("CREATE TABLE ab_contracts AS SELECT * FROM df_c")
    con.unregister("df_ss")
    con.unregister("df_c")
    print(f"  written to DuckDB.")
    return con


# ---- Step 2: atlas_categories ---------------------------------------------

def build_atlas_categories(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per (contract_services category x ministry): concentration metrics.

    Each row answers: "for this service category in this ministry, who provides it,
    how concentrated is the spend, what's the risk score?"
    """
    print("[2/4] Building atlas_categories ...")

    # Pull the per-vendor amounts; metrics are computed in pandas using metrics.py
    df = con.execute(
        """
        SELECT
            ministry,
            COALESCE(NULLIF(TRIM(contract_services), ''), '(uncategorised)') AS category,
            vendor,
            SUM(amount) AS amount
        FROM ab_sole_source
        WHERE amount IS NOT NULL AND amount > 0
          AND vendor IS NOT NULL AND ministry IS NOT NULL
        GROUP BY 1, 2, 3
        """
    ).fetchdf()

    # Cross-ministry vendor count is needed for risk scoring; compute it once
    cross_min_count = (
        df.groupby("vendor")["ministry"].nunique().rename("cross_ministry_count")
    )

    rows = []
    for (ministry, category), grp in df.groupby(["ministry", "category"]):
        amounts = grp["amount"].values
        sorted_grp = grp.sort_values("amount", ascending=False)
        top_vendor = sorted_grp.iloc[0]["vendor"]
        top_amount = float(sorted_grp.iloc[0]["amount"])
        total = float(amounts.sum())
        n_v = vendor_count(amounts)
        if total < 100_000:  # skip noise-level categories
            continue

        # Composite risk uses cross-ministry breadth of the TOP vendor as the lock-in signal
        top_vendor_breadth = int(cross_min_count.get(top_vendor, 1))
        risk = composite_concentration_risk(
            total_spend=total,
            top1_share=top_amount / total,
            n_vendors=n_v,
            cross_ministry_count=top_vendor_breadth,
        )

        # `headline_risk_score` is what the demo + Watchlist surface: same composite
        # but zeroed out for small categories (< $10M total) so research grants and
        # noise don't outrank Microsoft's $60M cloud lock-in. The raw `composite_risk_score`
        # is preserved for analytical drill-down (e.g. judges asking "what about the
        # smaller cases?").
        headline = risk if total >= 10_000_000 else 0.0

        rows.append({
            "ministry": ministry,
            "category": category,
            "total_spend": total,
            "n_vendors": n_v,
            "top1_vendor": top_vendor,
            "top1_amount": top_amount,
            "top1_share": top_amount / total,
            "top3_share": top_n_share(amounts, n=3),
            "herfindahl": herfindahl(amounts),
            "gini": gini(amounts),
            "top1_vendor_cross_ministry_count": top_vendor_breadth,
            "composite_risk_score": risk,
            "headline_risk_score": headline,
        })

    out = pd.DataFrame(rows).sort_values("headline_risk_score", ascending=False).reset_index(drop=True)
    out_path = ATLAS_DIR / "atlas_categories.parquet"
    out.to_parquet(out_path, index=False)
    print(f"  wrote {out_path.name}: {len(out):,} categories")
    headline = out[out["headline_risk_score"] > 0]
    print(f"  {len(headline):,} categories cleared the >=$10M magnitude floor for headline ranking")
    print(f"  top 8 by headline risk score:")
    for _, r in headline.head(8).iterrows():
        print(f"    risk={r['headline_risk_score']:.1f}  ${r['total_spend']:>13,.0f}  "
              f"share={r['top1_share']:.0%}  {r['top1_vendor'][:35]:<35}  "
              f"cat={r['category'][:50]}")
    return out


# ---- Step 3: atlas_vendor_dependency --------------------------------------

def build_atlas_vendor_dependency(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per vendor: cross-ministry/cross-category footprint.

    Surfaces the "vendor lock-in" question — vendors with broad horizontal
    presence are the ones the government cannot walk away from.
    """
    print("[3/4] Building atlas_vendor_dependency ...")

    df = con.execute(
        """
        WITH unioned AS (
            SELECT vendor, ministry, amount, contract_services AS category, 'sole_source' AS src
            FROM ab_sole_source
            WHERE amount IS NOT NULL AND amount > 0 AND vendor IS NOT NULL
            UNION ALL
            SELECT recipient AS vendor, ministry, amount, NULL AS category, 'contracts' AS src
            FROM ab_contracts
            WHERE amount IS NOT NULL AND amount > 0 AND recipient IS NOT NULL
        )
        SELECT vendor,
               COUNT(DISTINCT ministry) AS n_ministries,
               COUNT(DISTINCT category) FILTER (WHERE category IS NOT NULL) AS n_categories,
               SUM(amount) AS total_spend,
               COUNT(*) AS n_contracts,
               SUM(amount) FILTER (WHERE src = 'sole_source') AS sole_source_spend,
               COUNT(*) FILTER (WHERE src = 'sole_source') AS sole_source_count
        FROM unioned
        GROUP BY vendor
        HAVING SUM(amount) >= 1_000_000
        ORDER BY n_ministries DESC, total_spend DESC
        """
    ).fetchdf()

    df["sole_source_share"] = (df["sole_source_spend"].fillna(0) / df["total_spend"]).round(3)
    df["lockin_score"] = (
        (df["n_ministries"] * 1.5).clip(upper=30)
        + (df["total_spend"].apply(lambda x: max(0, min(30, (x / 10_000_000) ** 0.5 * 5))))
        + (df["sole_source_share"] * 20)
        + ((df["n_categories"].fillna(0)) * 0.8).clip(upper=20)
    ).round(1)

    out_path = ATLAS_DIR / "atlas_vendor_dependency.parquet"
    df.to_parquet(out_path, index=False)
    print(f"  wrote {out_path.name}: {len(df):,} vendors with >=$1M total")
    print(f"  top 5 by lock-in score:")
    for _, r in df.sort_values("lockin_score", ascending=False).head(5).iterrows():
        print(f"    lockin={r['lockin_score']:.1f}  {int(r['n_ministries']):>2d} ministries  "
              f"${r['total_spend']:>13,.0f}  ss_share={r['sole_source_share']:.0%}  "
              f"{(r['vendor'] or '')[:55]}")
    return df


# ---- Step 4: atlas_incumbency ---------------------------------------------

def build_atlas_incumbency(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per (ministry x vendor): year-over-year incumbency + temporal anomalies.

    Surfaces vendors that were dominant year after year (incumbency) AND vendors
    that emerged suddenly with a large step-function spike (temporal_zscore).
    """
    print("[4/4] Building atlas_incumbency ...")

    df = con.execute(
        """
        SELECT ministry, vendor, display_fiscal_year AS fy,
               SUM(amount) AS amount
        FROM ab_sole_source
        WHERE amount IS NOT NULL AND amount > 0
          AND vendor IS NOT NULL AND ministry IS NOT NULL
          AND display_fiscal_year IS NOT NULL
        GROUP BY 1, 2, 3
        """
    ).fetchdf()

    # Per (ministry, vendor): collect the yearly time series
    rows = []
    for (ministry, vendor), grp in df.groupby(["ministry", "vendor"]):
        years = sorted(grp["fy"].unique())
        if len(years) < 3:
            continue  # need enough history for incumbency to mean anything
        yearly_amounts = (
            grp.set_index("fy").reindex(years)["amount"].fillna(0).values
        )
        z = temporal_zscore(yearly_amounts)
        rows.append({
            "ministry": ministry,
            "vendor": vendor,
            "years_active": len(years),
            "fy_min": years[0],
            "fy_max": years[-1],
            "total_spend": float(yearly_amounts.sum()),
            "latest_year_spend": float(yearly_amounts[-1]),
            "temporal_zscore": z,
            "is_step_function": (z is not None and z > 5),
        })

    out = pd.DataFrame(rows).sort_values("total_spend", ascending=False).reset_index(drop=True)
    out_path = ATLAS_DIR / "atlas_incumbency.parquet"
    out.to_parquet(out_path, index=False)
    n_step = int(out["is_step_function"].sum())
    print(f"  wrote {out_path.name}: {len(out):,} (vendor x ministry) histories")
    print(f"  detected {n_step:,} step-function emergence patterns (z>5)")
    return out


# ---- Main ------------------------------------------------------------------

# ---- Step 5: atlas_regions ------------------------------------------------

# Normalize messy province strings (e.g. "Alberta"/"AB", "Ontario"/"ON") to a
# canonical 2-letter code so groupings don't double-count the same place.
_PROVINCE_CANONICAL = {
    "alberta": "AB", "ab": "AB",
    "ontario": "ON", "on": "ON",
    "british columbia": "BC", "bc": "BC",
    "saskatchewan": "SK", "sk": "SK",
    "manitoba": "MB", "mb": "MB",
    "quebec": "QC", "qc": "QC", "quebec ": "QC",
    "new brunswick": "NB", "nb": "NB",
    "nova scotia": "NS", "ns": "NS",
    "prince edward island": "PE", "pe": "PE",
    "newfoundland and labrador": "NL", "nl": "NL",
    "yukon": "YT", "yt": "YT",
    "northwest territories": "NT", "nt": "NT",
    "nunavut": "NU", "nu": "NU",
}


def _norm_province(p):
    if p is None:
        return None
    s = str(p).strip().lower()
    if not s or s in {"na", "n/a", "xx"}:
        return None
    return _PROVINCE_CANONICAL.get(s, s.upper()[:20])


def _norm_city(c):
    if c is None:
        return None
    s = str(c).strip()
    if not s:
        return None
    # "EDMONTON" -> "Edmonton" (title case), "Edmonton," -> "Edmonton"
    s = s.rstrip(",.").strip()
    return s.title()


def build_atlas_regions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per (vendor_province, vendor_city, ministry): concentration metrics.

    Surfaces (a) out-of-province dependency by category, (b) regional vendor
    concentration within Alberta cities, and (c) the in-province / out-of-
    province / unknown buckets at the headline level.
    """
    print("[5/5] Building atlas_regions ...")

    df = con.execute(
        """
        SELECT vendor_province AS raw_province,
               vendor_city AS raw_city,
               ministry, vendor, amount, contract_services
        FROM ab_sole_source
        WHERE amount IS NOT NULL AND amount > 0
          AND vendor IS NOT NULL AND ministry IS NOT NULL
        """
    ).fetchdf()

    df["province"] = df["raw_province"].apply(_norm_province)
    df["city"] = df["raw_city"].apply(_norm_city)
    df["region_bucket"] = df["province"].apply(
        lambda p: "Alberta-based" if p == "AB" else (
            "Unknown" if p is None else "Out-of-province"
        )
    )

    # ---- Tier 1: headline buckets per ministry ----
    headline = (
        df.groupby(["ministry", "region_bucket"])
        .agg(spend=("amount", "sum"), n_contracts=("amount", "count"),
             n_vendors=("vendor", "nunique"))
        .reset_index()
    )

    # ---- Tier 2: top vendors per Alberta city per ministry ----
    ab_only = df[df["province"] == "AB"].copy()
    city_rows = []
    for (city, ministry), grp in ab_only.groupby(["city", "ministry"]):
        if not city or len(grp) < 2:
            continue
        per_v = grp.groupby("vendor")["amount"].sum().sort_values(ascending=False)
        if per_v.iloc[0] < 100_000:
            continue
        total = per_v.sum()
        city_rows.append({
            "province": "AB",
            "city": city,
            "ministry": ministry,
            "total_spend": float(total),
            "n_vendors": int(len(per_v)),
            "top1_vendor": per_v.index[0],
            "top1_amount": float(per_v.iloc[0]),
            "top1_share": float(per_v.iloc[0] / total),
        })
    cities = pd.DataFrame(city_rows).sort_values("total_spend", ascending=False)

    # ---- Tier 3: out-of-province dependency per category ----
    cat_rows = []
    for category, grp in df.groupby("contract_services"):
        if not category or grp["amount"].sum() < 5_000_000:
            continue
        out_of_prov = grp[grp["region_bucket"] == "Out-of-province"]
        if out_of_prov.empty:
            continue
        oop_share = out_of_prov["amount"].sum() / grp["amount"].sum()
        if oop_share < 0.50:  # only flag categories where >50% leaves the province
            continue
        top_oop = (
            out_of_prov.groupby(["vendor", "province"])["amount"]
            .sum().sort_values(ascending=False)
        )
        cat_rows.append({
            "category": category,
            "total_spend": float(grp["amount"].sum()),
            "out_of_province_spend": float(out_of_prov["amount"].sum()),
            "out_of_province_share": float(oop_share),
            "top_out_of_province_vendor": top_oop.index[0][0] if len(top_oop) else None,
            "top_out_of_province_province": top_oop.index[0][1] if len(top_oop) else None,
            "top_out_of_province_amount": float(top_oop.iloc[0]) if len(top_oop) else 0.0,
        })
    oop = pd.DataFrame(cat_rows).sort_values("out_of_province_spend", ascending=False)

    # Persist all three as separate parquets so the Atlas tool can serve each
    headline.to_parquet(ATLAS_DIR / "atlas_regions_headline.parquet", index=False)
    cities.to_parquet(ATLAS_DIR / "atlas_regions_cities.parquet", index=False)
    oop.to_parquet(ATLAS_DIR / "atlas_regions_out_of_province.parquet", index=False)

    print(f"  wrote atlas_regions_headline.parquet:  {len(headline):,} ministry x bucket rows")
    print(f"  wrote atlas_regions_cities.parquet:    {len(cities):,} (city x ministry) concentrations")
    print(f"  wrote atlas_regions_out_of_province.parquet: {len(oop):,} categories where >50% leaves AB")
    print(f"  top 5 out-of-province categories by leaving-AB spend:")
    for _, r in oop.head(5).iterrows():
        print(f"    ${r['out_of_province_spend']:>13,.0f} ({r['out_of_province_share']:.0%}) "
              f"-> {r['top_out_of_province_vendor'][:40]} ({r['top_out_of_province_province']}) "
              f"cat={r['category'][:50]}")
    return headline


def main(force_refresh: bool = False):
    t0 = time.time()
    con = pull_source_tables(force=force_refresh)
    build_atlas_categories(con)
    build_atlas_vendor_dependency(con)
    build_atlas_incumbency(con)
    build_atlas_regions(con)
    print(f"\nAtlas build complete in {time.time()-t0:.1f}s")
    print(f"Outputs in: {ATLAS_DIR}")


if __name__ == "__main__":
    main(force_refresh="--refresh" in sys.argv)
