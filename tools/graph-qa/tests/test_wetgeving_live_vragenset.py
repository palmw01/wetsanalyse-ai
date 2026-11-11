"""De vragenset van Wetgeving buiten de kennisgraaf (`tests/data/wetgeving_live_vragenset.json`) tegen opgenomen antwoorden.

Per vraag toetst dit:

- **de route**: een genoemd artikel van een regeling buiten de graaf leest de code vooraf (`buiten_graaf.leesaanroepen`,
  route `vooraf`) met precies de argumenten uit de set; een dubbelzinnige afkorting wordt een vraag terug (`keuzevraag`);
- **de tool**: dezelfde argumenten gaan door `dispatch`, tegen de antwoorden van overheid.nl zoals ze op 11 nov 2026 waren
  (de opnames van `test_wetgeving_tools.py`, opnieuw opnemen met `WETGEVING_OPNEMEN=1`), en het resultaat voldoet aan
  `verwacht`. Een verzoek dat niet is opgenomen, faalt.

De graaf bevat alleen de Iw 1990, zoals in de set beschreven. De meting op acceptatie toetst wat het model ermee doet.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import buiten_graaf as bg
from agent import tools
from agent.tools import wetgeving_tools as w

from test_wetgeving_tools import AAN, VANDAAG, _bron, _graaf

SET = json.loads((Path(__file__).parent / "data" / "wetgeving_live_vragenset.json").read_text(encoding="utf-8"))["vragen"]
MET_TOOL = [v for v in SET if v.get("tool")]


@pytest.fixture(autouse=True)
def _vast(monkeypatch):
    monkeypatch.setattr(w, "_vandaag", lambda: VANDAAG)
    monkeypatch.setattr(bg, "_graafnamen", lambda graph: {"invorderingswet 1990", "iw 1990", "iw"})
    w._graaf_stand.clear()
    yield
    w._graaf_stand.clear()


def test_de_set_is_dekkend():
    soorten = {v["route"] for v in SET}
    assert {"vooraf", "keuzevraag", "graaf", "model", "uit"} <= soorten
    assert len({v["id"] for v in SET}) == len(SET) and all(v.get("goed") for v in SET)


@pytest.mark.parametrize("v", [v for v in SET if v["route"] == "vooraf"], ids=lambda v: v["id"])
def test_een_genoemd_artikel_leest_de_code_vooraf(v):
    genoemd = bg.genoemd(v["vraag"], _graaf(), _bron(), vandaag=VANDAAG)
    assert bg.leesaanroepen(genoemd) == [{"name": v["tool"], "input": v["args"]}]


@pytest.mark.parametrize("v", [v for v in SET if v["route"] == "keuzevraag"], ids=lambda v: v["id"])
def test_een_dubbelzinnige_afkorting_wordt_een_vraag(v):
    vraag = bg.keuzevraag(bg.genoemd(v["vraag"], _graaf(), _bron(), vandaag=VANDAAG))
    assert all(naam in vraag for naam in v["verwacht"]["keuze_bevat"])


@pytest.mark.parametrize("v", MET_TOOL, ids=lambda v: v["id"])
def test_de_tool_levert_wat_de_set_verwacht(v):
    uit = json.loads(tools.dispatch(v["tool"], _graaf(), v["args"], AAN, wetgeving_live=_bron()))
    verwacht = v["verwacht"]
    assert uit["status"] == verwacht["status"], uit
    if "reden" in verwacht:
        assert uit["reden"] == verwacht["reden"]
    for sleutel, waarde in (verwacht.get("stuk") or {}).items():
        assert uit["stuk"].get(sleutel) == waarde, (sleutel, uit["stuk"])
    rijen = uit.get("resultaten") or []
    if "tekst_bevat" in verwacht:
        assert any(verwacht["tekst_bevat"] in r.get("tekst", "") for r in rijen), rijen[:2]
    if "min_resultaten" in verwacht:
        assert len(rijen) >= verwacht["min_resultaten"], rijen
    if verwacht.get("geen_resultaten"):
        assert not rijen
    if "eerste" in verwacht:
        eerste = rijen[0]
        assert eerste["nummer"] == verwacht["eerste"]["bwb_id"] and eerste["titel"] == verwacht["eerste"]["titel"]
    if "labels" in verwacht:
        assert [r["label"] for r in rijen] == verwacht["labels"]
    if "eerste_kop_begint" in verwacht:
        assert rijen[0]["reeks"][0].startswith(verwacht["eerste_kop_begint"])
