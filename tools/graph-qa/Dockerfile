# Build-context = tools/graph-qa
# Bouwen: docker build -f tools/graph-qa/Dockerfile -t graph-qa tools/graph-qa
# CI (graph-qa-docker-publish.yml) pusht naar GHCR; Portainer/ACA pullen :latest.

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_PYTHON_PREFERENCE=only-system

WORKDIR /app

# Alleen de manifesten → betere layer-cache. package=false in pyproject.toml zodat
# uv de broncode (agent/api/) nog niet nodig heeft in deze stage.
COPY pyproject.toml uv.lock /app/

# --extra otel: OTel-pakketten zodat tracing werkt zodra OTEL_EXPORTER_OTLP_ENDPOINT
# gezet is; zonder dat endpoint is OTel een no-op.
RUN uv sync --extra otel --frozen

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# OS-pakketten patchen (BIO2 / ISO 27002:2022 §8.8).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Pip + setuptools upgraden: base-image shipt een gebundelde setuptools die kwetsbaar
# kan zijn (CVE-2025-47273 path traversal, CVE-2024-6345 unicode normalization).
RUN pip install --no-cache-dir --upgrade 'pip>=26.1' 'setuptools>=78.1.1'

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY agent/ agent/
COPY api/ api/

RUN useradd --no-create-home --uid 10001 --gid 0 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data \
    && chgrp -R 0 /app && chmod -R g=u /app
ENV HOME=/tmp \
    PATH="/app/.venv/bin:$PATH"
USER 10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
