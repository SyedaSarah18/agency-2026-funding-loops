# Conductor on AWS Bedrock AgentCore Runtime

The Conductor chat agent deployed to AWS Bedrock AgentCore Runtime
(`us-west-2`). Same Strands code as `agent-service/agents/conductor.py`,
but running in managed AWS infrastructure instead of a local FastAPI
process. Branch: `v3.1-agentcore`.

## Why this exists

`v3.0-atlas` runs the Conductor in-process under FastAPI on the user's
laptop. This works for the live demo and gives the lowest possible
latency. `v3.1-agentcore` proves the same agent code deploys unchanged
to AWS Bedrock AgentCore Runtime — the AWS sponsor-recommended
managed runtime for AI agents.

The frontend chat UI has a `local` / `cloud (AgentCore)` toggle so you
can demonstrate both side-by-side.

## What's deployed

- **Agent ARN:** `arn:aws:bedrock-agentcore:us-west-2:941377154016:runtime/agency26_conductor-QTN2spEIzM`
- **Region:** `us-west-2`
- **Model:** `us.anthropic.claude-sonnet-4-6` (Bedrock inference profile)
- **Tools shipped in container:** all 11 of the local Conductor's tools —
  `atlas_top_categories`, `atlas_category_detail`, `atlas_vendor_footprint`,
  `atlas_vendor_incumbency`, `atlas_region_breakdown`,
  `verify_concentration_share`, `verify_vendor_ministry_count`, `query_db`,
  `read_kb`, `list_kb`, `code_compute`.
- **Data shipped in container:** all 6 Atlas parquet files (~450 KB) under
  `atlas_data/`, all 5 KB markdown docs under `kb/`.
- **Deployment package size:** ~188 MB (Strands + Bedrock + boto3 +
  pandas + pyarrow + psycopg2-binary + our code + parquets).
- **Memory mode:** `NO_MEMORY` (session affinity gives free multi-turn).
- **Observability:** CloudWatch GenAI dashboard auto-enabled —
  https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#gen-ai-observability/agent-core

## Deployment cost

- AgentCore Runtime: ~$0.0895 per vCPU-hour + $0.00945 per GB-hour, 1-second
  granularity, billed only during active CPU. A demo session of 10 invocations
  at ~30s each ≈ $0.009 of Runtime cost.
- Bedrock model tokens: separate, billed against the existing AWS account.
- Memory/Identity/Gateway: not used. $0.

## How to redeploy

After any code change in `agent.py`, `agents/`, `tools/`, `kb/`, `atlas_data/`,
or `requirements.txt`:

```bash
cd deployment/conductor-agentcore
../../.venv/Scripts/python deploy.py
```

The script:
1. Loads AWS credentials + `PG_DSN` from the project-root `.env`.
2. Adds the venv `Scripts/` dir to `PATH` so `shutil.which("zip")` finds
   our `.venv/Scripts/zip.bat` shim (Windows only — the toolkit gates on
   the binary existing but uses Python's `zipfile` module for actual work).
3. Calls `Runtime.configure(deployment_type="direct_code_deploy", runtime_type="PYTHON_3_13")`
   to skip Docker entirely. AgentCore packages the code server-side via S3.
4. Calls `Runtime.launch(env_vars={...})` — passes `PG_DSN` so the
   deployed Conductor can hit the organizer's hosted Postgres.
5. ~3-5 min cold deploy. Subsequent deploys reuse the cached
   `dependencies.zip` if `requirements.txt` hasn't changed.

## How to invoke

CLI smoke test (uses `boto3 invoke_agent_runtime` directly — same pattern
as the frontend):

```bash
../../.venv/Scripts/python deploy.py --invoke "Show me IBM's footprint"
```

From the running frontend chat: toggle the **cloud (AgentCore)** button in
the Chat panel header. The frontend hits `/api/ask-cloud` which routes
through the FastAPI service's `/ask-cloud` endpoint, which does the boto3
invoke against the deployed Runtime.

## File layout (flat, vs. the project's nested layout)

```
deployment/conductor-agentcore/
├── agent.py              # @app.entrypoint wrapping make_conductor_agent()
├── deploy.py             # configure + launch + invoke wrapper
├── requirements.txt      # bedrock-agentcore + strands + boto3 + DB deps
├── config.py             # env-var-only (no .env in container)
├── agents/
│   └── conductor.py      # copy of the working v3.0 Conductor
├── tools/                # copies of all 5 tool modules
├── llm/                  # BedrockModel client factory
├── atlas_data/*.parquet  # 6 Atlas tables shipped in container
└── kb/*.md               # 5 knowledge-base docs shipped in container
```

Tools' `ROOT` constants flattened to `<package_root>/atlas_data` and
`<package_root>/kb` (vs. `analysis/atlas_data/` and project-root `kb/` in
the nested layout).

## What we deliberately did NOT use

- **AgentCore Gateway** — wraps external Lambdas / REST APIs as MCP tools.
  Our tools are use-case-specific in-process Python (parquet readers, verify
  functions, pandas eval, psycopg2 SQL), so wrapping them as Lambdas would
  add network hops + cold starts for negative net value. Lab 3 of the AWS
  workshop teaches this same boundary.
- **AgentCore Memory** — managed long-term + cross-session memory. We use
  AgentCore session affinity to give free in-process multi-turn instead.
  Memory is a $0.25/1k-events cost we'd pay only if we wanted recall across
  sessions (we don't, for the hackathon scope).
- **AgentCore Identity** — for OAuth/JWT inbound auth on the runtime. Not
  needed for the demo — the frontend hits the runtime via boto3 with our
  IAM credentials.
- **Bedrock Agents (the original 2023 product)** — declarative JSON agents
  with Lambda-only tools. We're using AgentCore Runtime (the newer flexible
  product) which hosts our Strands code as a container.

## Risks during demo

1. **Cold start.** First invoke after ~15 min idle adds 3-8s. Hit it with
   a warmup ping 60s before demoing.
2. **Bedrock model access.** AdministratorAccess on the IAM user is
   sufficient. Sponsor-provisioned event-day account will be pre-allowed.
3. **Network.** AgentCore is a US-East/US-West managed service. Demo on
   a hotel wifi: stable mostly, occasional lag — local backend is the
   safer option for live demo, cloud backend is the architectural-parity
   talking point.

## How to destroy

```bash
../../.venv/Scripts/agentcore destroy
```

Or via AWS CLI / Console: delete the AgentCore Runtime resource, then
the auto-created IAM role, then the S3 bucket
(`bedrock-agentcore-codebuild-sources-941377154016-us-west-2`).
