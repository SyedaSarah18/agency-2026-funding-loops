"""FastAPI entrypoint for the agent service.

Exposes:
  GET  /health                — liveness check
  POST /chat                  — SSE stream of agent events (Hour 3 wires this)
  GET  /dashboard/<endpoints> — read-only dashboard data (Hour 4 ports these
                                from agency-prep verbatim)

Run locally from project root:
    PYTHONPATH=agent/src .venv/Scripts/python.exe -m uvicorn agent.api:app \\
        --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# /chat — wired in Hour 3 (SSE stream of router → specialist(s) events)
# /dashboard/* — wired in Hour 4 (port from agency-prep/backend/api.py verbatim)
