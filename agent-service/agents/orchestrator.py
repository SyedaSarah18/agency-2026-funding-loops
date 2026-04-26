"""4-agent pipeline orchestrator.

Streams Strands events through a unified SSE-friendly format.
Discovery -> Investigation (per candidate) -> Validator (per dossier) -> Narrative (top N).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import AsyncIterator

from agents.discovery import make_discovery_agent
from agents.investigation import make_investigation_agent
from agents.validator import make_validator_agent
from agents.narrative import make_narrative_agent
from config import DISCOVERY_TOP_N, NARRATIVE_TOP_N


def _evt(agent: str, kind: str, message: str, payload: dict | None = None) -> dict:
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "kind": kind,
        "message": message,
        "payload": payload or {},
    }


def _extract_json(text: str):
    """Pull the first JSON value (object or array) out of an LLM response."""
    m = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    text = text.strip()
    # Greedy scan for the first balanced JSON value
    for i, ch in enumerate(text):
        if ch in "[{":
            opener, closer = ch, "]" if ch == "[" else "}"
            depth = 0
            in_str = False
            esc = False
            for j in range(i, len(text)):
                c = text[j]
                if esc:
                    esc = False
                    continue
                if c == "\\":
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if c == opener:
                    depth += 1
                elif c == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[i:j+1])
                        except Exception:
                            break
    return None


async def _run_agent_streamed(agent, user_prompt: str, agent_label: str) -> AsyncIterator[dict]:
    """Yield SSE-shaped events from a Strands agent run + return final text via a 'final' event."""
    yield _evt(agent_label, "start", f"{agent_label.capitalize()} agent invoked")
    final_text_chunks: list[str] = []
    last_tool_name = None

    async for event in agent.stream_async(user_prompt):
        if "current_tool_use" in event:
            tool_use = event["current_tool_use"] or {}
            tname = tool_use.get("name")
            if tname and tname != last_tool_name:
                last_tool_name = tname
                input_preview = str(tool_use.get("input", ""))[:140]
                yield _evt(agent_label, "tool", f"calling tool: {tname}", {"input_preview": input_preview})
        elif "data" in event:
            chunk = event.get("data", "")
            if chunk:
                final_text_chunks.append(chunk)
        elif "result" in event:
            full = "".join(final_text_chunks).strip() or str(event["result"])
            yield _evt(agent_label, "complete", f"{agent_label} done", {"output_chars": len(full)})
            yield {"__final__": full, "__agent__": agent_label}
            return
        elif "force_stop" in event:
            yield _evt(agent_label, "error", f"{agent_label} force stopped", {})
            return


async def run_pipeline() -> AsyncIterator[dict]:
    """Run Discovery -> Investigation x N -> Validator x N -> Narrative.

    Yields SSE-shaped event dicts the caller can serialize and stream.
    """
    yield _evt("pipeline", "start", "4-agent funding-loops investigation begins")

    # ---- 1. Discovery ----
    discovery = make_discovery_agent(top_n=DISCOVERY_TOP_N)
    discovery_final = None
    async for evt in _run_agent_streamed(
        discovery,
        f"Find the top {DISCOVERY_TOP_N} highest-signal candidates per your system instructions. Return strict JSON only.",
        "discovery",
    ):
        if "__final__" in evt:
            discovery_final = evt["__final__"]
        else:
            yield evt
    candidates = _extract_json(discovery_final or "") or []
    if not isinstance(candidates, list) or not candidates:
        yield _evt("pipeline", "error", "Discovery returned no parseable candidates", {"raw_preview": (discovery_final or "")[:300]})
        return
    yield _evt("pipeline", "step", f"Discovery surfaced {len(candidates)} candidates", {"count": len(candidates)})

    # ---- 2. Investigation per candidate (fresh agent each — Strands agents are stateful) ----
    dossiers = []
    for i, cand in enumerate(candidates[:DISCOVERY_TOP_N], 1):
        # Identifier may be loop_id (v1.x funding loops) or program_key (v2.x concentration).
        ident = cand.get("loop_id") or cand.get("program_key") or cand.get("program") or "?"
        yield _evt("pipeline", "step", f"Investigating candidate {i}/{len(candidates)} ({ident})")
        investigation = make_investigation_agent()
        dossier_final = None
        async for evt in _run_agent_streamed(
            investigation,
            f"Build a dossier for this candidate per your system instructions:\n{json.dumps(cand)}",
            "investigation",
        ):
            if "__final__" in evt:
                dossier_final = evt["__final__"]
            else:
                yield evt
        d = _extract_json(dossier_final or "")
        if d:
            dossiers.append(d)

    # ---- 3. Validator per dossier (fresh agent each) ----
    validated = []
    for i, dossier in enumerate(dossiers, 1):
        yield _evt("pipeline", "step", f"Validating dossier {i}/{len(dossiers)}")
        validator = make_validator_agent()
        validated_final = None
        async for evt in _run_agent_streamed(
            validator,
            f"Validate and score this dossier:\n{json.dumps(dossier)}",
            "validator",
        ):
            if "__final__" in evt:
                validated_final = evt["__final__"]
            else:
                yield evt
        v = _extract_json(validated_final or "")
        if v:
            validated.append({"finding": v, "dossier": dossier})

    # Rank by risk_score desc, drop likely_legitimate
    validated = [v for v in validated if v["finding"].get("verdict") != "likely_legitimate"]
    validated.sort(key=lambda x: x["finding"].get("risk_score", 0), reverse=True)
    top = validated[:NARRATIVE_TOP_N]
    yield _evt("pipeline", "step", f"{len(top)} findings rise to Narrative (top {NARRATIVE_TOP_N})", {"count": len(top)})

    # ---- 4. Narrative for top N (fresh agent each) ----
    briefs = []
    for i, item in enumerate(top, 1):
        yield _evt("pipeline", "step", f"Drafting brief {i}/{len(top)}")
        narrative = make_narrative_agent()
        brief_final = None
        async for evt in _run_agent_streamed(
            narrative,
            f"Write a Minister brief for this finding:\n"
            f"VALIDATOR_FINDING:\n{json.dumps(item['finding'])}\n\n"
            f"DOSSIER:\n{json.dumps(item['dossier'])}",
            "narrative",
        ):
            if "__final__" in evt:
                brief_final = evt["__final__"]
            else:
                yield evt
        b = _extract_json(brief_final or "")
        if b and not b.get("skip"):
            # Merge validator verifications + risk_score into the brief so the
            # frontend can render verified/unverified badges per claim and show
            # how the verdict was derived. Pure data carry-through, no LLM needed.
            finding = item["finding"]
            dossier = item["dossier"] or {}
            b["verifications"] = finding.get("verifications", [])
            b["risk_score"] = finding.get("risk_score")
            b["score_breakdown"] = finding.get("score_breakdown", {})
            # Domain-agnostic dossier excerpt for the frontend to render
            # whichever chart shape is appropriate for the current challenge.
            # v1.x funding-loops shape: {charities, edges}
            # v2.x vendor-concentration shape: {recipients, time_series, top_vendor}
            b["chart_data"] = {
                # v1.x loop fields (preserved for back-compat)
                "charities": dossier.get("charities", []),
                "edges": dossier.get("edges", []),
                # v2.x vendor concentration fields
                "program": dossier.get("program"),
                "dept": dossier.get("dept"),
                "recipients": dossier.get("recipients", []),
                "time_series": dossier.get("time_series", []),
                "top_vendor": dossier.get("top_vendor", {}),
            }
            briefs.append(b)

    yield _evt("pipeline", "done", f"Investigation complete: {len(briefs)} Minister-ready briefs",
               {"briefs": briefs})
