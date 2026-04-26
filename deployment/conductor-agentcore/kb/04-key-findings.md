# Key Findings — what the Atlas surfaced

## Top category monopolies (top1_share = 100%, total >= $10M)

52 categories meet this criteria. The headline-worthy ones:

| Category | Total | Top vendor | Note |
|---|---:|---|---|
| Govt-sponsored benefit administration | **$1.48B** | Alberta Blue Cross | Single contract 2017-2018 disclosure |
| **2025-2030 Microsoft Azure On-Demand Services** | **$60M** | **Microsoft Canada** | 5-year sole-source cloud agreement |
| **Enterprise License Agreement (2024-2030)** | **$55M** | **IBM Canada** | 6-year software lock-in |
| Cross Disability Support Services | $102M | Vecova Centre | Top-1 70%, 17 vendors |
| Student Loan Administration | $143M | DH Corporation | Top-1 80%, 2 vendors |
| **Extension of Mainframe Application Hosting** | **$40M** | **IBM Canada** | Multi-year extension past Jan 2019 |
| Personal Health Records platform | $34M | Telus Health Solutions | Sole-source MHR/MPR system |
| **GoA IMAGIS Services** | **$34M** | **IBM Canada** | PeopleSoft HR/Finance lock-in |
| Merchant card processing | $30M | TD Merchant Services | |
| Water Management Services | $28M | TransAlta Generation Partnership | |

## Top vendor lock-in (lockin_score >= 60)

| Vendor | Ministries | Total | Lockin |
|---|---:|---:|---:|
| Catholic Social Services | 5 | $451M | 77.5 |
| **IBM Canada Limited** | **20** | **$341M** | **72.4** |
| Hull Services | 4 | $243M | 70.6 |
| Wood's Homes | 5 | $210M | 70.4 |
| McMan Youth Family | 3 | $199M | 66.8 |
| Alberta Blue Cross | 1 | $1.48B | (single ministry) |

## The IBM angle (relevant for IBM internal pitch)

IBM Canada appears in the Alberta procurement data with:
- **3 separate 100% sole-source category monopolies** ($129M combined):
  - Enterprise License Agreement 2024-2030: $55M
  - Mainframe Application Hosting Extension: $40M
  - GoA IMAGIS Services: $34M
- **$341M total spend across 20 different ministries** (lockin_score 72.4 — top 1%)
- **Sole-source share 42%** of IBM's total Alberta footprint

This is exactly the kind of vendor strategy challenge IBM Consulting advises
clients on — and the methodology our system builds (composite Concentration
Risk Index + lock-in scoring + step-function emergence detection) is
generalizable to any large enterprise's vendor portfolio.

## The Microsoft Azure 5-year angle

The most demo-ready single finding:
- $60M, 100% sole-source, ONE vendor (Microsoft Canada Inc.)
- 5-year agreement spanning 2025-2030
- Category: "2025-2030 Microsoft Azure On-Demand Services (Enterprise-Wide)"
- Issued by: Technology and Innovation
- No competitive procurement was conducted before signing a 5-year cloud lock-in

## Step-function emergence patterns

65 (vendor x ministry) histories show z > 5 — vendors that suddenly appeared
at scale after a quiet historical baseline. These are the "GC Strategies
pattern" cases for Alberta.

## Data quality findings (bonus)

- **"SUNDRY, OTHER VENDORS BELOW $10,000"** appears as a single "vendor"
  receiving $172M across 61 ministries — clearly a placeholder/aggregation
  row, not a real vendor. Worth flagging to AB Treasury Board as a
  procurement-disclosure data integrity issue.
- IBM Canada appears under 2 different name variants — entity normalization
  is broken in the source disclosure system.
