"""4-agent pipeline — Discovery → Investigation → Validator → Narrative
with one divergence loop-back.

Each agent is invoked separately and its output text is captured. We
emit the SSE shape the frontend expects:

  {tool: "discovery", label: "Discovery", question: "..."}
  ...streamed text from discovery...
  {tool_done: "discovery"}
  {tool: "investigation", ...}
  ...

Math tools called inside each agent produce {text} events with the
agent's reasoning + the tool result summary inline. The audit drawer
gets the full payload via the EventBus side-channel.
"""

from __future__ import annotations

from vendor_concentration_agent.agents import (
    build_discovery_agent,
    build_investigation_agent,
    build_validator_agent,
    build_narrative_agent,
)
from vendor_concentration_agent.trace.events import EventBus


_LABELS = {
    "discovery": "Discovery",
    "investigation": "Investigation",
    "validator": "Validator",
    "narrative": "Narrative",
}


async def _run_agent(
    bus: EventBus,
    name: str,
    agent_factory,
    user_input: str,
    question_label: str,
) -> str:
    """Run one Strands agent, streaming its text to the bus, return its
    full collected response so the next agent can consume it as input.
    """
    await bus.emit_tool_start(name, _LABELS[name], question_label)

    agent = agent_factory()
    collected = ""
    try:
        async for event in agent.stream_async(user_input):
            if isinstance(event, dict) and "data" in event:
                token = event["data"]
                collected += token
                await bus.emit_text(token)
    except Exception as e:
        await bus.emit_error(f"{name} failed: {e}")
        raise
    finally:
        await bus.emit_tool_done(name)

    return collected


async def run_full_pipeline(bus: EventBus, question: str) -> str:
    """Discovery → Investigation → Validator → Narrative. One pass, with
    one divergence-driven re-investigation if the Validator says DIVERGE.
    Returns the final Narrative text.
    """
    plan = await _run_agent(
        bus, "discovery", build_discovery_agent,
        question, question_label=question,
    )

    findings = await _run_agent(
        bus, "investigation", build_investigation_agent,
        f"User question:\n{question}\n\nDiscovery plan:\n{plan}",
        question_label="run math on Discovery's candidates",
    )

    verdict = await _run_agent(
        bus, "validator", build_validator_agent,
        f"User question:\n{question}\n\nInvestigation findings:\n{findings}",
        question_label="cross-check the findings",
    )

    # Cheap divergence detector — if the Validator's text says DIVERGE,
    # one re-investigation pass with the verdict as a hint.
    if "DIVERGE" in verdict.upper() and "MATCH" not in verdict.upper().split("DIVERGE")[0].split("\n")[-1]:
        await bus.emit_text("\n\n_Validator reported divergence — re-running Investigation with verdict context._\n\n")
        findings = await _run_agent(
            bus, "investigation", build_investigation_agent,
            f"Original question:\n{question}\n\n"
            f"Validator flagged DIVERGE on the prior findings:\n{verdict}\n\n"
            f"Refine the investigation. Use a sibling table or finer slice.",
            question_label="refine after divergence",
        )
        verdict = await _run_agent(
            bus, "validator", build_validator_agent,
            f"User question:\n{question}\n\nRefined findings:\n{findings}",
            question_label="cross-check refined findings",
        )

    narrative = await _run_agent(
        bus, "narrative", build_narrative_agent,
        f"User question:\n{question}\n\n"
        f"Findings:\n{findings}\n\n"
        f"Validator verdict:\n{verdict}",
        question_label="write the Minister-ready brief",
    )

    return narrative


async def run_single_specialist(
    bus: EventBus,
    name: str,
    question: str,
    context: str = "",
) -> str:
    """Single-specialist routes (discovery / investigation / validation /
    narration). Each runs one agent and returns its text.
    """
    factory_map = {
        "discovery": build_discovery_agent,
        "investigation": build_investigation_agent,
        "validator": build_validator_agent,
        "narrative": build_narrative_agent,
    }
    if name not in factory_map:
        raise ValueError(f"unknown specialist: {name!r}")

    user_input = question if not context else f"Conversation context:\n{context}\n\nQuestion:\n{question}"
    return await _run_agent(bus, name, factory_map[name], user_input, question_label=question)
