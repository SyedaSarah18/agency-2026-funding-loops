# The Data — what we ingested and what each field means

## Source tables (organizer-hosted PostgreSQL)

### `ab.ab_sole_source` — 15,533 rows, $18.2B in non-competitive Alberta procurement

Sole-source means contracts where the government waived competitive bidding.
This is THE table for vendor-concentration analysis — by definition no
competition was permitted.

Key columns:
- `ministry` — issuing department
- `vendor` — recipient legal name
- `vendor_city`, `vendor_province` — vendor location (note: province strings inconsistent: "Alberta", "AB", "Ontario", "ON" all appear separately)
- `start_date`, `end_date` — contract term
- `amount` — dollar value
- `contract_services` — text describing what the contract is for (our category dimension)
- `permitted_situations` — single-letter code (a-l, z) for the legal justification under Alberta Procurement Accountability rules. Most common: 'd' ($12.7B across 7,825 contracts), 'b' ($3.6B), 'g' ($1.2B)
- `display_fiscal_year` — e.g. "2023 - 2024"

### `ab.ab_contracts` — 67,079 rows, complementary procurement disclosure

Thin schema: only id, display_fiscal_year, recipient, amount, ministry. No
service category, no region. We use it for vendor totals across ministries
in `atlas_vendor_dependency`, not for category concentration.

### `ab.ab_grants` — 2.0M rows, Alberta grant programs

Not used for v3.0 — grants are not procurement.

### `fed.grants_contributions` — 1.28M rows, federal grants/contributions

Briefly considered for v2.0 but deemed wrong table for the challenge.
Federal procurement scandals (ArriveCAN, McKinsey) are in a separate
dataset we didn't ingest.

## Atlas tables we pre-compute (`analysis/atlas_data/atlas_*.parquet`)

### `atlas_categories.parquet` — 2,219 (ministry x category) rows

What it answers: "Which service categories are concentrated, in which ministries?"

Columns: ministry, category, total_spend, n_vendors, top1_vendor, top1_amount,
top1_share, top3_share, herfindahl, gini, top1_vendor_cross_ministry_count,
composite_risk_score, headline_risk_score.

`headline_risk_score` zeroes out categories under $10M so research grants
don't outrank Microsoft cloud lock-in in the Watchlist.

### `atlas_vendor_dependency.parquet` — 2,920 vendors with >=$1M total

What it answers: "Which vendors has the government become dependent on?"

Columns: vendor, n_ministries, n_categories, total_spend, n_contracts,
sole_source_spend, sole_source_count, sole_source_share, lockin_score.

`lockin_score` combines cross-ministry breadth (1.5 pts per ministry, capped
at 30) + total spend (sqrt-scaled, capped at 30) + sole_source_share*20 +
n_categories*0.8 (capped at 20). Max possible 100.

### `atlas_incumbency.parquet` — 530 (vendor x ministry) yearly histories

What it answers: "Did this vendor appear suddenly? Has the same vendor won
year after year?"

Columns: ministry, vendor, years_active, fy_min, fy_max, total_spend,
latest_year_spend, temporal_zscore, is_step_function (z>5).

## Documented data quality issues

- **Province strings inconsistent**: "Alberta" / "AB" / "Ontario" / "ON" / "NA" / "XX"
- **IBM has 2 name variants**: "IBM CANADA LIMITED/IBM CANADA LIMITEE" and "IBM CANADA LIMITEDIBM CANADA LIMITEE" — same entity, broken normalization
- **`SUNDRY, OTHER VENDORS BELOW $10,000`** placeholder vendor aggregating $172M across 61 ministries
- **`permitted_situations` are single-letter codes** without a lookup table in our data
- **F-3 (federal data, unused)**: amendment double-counting inflates `agreement_value` totals by ~73%
- **F-6 (federal data, unused)**: `recipient_business_number` is NULL ~55% of the time
