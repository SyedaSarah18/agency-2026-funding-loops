"""Verify AWS Bedrock + Claude Sonnet 4.6 are reachable. Costs <$0.0001."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL  = os.environ.get("LLM_MODEL", "us.anthropic.claude-sonnet-4-6-20260101-v1:0")

print(f"Region:  {REGION}")
print(f"Model:   {MODEL}")
print(f"Calling Bedrock invoke_model …")

br = boto3.client("bedrock-runtime", region_name=REGION)
resp = br.invoke_model(
    modelId=MODEL,
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 30,
        "messages": [{"role": "user", "content": "Reply in one short sentence: are you Claude on AWS Bedrock?"}],
    }),
)
out = json.loads(resp["body"].read())
text = out.get("content", [{}])[0].get("text", "")
print(f"\n  Response: {text}")
print(f"\nOK -- Bedrock + Claude Sonnet 4.6 working from this machine.")
