"""De GraphDB-licentie blijft uit PR-runs (Lex Bench §20.5 stap 3, testplan api V1).

`projectie-graphdb.yml` draait de projectie tegen een echte GraphDB, en GraphDB 11 schrijft alleen met de licentie uit de
environment `acceptatie`. Een PR-run hoort geen secret te krijgen. Deze toets bewaakt dat:

- het secret `GRAPHDB_LICENSE_B64` staat alleen in de uitrol (`azure-infra.yml`) en in die ene job;
- geen workflow die het secret noemt, draait op `pull_request` of `pull_request_target`, en de poort noemt het nooit;
- de job hangt aan de environment `acceptatie` en draait alleen na de merge (push naar master) of met de hand;
- GraphDB draait daar in dezelfde versie als in `deploy/azure/main.bicep`.

Alleen tekst en regex: de poorttests draaien zonder afhankelijkheden.
"""
from __future__ import annotations

import pytest

import re

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R12")

WORKFLOWS = WORTEL / ".github" / "workflows"
GEHEIM = "GRAPHDB_LICENSE_B64"
JOB_WORKFLOW = WORKFLOWS / "projectie-graphdb.yml"
TOEGESTAAN = {"azure-infra.yml", "projectie-graphdb.yml"}


def _zonder_commentaar(tekst: str) -> str:
    return re.sub(r"(?m)^\s*#.*$", "", tekst)


def _trigger(tekst: str) -> str:
    """Het blok onder `on:` tot de volgende sleutel op het hoogste niveau."""
    m = re.search(r"(?ms)^on:\s*\n(.*?)(?=^\S)", tekst + "\nX")
    return m.group(1) if m else ""


def _jobs(tekst: str) -> dict[str, str]:
    """De jobs van een workflow, met hun tekst (de sleutels op twee spaties onder `jobs:`)."""
    blok = tekst.split("\njobs:\n", 1)[1] if "\njobs:\n" in tekst else ""
    delen = re.split(r"(?m)^  ([\w-]+):\s*\n", blok)
    return {delen[i]: delen[i + 1] for i in range(1, len(delen) - 1, 2)}


def test_het_secret_staat_alleen_in_de_uitrol_en_de_projectiejob():
    noemen = {p.name for p in WORKFLOWS.glob("*.yml") if GEHEIM in _zonder_commentaar(p.read_text(encoding="utf-8"))}
    assert noemen, "de zoektocht vindt het secret nergens: dan toetst deze test niets"
    assert noemen <= TOEGESTAAN, f"de GraphDB-licentie staat in een andere workflow: {sorted(noemen - TOEGESTAAN)}"
    assert "projectie-graphdb.yml" in noemen and "poort.yml" not in noemen


def test_geen_workflow_met_het_secret_draait_op_een_pull_request():
    for pad in WORKFLOWS.glob("*.yml"):
        tekst = _zonder_commentaar(pad.read_text(encoding="utf-8"))
        if GEHEIM in tekst:
            assert not re.search(r"\bpull_request(_target)?\b", _trigger(tekst)), f"{pad.name} draait op een PR"


def test_de_projectiejob_hangt_aan_acceptatie_en_draait_alleen_na_de_merge():
    tekst = _zonder_commentaar(JOB_WORKFLOW.read_text(encoding="utf-8"))
    trigger = _trigger(tekst)
    assert re.search(r"(?m)^  push:\s*\n\s+branches:\s*\[master\]", trigger), "alleen een push naar master"
    assert re.search(r"(?m)^  workflow_dispatch:", trigger)
    assert set(re.findall(r"(?m)^  (\w+):", trigger)) == {"push", "workflow_dispatch"}, "geen andere triggers"
    met_geheim = {naam: job for naam, job in _jobs(tekst).items() if GEHEIM in job}
    assert len(met_geheim) == 1, f"de licentie hoort in precies één job: {sorted(met_geheim)}"
    [job] = met_geheim.values()
    assert re.search(r"(?m)^    environment: acceptatie\s*$", job), "de job leest de licentie uit de environment acceptatie"


def test_graphdb_draait_in_dezelfde_versie_als_de_straten():
    bicep = (WORTEL / "deploy" / "azure" / "main.bicep").read_text(encoding="utf-8")
    straat = re.search(r"param graphdbImage string = '([^']+)'", bicep)
    job = re.search(r"(?m)^\s+image:\s*(ontotext/graphdb:\S+)", JOB_WORKFLOW.read_text(encoding="utf-8"))
    assert straat and job and job.group(1) == straat.group(1), "de projectiejob draait een andere GraphDB dan de straten"


def test_de_vormtoets_ziet_een_pr_trigger():
    """De positieve controle: een workflow met `pull_request` in zijn trigger wordt herkend."""
    voorbeeld = "name: x\n\non:\n  pull_request:\n  push:\n    branches: [master]\n\njobs:\n  a:\n    runs-on: x\n"
    assert re.search(r"\bpull_request\b", _trigger(voorbeeld))
    assert set(_jobs(voorbeeld)) == {"a"}
