"""FastAPI entrypoint for the agent service.

Endpoints:
  GET  /health                — liveness check
  POST /chat                  — SSE stream of agent events (matches
                                 agency-prep frontend's contract)
  GET  /audit/:call_id        — raw SQL + source rows for any tool call
                                 (Hour 4 — wired with audit store lookup)
  GET  /dashboard/<endpoints> — read-only dashboard data (Hour 4 — port
                                 from agency-prep/backend/api.py)

Run locally from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe -m uvicorn agent.api:app \\
        --reload --port 8000
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vendor_concentration_agent.dashboards import router as dashboards_router
from vendor_concentration_agent.orchestrator import handle as orchestrator_handle


app = FastAPI(
    title="Vendor Concentration agent",
    version="0.1.0",
    description="Agency 2026 hackathon · backend for the Strands agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(dashboards_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    message: str
    context: str = ""


def _format_sse(payload: dict) -> str:
    """Strip our internal `__kind__` marker; serialize the rest as one
    SSE message in the shape ChatDrawer.tsx expects.
    """
    payload = {k: v for k, v in payload.items() if not k.startswith("__")}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    """Stream SSE events for one user question. Three event shapes match
    the frontend exactly: {text}, {tool, label, question}, {tool_done}.
    """

    async def event_stream() -> AsyncIterator[str]:
        async for event in orchestrator_handle(body.message, body.context):
            yield _format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable nginx-style buffering if any reverse proxy is in front
            "X-Accel-Buffering": "no",
        },
    )


# /dashboard/* and /audit/:call_id wired in Hour 4
