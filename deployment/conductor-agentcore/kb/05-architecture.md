# Architecture — how the system is built

## 5-layer architecture

```
1. DATA LAYER  (Python + DuckDB + pandas, no LLM)
   analysis/atlas/{metrics,build,baselines,known_cases}.py
   Pre-computes 3 ranked Atlas tables (parquet) from Alberta procurement.

2. EVAL LAYER  (deterministic test harness, NOT the Validator agent)
   analysis/atlas/known_cases.py — asserts 8 known true positives surface
   at risk >= 60. Run after any agent code change.

3. PIPELINE AGENTS  (Mode 1: structured discovery)
   agent-service/agents/{discovery,investigation,validator,narrative}.py
   Discovery -> Investigation -> Validator -> Narrative.
   Reads from Atlas (NOT raw SQL). Produces ranked Minister briefs.

4. CONDUCTOR AGENT  (Mode 2: adaptive reasoning chat)
   agent-service/agents/conductor.py
   Single agent. Tools: query_atlas, query_db, verify_*, read_kb,
   compute, code_compute. Receives any natural-language question,
   picks tools per question, streams reasoning + tool calls + answer.

5. VISUALIZATION LAYER  (Next.js)
   frontend/app/components/{Watchlist,ConcentrationHeatmap,
   VendorFootprint,Chat}.tsx
```

## Two operating modes — the autonomy story

**Mode 1: Run Investigation pipeline.** Click button. 4 agents run in sequence.
Predetermined dossier shape, predetermined brief shape. Proves systematic
discovery without prompting.

**Mode 2: Conductor chat.** Type any question. Conductor reasons about which
tools the question needs, executes them, synthesizes an answer. Proves
adaptive reasoning to judges' follow-ups.

Both share the Atlas + verify_* tools. Different agent architectures, same
underlying data.

## Why agents (vs. just SQL)

Honest answer: the *Atlas* is just SQL/pandas. The *agents* add value where
SQL can't:
- Adaptive querying — Investigation picks different probes per candidate
- Self-validation — Validator runs verify_* tools and downgrades verdict on failure
- Natural-language Q&A — Conductor answers any question without pre-scripting
- Plain-English Minister briefs (Narrative)

The data layer is deterministic and defensible. The agent layer is autonomous
and adaptive. Both matter for the scoring rubric.

## How to run

```bash
# 1. Build the Atlas (once, ~10 sec after first run with cached DB)
python analysis/atlas/build.py

# 2. Verify methodology
python analysis/atlas/known_cases.py    # must exit 0

# 3. Start agent service (port 8000)
cd agent-service && python main.py

# 4. Start frontend (port 3000)
cd frontend && npm run dev

# 5. Open browser at http://localhost:3000
#    - Click "Run Investigation" -> pipeline produces briefs
#    - Type in chat -> Conductor answers any question
```
