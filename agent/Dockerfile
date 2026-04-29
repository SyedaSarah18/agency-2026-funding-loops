# Vendor Concentration agent — FastAPI + Strands on AWS Bedrock.
# Built for AWS App Runner: linux/amd64, Python 3.11.
#
# Build context = repo ROOT (not agent/) so we can include the references/
# registry that lives at root level.
#
# Build from repo root:
#   docker build -t vendor-concentration-agent -f agent/Dockerfile .
# Run:
#   docker run -p 8000:8000 --env-file .env vendor-concentration-agent

FROM --platform=linux/amd64 python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS deps — psycopg2-binary ships its own libpq, but we still need ca-certs
# for outbound HTTPS (Bedrock, references), and curl for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: deps (cached unless requirements.txt changes)
COPY agent/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Layer 2: agent source
COPY agent/src/ /app/src/
COPY agent/api.py /app/api.py
COPY agent/pyproject.toml /app/pyproject.toml

# References registry lives at repo root.
COPY references /app/references

# uvicorn reads PYTHONPATH; src/ layout means the package is at /app/src/
ENV PYTHONPATH=/app/src \
    PORT=8000

EXPOSE 8000

# App Runner / ECS health check polls /health
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT} --log-level info"]
