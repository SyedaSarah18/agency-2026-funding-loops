# Challenge Triage Scorecard — Agency 2026 Hackathon

**Date:**    2026-04-25 (practice run)
**Method:**  one targeted SQL probe per challenge against the organizer's hosted PostgreSQL (~23M rows total).
**Scoring:** Impact / Agent-Autonomy-Fit / Innovation / Demo-Readiness, 1-5 each (max 20). Reverse-engineered from the official 20-pt rubric.

---

## Raw probe results

| #    | Challenge                | Candidates  | $ Exposed       | Sample Named Entities                                            | Probe Time |
| ---- | ------------------------ | ----------: | --------------: | ---------------------------------------------------------------- | ---------: |
| 1    | Zombie Recipients        |       3,161 |         $243.7B | Alberta Health Services, Calgary School District, U of Alberta   |       3.2s |
| 2    | Ghost Capacity           |           0 |              $0 | (none — query too strict)                                        |       0.9s |
| 3    | **Funding Loops**        |   **4,526** |       **$4.34B**| 5+ multi-charity cycles per BN-hub                               |       0.1s |
| 4    | Amendment Creep          |       2,405 |          $11.6B | Toronto Metropolitan University, Salpac Fisheries                |       2.4s |
| 5    | Vendor Concentration     |          12 |          $12.8B | Jobs Economy Ministry, Children & Family Services                |       0.2s |
| 6    | **Director Networks**    |  **16,985** |  n/a (deferred) | Brian Armstrong, Edward Hill, Paul Goodyear                      |      11.3s |
| 7    | Policy Misalignment      |       6,039 |         $482.3B | Shared Health Priorities, Settlement, EV Battery Manufacturers   |       2.1s |
| 8    | Duplicative Funding      |      40,519 |  n/a (deferred) | Salvation Army Canada, YMCA Edmonton                             |       0.3s |
| 9    | Contract Intelligence    |         404 |          $79.6B | Shared Health Priorities, EV Batteries, Rare Diseases Strategy   |       1.2s |
| 10   | Adverse Media            |       6,623 |         $798.4B | Ontario Ministry of Health, Canada Foundation For Innovation     |       1.8s |

---

## Critical observations

**Ch. 1 Zombies — broken proxy.** Top "candidates" (Alberta Health Services, Calgary School District, U of A Financial Services) are obviously NOT zombie orgs. They show up because they're not charities — they don't file T3010s — so my "no CRA filing = inactive" proxy mis-classifies all government/quasi-public entities. Would need real status field or alternative proxy. **Not viable today.**

**Ch. 2 Ghost Capacity — zero results.** Probe used `field_300=0 OR NULL` AND 3+ years AND $100K threshold. Too strict, OR field_300 is non-NULL/zero in unexpected ways. Recoverable by relaxing thresholds, but signal feels weak.

**Ch. 3 Loops — perfect signal, cleanest data.** Pre-built `cra.loops` (5,808 cycles) with `path_bns`, `total_flow`, year ranges. Query runs in 0.1s. The repeated BN `107951618RR0307` appearing as the start AND end of multiple distinct cycles is itself a finding — that hub charity is in many cycles. Demo just needs a BN→legal_name lookup.

**Ch. 4 Amendment Creep — surprise strong.** Despite AB contracts being thin (no amendment data), FED grants_contributions has `is_amendment` + `amendment_number` + `amendment_date`. Real recognizable recipients (universities). $11.6B in over-creep across 2,405 contracts.

**Ch. 6 Director Networks — needs validation work but rich agentic story.** 16,985 multi-board people is a huge candidate set with real names. The validator MUST filter John-Smith collisions — judges will literally see the agent doing disambiguation work. Aligns with the user's architecture example ("Person X on 4 boards, $12M combined").

**Ch. 7 Policy — spend-side only without external augmentation.** $482B across 6,039 federal programs is a massive universe. But without policy commitments to compare against, we can't claim "misalignment" — we'd just be summarizing spending. Augmentation cost too high for 6 hours.

