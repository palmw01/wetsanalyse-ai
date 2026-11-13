"""Een verzoek volgens een methode die aan geen rol gekoppeld is (plan methodes scheiden, S1, test 5).

De regel staat in code, vóór het model: geen JAS-annotatie onder een andere naam, en geen model dat er zelf iets van
maakt. Een vraag óver de methode en een gewoon verzoek lopen zoals altijd.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import methodekeuze
from agent.methodepakket import PAKKET
from agent.nodes import supervisie
from test_routering import ModelGevraagd, _bouw

EVAL = Path(__file__).resolve().parents[1] / "eval"

VERZOEKEN = [
    "annoteer artikel 9 Iw volgens JRM",
    "Annoteer artikel 9 van de Invorderingswet 1990 volgens het JRM.",
    "maak een analyse volgens het juridisch referentiemodel",
    "werk dit uit als scenario met aktes",
    "Kun je artikel 25 markeren volgens de methode wetsuitvoering?",
    "Stel voor artikel 9 een juridisch scenario op",
    "Classificeer dit lid volgens JRM 2",
]
GEWOON = [
    "annoteer artikel 9 Iw",
    "wat is het rechtsgevolg van artikel 9?",
    "wat zegt het JRM over een rechtsfeit?",
    "Wat is het verschil tussen een analyse volgens het JAS en volgens het JRM?",
    "Hoe annoteer ik volgens JRM?",
    "Analyseer de notariële akte in artikel 3:89 BW",
    "Maak een overzicht van de artikelen over uitstel van betaling",
    "Wat bepaalt de wet over de uitvoering van deze regeling?",
    "",
]


@pytest.fixture(autouse=True)
def _stil(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))


def _state(vraag: str, **extra) -> dict:
    return {"question": vraag, "messages": [{"role": "user", "content": vraag}], "modus": "auto", "focus": {}, **extra}


@pytest.mark.parametrize("vraag", VERZOEKEN)
def test_een_verzoek_volgens_een_niet_gekoppelde_methode_wordt_herkend(vraag):
    assert methodekeuze.niet_gekoppeld(vraag) == "wetsuitvoering"


@pytest.mark.parametrize("vraag", GEWOON)
def test_een_gewoon_verzoek_of_een_vraag_over_de_methode_loopt_door(vraag):
    assert methodekeuze.niet_gekoppeld(vraag) == ""


@pytest.mark.parametrize("vorm", ["supervisor", "centraal"])
@pytest.mark.parametrize("vraag", VERZOEKEN[:3])
def test_de_beurt_start_geen_annotatie_en_geen_model(vraag, vorm):
    b = _bouw()  # een model dat faalt als het wordt aangeroepen
    state = _state(vraag, agentvorm=vorm)
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "afwijzen"
    assert upd["worker_plan"] == [] and upd["specialist"] == ""
    assert "kan ik nog niet" in upd["afwijs_melding"] and "JAS" in upd["afwijs_melding"]


def test_ook_met_een_aangewezen_bepaling_start_de_jas_keten_niet():
    b = _bouw()
    state = _state("annoteer dit artikel volgens JRM", opgegeven_doel={"bwbId": "BWBR0004770", "artikel": "9"})
    upd = supervisie.supervisor_node(b, state)
    assert supervisie._entry_node(b, {**state, **upd}) == "afwijzen" and "annotatie" not in upd["worker_plan"]


def test_een_vraag_over_de_methode_gaat_naar_het_model():
    b = _bouw()
    with pytest.raises(ModelGevraagd):
        supervisie.supervisor_node(b, _state("wat zegt het JRM over een rechtsfeit?"))


def test_een_klik_op_een_actie_noemt_geen_methode_en_loopt_door():
    b = _bouw()
    state = _state("", actie="werkgebied_annoteren", werkgebied_id="w1")
    upd = supervisie.supervisor_node(b, state)
    assert not upd.get("afwijzen")


def test_gekoppeld_komt_uit_het_methodepakket():
    assert "wetsanalyse" in methodekeuze.gekoppeld()
    heeft_rol = {s["skill"] for naam, s in PAKKET["secties"].items()
                 if any(naam in secties for secties in PAKKET["rollen"].values())}
    assert methodekeuze.gekoppeld() == heeft_rol


def test_de_regel_vervalt_zodra_de_methode_een_rol_krijgt(monkeypatch):
    pakket = {**PAKKET, "rollen": {**PAKKET["rollen"], "duiding": [*PAKKET["rollen"]["duiding"], "jrm-scenario"]}}
    monkeypatch.setattr(methodekeuze, "PAKKET", pakket)
    assert methodekeuze.niet_gekoppeld("annoteer artikel 9 Iw volgens JRM") == ""


def test_elke_andere_methode_skill_heeft_trefwoorden():
    """Een derde methode kan niet stil zonder deze regel bestaan."""
    assert set(PAKKET["skills"]) - {methodekeuze.EIGEN} <= set(methodekeuze.TREFWOORDEN)
    assert methodekeuze.EIGEN not in methodekeuze.TREFWOORDEN


@pytest.mark.parametrize("bestand", ["golden_routering.jsonl", "golden_gesprek.jsonl", "golden_duiding.jsonl", "golden.jsonl"])
def test_geen_vraag_uit_de_sets_valt_in_de_regel(bestand):
    """Alleen de rijen die de regel zelf toetsen (id `methode-…`) mogen erin vallen."""
    geraakt = []
    for regel in (EVAL / bestand).read_text(encoding="utf-8").splitlines():
        if not regel.strip() or regel.startswith("#"):
            continue
        rij = json.loads(regel)
        if str(rij.get("id", "")).startswith("methode-"):
            continue
        vragen = [rij.get("vraag") or rij.get("question") or ""] + [
            b.get("vraag", "") if isinstance(b, dict) else str(b) for b in rij.get("beurten") or []]
        geraakt += [v for v in vragen if v and methodekeuze.niet_gekoppeld(v)]
    assert geraakt == []
