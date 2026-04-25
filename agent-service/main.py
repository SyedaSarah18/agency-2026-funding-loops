"""FastAPI agent service.

POST /investigate?mode=real|fake
  - real: runs the 4-agent Strands pipeline (requires Bedrock credentials)
  - fake: streams hard-coded events (Phase 2 plumbing demo / fallback if AWS not ready)
GET  /health -> liveness check.
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

app = FastAPI(title="Agency 2026 Agent Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(payload: dict) -> dict:
    return {"data": json.dumps(payload, default=str)}


def _evt(agent: str, kind: str, message: str, payload: dict | None = None) -> dict:
    return _sse({
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "kind": kind,
        "message": message,
        "payload": payload or {},
    })


# Phase-2 fallback (used if mode=fake or if real pipeline import fails)
FAKE_RUN = [
    ("discovery",     "start",    "Discovery agent: scanning cra.loops for high-flow cycles", None, 0.4),
    ("discovery",     "step",     "Querying loops with total_flow >= $100K", None, 0.6),
    ("discovery",     "step",     "Found 47 candidate cycles", {"candidate_count": 47}, 0.4),
    ("discovery",     "complete", "Discovery done", {"top_id": 42}, 0.2),
    ("investigation", "start",    "Investigation agent: building dossier per candidate", None, 0.4),
    ("investigation", "step",     "Resolving BNs to charity legal names via cra_identification", None, 0.6),
    ("investigation", "step",     "Building NetworkX graph for cycle 1/47", None, 0.4),
    ("investigation", "complete", "Dossiers ready", {"dossier_count": 47}, 0.2),
    ("validator",     "start",    "Validator: ruling out denominational hierarchies + scoring severity", None, 0.4),
    ("validator",     "step",     "Cross-referencing director overlap via cra_directors", None, 0.6),
    ("validator",     "step",     "Cross-referencing fed/AB funding via general.entity_source_links", None, 0.6),
    ("validator",     "complete", "Top 5 findings ranked", {"final_count": 5}, 0.2),
    ("narrative",     "start",    "Narrative agent: drafting Minister-ready briefs", None, 0.4),
    ("narrative",     "step",     "Brief 1/5 - quantitative-first lead, evidence refs attached", None, 0.6),
    ("narrative",     "complete", "Briefs ready", {"briefs": 5}, 0.2),
    ("pipeline",      "done",     "Investigation complete", {"total_findings": 5}, 0.0),
]


@app.get("/health")
def health():
    return {"status": "ok", "service": "agency-26-agent-service"}


@app.post("/investigate")
async def investigate(mode: str = Query(default="real", pattern="^(real|fake)$")):
    print(f"[investigate] mode={mode}", flush=True)
    async def stream():
        if mode == "fake":
            for agent, kind, msg, payload, delay in FAKE_RUN:
                yield _evt(agent, kind, msg, payload)
                await asyncio.sleep(delay)
            return

        try:
            from agents.pipeline import run_pipeline
            async for evt in run_pipeline():
                # run_pipeline yields raw event dicts; wrap in SSE shape.
                yield _sse(evt)
        except Exception as e:
            tb = traceback.format_exc()
            yield _evt("pipeline", "error", f"Pipeline crashed: {e}", {"trace": tb[:1000]})

    return EventSourceResponse(stream())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
