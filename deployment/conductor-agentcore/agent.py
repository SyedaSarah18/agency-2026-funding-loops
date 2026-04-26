"""AgentCore Runtime entrypoint for the Conductor agent.

Matches the pattern from AWS Bedrock AgentCore Workshop Lab 4:
- BedrockAgentCoreApp() wraps a Strands agent
- @app.entrypoint decorates the invocation handler
- payload = {"prompt": "..."}; response = streamed text
- Container exposes POST /invocations on port 8080 (auto-wired by the SDK)

Tools, agent, and knowledge base ship in the container — no Gateway needed
since our tools are use-case-specific in-process Python (parquet reads,
verify_* against Postgres, code_compute pandas sandbox).

Session affinity: AgentCore Runtime routes the same runtimeSessionId to the
same container instance for ~8 hours, so a single global Conductor agent
naturally retains conversation context across turns within a session.
For cross-session memory, switch to AgentCore Memory (deferred).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the package directory importable so `from agents.conductor import ...` works.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from agents.conductor import make_conductor_agent

app = BedrockAgentCoreApp()

# Single global Conductor — session affinity keeps it stateful per session.
_conductor = make_conductor_agent()


@app.entrypoint
async def invoke(payload, context=None):
    """Stream the Conductor's response to a single prompt.

    payload schema:
        {"prompt": "<user question>"}

    Yields token chunks + tool-use events the client SSE-renders.
    """
    prompt = (payload or {}).get("prompt", "")
    if not prompt.strip():
        yield {"error": "empty prompt"}
        return

    async for event in _conductor.stream_async(prompt):
        # Re-emit only the event keys the client UI cares about; AgentCore
        # serializes whatever we yield as a JSON line in the SSE stream.
        if "current_tool_use" in event:
            tu = event["current_tool_use"] or {}
            yield {
                "type": "tool",
                "name": tu.get("name"),
                "input_preview": str(tu.get("input", ""))[:200],
            }
        elif "data" in event:
            chunk = event.get("data", "")
            if chunk:
                yield {"type": "text", "chunk": chunk}
        elif "result" in event:
            yield {"type": "done"}
            return
        elif "force_stop" in event:
            yield {"type": "error", "message": "agent force-stopped"}
            return


if __name__ == "__main__":
    app.run()
