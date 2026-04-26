"""View any of the Atlas parquet files from the command line.

Defaults to atlas_vendor_dependency.parquet (the cross-ministry vendor
lock-in table). Use --table to pick a different one.

Examples:
  # default — top 20 vendors by lockin_score
  python analysis/view_atlas.py

  # other Atlas tables
  python analysis/view_atlas.py --table categories
  python analysis/view_atlas.py --table incumbency
  python analysis/view_atlas.py --table regions_oop

  # change sort + row count
  python analysis/view_atlas.py --sort total_spend --top 50

  # filter by substring (case-insensitive) on the vendor / category / ministry column
  python analysis/view_atlas.py --filter ibm
  python analysis/view_atlas.py --table categories --filter "Microsoft"

  # dump the schema + summary stats only (no rows)
  python analysis/view_atlas.py --schema-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ATLAS_DIR = ROOT / "analysis" / "atlas_data"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Friendly name -> filename + which column to filter on by default.
TABLES = {
    "vendors":       ("atlas_vendor_dependency.parquet",          "vendor"),
    "categories":    ("atlas_categories.parquet",                 "category"),
    "incumbency":    ("atlas_incumbency.parquet",                 "vendor"),
    "regions_head":  ("atlas_regions_headline.parquet",           "ministry"),
    "regions_cities":("atlas_regions_cities.parquet",             "city"),
    "regions_oop":   ("atlas_regions_out_of_province.parquet",    "category"),
}


def fmt_money(v):
    if pd.isna(v) or not isinstance(v, (int, float)):
        return v
    if abs(v) >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--table", choices=list(TABLES.keys()), default="vendors",
                   help="Which Atlas table to view (default: vendors)")
    p.add_argument("--sort", default=None,
                   help="Column to sort by descending (default depends on table)")
    p.add_argument("--top", type=int, default=20,
                   help="Number of rows to show (default 20). Use 0 for all.")
    p.add_argument("--filter", default=None,
                   help="Case-insensitive substring filter on the table's primary text column")
    p.add_argument("--schema-only", action="store_true",
                   help="Print column types + describe() summary, no rows")
    p.add_argument("--columns", default=None,
                   help="Comma-separated list of columns to show (default: all)")
    args = p.parse_args()

    fname, default_filter_col = TABLES[args.table]
    path = ATLAS_DIR / fname
    if not path.exists():
        print(f"ERROR: {path} not found. Run `python analysis/atlas/build.py` first.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(path)
    print(f"\n  {fname}  —  {len(df):,} rows × {len(df.columns)} columns")
    print(f"  source: {path}\n")

    print("  Columns:")
    for c in df.columns:
        dtype = str(df[c].dtype)
        sample = df[c].dropna().iloc[0] if not df[c].dropna().empty else None
        sample_str = f"  e.g. {str(sample)[:60]!r}" if sample is not None else ""
        print(f"    {c:<40s} {dtype:<12s}{sample_str}")
    print()

    if args.schema_only:
        print("  Numeric column summary:")
        num_cols = df.select_dtypes(include="number").columns
        if len(num_cols):
            print(df[num_cols].describe(percentiles=[0.5, 0.9, 0.95, 0.99]).to_string())
        return

    # Apply filter
    if args.filter:
        col = default_filter_col
        if col not in df.columns:
            # find first text column
            for c in df.columns:
                if df[c].dtype == "object":
                    col = c; break
        before = len(df)
        df = df[df[col].astype(str).str.contains(args.filter, case=False, na=False)]
        print(f"  filter: {col} contains {args.filter!r} → {len(df):,} of {before:,} rows match\n")

    # Pick sort column
    sort_col = args.sort
    if not sort_col:
        # sensible defaults per table
        if "lockin_score" in df.columns: sort_col = "lockin_score"
        elif "headline_risk_score" in df.columns: sort_col = "headline_risk_score"
        elif "total_spend" in df.columns: sort_col = "total_spend"
        elif "out_of_province_spend" in df.columns: sort_col = "out_of_province_spend"
        elif "spend" in df.columns: sort_col = "spend"
        elif df.select_dtypes(include="number").columns.size:
            sort_col = df.select_dtypes(include="number").columns[0]
    if sort_col and sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False)
        print(f"  sorted by: {sort_col} desc\n")

    # Pick columns to show
    if args.columns:
        cols = [c.strip() for c in args.columns.split(",") if c.strip() in df.columns]
        df = df[cols]

    # Format money columns for display
    money_cols = [c for c in df.columns if any(k in c.lower() for k in
        ("spend", "amount", "total", "value", "fed_total"))]
    show = df.copy()
    for mc in money_cols:
        if mc in show.columns and pd.api.types.is_numeric_dtype(show[mc]):
            show[mc] = show[mc].apply(fmt_money)

    n = args.top if args.top > 0 else len(show)
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 200,
        "display.max_colwidth", 60,
        "display.colheader_justify", "left",
    ):
        print(show.head(n).to_string(index=False))
    print()
    print(f"  showing {min(n, len(show)):,} of {len(show):,} rows after filter")


if __name__ == "__main__":
    main()
