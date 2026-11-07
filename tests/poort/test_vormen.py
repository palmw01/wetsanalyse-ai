"""Regels uit de CLAUDE-bestanden die in code kunnen staan, in plaats van alleen in tekst.

Elke regel hier heeft ooit iets gekost, en breekt zonder test stil. De bestanden worden als tekst gelezen.
"""
from __future__ import annotations

import re

import pytest

from routeboek import FRONTEND, WORTEL

BFF = FRONTEND / "app" / "api"
WORKFLOWS = WORTEL / ".github" / "workflows"
PUBLISH = ("api", "frontend", "graph-qa", "bwb-import")


def _serverbestanden():
    yield from (p for p in BFF.rglob("*.ts") if ".test." not in p.name)
    yield FRONTEND / "lib" / "server.ts"


def test_elke_upstream_fetch_draagt_de_trace():
    """Zonder `metTrace` komt telemetrie gewoon binnen, alleen het verband tussen de diensten ontbreekt."""
    fout = []
    for pad in _serverbestanden():
        s = pad.read_text(encoding="utf-8")
        for m in re.finditer(r"\bfetch\(", s):
            aanroep = s[m.start():m.start() + 500]
            if "metTrace(" not in aanroep:
                fout.append(f"{pad.relative_to(WORTEL)}:{s[:m.start()].count(chr(10)) + 1}")
    assert not fout, f"fetch zonder metTrace: {fout}"


def test_geen_kale_encode_in_een_upstream_pad():
    """`pathSegment` weigert `..`; `encodeURIComponent` laat het door. In een query is hij wel juist."""
    fout = [
        f"{p.relative_to(WORTEL)}: {m.group(0)}"
        for p in BFF.rglob("route.ts")
        for m in re.finditer(r"/\$\{encodeURIComponent\([^)]*\)\}", p.read_text(encoding="utf-8"))
    ]
    assert not fout, f"gebruik pathSegment: {fout}"


def test_terugrollen_blijft_kunnen():
    """`rollback.yml` werkt alleen als oude revisies blijven staan."""
    bicep = (WORTEL / "deploy" / "azure" / "main.bicep").read_text(encoding="utf-8")
    assert bicep.count("maxInactiveRevisions: 5") >= 3


@pytest.mark.parametrize("naam", PUBLISH)
def test_een_build_per_image_tegelijk(naam):
    """Twee builds pushen allebei `latest`; afbreken eindigt op `MANIFEST_UNKNOWN`."""
    tekst = (WORKFLOWS / f"{naam}-docker-publish.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s*cancel-in-progress: false", tekst, re.M)


def test_de_retentie_raakt_productie_niet():
    tekst = (WORKFLOWS / "ghcr-cleanup.yml").read_text(encoding="utf-8")
    regels = re.findall(r"exclude-tags:\s*(.+)", tekst)
    assert regels
    for regel in regels:
        assert {"latest", "prd", "prd-vorige"} <= {t.strip() for t in regel.strip("'\" ").split(",")}


def test_de_waarschuwingsdrempel_is_gelijk():
    api = (WORTEL / "api" / "app" / "verbruik_contracts.py").read_text(encoding="utf-8")
    frontend = (FRONTEND / "lib" / "tokenbudget.ts").read_text(encoding="utf-8")
    drempel = re.search(r"^WAARSCHUWINGSDREMPEL = (\d+)", api, re.M)
    assert drempel and f"WAARSCHUWINGSDREMPEL = {drempel.group(1)};" in frontend


def test_een_client_component_komt_niet_bij_de_tokens():
    """`lib/config` en `lib/server` dragen de server-tokens."""
    fout = []
    for pad in [*(FRONTEND / "components").rglob("*.tsx"), *(FRONTEND / "app").rglob("*.tsx")]:
        s = pad.read_text(encoding="utf-8")
        if s.lstrip().startswith(('"use client"', "'use client'")) and re.search(
                r'from\s+"@/lib/(config|server)"', s):
            fout.append(str(pad.relative_to(WORTEL)))
    assert not fout, f"client component importeert serverconfig: {fout}"


def test_geen_eigen_image_draait_als_root():
    """SEC-12: elk eigen image zet een USER vóór zijn startcommando; zonder draait de container als root."""
    dockerfiles = [p for p in WORTEL.rglob("Dockerfile") if "node_modules" not in p.parts and ".venv" not in p.parts]
    assert len(dockerfiles) >= 4, dockerfiles
    for pad in dockerfiles:
        regels = [r.strip() for r in pad.read_text(encoding="utf-8").splitlines()]
        start = max(i for i, r in enumerate(regels) if r.startswith(("CMD", "ENTRYPOINT")))
        gebruikers = [r.split(None, 1)[1] for r in regels[:start] if r.startswith("USER ")]
        assert gebruikers and gebruikers[-1] not in ("root", "0"), pad.relative_to(WORTEL)
