"""Strands @tool wrappers around the deterministic math layer.

Each tool here is a thin wrapper that:
  1. takes simple arg types friendly to the LLM tool-call schema
  2. delegates to a math_layer function
  3. returns the MathResult so the agent can read .value AND the trace bus
     can capture .sql / .source_rows / .references for the SSE feed.

Tools land here in Hour 3.
"""
