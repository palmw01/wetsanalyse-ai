# ── Builder ───────────────────────────────────────────────────────────────────
# Zoals api/Dockerfile: uv leeft alleen in deze stage en bouwt de .venv uit de lock; de runtime krijgt alleen die venv.
# Supply chain (SonarQube S8541/S8544): `--frozen` installeert precies de versies uit uv.lock, die de poort en pip-audit
# al toetsten, en `--no-build` bouwt niets vanaf de bron behalve onze eigen pakketten (`[tool.uv] no-binary-package`).
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /bin/uv

# De systeem-Python van de base: dan wijst de .venv naar /usr/local/bin/python3.14, dat ook in de runtime bestaat.
# Het project staat hier zoals in de repo (`../../packages/bronmodel` moet binnen het bestandssysteem blijven); de venv
# komt meteen op zijn plek in de runtime, /app/.venv. Alles gaat er niet-editable in, dus niets wijst terug naar /src.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src/tools/graph-qa

# Eerst alleen de manifesten (betere layer-cache): de dependencies zonder het project zelf.
#  - 'otel': OTel werkt zodra OTEL_EXPORTER_OTLP_ENDPOINT gezet is; zonder degradeert observability naar alleen
#    JSON-logs zónder trace_id.
#  - 'nlp': spaCy voor de taalanalyse van de hybride JAS-pijplijn (ADR-002). Zonder draait de annotatieketen
#    gedegradeerd (alleen tokens), zichtbaar in de run-provenance.
# Eén lijst, één bron van waarheid (pyproject.toml + uv.lock): een handmatig herhaalde lijst liep uit de pas, waardoor
# langgraph-checkpoint-postgres en psycopg ontbraken en de agent bij een gezette CHECKPOINT_DB_URL omviel.
COPY tools/graph-qa/pyproject.toml tools/graph-qa/uv.lock tools/graph-qa/taalmodel.txt ./
COPY packages/bronmodel /src/packages/bronmodel
RUN uv sync --frozen --no-build --extra otel --extra nlp --no-install-project --no-editable

COPY tools/graph-qa/agent/ agent/
COPY tools/graph-qa/api/ api/

# Nu het project zelf, als gewone (niet-editable) installatie in de venv: `eval/run_eval.py` importeert `agent` uit de
# venv, net als voorheen met `pip install .`.
RUN uv sync --frozen --no-build --extra otel --extra nlp --no-editable

# Het Nederlandse md-model van spaCy staat niet op PyPI en niet in uv.lock: taalmodel.txt noemt URL en hash.
# `tests/runs/test_deploy_drift.py` bewaakt dat de image en de poort dit bestand gebruiken.
# Ná de laatste sync: `uv sync` haalt weg wat niet in de lock staat.
RUN uv pip install --python /app/.venv/bin/python --no-deps --no-build --require-hashes -r taalmodel.txt

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.14-slim AS runtime

WORKDIR /app

# OS-pakketten patchen (BIO2 / ISO 27002:2022 §8.8), zoals api/Dockerfile en frontend/Dockerfile.
# De base-image loopt achter op Debian-security-updates; zonder upgrade blokkeert de Trivy-gate de
# build op een HIGH-CVE waarvoor de patch al in Debian staat.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# De runtime installeert niets: pip eruit, zoals de frontend npm weghaalt. Een achterlopende pip uit de base (en de
# CycloneDX-SBOM van zijn vendored deps, `pip/_vendor/bom.cdx.json`) leverde anders Trivy-alerts op zonder ooit te draaien.
RUN rm -rf /usr/local/lib/python3*/site-packages/pip /usr/local/lib/python3*/site-packages/pip-*.dist-info \
    /usr/local/bin/pip /usr/local/bin/pip3*

COPY --from=builder /app/.venv /app/.venv
COPY tools/graph-qa/pyproject.toml ./
COPY tools/graph-qa/agent/ agent/
COPY tools/graph-qa/api/ api/

# De eval-harnas reist mee in het image, en dat is geen slordigheid. De graaf is `external: false`
# — alleen bereikbaar bínnen de container-apps-omgeving — dus de enige plek waar de annotatieketen
# tegen de échte wettekst te meten is, is een job in diezelfde omgeving (`${appName}-eval` in
# deploy/azure/main.bicep). Die job draait dit image met een ander commando.
#
# Het is een paar kilobyte Python plus twee jsonl-sets en het draait nooit vanzelf: de service-CMD
# hieronder raakt het niet aan. `tests/` gaat bewust NIET mee — die importeert run_eval alleen in
# de `--offline`-tak, en die tak hoort thuis op een ontwikkelmachine, niet in productie.
COPY tools/graph-qa/eval/ eval/

ENV PATH="/app/.venv/bin:$PATH"

# Non-root + /data voor de durable checkpointer-db (named volume; CHECKPOINT_DB_PATH=/data/...).
#
# `chmod -R a+rX /app` maakt de build onafhankelijk van de umask van wie 'm bouwt: COPY neemt de
# bronpermissies over, dus met een strakke umask (077) belandt de code als 0600/root in de image en
# kan appuser 'm niet lezen – de container faalt dan op "PermissionError: /app/api/__init__.py".
# In CI (umask 022) valt dat niet op, lokaal wel. a+rX zet leesrechten en houdt +x alleen op mappen.
RUN useradd -u 10001 -m appuser && mkdir -p /data && chown appuser:appuser /data \
    && chmod -R a+rX /app
USER appuser

# De commit waaruit dit image is gebouwd, voor de melding van wat er in het image zit (`agent/imagemelding.py`,
# ADR-016 §B1). Onderaan, zodat een nieuwe commit geen laag hierboven ongeldig maakt.
ARG REVISIE=""
ENV LEX_REVISIE=${REVISIE}

EXPOSE 8080

# `--timeout-graceful-shutdown`: na zoveel seconden sluit uvicorn de open SSE-verbindingen (een kijker haakt opnieuw aan
# op een andere replica), waarna de lifespan de lopende beurten laat afronden (`runstore.postgres.DRAIN_S`).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--timeout-graceful-shutdown", "120"]
