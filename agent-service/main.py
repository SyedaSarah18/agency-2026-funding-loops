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

from datetime import datetime, timezone

from fastapi import FastAPI, Query, Body
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
            from agents.orchestrator import run_pipeline
            async for evt in run_pipeline():
                # run_pipeline yields raw event dicts; wrap in SSE shape.
                yield _sse(evt)
        except Exception as e:
            tb = traceback.format_exc()
            yield _evt("pipeline", "error", f"Pipeline crashed: {e}", {"trace": tb[:1000]})

    return EventSourceResponse(stream())


# In-memory conductor session store (single-process, lost on restart).
# Each session_id keeps its own Agent instance so conversation context persists.
_CONDUCTOR_SESSIONS: dict = {}


def _conductor_evt(kind: str, message: str, payload: dict | None = None) -> dict:
    return _sse({
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": "conductor",
        "kind": kind,
        "message": message,
        "payload": payload or {},
    })


@app.post("/ask")
async def ask(body: dict = Body(...)):
    """Conductor chat endpoint. Streams reasoning + tool calls + final answer.

    Body: {session_id: <str>, question: <str>}
    Streams SSE events of shape {ts, agent, kind, message, payload} where
    kind is one of: start | tool | data | complete | error.
    """
    session_id = (body or {}).get("session_id") or "default"
    question = (body or {}).get("question") or ""
    if not question.strip():
        return EventSourceResponse(iter([_conductor_evt("error", "empty question")]))

    print(f"[ask] session={session_id} q={question[:80]!r}", flush=True)

    async def stream():
        # Lazy-import so /investigate keeps working even if conductor deps are broken.
        try:
            from agents.conductor import make_conductor_agent
        except Exception as e:
            yield _conductor_evt("error", f"conductor import failed: {e}")
            return

        agent = _CONDUCTOR_SESSIONS.get(session_id)
        if agent is None:
            agent = make_conductor_agent()
            _CONDUCTOR_SESSIONS[session_id] = agent
            yield _conductor_evt("start", "new conductor session opened",
                                 {"session_id": session_id})
        else:
            yield _conductor_evt("start", "continuing conductor session",
                                 {"session_id": session_id})

        last_tool = None
        text_chunks: list = []
        try:
            async for evt in agent.stream_async(question):
                if "current_tool_use" in evt:
                    tu = evt["current_tool_use"] or {}
                    tname = tu.get("name")
                    if tname and tname != last_tool:
                        last_tool = tname
                        input_preview = str(tu.get("input", ""))[:160]
                        yield _conductor_evt("tool", f"calling tool: {tname}",
                                             {"input_preview": input_preview})
                elif "data" in evt:
                    chunk = evt.get("data", "")
                    if chunk:
                        text_chunks.append(chunk)
                        yield _conductor_evt("data", chunk)
                elif "result" in evt:
                    answer = "".join(text_chunks).strip() or str(evt["result"])
                    yield _conductor_evt("complete", "answer ready",
                                         {"final_answer": answer})
                    return
                elif "force_stop" in evt:
                    yield _conductor_evt("error", "conductor force-stopped")
                    return
        except Exception as e:
            yield _conductor_evt("error", f"conductor crashed: {e}")

    return EventSourceResponse(stream())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
