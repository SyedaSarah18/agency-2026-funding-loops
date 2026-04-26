"""One-shot deploy script for the Conductor AgentCore Runtime.

Usage:
  python deploy.py            # configure + launch
  python deploy.py --status   # check status
  python deploy.py --invoke "Show me IBM's footprint"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 stdout BEFORE the toolkit imports rich — rich prints emoji error
# messages that otherwise crash on Windows cp1252 console.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent

# Pull AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_REGION + PG_DSN out of
# the project-root .env so boto3 (used by the Runtime starter toolkit) finds
# credentials. .env is gitignored; nothing leaks.
load_dotenv(PROJECT_ROOT / ".env")

# Add the venv Scripts dir to PATH so shutil.which() inside the toolkit finds
# our .bat shims (e.g. zip.bat — the toolkit gates on a `zip` binary existing
# even though the actual zip work uses Python's zipfile module). This is the
# Windows equivalent of putting /usr/local/bin on PATH.
if sys.platform == "win32":
    venv_scripts = str(Path(sys.executable).resolve().parent)
    if venv_scripts not in os.environ.get("PATH", ""):
        os.environ["PATH"] = venv_scripts + os.pathsep + os.environ.get("PATH", "")

from bedrock_agentcore_starter_toolkit import Runtime  # noqa: E402

os.chdir(HERE)  # configure + launch read paths relative to cwd

REGION = os.environ.get("AWS_REGION", "us-west-2")
AGENT_NAME = "agency26_conductor"


def _read_pg_dsn_from_env_file() -> str:
    """Pull PG_DSN from the project root .env when not in process env."""
    env_file = HERE.parent.parent / ".env"
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
        if line.startswith("PG_DSN="):
            return line.split("=", 1)[1].strip()
    return ""


PG_DSN = os.environ.get("PG_DSN") or _read_pg_dsn_from_env_file()
if not PG_DSN:
    sys.exit("ERROR: no PG_DSN in env or in ../../.env")

RUNTIME_ENV = {
    "PG_DSN": PG_DSN,
    "AWS_REGION": REGION,
    "LLM_BACKEND": "bedrock",
    "LLM_MODEL": "us.anthropic.claude-sonnet-4-6",
}


def cmd_deploy():
    runtime = Runtime()

    print(f"[1/2] Configuring AgentCore Runtime '{AGENT_NAME}' (region={REGION})...")
    runtime.configure(
        entrypoint="agent.py",
        agent_name=AGENT_NAME,
        requirements_file="requirements.txt",
        region=REGION,
        protocol="HTTP",
        memory_mode="NO_MEMORY",
        auto_create_ecr=True,
        auto_create_execution_role=True,
        auto_create_s3=True,
        # direct_code_deploy uploads a zip to S3 instead of requiring a local
        # Docker daemon to build a container image. AgentCore handles the
        # packaging on the server side. Right choice for Windows dev machines
        # that don't have Docker Desktop installed.
        deployment_type="direct_code_deploy",
        runtime_type="PYTHON_3_13",
    )
    print("  configured. Generated .bedrock_agentcore.yaml + Dockerfile.")

    print("\n[2/2] Launching (CodeBuild remote build, ~8-12 min cold start)...")
    masked = {k: ("<...>" if k == "PG_DSN" else v) for k, v in RUNTIME_ENV.items()}
    print(f"  env vars: {masked}")
    result = runtime.launch(env_vars=RUNTIME_ENV)
    print("\nLaunch result:")
    print(f"  agent_arn:  {getattr(result, 'agent_arn', None)}")
    print(f"  agent_id:   {getattr(result, 'agent_id', None)}")
    print(f"  ecr_uri:    {getattr(result, 'ecr_uri', None)}")
    print("\nDone. Smoke-test with: python deploy.py --invoke 'hello'")


def cmd_status():
    runtime = Runtime()
    status = runtime.status()
    print(json.dumps(status.model_dump() if hasattr(status, "model_dump") else status,
                     indent=2, default=str))


def cmd_invoke(prompt: str):
    """Production-style invoke via boto3 — same pattern the frontend will use.

    Reads the deployed agent ARN from .bedrock_agentcore.yaml so this works
    after a fresh shell with no Runtime() session state.
    """
    import uuid
    import boto3
    import yaml

    cfg = yaml.safe_load((HERE / ".bedrock_agentcore.yaml").read_text())
    default_agent_name = cfg.get("default_agent")
    agent_cfg = cfg["agents"][default_agent_name]
    agent_arn = agent_cfg["bedrock_agentcore"]["agent_arn"]
    print(f"Invoking {default_agent_name} ({agent_arn.split('/')[-1]}) with prompt: {prompt!r}")

    client = boto3.client("bedrock-agentcore", region_name=REGION)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=str(uuid.uuid4()).replace("-", "") + "x" * 33,  # AgentCore wants >=33 chars
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
        qualifier="DEFAULT",
    )
    print("--- streaming response ---")
    for chunk in resp.get("response", []):
        sys.stdout.write(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
        sys.stdout.flush()
    print()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--status", action="store_true")
    p.add_argument("--invoke", type=str, default=None)
    args = p.parse_args()
    if args.status:
        cmd_status()
    elif args.invoke:
        cmd_invoke(args.invoke)
    else:
        cmd_deploy()
