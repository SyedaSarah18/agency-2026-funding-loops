# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Practice-run codebase for the Agency 2026 hackathon (Government of Alberta, April 29 2026). A 4-agent Strands pipeline that surfaces suspicious circular funding patterns in Canadian charity data (~23M rows in the organizer's hosted PostgreSQL). Goal: dollar-quantified, named-entity findings a Minister could read in 60 seconds.

Branches:
- `main` — stable
- `v1.0` — frozen practice baseline (don't move)
- `v1.1-dev` — proven funding-loops version (the hard fallback)
- `v2.0-vendor-concentration` — frozen attempt at agent-first vendor-concentration on `fed.grants_contributions`. Pivoted away from because that table is grants/contributions not procurement; live runs produced 0 briefs. Kept as audit trail.
- **`v3.0-atlas` — DEMO BASELINE.** Data-first vendor-concentration on `ab.ab_sole_source` running locally (FastAPI on :8000 + Next.js on :3000). The hard-fallback for the live demo — proven, low-latency, no cold-start risk.
- **`v3.1-agentcore` — Phase F: Conductor deployed to AWS Bedrock AgentCore Runtime.** Same Strands code as v3.0, hosted in managed AWS infra (`us-west-2`). Frontend chat has a local/cloud toggle. ARN: `arn:aws:bedrock-agentcore:us-west-2:941377154016:runtime/agency26_conductor-QTN2spEIzM`. See `deployment/conductor-agentcore/README.md` for redeploy + invoke + cost + risks.

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

### Discovery agent must filter cross-entity cycles (v1.x ONLY — historical note)

In v1.x funding loops, `cra.loops` included ~600 same-org sub-registration cycles (Salvation Army has 600+ chapters under BN root `107951618`). Discovery's prompt required a cross-BN-root filter or every candidate got ruled `likely_legitimate`. v3.x doesn't use `cra.loops` — the equivalent v3.x discipline is the `headline_risk_score` floor at $10M total spend (see `analysis/atlas/build.py`'s `build_atlas_categories` function), which keeps small research-grant categories from outranking real lock-in patterns.

### Narrative has a hard no-hallucinated-numbers constraint

`agents/narrative.py` prompt explicitly forbids any number not in the input dossier. `lead_sentence` MUST start with a number. Output is structured JSON (`lead_number`, `evidence_refs`, etc.) so `MinisterBrief` rendering can map back to source rows. Treat this constraint as load-bearing — judges will verify.

### SQL tool is read-only by design

`agent-service/tools/sql.py` opens connections with `set_session(readonly=True)` AND has a deny-list for write keywords. Returns max 200 rows per call as JSON. Statement timeout 60s. The tool's docstring is the schema cheat-sheet the LLM uses — keep it accurate when adding new tables.

### Validator has dedicated verify_* tools, not just SQL

`agent-service/tools/verify.py` exposes six `@tool` functions. v3.x active uses:
- `verify_concentration_share(ministry, category_substr, claimed_share, claimed_vendor)` — re-runs the share math against `ab.ab_sole_source` to confirm the headline concentration claim.
- `verify_vendor_ministry_count(vendor_substr, claimed_count, claimed_total)` — sums the vendor's full footprint across `ab.ab_sole_source + ab.ab_contracts`.

v1.x verify tools kept for back-compat (unused on v3.x but harmless if Validator decides a recipient IS a charity):
- `verify_gift`, `verify_director`, `verify_charity_revenue`, `verify_external_funding`.

Why dedicated verify tools instead of letting the Validator write SQL: standardises the pass/fail shape (`{verified, claimed, actual, delta_pct, ...}`), constrains the Validator's prompt to do at most ~4 verifications per dossier, makes the audit trail uniform.

Caveats:
- `verify_charity_revenue` prefers T3010 `field_4700` (total revenue) and falls back to `field_4500` (tax-receipted gifts) — this distinction matters because v1.0 saw the agent confidently report `field_4500` as "revenue" and inflate a multiple by 3×.
- `verify_external_funding` for `source='fed'` tries BN match first, then falls back to legal-name match (KNOWN-DATA-ISSUE F-6: ~55% of fed rows have NULL `recipient_business_number`).
- Tolerance defaults: 5% for gifts/revenue/share (clean tables), 10% for external funding + vendor totals (FED-3 amendment double-counting).

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

### v3.x active source tables (procurement)

- `ab.ab_sole_source` (15,533 rows, $18.2B) — Alberta sole-source procurement. The PRIMARY signal table. Columns we use: `ministry`, `vendor`, `vendor_city`, `vendor_province`, `start_date`, `end_date`, `amount`, `contract_services`, `permitted_situations`, `display_fiscal_year`.
- `ab.ab_contracts` (67,079 rows) — broader Alberta procurement. Thin schema (id, fy, recipient, amount, ministry).
- `fed.grants_contributions` (1.28M rows) — federal grants. NOT used for v3.x. Briefly attempted in v2.x and abandoned because it's grants/contributions not procurement, so the politically-resonant scandals (ArriveCAN, McKinsey) live elsewhere (PSPC contracts disclosure on open.canada.ca, NOT ingested).
- `cra.*` and `general.*` schemas — used by v1.x funding loops, dormant in v3.x.

### Pre-computed Atlas (the 6 parquet files agents read)

Built once by `analysis/atlas/build.py`. Agents NEVER read raw SQL for analytical work — they read these parquets via `tools/atlas.py`:

| File | Rows | What it answers |
|---|---:|---|
| `atlas_categories.parquet` | 2,219 | Per (ministry × category): top-1 vendor, share, Herfindahl, composite_risk_score, headline_risk_score (zeroed below $10M floor) |
| `atlas_vendor_dependency.parquet` | 2,920 | Per vendor: cross-ministry breadth, sole-source share, total spend, lockin_score |
| `atlas_incumbency.parquet` | 530 | Per (vendor × ministry): yearly history, temporal_zscore, is_step_function (z>5) |
| `atlas_regions_headline.parquet` | 124 | Per ministry: Alberta-based vs Out-of-province vs Unknown spend split |
| `atlas_regions_cities.parquet` | 572 | Within Alberta, per (city × ministry): top vendor + concentration |
| `atlas_regions_out_of_province.parquet` | 35 | Categories where >50% of spend leaves Alberta |

### lockin_score formula (atlas_vendor_dependency)

Composed in `analysis/atlas/build.py` `build_atlas_vendor_dependency()`. Max 100:
- Cross-ministry breadth: `n_ministries × 1.5`, capped at 30
- Total spend (sqrt-scaled): `√(total_spend / $10M) × 5`, capped at 30
- Sole-source share: `sole_source_share × 20`
- Category breadth: `n_categories × 0.8`, capped at 20

IBM Canada example: 20 min × 1.5 = 30, √(341.3/10) × 5 = 29.2, 0.421 × 20 = 8.4, 6 × 0.8 = 4.8 → 72.4. Catholic Social Services: 7.5 + 30 + 20 + 20 (capped) → 77.5.

Weights are first-pass; not tuned against ground truth. Calibration target = `analysis/atlas/known_cases.py` true positives.

### View any Atlas table from the CLI

`analysis/view_atlas.py` (sortable, filterable, money-formatted):

```bash
.venv/Scripts/python analysis/view_atlas.py                              # default: top 20 vendors by lockin
.venv/Scripts/python analysis/view_atlas.py --table categories           # categories by headline_risk_score
.venv/Scripts/python analysis/view_atlas.py --table regions_oop          # out-of-province dependency
.venv/Scripts/python analysis/view_atlas.py --table incumbency           # year-over-year + step functions
.venv/Scripts/python analysis/view_atlas.py --filter ibm                 # rows matching "ibm"
.venv/Scripts/python analysis/view_atlas.py --schema-only                # dtypes + describe()
```

### Honest caveats from the data

- **`vendor_province` is the contract billing address, NOT corporate HQ.** Microsoft Canada always bills Toronto/Ontario in our data. IBM Canada SPLITS — Enterprise License Agreement bills to Markham/Ontario, but Mainframe Hosting + IMAGIS bill to Edmonton/Alberta. Don't claim "IBM is Ontario-based" — claim what the field actually says per contract.
- **Data quality findings worth surfacing**: `SUNDRY, OTHER VENDORS BELOW $10,000` placeholder vendor aggregates $172M across 61 ministries. IBM appears under 2 entity-name variants. Province strings inconsistent (Alberta/AB/Ontario/ON/NA/XX).
- `permitted_situations` field is a single-letter code (a-l, z) without a lookup table in our data. Top: `d` ($12.7B), `b` ($3.6B), `g` ($1.2B).

## How challenge selection was made

Don't re-pick the challenge — it's locked on Ch.5 Vendor Concentration. Original empirical scorecard at `analysis/scorecard.md` (Phase 1c probes against the live DB). User pivoted to Ch.5 mid-build because (a) Phase 6d deep re-probe of the original triage revealed Ch.5 was 100x undercounted (we'd only sliced AB ministries; the right framing is FED program-level + AB sole-source), (b) Ch.5 is IBM-relevant for the user's internal pitch — IBM appears with 3 separate 100% sole-source category monopolies in the data.

## Phase F: AgentCore deployment (v3.1-agentcore branch)

Conductor agent deployed to AWS Bedrock AgentCore Runtime in `us-west-2`.

- **ARN:** `arn:aws:bedrock-agentcore:us-west-2:941377154016:runtime/agency26_conductor-QTN2spEIzM`
- **Account:** 941377154016
- **Execution role:** `AmazonBedrockAgentCoreSDKRuntime-us-west-2-fb94713b8d` (auto-created)
- **S3 staging bucket:** `bedrock-agentcore-codebuild-sources-941377154016-us-west-2`
- **Memory mode:** `NO_MEMORY` (session affinity gives free multi-turn within ~8hr per `runtimeSessionId`)
- **Deployment package:** ~204 MB (Strands + Bedrock + boto3 + pandas + pyarrow + psycopg2-binary + our code + parquets + kb)
- **CloudWatch log group:** `/aws/bedrock-agentcore/runtimes/agency26_conductor-QTN2spEIzM-DEFAULT`

### Deploy commands

```bash
# fresh deploy or redeploy (uses bedrock_agentcore_starter_toolkit Runtime SDK)
cd deployment/conductor-agentcore
../../.venv/Scripts/python deploy.py

# CLI smoke test (boto3 invoke_agent_runtime)
../../.venv/Scripts/python deploy.py --invoke "Show me IBM's footprint"

# from frontend chat: toggle "cloud (AgentCore)" button in the Chat header.
# Frontend hits /api/ask-cloud -> FastAPI /ask-cloud -> boto3 invoke_agent_runtime
```

### Two backends for the chat

- `/api/ask` (Next.js) → FastAPI `/ask` → in-process Conductor (local, lowest latency, demo-default)
- `/api/ask-cloud` (Next.js) → FastAPI `/ask-cloud` → boto3 → AgentCore Runtime (cloud, sponsor-architecture parity)

Same prompt, same tools, same SSE event shape. Toggle in `frontend/app/components/Chat.tsx`.

### Phase F deployment gotchas (lessons learned the hard way)

1. **No Docker on Windows.** Toolkit's default container path needs Docker/Finch/Podman. Switch to `deployment_type="direct_code_deploy"` + `runtime_type="PYTHON_3_13"` to skip Docker entirely. AgentCore packages server-side via S3.
2. **`uv` required** for direct_code_deploy — `pip install uv` once. The toolkit uses uv to cross-compile dependencies for `aarch64-manylinux2014`.
3. **`zip` CLI gate on Windows.** Toolkit's precondition checks `shutil.which("zip")` even though actual zip work uses Python's `zipfile` module. Workaround: a no-op `.venv/Scripts/zip.bat` shim (gitignored). `deploy.py` adds `.venv/Scripts` to PATH at startup so `shutil.which` finds the shim.
4. **`aws-opentelemetry-distro` cross-compile fails from Windows.** Toolkit detects it in `requirements.txt`, sets the runtime to OTel mode, but the `opentelemetry-instrument` CLI binary doesn't make it into the ARM64 zip — runtime then refuses to start with "OpenTelemetry instrumentation executable not found." Fix: keep OTel out of `requirements.txt`. Logs go to CloudWatch via stdout (see `agent.py` logging config). X-Ray traces deferred to a Linux build host.
5. **Observability flag sticks in the YAML.** Once `.bedrock_agentcore.yaml` has `observability: enabled: true`, every subsequent deploy demands OTel deps even after you remove the dep. To unwind: `boto3 bedrock-agentcore-control delete_agent_runtime` + delete `.bedrock_agentcore.yaml` + redeploy fresh.
6. **`runtimeSessionId` must be ≥33 characters.** The boto3 invoke fails with a validation error otherwise. We pad short session IDs in `/ask-cloud`: `(session_id + "x" * 33)[:64]`.
7. **AgentCore Runtime streams tool inputs character-by-character.** Without dedup the chat UI shows 5-8 duplicate `⚙ tool_name` badges per actual call. `/ask-cloud` dedupes: emit only on tool name change OR when input parses as complete JSON.
8. **First invoke after >15 min idle has 3-8s cold start.** Hit it with a warmup ping 60s before any live demo.
9. **IAM permissions.** `AmazonBedrockFullAccess` is for runtime invoke only. Deploy + manage Runtime resources needs ECR + CodeBuild + IAM:CreateRole + S3 + CloudFormation. For the hackathon timeline, attach `AdministratorAccess` to the IAM user (zero cost difference vs. fine-grained policies — IAM permissions are free, AWS bills for services used). Detach + delete keys post-event.
10. **Cost.** AgentCore Runtime: $0.0895/vCPU-hour + $0.00945/GB-hour, billed only during active CPU. A 10-invocation demo session ≈ $0.009 of Runtime cost. Bedrock model tokens billed separately.

### When NOT to use AgentCore primitives

- **Gateway** — for wrapping external Lambdas/APIs as MCP tools or cross-team tool sharing. Our tools are use-case-specific in-process Python (parquet readers, verify, pandas eval). Lab 3 of the AWS workshop teaches the same boundary: keep use-case-specific tools local. Don't reach for Gateway.
- **Memory** — for cross-session recall ($0.25/1k events). Session affinity gives free multi-turn within a session.
- **Identity** — for OAuth/JWT inbound auth on the runtime. Not needed; frontend uses IAM creds via boto3.
- **Bedrock Agents** (the original 2023 product) — declarative JSON + Lambda tools. We're on AgentCore Runtime (the newer flexible product) which hosts our Strands code as a container.

## Frontend gotchas (collected this session)

- **SSE through Next.js needs careful proxying.** `route.ts` must use a `TransformStream` re-pipe of `upstream.body` and set `X-Accel-Buffering: no` headers; otherwise Next.js buffers the entire stream until the upstream closes. See `frontend/app/api/investigate/route.ts` and `frontend/app/api/ask-cloud/route.ts` for the pattern.
- **SSE event boundaries can be `\n\n` OR `\r\n\r\n`** depending on whether the proxy normalizes line endings. Chat.tsx splits on `/\r?\n\r?\n/` — accept both.
- **Hydration mismatch from `Date.now()` at module init.** Next.js server-renders the component once and the client renders again; if the value differs (e.g. session id from `Date.now()`) you get a hydration error and the tree re-renders. Fix: generate the value in a `useEffect` after mount; SSR ships a stable placeholder.
- **Chat input text was white-on-white** — Tailwind didn't auto-color the `<input>`. Set `text-slate-900 placeholder:text-slate-400 bg-white` explicitly.
- **`tools/atlas.py` and `tools/kb.py` use different ROOT calculations** depending on which tree they're in. In `agent-service/`, `ROOT = parent.parent.parent` (project root). In `deployment/conductor-agentcore/`, `ROOT = parent.parent` (package root). The tools are otherwise identical between trees.
- **Markdown tables in chat need `react-markdown` + `remark-gfm`.** The Conductor returns markdown tables; without proper renderer columns are misaligned. `Chat.tsx` uses ReactMarkdown with custom `table`/`th`/`td` components for Excel-like grid styling + `tabular-nums` for digit alignment.
- **Both servers' state survives branch checkouts.** When you `git checkout` to a different branch, the running FastAPI/Next.js processes keep the previously-loaded code in memory. Restart processes (kill + re-run) to pick up code from the new branch.

## Architecture diagram

`docs/architecture-diagram.md` has both ASCII (paste into slides) and Mermaid (renders on GitHub) diagrams of the full system.
