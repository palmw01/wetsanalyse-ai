# Self-contained image voor de BWB-importer: de jobs op Azure starten `python -m app.main`.
# ── Builder ───────────────────────────────────────────────────────────────────
# Zoals api/Dockerfile: uv leeft alleen in deze stage en bouwt de .venv uit de lock; de runtime krijgt alleen die venv.
# Supply chain (SonarQube S8541/S8544): `--frozen` installeert precies de versies uit uv.lock, die de poort en pip-audit
# al toetsten, en `--no-build` bouwt niets vanaf de bron behalve onze eigen pakketten (`[tool.uv] no-binary-package`).
# De buildcontext is de projectroot (zoals bij api en graph-qa): de BWB-lezer en de officiële XSD's staan in
# packages/bronmodel (`bronmodel.bwb`), gedeeld met graph-qa.
FROM python:3.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /bin/uv

# De systeem-Python van de base: dan wijst de .venv naar /usr/local/bin/python3.15, dat ook in de runtime bestaat.
# Het project staat hier zoals in de repo (`../../packages/bronmodel` moet binnen het bestandssysteem blijven); de venv
# komt meteen op zijn plek in de runtime, /app/.venv. Alles gaat er niet-editable in, dus niets wijst terug naar /src.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src/tools/bwb-import

# Alleen de runtime-dependencies (de extra `dev` – pytest, ruff, black – blijft buiten de image). lxml-wheels bundelen
# libxml2/libxslt.
COPY tools/bwb-import/pyproject.toml tools/bwb-import/uv.lock ./
COPY packages/bronmodel /src/packages/bronmodel
RUN uv sync --frozen --no-build --no-editable

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.15-slim AS runtime

WORKDIR /app

# OS-pakketten patchen (BIO2 / ISO 27002:2022 §8.8), zoals api/Dockerfile en frontend/Dockerfile.
# De base-image loopt achter op Debian-security-updates; zonder upgrade blokkeert de Trivy-gate
# de build op CVE's waarvoor de gepatchte pakketversie er al is.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# De runtime installeert niets: pip eruit, zoals de frontend npm weghaalt. Een achterlopende pip uit de base (en de
# CycloneDX-SBOM van zijn vendored deps, `pip/_vendor/bom.cdx.json`, die hier ooit setuptools 70.3.0 en msgpack 1.1.2
# als kwetsbaar liet melden) leverde anders Trivy-alerts op zonder ooit te draaien.
RUN rm -rf /usr/local/lib/python3*/site-packages/pip /usr/local/lib/python3*/site-packages/pip-*.dist-info \
    /usr/local/bin/pip /usr/local/bin/pip3*

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Applicatiecode.
COPY tools/bwb-import/app ./app

# Niet als root (SEC-12), net als de andere images. De importer schrijft alleen zijn downloadcache (`BWB_DATA_DIR`,
# standaard /app/data); die map is van de gebruiker.
RUN useradd --no-create-home --uid 10003 --gid 0 importer \
 && mkdir -p /app/data && chown 10003:0 /app/data
USER 10003

CMD ["python", "-m", "app.main"]
