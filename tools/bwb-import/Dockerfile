# Self-contained image voor de BWB-importer: de jobs op Azure starten `python -m app.main`.
FROM python:3.14-slim

WORKDIR /app

# OS-pakketten patchen (BIO2 / ISO 27002:2022 §8.8), zoals api/Dockerfile en frontend/Dockerfile.
# De base-image loopt achter op Debian-security-updates; zonder upgrade blokkeert de Trivy-gate
# de build op CVE's waarvoor de gepatchte pakketversie er al is.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Pip eerst upgraden en zijn vendored SBOM weghalen — zelfde fix als in api/Dockerfile en
# tools/graph-qa/Dockerfile, dit was de derde plek die hem nodig had. pip 26.x bakt een
# CycloneDX-SBOM van zijn eigen vendored deps mee (`pip/_vendor/bom.cdx.json`) die Trivy als
# pakketinventaris leest: die meldde hier setuptools 70.3.0 (CVE-2025-47273, CVE-2026-59890) en
# msgpack 1.1.2 (GHSA-6v7p-g79w-8964) terwijl geen van beide als pakket geïnstalleerd is.
RUN pip install --no-cache-dir --upgrade pip 'setuptools>=83.0.0' \
 && rm -f /usr/local/lib/python3.14/site-packages/pip/_vendor/bom.cdx.json

# Dependencies (betere layer-caching). lxml-wheels bundelen libxml2/libxslt. De buildcontext is de projectroot (zoals
# bij api en graph-qa): de BWB-lezer en de officiële XSD's staan in packages/bronmodel (`bronmodel.bwb`), gedeeld met
# graph-qa. requirements.txt noemt hem als `../../packages/bronmodel[bwb]`; vanuit /app is dat /packages/bronmodel.
COPY packages/bronmodel /packages/bronmodel
COPY tools/bwb-import/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Applicatiecode.
COPY tools/bwb-import/app ./app

# Niet als root (SEC-12), net als de andere images. De importer schrijft alleen zijn downloadcache (`BWB_DATA_DIR`,
# standaard /app/data); die map is van de gebruiker.
RUN useradd --no-create-home --uid 10003 --gid 0 importer \
 && mkdir -p /app/data && chown 10003:0 /app/data
USER 10003

CMD ["python", "-m", "app.main"]
