# Methodology — How Concentration Metrics Are Computed

## HHI — Herfindahl-Hirschman Index

**Formula:** HHI = Σ (sᵢ)²
where sᵢ is vendor i's share of total category spend as a percentage (0–100).

**Range:** 0 – 10,000

**DOJ/FTC thresholds (the legal standard):**
- Below 1,500 → Competitive market
- 1,500 – 2,500 → Moderately concentrated
- Above 2,500 → Highly concentrated
- 10,000 → Perfect monopoly (single vendor)

**How we compute it:** For a given dataset + category, we pull all vendor
amounts from Postgres, compute each vendor's percentage share of total
category spend, square each share, and sum. A category with one vendor
always returns HHI = 10,000.

**Reference:** U.S. Department of Justice / FTC Horizontal Merger Guidelines.

---

## CR_n — Concentration Ratio (top-n combined share)

**Formula:** CR_n = Σ sᵢ for the top n vendors by spend (i = 1 … n)
where sᵢ is each vendor's share of total category spend (%).

**Common variants:**
- CR_1 = single largest vendor's share (%)
- CR_4 = top-4 vendors' combined share (standard industrial-org metric)

**Range:** 0 – 100 (a percentage)

**How we compute it:** Sort vendors by descending spend, take the top n,
sum their amounts, divide by total category spend × 100.

---

## Gini Coefficient

**Formula (sorted-array form):**
G = (2 · Σ(i · xᵢ)) / (n · Σxᵢ) − (n + 1) / n

where xᵢ are vendor amounts sorted **ascending** and i is 1-indexed.

**Range:** 0 – 1
- 0 = perfect equality (every vendor wins the same dollar amount)
- 1 = one vendor takes everything

**Thresholds (informal):**
- Below 0.3 → relatively equal distribution
- 0.3 – 0.6 → moderate inequality
- Above 0.6 → highly unequal (one or few vendors dominate)

**Reference:** Statistics Canada Gini methodology for income inequality.

---

## Sole-Source Rate

**Formula:** sole_source_rate = ab_sole_source_$ / (ab_sole_source_$ + ab_contracts_$) × 100

Computed per ministry and optional fiscal year. Answers: "what share of
this ministry's total procurement was awarded without competitive bid?"

**Range:** 0 – 100 (a percentage)

---

## Incumbency Streak

**Definition:** Longest run of consecutive fiscal years in which a given
vendor held at least one contract in a given category.

**How we compute it:** For a vendor × category pair, pull distinct
`display_fiscal_year` values from `ab_sole_source`, sort chronologically,
find the longest unbroken sequence of consecutive years.

**Interpretation:**
- 1–2 years → short tenure
- 3–5 years → established incumbent
- 6+ years → entrenched; switching costs likely high

---

## Vendor Footprint

Counts the distinct ministries, categories, and total dollar value a vendor
has accumulated across the `ab_sole_source` dataset. Answers: "how dependent
is the government on this vendor across different areas?"

Fields returned: `contract_count`, `total_amount`, `ministry_count`,
`category_count`, `first_year`, `last_year`, `ministries` (list).

---

## Data caveats

| Dataset | Known caveats |
| ------- | ------------- |
| `ab_sole_source` | Every row is sole-source by definition — `vendor_count = 1` is structural, not a finding. Look at dollar magnitude and incumbency streak instead. |
| `ab_contracts` | No category column — only ministry. Competition analysis is ministry-level, not service-level. |
| `fed_contracts` | `contract_value` stored as TEXT — non-numeric strings are cast to NULL and excluded. Contracts below $10K may not appear (Proactive Disclosure threshold). |
| `fed_grants` | Not included in the default concentration pipeline (Challenge 1/2/3 territory). |
