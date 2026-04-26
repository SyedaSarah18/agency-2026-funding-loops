"""Strands model-client factory.

Returns the right Strands BedrockModel (or Anthropic fallback) based on .env config.
Agent code stays identical regardless of backend.
"""
from __future__ import annotations

from strands.models import BedrockModel

from config import LLM_BACKEND, LLM_MODEL, AWS_REGION


def make_model():
    """Construct the Strands model for the configured backend."""
    if LLM_BACKEND == "bedrock":
        return BedrockModel(
            model_id=LLM_MODEL,
            region_name=AWS_REGION,
            streaming=True,
            temperature=0.3,
        )
    if LLM_BACKEND == "anthropic":
        # Fallback path if someone wants to test without AWS.
        from strands.models.anthropic import AnthropicModel
        from config import ANTHROPIC_KEY
        return AnthropicModel(
            client_args={"api_key": ANTHROPIC_KEY},
            model_id=LLM_MODEL.replace("us.anthropic.", "").rsplit("-", 2)[0],  # strip bedrock prefix
            max_tokens=4096,
            params={"temperature": 0.3},
        )
    raise ValueError(f"Unknown LLM_BACKEND: {LLM_BACKEND}")