**Ch. 8 Duplicative — 40K candidates is too noisy.** Just being in 2+ datasets isn't suspicious by itself (Salvation Army legitimately receives both fed + AB funding). Needs much tighter "same purpose" definition that NLP could provide but adds complexity.

---

## Scorecard (1-5 per axis, total /20)

| #     | Challenge                | Impact | Agent-Fit | Innovation | Demo  | **Total** | Verdict                                  |
| ----- | ------------------------ | :----: | :-------: | :--------: | :---: | --------: | ---------------------------------------- |
| 1     | Zombies                  |   3    |     2     |     3      |   1   |       9   | proxy broken, too noisy                  |
| 2     | Ghost Capacity           |   2    |     2     |     3      |   1   |       8   | thin signal                              |
| **3** | **Funding Loops**        | **5**  |   **5**   |   **3**    | **5** |  **18**   | **STRONGEST CHOICE**                     |
| 4     | Amendment Creep          |   5    |     4     |     3      |   4   |      16   | strong runner-up                         |
| 5     | Vendor Concentration     |   4    |     3     |     3      |   3   |      13   | abstract narrative                       |
| 6     | Director Networks        |   4    |     5     |     4      |   4   |      17   | very strong, but Ch.3 has cleaner data   |
| 7     | Policy Misalignment      |   4    |     2     |     5      |   2   |      13   | augmentation cost too high               |
| 8     | Duplicative              |   3    |     3     |     3      |   3   |      12   | noisy without NLP                        |
| 9     | Contract Intelligence    |   5    |     3     |     3      |   4   |      15   | mostly aggregation, low autonomy         |
| 10    | Adverse Media            |   4    |     3     |     4      |   3   |      14   | external dependency risk                 |

---

## DECISION: Challenge 3 — Funding Loops

### Why
1. **Cleanest, fastest signal.** 4,526 detected cycles, $4.34B in flow, query returns in 0.1s. Pre-built `cra.loops` table = ~2 hr head start vs. building cycle detection from scratch.
2. **Every agent has real, distinct work** — Discovery scans `loops` ranked by `total_flow`; Investigation pulls each cycle's full charity dossiers + builds NetworkX graphs; Validator rules out legitimate denominational hierarchies + scores severity; Narrative writes the Minister-ready brief.
3. **Maximum visualization power.** Network graphs of money cycling between named charities is the kind of "huh, that's striking" image judges remember. Per the briefing materials, that's the moment they're listening for.
4. **Defensible math.** Cycle detection is deterministic — no LLM-hallucinated relationships. Every claim traces to a specific `cra.cra_qualified_donees` row.
5. **Layerable enrichments.** We can fold in Ch. 6 director-overlap as a *validator signal* ("these 4 cycle-charities also share 3 directors — coordinated, not coincidence") and Ch. 8 cross-dataset funding ("and they collectively received $12M from FED + AB outside the loop") without scope-creeping into a second challenge.

### Sanity check (≥3 named, recognizable entities)
The probe returns BNs as the path keys. Joining `cra.cra_identification` to those BNs will produce real charity legal names, addresses, and designation codes — confirmed by the schema. Will validate this in the first 10 min of Phase 4 (Discovery agent's first call).

### What today's agents will look for
- Top 50 cycles by `total_flow` from `cra.loops`
- For each: pull charities, directors, financial profiles via `general.entity_golden_records.cra_profile`/`fed_profile`/`ab_profile`
- Validate: rule out same-name-prefix hierarchies (denominational), rule out cycles where all parties are <$50K (noise)
- Score: total $ in cycle × cycle tightness (shorter hops = more suspicious) × director overlap × govt-funding receipt
- Narrative top 3-5: "$X moved between Y named charities in FY Z; together they received $W in fed/AB funding; share N directors. Recommended: trigger CRA audit."
