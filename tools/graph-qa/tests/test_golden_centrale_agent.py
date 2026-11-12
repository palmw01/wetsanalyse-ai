"""De agentset (ADR-016 §A6, stap M0): de vorm van `eval/golden_centrale_agent.jsonl`.

De set beschrijft het doel van de centrale agent en is de maat voor elke ronde van de meetlus. Een rij die van vorm
verandert, maakt rondes onvergelijkbaar; deze test houdt de groepen, de velden en de namen vast. Hij draait de
opdrachten niet: dat doet de meting op acceptatie.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
from bronmodel.connectors import CONNECTORS

from agent.sjablonen import SJABLONEN
from agent.specialists import SPECIALISTS
from agent.tools import JAS_TOOLS, TOOLS

EVAL = Path(__file__).resolve().parents[1] / "eval"
SET = EVAL / "golden_centrale_agent.jsonl"


def _lees(pad: Path) -> list[dict]:
    return [json.loads(r) for r in pad.read_text(encoding="utf-8").splitlines() if r.strip() and not r.startswith("#")]


ALLES = _lees(SET)
WERKGEBIED = next(r for r in ALLES if r["id"] == "_werkgebied")
RIJEN = [r for r in ALLES if r["id"] != "_werkgebied"]
PER_ID = {r["id"]: r for r in RIJEN}

#: §A6, de tabel met groepen.
GROEPEN = {"enkelvoudig": 10, "een_subagent": 5, "meer_subagents": 6, "vraag_omhoog": 4, "vervolg": 5}
VELDEN = {"route", "route_code", "subagents", "profielen", "tools_verplicht", "tools_verboden", "vraag_omhoog",
          "sjabloon", "bevestiging", "regisseur"}
#: Tools die ADR-016 toevoegt en die er nu nog niet zijn (A1, A4, A5). Komt er een bij in het ADR, dan hier ook.
NIEUW = {"subagent", "rapport", "regie_plan", "delegatie_stand", "beantwoord_kaart", "laad_skill", "lees_skill"}
#: Geen tool maar een keten: verboden waar Lex vóór de poort van de jurist niet mag annoteren.
KETENS = {"annoteer"}
#: Routes in code die niet in de routeringsset staan: de getypte opdracht aan de regisseur (de ingang van de run, vóór
#: de supervisor) en het antwoord op een keuzekaart (een klik met een vaste actie).
ROUTES_BUITEN_DE_SET = {"regie", "keuze"}
#: `centraal` is het profiel van de centrale agent zelf (A2) en bestaat pas na A1.
PROFIELEN = set(SPECIALISTS) | {"centraal"}
#: De bepalingen van de voorbeelden en de evals in de skill: de set gebruikt andere (§A6).
SKILLVOORBEELD = re.compile(r"\bartikel (?:9|25)\b[^.]*Invorderingswet 1990|Successiewet", re.I)


def _namen(ingangen: list[str]) -> set[str]:
    return {naam for ingang in ingangen for naam in ingang.split("|")}


def test_dertig_opdrachten_in_de_groepen_van_het_adr():
    assert len(RIJEN) == 30
    assert Counter(r["groep"] for r in RIJEN) == GROEPEN
    assert len(PER_ID) == 30, "een id komt twee keer voor"


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_elke_opdracht_legt_vast_wat_het_adr_vraagt(rij):
    assert rij["opdracht"].strip() and rij["goed"].strip()
    v = rij["verwacht"]
    assert set(v) == VELDEN
    assert v["route"] in {"code", "centraal"}
    laag, hoog = v["subagents"]
    assert 0 <= laag <= hoog
    assert set(v["profielen"]) <= PROFIELEN
    assert bool(v["profielen"]) == (hoog > 0), "profielen horen bij een opdracht die een subagent kan hebben"
    assert isinstance(v["bevestiging"], bool) and isinstance(v["regisseur"], bool)
    if v["vraag_omhoog"] is not None:
        assert set(v["vraag_omhoog"]) == {"van", "landt_bij"}
        assert set(v["vraag_omhoog"]["van"]) <= {"centraal", "subagent"} and v["vraag_omhoog"]["van"]
        assert v["vraag_omhoog"]["landt_bij"] in {"jurist", "centraal"}


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_namen_bestaan(rij):
    v = rij["verwacht"]
    tools = {t["name"] for t in TOOLS + JAS_TOOLS} | set(SJABLONEN) | NIEUW | KETENS
    verplicht, verboden = _namen(v["tools_verplicht"]), _namen(v["tools_verboden"])
    assert verplicht | verboden <= tools, sorted((verplicht | verboden) - tools)
    assert not verplicht & verboden
    if v["sjabloon"] is not None:
        assert _namen([v["sjabloon"]]) <= set(SJABLONEN)
    assert set((rij.get("context") or {}).get("bronnen", [])) <= set(CONNECTORS)
    if v["route_code"] is not None:
        routes = {r["verwacht"].get("route") for r in _lees(EVAL / "golden_routering.jsonl")} | ROUTES_BUITEN_DE_SET
        assert v["route_code"] in routes
    if v["route"] == "code":
        assert v["route_code"], "een route in code heeft een naam"


@pytest.mark.parametrize("rij", RIJEN, ids=lambda r: r["id"])
def test_de_groep_past_bij_de_verwachting(rij):
    v, groep = rij["verwacht"], rij["groep"]
    laag, hoog = v["subagents"]
    if groep == "enkelvoudig":
        assert hoog == 0 and "subagent" in v["tools_verboden"] and v["vraag_omhoog"] is None
    if groep == "een_subagent":
        assert (laag, hoog) == (1, 1) and "subagent" in v["tools_verplicht"]
    if groep == "meer_subagents":
        assert laag >= 2 and v["bevestiging"], "meer dan één subagent vraagt een bevestigingskaart (A5)"
        assert v["regisseur"] == ("regie_plan" in v["tools_verplicht"] or v["route_code"] == "regie")
    if groep == "vraag_omhoog":
        assert v["vraag_omhoog"] is not None
    if groep == "vervolg":
        assert rij.get("opzet"), "een vervolg heeft beurten ervoor"
    if v["regisseur"]:
        assert (rij.get("context") or {}).get("werkgebied"), "de regisseur verdeelt per deelvraag van een werkgebied"


def test_opzet_verwijst_naar_bestaande_opdrachten():
    for rij in RIJEN:
        for stap in rij.get("opzet", []):
            assert ("opdracht" in stap) != ("vraag" in stap), rij["id"]
            if "opdracht" in stap:
                assert stap["opdracht"] in PER_ID and stap["opdracht"] != rij["id"]
                assert not PER_ID[stap["opdracht"]].get("opzet"), "een opzet is één laag diep"


def test_andere_bepalingen_dan_de_voorbeelden_in_de_skill():
    for rij in RIJEN:
        assert not SKILLVOORBEELD.search(rij["opdracht"]), rij["id"]
        for b in rij.get("bron", []):
            assert re.fullmatch(r"BWB[RV]\d+", b["bwb_id"])
            assert not (b["bwb_id"] == "BWBR0004770" and b["artikel"] in {"9", "25"}), rij["id"]


def test_het_meetwerkgebied_draagt_de_opdrachten_met_een_werkgebied():
    assert WERKGEBIED["naam"] and WERKGEBIED["analysevraag"]
    assert len(WERKGEBIED["deelvragen"]) == 3
    assert all(re.fullmatch(r"BWB[RV]\d+", b) for b in WERKGEBIED["zoekbereik"])
    for rij in RIJEN:
        v = rij["verwacht"]
        if v["regisseur"]:
            assert v["subagents"] == [3, 3], "de regisseur start één kind per deelvraag"
    assert not any("verjaring" in d.lower() for d in WERKGEBIED["deelvragen"]), "V02 vraagt naar een deelvraag die ontbreekt"
