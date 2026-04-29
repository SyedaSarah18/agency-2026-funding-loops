"""Tolerant JSON extraction. Models often wrap JSON in markdown fences or
prepend a sentence; this strips both and pulls out the right object.

The tricky case: Strands streams tool-result dicts as "data" events
alongside the agent's final response JSON. We must prefer agent-output
objects (those with `headline`, `candidates`, `verdict`, `metrics`, etc.)
over tool-result objects (those with `call_id`, `formula_id`, `value`, ...).
Fall back to the LARGEST object when no agent-output keys are found.
"""

from __future__ import annotations

import json
import re

# Keys that appear in agent final responses but not in tool-result dicts.
_AGENT_KEYS = {"headline", "candidates", "verdict", "scope", "metrics",
               "checks_run", "supporting_facts", "next_actions", "raw_text"}


def _iter_json_objects(text: str):
    """Yield every valid top-level JSON object found in text, in order."""
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        # Found a '{'; try to parse from here, trimming from the end
        fragment = text[i:]
        for end in range(len(fragment), 0, -1):
            try:
                v = json.loads(fragment[:end])
                if isinstance(v, dict):
                    yield v
                    i += end  # advance past this object
                    break
            except json.JSONDecodeError:
                continue
        else:
            i += 1  # no valid object starting here; move on


def extract_json(text: str) -> dict | None:
    """Return the most-agent-like JSON object found in `text`, or None.

    Priority:
      1. If the whole text parses cleanly as one object, return it.
      2. Prefer objects whose keys overlap with agent output schemas
         (headline / candidates / verdict / metrics / etc.).
      3. Fall back to the largest object found — the agent's final
         response is always larger than the tool-result snippets mixed in.
    """
    if not text:
        return None
    text = text.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Fast path: whole text is a single clean object
    try:
        v = json.loads(text)
        if isinstance(v, dict):
            return v
    except json.JSONDecodeError:
        pass

    all_objects = list(_iter_json_objects(text))
    if not all_objects:
        return None

    # Prefer agent-output objects
    agent_objects = [o for o in all_objects if _AGENT_KEYS & o.keys()]
    if agent_objects:
        # Among agent objects, take the largest (most complete)
        return max(agent_objects, key=lambda o: len(json.dumps(o)))

    # Fall back to largest object overall
    return max(all_objects, key=lambda o: len(json.dumps(o)))
