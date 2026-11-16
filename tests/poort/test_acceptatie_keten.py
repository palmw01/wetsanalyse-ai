"""Het ketenscenario op acceptatie: het accounttoken blijft uit PR-runs, en de job is nooit groen zonder werk.

`acceptatie-keten.yml` logt in met `WA_ACC_TOKEN`, het accounttoken van de gebruiker zelf (Lex Bench §20.5 stap 5,
keten 3). Deze toets bewaakt:

- het secret staat alleen in die workflow, en die draait nooit op `pull_request` of `pull_request_target`;
- beide jobs hangen aan de environment `acceptatie`;
- ontbreekt het token, dan meldt `voorwaarde` dat en wordt `keten` overgeslagen (grijs), niet groen gedraaid;
- de URL komt uit Azure en wordt gemaskeerd: geen hostnaam in de repo of in de log;
- het scenario werkt alleen onder het voorvoegsel `lex-bench-keten · `, en dat voorvoegsel kent de vangrail.

Alleen tekst en regex: de poorttests draaien zonder afhankelijkheden.
"""
from __future__ import annotations

import re

import pytest

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R19", laag=2)

WORKFLOWS = WORTEL / ".github" / "workflows"
GEHEIM = "WA_ACC_TOKEN"
WORKFLOW = WORKFLOWS / "acceptatie-keten.yml"
MCP = WORTEL / "tools" / "wetsanalyse-acceptatie-mcp" / "src"


def _zonder_commentaar(tekst: str) -> str:
    return re.sub(r"(?m)^\s*#.*$", "", tekst)


def _trigger(tekst: str) -> str:
    m = re.search(r"(?ms)^on:\s*\n(.*?)(?=^\S)", tekst + "\nX")
    return m.group(1) if m else ""


def _jobs(tekst: str) -> dict[str, str]:
    blok = tekst.split("\njobs:\n", 1)[1] if "\njobs:\n" in tekst else ""
    delen = re.split(r"(?m)^  ([\w-]+):\s*\n", blok)
    return {delen[i]: delen[i + 1] for i in range(1, len(delen) - 1, 2)}


def test_het_token_staat_alleen_in_de_ketenworkflow():
    noemen = {p.name for p in WORKFLOWS.glob("*.yml") if GEHEIM in _zonder_commentaar(p.read_text(encoding="utf-8"))}
    assert noemen == {WORKFLOW.name}, f"het accounttoken staat in een andere workflow: {sorted(noemen)}"


def test_nooit_op_een_pull_request():
    trigger = _trigger(_zonder_commentaar(WORKFLOW.read_text(encoding="utf-8")))
    assert not re.search(r"\bpull_request(_target)?\b", trigger)
    assert set(re.findall(r"(?m)^  (\w+):", trigger)) == {"workflow_run", "workflow_dispatch"}


def test_zonder_token_overgeslagen_en_niet_groen():
    jobs = _jobs(_zonder_commentaar(WORKFLOW.read_text(encoding="utf-8")))
    assert set(jobs) == {"voorwaarde", "keten"}
    for naam, job in jobs.items():
        assert re.search(r"(?m)^    environment: acceptatie\s*$", job), f"{naam} hangt niet aan acceptatie"
    assert "::notice::WA_ACC_TOKEN ontbreekt" in jobs["voorwaarde"] and "token=nee" in jobs["voorwaarde"]
    assert re.search(r"(?m)^    if: \$\{\{ needs\.voorwaarde\.outputs\.token == 'ja' \}\}\s*$", jobs["keten"]), \
        "de job keten draait alleen met een token; anders is hij overgeslagen, niet groen"
    # Een stap die zichzelf overslaat (`if: env.X != ''` of `exit 0` zonder token) zou de job groen laten zonder werk.
    assert "exit 0" not in jobs["keten"] and not re.search(r"(?m)^\s+if:", jobs["keten"].split("steps:", 1)[1])


def test_geen_hostnaam_en_de_url_gemaskeerd():
    tekst = _zonder_commentaar(WORKFLOW.read_text(encoding="utf-8"))
    assert re.findall(r"https://[^\s\"']+", tekst) == ["https://$fqdn"], "de URL komt uit Azure, niet uit de repo"
    assert 'echo "::add-mask::$fqdn"' in tekst


def test_het_scenario_werkt_onder_een_eigen_voorvoegsel_dat_de_vangrail_kent():
    runruimte = (MCP / "runruimte.ts").read_text(encoding="utf-8")
    keten = (MCP / "keten.ts").read_text(encoding="utf-8")
    voorvoegsels = re.search(r"VOORVOEGSELS = \[([^\]]+)\]", runruimte).group(1)
    assert voorvoegsels.split(",")[0].strip() == '"lex-bench-keten · "'
    assert "export const KETEN = VOORVOEGSELS[0];" in keten
    # Geen bulkroute en geen eigen DELETE: verwijderen gaat alleen via voerUit, langs de vangrail.
    assert '"DELETE"' not in keten.replace('toetsVerwijderen(c, "DELETE"', "")
    assert "/verwijderen\"" not in keten.replace('toetsVerwijderen(c, "POST", "/api/gesprekken/verwijderen"', "")
