"""SSE event schema + per-request event bus.

Matches agency-prep's frontend contract exactly — three event types that the
ChatDrawer's `streamChatEvents()` parses out of `data: {json}\n` lines:

    {"text": "..."}                                       — assistant token
    {"tool": "<name>", "label": "...", "question": "..."} — agent/tool started
    {"tool_done": "<name>"}                                — agent/tool finished
    {"error": "..."}                                       — fatal

The orchestrator + each agent emits via the per-request EventBus exposed
through `current_bus()`. The /chat endpoint reads from the bus, formats
each event as `data: {json}\\n\\n`, and yields to the StreamingResponse.

Tool-result audit data (SQL, source_rows, formula_id) is captured in a
side-channel on the bus so /audit/:call_id can serve it without polluting
the SSE stream.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


EventKind = Literal["text", "tool", "tool_done", "error", "route", "audit"]


@dataclass
class Event:
    kind: EventKind
    payload: dict[str, Any]

    def to_sse_lines(self) -> str:
        """Serialize as one SSE message. Audit events are not sent over the
        wire — they're consumed locally by the bus's audit-store hook.
        """
        if self.kind == "audit":
            return ""
        if self.kind == "route":
            # Render route decisions as a small text breadcrumb in the chat
            # thread; the actual UI badge is driven by the route metadata
            # included as a tool event before it.
            return f"data: {json.dumps({'text': self.payload.get('display', '')})}\n\n"
        return f"data: {json.dumps(self.payload, ensure_ascii=False)}\n\n"


class EventBus:
    """Per-request queue of events. Producers (agents, tools, orchestrator)
    push; the /chat endpoint pulls and yields to the SSE response.

    Also collects per-tool-call audit data so /audit/:call_id can serve the
    raw SQL + source_rows + trace_steps without re-running anything.
    """

    def __init__(self) -> None:
        self._q: asyncio.Queue[Event | None] = asyncio.Queue()
        self.audit: dict[str, dict[str, Any]] = {}

    async def emit(self, event: Event) -> None:
        if event.kind == "audit":
            call_id = event.payload["call_id"]
            self.audit[call_id] = event.payload
            return
        await self._q.put(event)

    async def emit_text(self, text: str) -> None:
        if not text:
            return
        await self.emit(Event("text", {"text": text}))

    async def emit_tool_start(self, name: str, label: str, question: str = "") -> str:
        """Emit a tool/agent-start event and return the call_id used to
        correlate with the matching tool_done + audit row.
        """
        call_id = f"{name}-{uuid.uuid4().hex[:8]}"
        await self.emit(Event("tool", {"tool": name, "label": label, "question": question, "call_id": call_id}))
        return call_id

    async def emit_tool_done(self, name: str) -> None:
        await self.emit(Event("tool_done", {"tool_done": name}))

    async def emit_error(self, message: str) -> None:
        await self.emit(Event("error", {"error": message}))

    async def emit_audit(self, call_id: str, audit: dict[str, Any]) -> None:
        await self.emit(Event("audit", {"call_id": call_id, **audit}))

    async def close(self) -> None:
        await self._q.put(None)

    async def __aiter__(self):
        while True:
            event = await self._q.get()
            if event is None:
                return
            yield event


# ---- per-request contextvar so deeply-nested tool functions can find it ----

_current_bus: contextvars.ContextVar[EventBus | None] = contextvars.ContextVar(
    "current_event_bus", default=None
)


def set_bus(bus: EventBus | None) -> contextvars.Token:
    return _current_bus.set(bus)


def reset_bus(token: contextvars.Token) -> None:
    _current_bus.reset(token)


def current_bus() -> EventBus | None:
    return _current_bus.get()
