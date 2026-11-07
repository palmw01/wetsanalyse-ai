"""De uitrolpoort staat één keer, in `.github/actions/wacht-op-revisie`.

Hij stond eerst als eigen lus in zes workflows en liep uit elkaar: alleen azure-infra kende `ScaledToZero`
als gezond, terwijl api en graph-qa op minReplicas 0 kunnen staan. Deze tests houden de poort op één plek
en houden de rooktest erin.
"""
from __future__ import annotations

import re

import pytest

from routeboek import WORTEL

WORKFLOWS = WORTEL / ".github" / "workflows"
ACTION = WORTEL / ".github" / "actions" / "wacht-op-revisie"
GEBRUIK = "uses: ./.github/actions/wacht-op-revisie"
# Wat een revisie uitrolt: een image-swap of de app-bicep. `az containerapp job update` is een job en
# heeft geen revisie; grafana.bicep heeft een eigen HTTP-controle.
ROLT_UIT = re.compile(r"az containerapp update\b|deploy/azure/gen-deploy\.py")


def _workflows():
    return sorted(WORKFLOWS.glob("*.yml"))


def _jobs(tekst: str) -> dict[str, str]:
    """De jobs van een workflow als tekstblokken (inspringing van twee spaties onder `jobs:`)."""
    _, _, rest = tekst.partition("\njobs:\n")
    delen = re.split(r"^  ([A-Za-z0-9_-]+):\s*$", rest, flags=re.M)
    return dict(zip(delen[1::2], delen[2::2]))


@pytest.mark.parametrize("pad", _workflows(), ids=lambda p: p.name)
def test_geen_eigen_kopie_van_de_poortlus(pad):
    """Een eigen `revision show … runningState`-lus loopt vroeg of laat uit de pas met de action."""
    tekst = pad.read_text(encoding="utf-8")
    assert not re.search(r'--query\s+"properties\.runningState"', tekst), (
        f"{pad.name} heeft een eigen poortlus; gebruik {GEBRUIK}")


@pytest.mark.parametrize("pad", _workflows(), ids=lambda p: p.name)
def test_wie_uitrolt_gebruikt_de_poort(pad):
    for naam, job in _jobs(pad.read_text(encoding="utf-8")).items():
        regels = [r for r in job.splitlines() if not r.lstrip().startswith("#")]
        if not any(ROLT_UIT.search(r) for r in regels):
            continue
        assert GEBRUIK in job, f"{pad.name}: job `{naam}` rolt uit zonder de uitrolpoort"


def _gebruiken():
    return list(_gebruiken_iter())


def _gebruiken_iter():
    for pad in _workflows():
        for naam, job in _jobs(pad.read_text(encoding="utf-8")).items():
            if GEBRUIK in job:
                yield pytest.param(pad.name, naam, job, id=f"{pad.name}:{naam}")


def test_de_poort_wordt_gebruikt():
    """Zes plekken bij de invoering: drie publish-workflows, promote, rollback en azure-infra."""
    assert len([p for p in _workflows() if GEBRUIK in p.read_text(encoding="utf-8")]) >= 6


@pytest.mark.parametrize(("workflow", "naam", "job"), _gebruiken())
def test_elk_gebruik_heeft_een_checkout_en_de_rooktest(workflow, naam, job):
    """Een lokale action bestaat pas na een checkout; zonder `keten` toetst de poort de keten niet."""
    checkout = job.find("actions/checkout@")
    assert 0 <= checkout < job.find(GEBRUIK), f"{workflow}: job `{naam}` mist een checkout vóór de poort"
    blok = job[job.find(GEBRUIK):]
    blok = blok[:m.start()] if (m := re.search(r"^      - ", blok, re.M)) else blok
    assert re.search(r"^\s+keten:\s*\S", blok, re.M), f"{workflow}: job `{naam}` zonder rooktest"


def test_scaled_to_zero_telt_als_gezond():
    script = (ACTION / "wacht.sh").read_text(encoding="utf-8")
    assert re.search(r"Running\|RunningAtMaxScale\|ScaledToZero\)", script)
    assert "api/health?keten=1" in script


def test_de_health_route_kent_de_ketenstand():
    """De probes en de HEALTHCHECK gebruiken `/api/health` zonder parameter; alleen `?keten` mag 503 geven."""
    route = (WORTEL / "frontend" / "app" / "api" / "health" / "route.ts").read_text(encoding="utf-8")
    assert 'searchParams.has("keten")' in route
    assert "503" in route
