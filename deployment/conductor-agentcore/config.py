"""Config for AgentCore deployment.

Env vars are injected by `Runtime.launch(env_vars={...})` at deploy time.
NO .env file in the container.
"""
from __future__ import annotations

import os

PG_DSN          = os.environ["PG_DSN"]
LLM_BACKEND     = os.environ.get("LLM_BACKEND", "bedrock")
LLM_MODEL       = os.environ.get("LLM_MODEL", "us.anthropic.claude-sonnet-4-6")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
AWS_REGION      = os.environ.get("AWS_REGION", "us-west-2")

DISCOVERY_TOP_N = int(os.environ.get("DISCOVERY_TOP_N", "3"))
NARRATIVE_TOP_N = int(os.environ.get("NARRATIVE_TOP_N", "3"))
