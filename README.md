# Agency 2026 — Funding Loops Investigator

A 4-agent AI pipeline that finds suspicious circular funding patterns in Canadian charity data, built for the [Agency 2026 National AI Hackathon](https://luma.com/5e83iia8) (Government of Alberta, April 29 2026).

## What it does

Given the [GovAlta hackathon dataset](https://github.com/GovAlta/agency-26-hackathon) (~23M rows of CRA charity filings, federal grants, Alberta open data unified in PostgreSQL), the system autonomously surfaces dollar-quantified, named-entity findings about suspicious money flows between charities — the kind a Minister could action.

A typical run produces briefs like:

> **$30.7M circulated through 6 charities** across BC/ON/AB between 2020-2024. Toronto Foundation (recipient of $65.4M in federal grants) routed $9M to Cidel Foundation, which then disbursed $20.7M in a single 2023 transfer — 7.4× Cidel's own annual revenue. Recommended: trigger CRA T3010 audits on all 6 charities for FY2020-2024.

## Architecture

Four Strands agents run in sequence, each with distinct tools, streaming SSE events to a Next.js dashboard:

| Agent           | Role                                            | Tools                                  |
|-----------------|-------------------------------------------------|----------------------------------------|
| Discovery       | Scans `cra.loops` for high-flow cross-entity cycles | `query_db`                             |
| Investigation   | Builds dossier per candidate (charities, edges, directors, cross-fund) | `query_db`, `build_loop_graph` (NetworkX) |
| Validator       | Rules out legit hierarchies, scores severity 0-100 | `query_db`                             |
| Narrative       | Quantitative-first Minister briefs (no hallucinated numbers) | LLM-only                               |

## Stack

- **LLM:** Claude Sonnet 4.6 via AWS Bedrock (`us-west-2`)
- **Agent SDK:** [Strands Agents](https://github.com/strands-agents/sdk-python) (Python, open-source)
- **Backend:** FastAPI + SSE streaming (port 8000)
- **Frontend:** Next.js 16 (App Router) + Tailwind 4 (port 3000)
- **Data:** PostgreSQL (organizer-hosted) + NetworkX for graph metrics

## Quickstart

See [docs/quickstart.md](docs/quickstart.md) for full setup. TL;DR:

```bash
# 1. Configure .env (copy .env.example, fill AWS_* + PG_DSN)
# 2. Install
python -m venv .venv && .venv/Scripts/pip install -r <(grep dependencies agent-service/pyproject.toml -A 20)
cd frontend && npm install && cd ..

# 3. Run (two terminals)
cd agent-service && python main.py            # :8000
cd frontend && npm run dev                    # :3000

# Open http://localhost:3000 -> click "Run Investigation"
```

## How the challenge was chosen

We didn't guess. We probed all 10 challenges against real data first — see [analysis/scorecard.md](analysis/scorecard.md). Funding Loops won 18/20 because:
- Pre-built `cra.loops` table = ~2hr head start
- 4,343 cross-entity cycles totalling $2.86B = real signal
- Every agent has distinct, autonomous work
- Network graphs are visualizable for non-technical judges

## Status

This is the **v1.0 practice-run** baseline (2026-04-25). Plumbing perfect, content rough. Event-day work tracked on the next-version branch.

## Repo layout

```
hackathon-agency-2026/
├── analysis/           Phase 1 — data triage probes + scorecard
├── agent-service/      Phase 4 — Strands agents + FastAPI
├── frontend/           Phase 2 — Next.js dashboard
├── scripts/            Bedrock ping + utilities
├── docs/               Quickstart + 3-min pitch script
└── data/               Cached "last good run" for demo fallback
```
