"""Router: one cheap LLM call that classifies the user's question into one
of six routes. Returns a typed Decision. Used by the orchestrator to pick
which specialist(s) to dispatch.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from vendor_concentration_agent.agents import build_router_agent

Route = Literal[
    "pipeline",
    "discovery",
    "investigation",
    "validation",
    "narration",
    "out_of_scope",
]

VALID_ROUTES: set[str] = {
    "pipeline", "discovery", "investigation",
    "validation", "narration", "out_of_scope",
}


@dataclass
class RouterDecision:
    route: Route
    reason: str
    raw: str  # the model's literal response, for debugging / audit


_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of the model's response. Tolerates
    markdown fences and stray prose around it.
    """
    if not text:
        return None
    text = text.strip()
    # Try the whole thing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Then look for the first { ... } block
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return None
    return None


async def classify(question: str, context: str = "") -> RouterDecision:
    """Run the Router agent on the user's question; return a validated
    RouterDecision. Defaults to `pipeline` on any parse/route failure
    (the rule from prompts/router.md).
    """
    agent = build_router_agent()
    user_input = question if not context else f"Conversation so far:\n{context}\n\nLatest question:\n{question}"

    response = ""
    async for event in agent.stream_async(user_input):
        if isinstance(event, dict) and "data" in event:
            response += event["data"]

    parsed = _extract_json(response) or {}
    route_raw = parsed.get("route", "pipeline")
    route = route_raw if route_raw in VALID_ROUTES else "pipeline"
    reason = parsed.get("reason", "default route on uncertain classification")
    return RouterDecision(route=route, reason=reason, raw=response)
