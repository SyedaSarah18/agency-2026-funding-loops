# Original Practice-Run Plan (2026-04-25)

This is the plan we built before writing any code. It captures the reasoning, the
phasing, and the trade-offs that shaped the v1.0 baseline — preserved verbatim
so future sessions understand *why* the codebase looks the way it does (not just
what it contains).

Where reality diverged from the plan, see the "Plan-vs-actual" section at the bottom.

---

# Agency 2026 Hackathon — Practice Run Plan

## Context

You are participating in the **Agency 2026 National AI Hackathon** in Alberta on April 29, 2026 (4 days from today). The event runs 6 hours, judged by Minister Nate Glubish (Alberta Tech & Innovation), Deputy Minister Janak Alford, federal/provincial officials, and sponsor reps from AWS, Google, Microsoft, Cohere.

**The mission:** use Agentic AI to find waste, fraud, inefficiency, or accountability gaps in real Canadian government spending data (CRA charity filings + federal grants/contributions + Alberta open data, ~23M rows pre-loaded into PostgreSQL).

**Why this practice session:** today (2026-04-25) is a dry run. Goals:
1. Stand up the actual stack you'll use on event day so there are zero surprises.
2. Use real data to *empirically* pick which of the 10 challenges has the strongest signal for our agent architecture (vs. guessing).
3. Build a working v0.1 of the 4-agent pipeline so event day is iteration, not green-field building.

**Scoring rubric (20 pts total) — every architecture decision is reverse-engineered from this:**
- Impact & Significance (1-5): real waste/fraud at meaningful scale, with $ amounts and named entities
- Agent Autonomy (1-5): agent independently discovers + validates without manual hand-holding
- Innovation & Originality (1-5): creative AI use for public-sector accountability
- Presentation & Clarity (1-5): non-technical decision-maker can act on it

**Our north star:** A four-agent pipeline (Discovery → Investigation/Graph → Cross-ref/Validator/Risk → Narrative) that autonomously surfaces a small number of high-confidence, dollar-quantified, named-entity findings, presented through a polished Next.js dashboard a Minister could read in 60 seconds.

---

## Strategy

### Architecture: 4-Agent Pipeline

| Agent | Role | Inputs | Tools | Outputs |
|---|---|---|---|---|
| **1. Discovery** | Scans datasets for candidate signals matching the chosen challenge | Schema, challenge spec | SQL query tool, schema introspection | Ranked candidate list (entity IDs + preliminary scores) |
| **2. Investigation / Graph Builder** | Pulls full context per candidate; builds graph structures (loops, director networks, contract lineage) | Candidate list | SQL tool, NetworkX, entity-resolution lookup | Enriched candidate dossiers + graph artifacts (JSON/edges) |
| **3. Cross-Referencer / Validator / Risk Scorer** | Verifies findings against other datasets, rules out legitimate explanations, scores severity on judge-relevant axes ($ magnitude, breadth, recency, named-entity prominence) | Dossiers | SQL tool, golden-records lookup, optional adverse-media web search | Validated, ranked findings with risk scores 0-100 |
| **4. Narrative** | Writes plain-English 1-paragraph briefs for the top findings, suitable for a Minister | Validated findings | LLM | Human-readable briefs + structured JSON for the dashboard |

**Why 4 agents (not 1 monolithic agent):** judges score "agent autonomy" — distinct agents with distinct tools, handing off structured artifacts, demonstrate genuine multi-agent orchestration. Each agent should be inspectable in the demo (show its trace).

### Tech stack

- **Frontend:** Next.js (App Router) + Tailwind. Single dashboard page showing: agent trace timeline, top findings cards, network/graph visualization, and per-finding "Minister Brief" panels.
- **Orchestration:** Next.js API routes (`/api/investigate`) coordinate the run, stream agent updates to the UI via SSE.
- **Agent service:** Single Python FastAPI microservice (`agent-service/main.py`) that runs the 4 Strands agents and the NetworkX graph computation. Next.js calls it over HTTP.
- **LLM:** Claude Sonnet 4.6 via AWS Bedrock (`us-west-2`). Strands code is identical against Anthropic API for offline dev.
- **Agent SDK:** Strands Agents (open-source Python) — backend-agnostic.
- **DB:** organizer's hosted PostgreSQL via psycopg2. Read-only.

