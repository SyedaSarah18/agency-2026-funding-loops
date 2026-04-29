# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this repo is

Hackathon entry for **Agency 2026 Challenge 5 — Vendor Concentration**.
Builds an autonomous agent on AWS Bedrock that finds vendor lock-in patterns
in Canadian government spending, with every number sourced.

Source of truth for design decisions: `docs/architecture.md` and
`docs/judges-context.md` (verbatim organizer briefing).

## Three deployable units

| Path | What | Stack |
|---|---|---|
| `agent/` | Strands agent + FastAPI service | Python 3.11+, Strands SDK, Bedrock Sonnet 4, psycopg2, DuckDB |
| `frontend/` | Dashboard + chat drawer | Next.js 16 (App Router — see `frontend/AGENTS.md`), shadcn/ui, Recharts, Fraunces+DM Sans, next-themes |
| `infra/` | AWS deploy scripts | App Runner + Amplify (primary), Bedrock AgentCore (stretch) |

The agent and frontend speak SSE over `POST /chat`. The agent emits exactly
three event types: `{"text": "..."}`, `{"tool": "...", "label": "...",
"question": "..."}`, `{"tool_done": "..."}`. Don't change this contract — the
frontend's `ChatDrawer.tsx` is built around it.

## Agent architecture

- **Router** (top): classifies user question into one of 6 routes
  (`pipeline`, `discovery`, `investigation`, `validation`, `narration`,
  `out_of_scope`). One LLM call, no tools.
- **Specialists**: Discovery, Investigation, Validator, Narrative — each a
  Strands `Agent` instance with its own system prompt and tool subset.
- **Math layer** (`agent/src/vendor_concentration_agent/math/`): deterministic
  Python — HHI, CR_n, Gini, sole-source rate, etc. Every function returns
  a `MathResult` with `value`, `sql`, `source_rows`, `trace_steps`,
  `formula_id`, `references`. Agents never invent numbers; they only call
  these tools and reason about results.
- **Validator gates**: programmatic block-on-fail before any output ships
  — every numeric claim must have a `tool_call_id`, every context claim
  must have a `reference_id` resolving to a real URL + excerpt.

## Imports & running

`agent/` uses the `src/` layout. The package name is
`vendor_concentration_agent`. To run anything from the project root, set
`PYTHONPATH=agent/src`.

```bash
# Smoke test the math layer
PYTHONPATH=agent/src .venv/Scripts/python.exe agent/scripts/smoke.py

# Start FastAPI
PYTHONPATH=agent/src .venv/Scripts/python.exe -m uvicorn agent.api:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

The single `.env` at the repo root is loaded automatically (`load_dotenv()`
walks up from cwd).

## What to never do

- Invent metrics. Only use textbook formulas (HHI, Gini, CR_n) or pure
  arithmetic (rates, counts). No `lockin_score`, no custom risk indices.
- Make context claims without a `reference_id` resolving in
  `references/references.json`. If no real source exists, drop the claim.
- Modify the SSE event contract. The frontend depends on the exact shape.
- Reach into Postgres outside `agent/src/vendor_concentration_agent/data/postgres.py`.
  All DB access goes through one read-only connection helper.
