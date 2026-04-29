"""Internal helper: turn a MathResult into (LLM-friendly summary, audit blob).

The LLM only needs the headline value + interpretation hooks; the SQL and
source rows are voluminous and would just clog its context window. We send
the lean summary back to Strands (which forwards it to the model) and stash
the full audit on the EventBus so /audit/:call_id can serve it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from vendor_concentration_agent.math.types import MathResult
from vendor_concentration_agent.trace.events import current_bus


def _trim_rows(rows: list[dict], cap: int = 5) -> list[dict]:
    return rows[:cap]


def _trim_trace(steps: list[dict], cap: int = 10) -> list[dict]:
    return steps[:cap]


def emit_audit_sync(call_id: str, math_result: MathResult) -> None:
    """Push the full MathResult to the audit store. Safe to call from sync
    code — schedules the coroutine on the running loop. No-op if no bus is
    set (e.g. during smoke tests run outside an event loop).
    """
    bus = current_bus()
    if bus is None:
        return
    audit = {
        "formula_id": math_result.formula_id,
        "value": math_result.value,
        "sql": math_result.sql,
        "source_rows": math_result.source_rows,
        "trace_steps": math_result.trace_steps,
        "references": math_result.references,
        "inputs": math_result.inputs,
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(bus.emit_audit(call_id, audit))
    except RuntimeError:
        # No running loop — sync test context; silently drop.
        pass


def summarize_for_llm(math_result: MathResult, call_id: str) -> dict[str, Any]:
    """Lean dict the LLM sees. Tool-call summary, not raw payload."""
    emit_audit_sync(call_id, math_result)
    return {
        "call_id": call_id,
        "formula_id": math_result.formula_id,
        "value": math_result.value,
        "references": math_result.references,
        "inputs": math_result.inputs,
        "trace_preview": _trim_trace(math_result.trace_steps, cap=5),
        "rows_preview": _trim_rows(math_result.source_rows, cap=3),
        "row_count": len(math_result.source_rows),
    }


def new_call_id(prefix: str) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
