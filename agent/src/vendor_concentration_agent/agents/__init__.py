"""Per-agent constructors — Discovery, Investigation, Validator, Narrative.

Each module exposes a `build_<role>_agent()` function that returns a
configured strands.Agent instance. The orchestrator wires them together.

Agents land here in Hour 3.
"""
