# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Practice-run codebase for the Agency 2026 hackathon (Government of Alberta, April 29 2026). A 4-agent Strands pipeline that surfaces suspicious circular funding patterns in Canadian charity data (~23M rows in the organizer's hosted PostgreSQL). Goal: dollar-quantified, named-entity findings a Minister could read in 60 seconds.

Branches:
- `main` — stable
- `v1.0` — frozen practice baseline (don't move)
- `v1.1-dev` — proven funding-loops version (the hard fallback)
- `v2.0-vendor-concentration` — frozen attempt at agent-first vendor-concentration on `fed.grants_contributions`. Pivoted away from because that table is grants/contributions not procurement; live runs produced 0 briefs. Kept as audit trail.
- **`v3.0-atlas` — ACTIVE WORK.** Data-first vendor-concentration on `ab.ab_sole_source` (where the real procurement signal lives). New architecture detailed below.

**Read these before changing the architecture:**
- [docs/original-plan.md](docs/original-plan.md) — original Funding Loops plan + plan-vs-actual
- [analysis/scorecard.md](analysis/scorecard.md) — empirical scorecard, including the deep Phase 6d re-probe of Ch.5 that revealed the right table is `ab.ab_sole_source` not `fed.grants_contributions`

## v3.0 Atlas architecture (active plan)

**Why we pivoted:** v1.1 worked end-to-end on Funding Loops but the user wanted to maximise scoring on Ch.5 Vendor Concentration (5/5 Impact + 5/5 Innovation, IBM-relevant). Honest data probing showed `fed.grants_contributions` is grants/contributions (recipients are universities, NPOs, treaty obligations) — the procurement scandals (ArriveCAN, McKinsey, sole-source IT) live in a different dataset. **`ab.ab_sole_source` (15,533 rows, $18.2B in Alberta sole-source procurement) is where Ch.5's signal actually is.**

**The 5-layer architecture (data-first, agents-second):**

1. **Data layer** (Python + DuckDB + pandas, no LLM) — pre-computes the **Procurement Concentration Atlas**: tables of category-level concentration metrics (Herfindahl, top-1 share, top-3 share), cross-ministry vendor dependency, time-series incumbency, statistical baselines. Output: `atlas_*.parquet` files.
2. **Eval layer** (deterministic pytest harness, NOT the Validator agent) — known-cases test suite asserts the system flags real Canadian procurement issues at risk ≥ 60. Runs only when agent code changes; catches regressions; provides defensibility ("how do you know your method works?").
3. **Pipeline agents** (Mode 1 — structured discovery) — Discovery → Investigation → Validator → Narrative, each reading from the Atlas (NOT running analytical SQL). Produces ranked Minister briefs on click.
4. **Conductor agent** (Mode 2 — adaptive reasoning chat) — single Strands agent with `query_atlas` / `query_db` / `verify_*` / `read_kb` / `compute` / `code_compute` (constrained pandas) tools. Receives any natural-language question, picks tools per question, streams reasoning + tool calls + final answer. The autonomy story.
5. **Visualization layer** — ConcentrationHeatmap (ministry × category), VendorFootprint sunburst, Watchlist cards, Conductor chat panel.

**The two operating modes are the autonomy story.** Pipeline = systematic discovery without prompting. Chat = adaptive reasoning to any judge question. Both share the Atlas + verify_* tools but use different agent architectures.

**Critical disciplines for v3.0:**
- **Agents never run analytical SQL.** They read pre-computed Atlas tables. The data layer owns the math; the agent layer owns synthesis + narrative + Q&A.
- **All thresholds derived from data percentiles.** No magic numbers. "Top-1 share ≥ 0.80" is justified as "99th percentile of the actual distribution" — defensible against "how do you know this isn't noise?"
- **Validator (LLM, runtime) and eval suite (deterministic, dev-time) are different things.** Don't merge.
- **Conductor's `code_compute` tool is constrained** — pandas method-chain expressions on safelisted DataFrames only. NOT full Python. Full Bedrock CodeInterpreter is a v3.1 stretch.

**Top monopoly findings the data already surfaced (the demo material):**
- 2025-2030 Microsoft Azure: $60M, 100% sole-source, 1 vendor
- IBM Canada: 3 separate 100% sole-source enterprise monopolies ($129M combined: software licensing, mainframe hosting, IMAGIS)
- Alberta Blue Cross: $1.48B benefit administration, 100%, 1 vendor
- Telus Health, TD Merchant Services, TransAlta, Enmax — each 100% sole-source in their category

**Phase plan:** A (data layer, 3hr) → B (rewire agents to Atlas, 2hr) → C (viz, 1.5hr) → D (Conductor + chat, 2hr) → E (pitch + cache + CLAUDE.md update, 1hr). Total ~9.5 hr.

## Commands

**Two-process dev loop.** Both must be running for the dashboard to work:

```bash
# Agent service (FastAPI on :8000) — run from the agent-service dir so `from config import ...` works
cd agent-service && ../.venv/Scripts/python main.py

# Frontend (Next.js 16 on :3000) — different terminal
cd frontend && npm run dev
```

**Smoke-test the pipeline without the UI:**
```bash
# Fake events (no LLM, no AWS) — confirms SSE plumbing
curl -sN -X POST 'http://127.0.0.1:8000/investigate?mode=fake'

# Real run — burns Bedrock tokens; configurable via DISCOVERY_TOP_N + NARRATIVE_TOP_N in .env
curl -sN -X POST 'http://127.0.0.1:8000/investigate?mode=real'
```

**Verify Bedrock + model access** (run after any AWS credential change):
```bash
.venv/Scripts/python scripts/bedrock_ping.py
```

**Re-run data triage against the live DB** (regenerates `analysis/scorecard.md` evidence):
```bash
.venv/Scripts/python analysis/triage.py
```

**Restart the agent service cleanly** when uvicorn reload drifts (it reliably stales after multi-step edits):
```bash
powershell -NoProfile -Command "Get-WmiObject Win32_Process -Filter \"name like 'python%'\" | Where-Object { \$_.CommandLine -like '*main.py*' -or \$_.CommandLine -like '*spawn_main*' } | ForEach-Object { taskkill /F /T /PID \$_.ProcessId 2>&1 | Out-Null }"
# then restart in agent-service/
```

## Architecture (the parts that span multiple files)

### Pipeline data flow

```
Discovery → [candidates JSON] → Investigation × N → [dossiers] → Validator × N → [findings] → Narrative × top → [briefs]
```

Orchestrated in `agent-service/agents/orchestrator.py` (the `run_pipeline()` async generator). Each handoff goes through `_extract_json()` because Strands agents return free-form text containing a JSON value. Findings whose `verdict == "likely_legitimate"` are dropped before Narrative.

### Strands agents are stateful — instantiate fresh per task

Reusing a `strands.Agent` across loop iterations raises `Agent is already processing a request. Concurrent invocations are not supported.` The pipeline calls `make_investigation_agent()` / `make_validator_agent()` / `make_narrative_agent()` *inside* the per-candidate loop, not once outside. Don't refactor that into a hoisted constant.

### LLM backend swap is one config flag

`agent-service/llm/client.py` reads `LLM_BACKEND` from `.env` (`bedrock` | `anthropic`). Agent code never imports the underlying SDK — it gets a Strands `Model` object. Switching for event-day Bedrock parity vs. local Anthropic dev is a single env var change, no agent edits.

### SSE event shape is the integration contract

Pipeline yields `{ts, agent, kind, message, payload}` dicts. `agent` is one of `discovery|investigation|validator|narrative|pipeline`. `kind` is one of `start|step|tool|complete|done|error`. `frontend/app/components/AgentTrace.tsx` types this as `AgentEvent` and color-codes by agent. The final `pipeline:done` event carries `payload.briefs` — that's how the Minister Briefs panel populates. Don't break this shape without updating both ends.

### Discovery agent must filter cross-entity cycles

`cra.loops` includes ~600 same-org sub-registration cycles (Salvation Army has 600+ chapters under BN root `107951618`). Money flowing between them is internal accounting, not fraud. Discovery's prompt requires the SQL filter `(SELECT COUNT(DISTINCT substring(bn FROM 1 FOR 9)) FROM unnest(path_bns) AS bn) >= 2`. Without it, the Validator correctly throws every candidate out as `likely_legitimate` and Narrative produces zero briefs.

### Narrative has a hard no-hallucinated-numbers constraint

`agents/narrative.py` prompt explicitly forbids any number not in the input dossier. `lead_sentence` MUST start with a number. Output is structured JSON (`lead_number`, `evidence_refs`, etc.) so `MinisterBrief` rendering can map back to source rows. Treat this constraint as load-bearing — judges will verify.

### SQL tool is read-only by design

`agent-service/tools/sql.py` opens connections with `set_session(readonly=True)` AND has a deny-list for write keywords. Returns max 200 rows per call as JSON. Statement timeout 60s. The tool's docstring is the schema cheat-sheet the LLM uses — keep it accurate when adding new tables.

### Validator has dedicated verify_* tools, not just SQL

`agent-service/tools/verify.py` exposes four `@tool` functions (`verify_gift`, `verify_director`, `verify_charity_revenue`, `verify_external_funding`) that the Validator agent uses to spot-check Investigation's numerical claims. They exist because spot-checking with raw SQL produced inconsistent verification rigor across runs — these standardise the pass/fail shape (`{verified, claimed, actual, delta_pct, ...}`) and constrain the Validator's prompt to do at most 5 verifications per dossier.

Caveats:
- `verify_charity_revenue` prefers T3010 `field_4700` (total revenue) and falls back to `field_4500` (tax-receipted gifts) — this distinction matters because v1.0 saw the agent confidently report `field_4500` as "revenue" and inflate a multiple by 3×.
- `verify_external_funding` for `source='fed'` tries BN match first, then falls back to legal-name match (because KNOWN-DATA-ISSUE F-6 leaves ~55% of fed rows with NULL `recipient_business_number`).
- Tolerance defaults: 5% for gifts/revenue (clean tables), 10% for external funding (FED-3 amendment double-counting).

## Improving agents — discipline for future sessions

Agents don't train the way ML models do. There's no gradient descent, no labelled training set. Improvement is a *deliberate iteration loop* on prompts, tool schemas, and output validators — and depth/accuracy here is the single biggest scoring factor for hackathon judges. Follow this loop strictly when changing agent behaviour:

1. **Reproduce the failure on a known input.** Use the cached run in `data/last_good_run.jsonl` (or kick off a fresh one with `DISCOVERY_TOP_N=3` for speed) so you have a baseline to compare against.
2. **Diagnose root cause from the trace, not the output.** Look at which tool call returned wrong data, which prompt instruction was ambiguous, which evidence the agent missed. The brief is the symptom; the orchestrator's SSE log is the diagnostic.
3. **Fix at the lowest layer that resolves it.** Order of preference:
   - New `verify_*` tool to enforce a fact-check (cheapest, most auditable)
   - Tool docstring / type-hint improvement (Strands feeds these to the LLM)
   - System-prompt rule with explicit "MUST" / "downgrade to medium if X"
   - Few-shot example in the prompt
   - Different model (e.g. Sonnet → Opus) for the failing agent only
   - Last resort: hand-coded post-processing in `orchestrator.py`
4. **Re-run end-to-end and confirm the failure is gone.** Don't trust isolated tests — the agents interact.
5. **Verify you haven't regressed prior wins.** Compare the new brief against `data/last_good_run.jsonl`. If a previously-correct claim now fails, the fix is bad.
6. **Cache the new good run and commit.** Update `data/last_good_run.jsonl`, commit with a message that names the failure and the fix.

**Anti-patterns to avoid:**

- Hardcoding a specific entity name into a prompt to "fix" a single bad finding. That's overfitting to one example. Fix the *class* of failure.
- Adding a Python `if/else` in the orchestrator to override an agent's verdict. The agent should make the call; if it can't, give it a better tool.
- Skipping the regression check ("the new finding looks good"). Past wins must keep working.
- Tuning prompts without a cached comparison run. You'll never know if you actually improved anything.

**What "good" looks like for an agent change:**

- The diff is small (one tool added, one prompt clause added/edited).
- The cached run before/after diff shows the targeted failure resolved AND no other claim got worse.
- The commit message names the specific failure mode and the fix layer.

## Important gotchas

- **Next.js 16 ≠ your training data.** `frontend/AGENTS.md` says: read `frontend/node_modules/next/dist/docs/` before writing any Next.js code. App Router conventions, route handler config, caching defaults all changed. Don't assume.
- **Windows console encoding.** Any new Python script that prints Unicode (arrows, em-dashes) must include `sys.stdout.reconfigure(encoding='utf-8')` or it'll crash with `UnicodeEncodeError` under cp1252.
- **Background bash + python on Windows.** Killing the parent doesn't always kill spawned uvicorn workers. Use the `taskkill /F /T` powershell snippet above when port 8000 stays bound.
- **`.env` holds live AWS credentials.** Gitignored. Never `git add .env`. The `.env.example` is the safe-to-commit template.
- **DB credentials in the brief are real and shared.** The PostgreSQL connection string in `.env` is the organizer-provided read-replica; safe to commit references but not edits.

## Data foundation

Pre-built tables that the pipeline depends on:
- `cra.loops` (5,808 rows) — pre-detected gift cycles with `path_bns`, `total_flow`, `min_year`, `max_year`. Discovery's primary source.
- `cra.cra_qualified_donees` (1.66M) — charity-to-charity gifts; column is `total_gifts`, NOT `amount`.
- `cra.cra_directors` (2.87M) — `first_name` + `last_name`, `at_arms_length` flag for related-party detection.
- `general.entity_golden_records` (851K) — cross-dataset entity resolution; `cra_profile`/`fed_profile`/`ab_profile` are pre-aggregated JSONB.
- `general.entity_source_links` (5.16M) — maps source rows to canonical entities; columns are `source_schema` + `source_table` (NOT `source_dataset`).

See `analysis/scorecard.md` for the full per-challenge probe results and the rationale for picking Funding Loops.

## How challenge selection was made

Don't re-pick the challenge — it's locked. Empirically chosen via `analysis/triage.py` (one SQL probe per challenge against the live DB). Funding Loops scored 18/20 because `cra.loops` was pre-built (~2hr head start) and the 4-agent pattern maps cleanly. The decision rationale + raw probe numbers are in `analysis/scorecard.md`.
