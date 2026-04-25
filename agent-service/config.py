"""Centralised config loaded from .env at the project root."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PG_DSN          = os.environ["PG_DSN"]
LLM_BACKEND     = os.environ.get("LLM_BACKEND", "anthropic")
LLM_MODEL       = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
AWS_REGION      = os.environ.get("AWS_REGION", "us-east-1")

# How many cycles to investigate per run (keeps demo fast)
DISCOVERY_TOP_N = int(os.environ.get("DISCOVERY_TOP_N", "20"))
NARRATIVE_TOP_N = int(os.environ.get("NARRATIVE_TOP_N", "5"))
