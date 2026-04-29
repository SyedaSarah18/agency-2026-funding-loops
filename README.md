# Vendor Concentration — Agency 2026

> Hackathon entry for **Challenge 5: Vendor Concentration**. Autonomous Strands
> agent on AWS Bedrock that finds where Canadian government spending has
> become locked into single suppliers, with every number sourced and every
> formula explained.

```
hackathon-agency-2026/
├── agent/         Strands agent (Python, FastAPI, Bedrock Sonnet 4)
├── frontend/      Next.js dashboard + chat drawer (Canadian govt theme)
├── references/    Govt doc excerpts (HHI, Gini, TBS contracting policy, …)
├── stories/       Pre-baked SSE traces for the homepage cards
├── data/          Local caches (gitignored)
├── infra/         AWS deploy (App Runner + Amplify, optional AgentCore)
└── docs/          Architecture, judges' context, pitch
```

## Quick start (local)

```bash
# Backend
cp .env.example .env   # fill in PG_DSN, AWS_*, etc.
PYTHONPATH=agent/src .venv/Scripts/python.exe -m uvicorn agent.api:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev          # http://localhost:3000
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the canonical spec.
See [`docs/judges-context.md`](docs/judges-context.md) for verbatim source
material from the organizers (briefing, datasets, scoring rubric).

## Provenance

The frontend was vendored from a sibling prep repo (`agency-prep/frontend`)
with the chat drawer's pipeline nodes rewired to our 4 specialist agents
(Discovery → Investigation → Validator → Narrative) plus a top-level Router.
Theme, dashboards, and SSE contract are unchanged.