---

## Execution plan

### Phase 1: Data triage — picks the challenge

**Objective:** produce `analysis/scorecard.md` with empirical evidence for each of the 10 challenges, then pick the winner.

#### Phase 1a — Connect & inventory
- Create the project folder + Python venv. Install psycopg2-binary, pandas, python-dotenv.
- `analysis/schema_inventory.py`: connect read-only, dump all schemas/tables/columns/row-counts to `analysis/schema.json`. Verify ~23M total rows.

#### Phase 1b — Per-dataset profiling
- `analysis/profile.py`: date coverage, $ volume by year, NULL rates on key columns, distinct entity counts, % covered by `general.entity_golden_records`, top 20 recipients by $.
- Cross-reference KNOWN-DATA-ISSUES.md to tag landmines (FED-3 cumulative agreement_value overstates by 73%, AB-13 5,557 duplicate rows, etc.).

#### Phase 1c — Signal probes for all 10 challenges

`analysis/triage.py` — one targeted probe per challenge:

- **Ch. 1 Zombies:** orgs with FED+AB ≥ $500K then no recent CRA filing.
- **Ch. 2 Ghost Capacity:** charities with 0 employees 3+ yrs AND govt funding.
- **Ch. 3 Funding Loops:** `cra.loop_universe` / `cra.loops` distribution + bucket by score.
- **Ch. 4 Amendment Creep:** distribution of `(final - initial)/initial` on contract amendments.
- **Ch. 5 Vendor Concentration:** Herfindahl index per spend category.
- **Ch. 6 Director Networks:** directors on ≥4 distinct boards via `cra_directors`.
- **Ch. 7 Policy Misalignment:** spend-side only — top fed programs since 2020.
- **Ch. 8 Duplicative Funding:** same recipient, multiple datasets, similar program text.
- **Ch. 9 Contract Intelligence:** YoY growth in spend categories.
- **Ch. 10 Adverse Media:** top funded entities by $ — universe for news matching.

Output `analysis/scorecard.md` with ranked challenges (Impact / Agent-Fit / Innovation / Demo, /20).

#### Phase 1d — Pick the challenge
Top pick must have ≥3 named recognizable entities (a Minister demo needs faces, not row IDs).

### Phase 2: Stack scaffold — parallel to Phase 1

- `frontend/`: `npx create-next-app@latest frontend --typescript --tailwind --app --no-eslint`.
- `agent-service/`: pyproject with fastapi, uvicorn, psycopg2-binary, strands-agents, boto3, networkx, sse-starlette.
- `agent-service/main.py`: stub `/investigate` POST that streams 3 fake agent events.
- `frontend/app/api/investigate/route.ts`: proxies to FastAPI, forwards SSE.
- `frontend/app/page.tsx`: minimal UI with `<AgentTrace>` showing the streamed events.

End state: hit "Run Investigation", watch fake events stream. Plumbing proven.

### Phase 3: LLM access

- Create AWS account. Bedrock → Model access → request Claude Sonnet 4.6 in us-west-2.
- IAM user with `AmazonBedrockFullAccess`. Drop access keys into `.env`.
- Verify with `scripts/bedrock_ping.py` (10-token call).
- Strands `BedrockModel(model_id="us.anthropic.claude-sonnet-4-6", region_name="us-west-2", streaming=True)`.

### Phase 4: Build the 4-agent pipeline against chosen challenge

- **Discovery agent**: Strands agent + read-only SQL tool. Returns top-N candidates as JSON with preliminary score + rationale per candidate.
- **Investigation agent**: per candidate — pulls full dossier (charities, edges, directors, cross-fund) via SQL + NetworkX graph metrics.
- **Validator/Risk agent**: rules out legitimate explanations (denominational hierarchies, parent-subsidiary, trivial $). Scores 0-100 on $ magnitude / cycle tightness / director overlap / govt funding / independence.
- **Narrative agent**: quantitative-first Minister Brief. Hard constraint: every numeric claim traceable to a dossier field. Structured JSON output (`{lead_number, lead_unit, entities[], mechanism, recommendation, evidence_refs}`).

