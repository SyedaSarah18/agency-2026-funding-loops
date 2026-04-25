# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Practice-run codebase for the Agency 2026 hackathon (Government of Alberta, April 29 2026). A 4-agent Strands pipeline that surfaces suspicious circular funding patterns in Canadian charity data (~23M rows in the organizer's hosted PostgreSQL). Goal: dollar-quantified, named-entity findings a Minister could read in 60 seconds.

Branches: `main` = stable, `v1.0` = frozen practice baseline (don't move), `v1.1-dev` = active work (default checkout).

**Read this before changing the architecture:** [docs/original-plan.md](docs/original-plan.md) is the practice-run plan we built before writing any code, including the 5-phase execution flow, the empirical-vs-guessing rationale for picking Funding Loops, the v0.1 success criteria (plumbing perfect / content rough), and a "plan-vs-actual" section listing what diverged during execution. Any major architectural change should reconcile against it.

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

Orchestrated in `agent-service/agents/pipeline.py`. Each handoff goes through `_extract_json()` because Strands agents return free-form text containing a JSON value. Findings whose `verdict == "likely_legitimate"` are dropped before Narrative.

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
