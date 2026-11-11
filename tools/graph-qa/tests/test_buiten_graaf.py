"""Een regeling die niet in de kennisgraaf staat, herkent de code vóór het model (`agent/buiten_graaf.py`).

Tegen dezelfde opnames als `test_wetgeving_tools.py` (opnieuw opnemen met `WETGEVING_OPNEMEN=1`) en een nep-graaf met
alleen de Iw 1990. De vragen komen uit de vragenset (`tests/data/wetgeving_live_vragenset.json`).
"""
from __future__ import annotations

import pytest

from agent import buiten_graaf as bg
from agent.tools import wetgeving_tools as w

from test_wetgeving_tools import IW, PW, VANDAAG, _bron, _graaf


@pytest.fixture(autouse=True)
def _vast(monkeypatch):
    monkeypatch.setattr(bg, "_graafnamen", lambda graph: {"invorderingswet 1990", "iw 1990", "iw"})
    w._graaf_stand.clear()
    yield
    w._graaf_stand.clear()


def _genoemd(vraag: str):
    return bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG)


@pytest.mark.parametrize(("vraag", "kandidaten"), [
    ("Wat staat er in artikel 31 van de Participatiewet?", [("Participatiewet", "Participatiewet", "")]),
    ("Wat regelt artikel 7:610 lid 1 BW?", [("7:610 BW", "Burgerlijk Wetboek Boek 7", "610")]),
    ("Wat zegt de Wlz over de indicatie?", [("Wlz", "Wlz", "")]),
    ("Wat staat er in artikel 1 Pw?", [("Pw", "Pw", "1")]),
    ("Hoe is de Wet IB 2001 opgebouwd?", [("Wet IB 2001", "Wet IB 2001", "")]),
    ("Geldt de Wet op de loonbelasting 1964 ook?", [("Wet op de loonbelasting 1964", "Wet op de loonbelasting 1964", "")]),
    ("Wat is een belastingschuldige?", []),
    ("Wat zei de Hoge Raad?", []),
])
def test_de_kandidaten_uit_de_vraag(vraag, kandidaten):
    assert bg._kandidaten(vraag) == kandidaten


def test_een_genoemd_artikel_van_een_wet_buiten_de_graaf_wordt_vooraf_gelezen():
    uit = _genoemd("Wat staat er in artikel 31 van de Participatiewet?")
    assert [(g.bwb_id, g.titel, g.artikel) for g in uit] == [(PW, "Participatiewet", "31")]
    assert bg.leesaanroepen(uit) == [{"name": "get_wettekst", "input": {"bwb_id": PW, "artikel": "31"}}]
    assert "Participatiewet (BWBR0015703)" in bg.plan_regel(uit)


def test_een_artikel_van_een_boek_van_het_bw_met_lid():
    uit = _genoemd("Wat regelt artikel 7:610 lid 1 BW?")
    assert [(g.titel, g.artikel, g.lid) for g in uit] == [("Burgerlijk Wetboek Boek 7", "610", "1")]


def test_een_afkorting_die_bij_meer_regelingen_past_laat_kiezen():
    uit = _genoemd("Wat staat er in artikel 1 Pw?")
    assert len(uit) == 1 and uit[0].dubbelzinnig
    vraag = bg.keuzevraag(uit)
    assert "Participatiewet" in vraag and "Pensioenwet" in vraag and vraag.endswith("dan lees ik de tekst.")
    assert bg.leesaanroepen(uit) == []


def test_een_regeling_in_de_graaf_valt_af():
    assert _genoemd("Wat staat er in artikel 9 van de Invorderingswet 1990?") == []


def test_een_regeling_die_niet_bestaat_is_geen_treffer():
    assert _genoemd("Wat staat er in artikel 3 van de Wet op de robotbelasting?") == []


def test_een_storing_kost_alleen_de_herkenning():
    from test_wetgeving_tools import Dienst

    assert bg.genoemd("Wat staat er in artikel 31 van de Participatiewet?", _graaf(), _bron(Dienst(weg=True)),
                      vandaag=VANDAAG) == []
    assert bg.genoemd("Wat staat er in artikel 31 van de Participatiewet?", _graaf(weg=True), _bron(),
                      vandaag=VANDAAG) == []


def test_samen_met_de_graaf_alleen_de_wet_buiten_de_graaf():
    uit = _genoemd("Verschilt artikel 33 Iw 1990 van artikel 2:9 BW?")
    assert [(g.titel, g.artikel) for g in uit] == [("Burgerlijk Wetboek Boek 2", "9")]
    assert IW not in {g.bwb_id for g in uit}
