# Quickstart

## Prerequisites
- Python 3.11+ with the project venv: `hackathon-agency-2026/.venv`
- Node 20+ with `frontend/node_modules` installed
- AWS Bedrock access in `us-west-2` for Claude Sonnet 4.6 (see Bedrock setup below)

## Run locally
Two terminals.

**Terminal 1 — agent service (FastAPI):**
```
cd agent-service
../.venv/Scripts/python main.py
# -> http://127.0.0.1:8000  (POST /investigate?mode=real|fake)
```

**Terminal 2 — frontend (Next.js):**
```
cd frontend
npm run dev
# -> http://localhost:3000
```

Open http://localhost:3000 → tick "fake-events mode" if AWS isn't ready yet → click "Run Investigation".

## Modes
- **fake** (no AWS needed): streams 16 hard-coded events, demos the SSE plumbing only.
- **real**: runs the 4-agent Strands pipeline against Bedrock + the organizer's PostgreSQL. Produces real Minister Briefs.

## Bedrock setup (us-west-2)
1. AWS Console → top-right region → switch to **US West (Oregon) us-west-2**.
2. Bedrock → Bedrock configurations → **Model access** → Modify → enable `Anthropic Claude Sonnet 4.6` → fill the First-Time-Use form. Approval is usually <1 min.
3. IAM → Users → create user → attach `AmazonBedrockFullAccess` → create access key.
4. Drop into `hackathon-agency-2026/.env`:
   ```
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=us-west-2
   LLM_BACKEND=bedrock
   LLM_MODEL=us.anthropic.claude-sonnet-4-6-20260101-v1:0
   ```
5. Verify with `python scripts/bedrock_ping.py` (creates a 10-token completion; costs <$0.0001).

## Project layout
```
hackathon-agency-2026/
├── analysis/                       # Phase 1 — data triage
│   ├── schema_inventory.py         # dump all schemas/tables/columns
│   ├── profile.py                  # date coverage, NULL rates, top entities
│   ├── triage.py                   # ONE probe per challenge
│   └── scorecard.md                # ranked challenge decision (Ch.3 won)
├── agent-service/                  # Phase 4 — Strands agents + FastAPI
│   ├── main.py                     # SSE endpoint
│   ├── config.py                   # .env loader
│   ├── llm/client.py               # Bedrock / Anthropic factory
│   ├── tools/sql.py                # @tool query_db (read-only PG)
│   ├── tools/graph.py              # @tool build_loop_graph (NetworkX)
│   └── agents/
│       ├── discovery.py            # finds top-N cycles in cra.loops
│       ├── investigation.py        # builds dossiers (charities, edges, directors, cross-fund)
│       ├── validator.py            # rules out legit hierarchies, scores severity
│       ├── narrative.py            # quantitative-first Minister briefs
│       └── orchestrator.py         # orchestrates D > I > V > N, emits SSE-shaped events
├── frontend/                       # Phase 2 — Next.js dashboard
│   └── app/
│       ├── api/investigate/route.ts # proxies SSE
│       ├── components/AgentTrace.tsx # live event stream + Minister Briefs panel
│       └── page.tsx
└── docs/
    ├── quickstart.md               # this file
    └── pitch.md                    # 3-minute demo script (Phase 5)
```

## Re-run the data triage
```
.venv/Scripts/python analysis/triage.py
```
Refreshes `analysis/triage_results.json` against the live DB.
