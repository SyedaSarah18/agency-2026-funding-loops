# The Challenge — verbatim from Agency 2026 organizers

**Vendor concentration:** In any given category of government spending, how
many vendors are actually competing? Identify areas where a single supplier
or a small group of suppliers receives a disproportionate share of contracts.
Measure concentration by category, department, and region. Where has incumbency
replaced competition? Where has government become dependent on a vendor it
can no longer walk away from?

## How our system addresses each part of the challenge

| Challenge phrase                                          | Our handling                                                                          |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| "category of government spending"                         | Use `contract_services` text from `ab.ab_sole_source` as the natural category label    |
| "how many vendors are actually competing"                  | Pre-computed `n_vendors` per (ministry x category) in `atlas_categories.parquet`       |
| "single supplier ... disproportionate share"              | `top1_share`, `top3_share`, `herfindahl` index per category                             |
| "by category, department, and region"                     | Atlas grouped by ministry x category; vendor_province available in `ab_sole_source`    |
| "incumbency replaced competition"                         | `atlas_incumbency.parquet` tracks year-over-year vendor dominance per (ministry x vendor) |
| "vendor it can no longer walk away from"                   | `atlas_vendor_dependency.parquet` — `lockin_score` combining cross-ministry breadth + sole-source share + total spend + category breadth |

## Scope honesty

We use Alberta procurement data (`ab.ab_sole_source` + `ab.ab_contracts`)
because the federal grants table (`fed.grants_contributions`) is grants/
contributions, not procurement contracts. The federal procurement scandals
that come to mind (ArriveCAN, McKinsey contracts) live in a separate
dataset (PSPC contracts disclosure on open.canada.ca) which we did NOT
ingest for v3.0. If a judge asks about federal procurement, we say so
honestly and explain the data-source limitation.