Each agent emits SSE events on every step — judges literally see the agents thinking.

### Phase 5: Demo polish

- `docs/pitch.md`: 3-minute script (problem 30s → live demo 90s → finding deep-dive 45s → close 15s).
- Single button → full pipeline → results in <60s.
- Cache last successful run to local JSON for demo fallback.

---

## Verification

End-to-end test:
1. Start agent service + frontend.
2. Open `http://localhost:3000`, click "Run Investigation".
3. Confirm: agent trace streams in real time; 4 distinct phases; findings render with named entities + dollar amounts; Minister Brief reads cleanly.
4. Confirm `analysis/scorecard.md` has all 10 challenges scored.
5. Read `docs/pitch.md` aloud against live demo — does it flow in 3 minutes?

Priority order if anything fails: (1) demo runs end-to-end, (2) findings real and grounded, (3) UI is pretty.

---

## What success looked like at end of today (v0.1 — plumbing perfect, content rough)

**Non-negotiable:**
- `analysis/scorecard.md` populated for all 10 challenges, challenge chosen with evidence.
- Both services running locally; SSE working end-to-end without dropouts.
- "Run Investigation" → 4 agents execute → top findings render. No mid-run crashes.
- Every dollar/count/date is SQL-verifiable. Zero hallucinated numbers.
- Last-good run cached to local JSON as demo fallback.
- 3-minute pitch script drafted.

**Acceptable to be rough:**
- Discovery agent's SQL templates may need iteration to filter noise.
- Validator's rule-out logic will miss edge cases.
- Risk-score weights uncalibrated.
- Narrative agent occasionally picks suboptimal lead numbers.
- UI is functional Tailwind, not designed.

**Why this trade-off:** today's job was to surface the painful surprises early so event day is iteration on a known-working system, not greenfield under a 6-hour clock.

---

## Plan-vs-actual (what changed during execution)

- **LLM provider:** plan started with Anthropic Console (free credit), then user decided to set up Bedrock today instead. Result: Bedrock + Sonnet 4.6 in us-west-2 from the start. Same Strands code path, just `LLM_BACKEND=bedrock`.
- **Model ID:** initial guess `us.anthropic.claude-sonnet-4-6-20260101-v1:0` was wrong. Real ID is just `us.anthropic.claude-sonnet-4-6` (no date suffix). Discovered via `bedrock.list_inference_profiles()`.
- **Strands agents are stateful.** Plan didn't anticipate this. The pipeline orchestrator (`agents/pipeline.py`) instantiates a fresh agent per loop iteration via `make_*_agent()`. Hoisting it out of the loop crashes with "Agent is already processing a request".
- **Discovery cross-entity filter is critical.** Plan assumed top-flow cycles would be interesting. Reality: top 600+ cycles are Salvation Army intra-entity flows (same BN root). Discovery prompt now requires `(SELECT COUNT(DISTINCT substring(bn FROM 1 FOR 9)) FROM unnest(path_bns)) >= 2` to skip them.
- **Frontend folder structure:** plan put `components/` at `frontend/components/`. Actual layout is `frontend/app/components/` (kept inside the App Router tree).
- **Some folders/files in the plan don't exist yet:**
  - `tools/entity_lookup.py` — not built; the JSONB profiles in `general.entity_golden_records` cover the use case from inside `query_db`.
  - `frontend/app/dashboard/page.tsx`, `frontend/app/api/findings/route.ts` — the single landing page (`app/page.tsx` + `AgentTrace.tsx`) does both jobs.
  - `frontend/components/NetworkGraph.tsx` + `react-force-graph` — deferred; v1.0 has no graph viz yet, just the briefs panel.
  - `docs/architecture-diagram.md` — not written.
- **AWS provisioning form** (event-day track) is still TBD. Plan called for submission by 2026-04-27.
