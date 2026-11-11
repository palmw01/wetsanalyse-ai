"""De routes van Wetgeving buiten de kennisgraaf na de eerste meting (11 nov 2026, `docs/architectuur/metingen/
wetgeving-live-2026-11-11/`). Per bevinding één toets of meer, tegen de opnames van overheid.nl (`test_wetgeving_tools.py`):

1. een gelezen wettekst van overheid.nl staat in de bronnenlijst (was "Klaar · 0 bronnen");
2. een genoemd artikel krijgt het blok `extern` uit de code, met de controle op letterlijkheid (was: geen sjabloon,
   grounding `onbepaald`);
3. de code leest het hele artikel, alle pagina's (was: het model bladerde, 131k en 144k tokens);
4. een eerdere tekst van een regeling in de graaf leest de code vooraf (was: zoeken en zeven rondes);
5. annoteren van een regeling buiten de graaf geeft de vaste melding (was: "Ongeldig BWB-id");
6. met de connector uit volgt de vaste melding zonder model (was: vier rondes en 46k).
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import json

import pytest

from agent import bepaling_workflow as wf
from agent import buiten_graaf as bg
from agent import tools
from agent.grounding import alleen_gelezen_extern, live_niet_letterlijk
from agent.models import Source
from agent.nodes import supervisie
from agent.tools import wetgeving_tools as w
from agent.tools.connectortools import MODULES

from test_wetgeving_tools import AAN, IW, PW, VANDAAG, _bron, _graaf

_AAN = {"wetgeving_live": {"naam": "wetgeving_live", "label": "Wetgeving buiten de kennisgraaf", "aan": True,
                           "reden": "aan"}}
_UIT = {"wetgeving_live": {**_AAN["wetgeving_live"], "aan": False, "reden": "gesprek"}}
NAMEN = {"invorderingswet 1990", "iw 1990", "iw"}


@pytest.fixture(autouse=True)
def _vast(monkeypatch):
    monkeypatch.setattr(w, "_vandaag", lambda: VANDAAG)
    monkeypatch.setattr(bg, "_graafnamen", lambda graph: NAMEN)
    monkeypatch.setattr(MODULES["wetgeving_live"], "_bron", _bron())
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))

    class _Datum(dt.date):
        @classmethod
        def today(cls):
            return dt.date.fromisoformat(VANDAAG)
    monkeypatch.setattr(dt, "date", _Datum)
    w._graaf_stand.clear()
    yield
    w._graaf_stand.clear()


def _voer_uit(graaf):
    return lambda tool, args: tools.dispatch(tool, graaf, args, AAN, wetgeving_live=_bron())


def _bouw(graaf):
    from test_routering import _bouw as bouw
    return dataclasses.replace(bouw(), graph=graaf)


def _kies(vraag: str, stand: dict, graaf=None) -> dict:
    graaf = graaf if graaf is not None else _graaf()
    state = {"question": vraag, "modus": "auto", "focus": {}, "bronstand": stand,
             "messages": [{"role": "user", "content": vraag}]}
    return supervisie.supervisor_node(_bouw(graaf), state)


# --- 1. de bronnenlijst ----------------------------------------------------------------------------------------------

def test_een_gelezen_wettekst_van_overheid_blijft_in_de_bronnenlijst():
    raw = tools.dispatch("get_wettekst", _graaf(), {"bwb_id": PW, "artikel": "12"}, AAN, wetgeving_live=_bron())
    ident = json.loads(raw)["stuk"]["id"]
    bron = Source(label="Participatiewet, artikel 12", uri=ident, origin_tool="get_wettekst", brontype="wettekst_live")
    # Het antwoord noemt het id niet (dat doet lopende tekst nooit), en er is geen sjabloon.
    assert alleen_gelezen_extern([bron], [("get_wettekst", raw)], "Artikel 12 is vervallen.") == [bron]


def test_een_alleen_gevonden_wettekst_is_geen_bron():
    bron = Source(label="x", uri=f"bwbt:{PW}:2026-07-01_0:artikel:31", origin_tool="zoek_artikelen",
                  brontype="wettekst_live")
    assert alleen_gelezen_extern([bron], [], "Artikel 31 gaat over middelen.") == []


# --- 2 en 3. het hele artikel in het blok extern, letterlijk -------------------------------------------------------------

def test_een_artikel_buiten_de_graaf_leest_de_code_helemaal_en_toont_het_letterlijk():
    vraag = "Wat staat er in artikel 31 van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    assert v == wf.Bepalingsvraag(bwb_id=PW, artikel="31", live=True)
    trace = wf.haal(_graaf(), v, _voer_uit(_graaf()))
    assert trace and len(trace) > 1, "artikel 31 past niet op één pagina: de code leest het vervolg"
    rijen = [r for _, t in trace for r in json.loads(t)["resultaten"]]
    antwoord = wf.antwoord(v, trace, "Dit artikel zegt wat tot de middelen hoort.")
    assert antwoord.sjabloon == "extern"
    blok = antwoord.blokken[0]
    assert blok.soort == "extern" and blok.brontype == "wettekst_live"
    assert [p.nr for p in blok.passages] == [r["nr"] for r in rijen], "alle rijen, ook voorbij MAX_PASSAGES"
    assert blok.tekststand == "huidige tekst" and blok.tekst_vanaf == "2026-07-01"
    assert antwoord.blokken[-1].soort == "toelichting"
    assert live_niet_letterlijk(antwoord.model_dump(), trace) == (True, [])


def test_een_passage_die_niet_letterlijk_gelezen_is_keurt_de_controle_af():
    vraag = "Wat staat er in artikel 31 van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    trace = wf.haal(_graaf(), v, _voer_uit(_graaf()))
    data = wf.antwoord(v, trace).model_dump()
    data["blokken"][0]["passages"][0]["tekst"] += " (en ook de spaarrekening)"
    heeft, fout = live_niet_letterlijk(data, trace)
    assert heeft and len(fout) == 1 and fout[0].startswith("Tot de middelen")


def test_een_vervallen_artikel_zegt_dat_in_code():
    vraag = "Wat staat er in artikel 12 van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    antwoord = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf())))
    leemte = next(b for b in antwoord.blokken if b.soort == "leemte")
    assert "vervallen per 1 januari 2026" in leemte.tekst and "geen tekst meer" in leemte.tekst


def test_een_bepaling_die_nog_niet_geldt_zegt_dat_in_code():
    vraag = "Wat staat er in artikel 24a van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    antwoord = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf())))
    leemte = next(b for b in antwoord.blokken if b.soort == "leemte")
    assert "nog niet in werking" in leemte.tekst and "1 januari 2027" in leemte.tekst


def test_een_uitlegvraag_gaat_niet_door_de_workflow():
    vraag = "Wat betekent artikel 31 van de Participatiewet?"
    assert wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG)) is None


def test_de_supervisor_kiest_de_workflow_voor_een_artikel_buiten_de_graaf():
    upd = _kies("Wat staat er in artikel 31 van de Participatiewet?", _AAN)
    assert upd["bepalingsvraag"] == {"bwb_id": PW, "artikel": "31", "lid": "", "live": True}


def test_een_niet_tekstvraag_leest_de_code_vooraf_met_alle_paginas(monkeypatch):
    from agent.nodes import bron_lezen

    upd = _kies("Neem artikel 31 van de Participatiewet op in de bronselectie", _AAN)
    assert upd["bron_lezen"] == [{"name": "get_wettekst", "input": {"bwb_id": PW, "artikel": "31"}}]
    graaf = _graaf()
    monkeypatch.setattr(bron_lezen, "execute_tool", lambda b, state, writer, t: _voer_uit(graaf)(t["name"], t["input"]))
    monkeypatch.setattr(bron_lezen, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(bron_lezen, "_stap", lambda *a, **k: None)
    uit = bron_lezen.bron_lezen_node(_bouw(graaf), {"bron_lezen": upd["bron_lezen"], "source_trace": []})
    paginas = [json.loads(t) for n, t in uit["source_trace"] if n == "get_wettekst"]
    assert len(paginas) > 1 and paginas[-1]["volledig"] and not paginas[-1].get("vervolg")


# --- 4. een eerdere tekst van een regeling in de graaf ---------------------------------------------------------------

def test_een_peildatum_buiten_de_graaftoestand_leest_de_code_bij_overheid(monkeypatch):
    from agent import bepaling_workflow

    monkeypatch.setattr(bepaling_workflow, "regelingen_in_vraag", lambda graph, vraag: [IW])
    vraag = "Wat zei artikel 9 van de Invorderingswet 1990 op 1 januari 2020?"
    v = wf.lees(vraag, _graaf(), live_aan=True)
    assert v == wf.Bepalingsvraag(bwb_id=IW, artikel="9", live=True, peildatum="2020-01-01")
    antwoord = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf())))
    blok = antwoord.blokken[0]
    assert blok.tekststand == "eerdere tekst" and blok.tekst_vanaf == "2020-01-01" and blok.id.startswith(f"bwbt:{IW}:2020-01-01_1")
    # Zonder connector geen graaftekst als antwoord op een vraag naar een andere datum: de agent zegt wat de graaf heeft.
    assert wf.lees(vraag, _graaf(), live_aan=False) is None
    # Een peildatum binnen de graaftoestand is gewoon de graaf.
    assert wf.lees("Wat staat er op 1 november 2026 in artikel 9 Iw 1990?", _graaf(), live_aan=True) == \
        wf.Bepalingsvraag(bwb_id=IW, artikel="9")


def test_de_supervisor_kiest_de_workflow_voor_een_eerdere_tekst(monkeypatch):
    from agent import bepaling_workflow

    monkeypatch.setattr(bepaling_workflow, "regelingen_in_vraag", lambda graph, vraag: [IW])
    upd = _kies("Wat zei artikel 9 van de Invorderingswet 1990 op 1 januari 2020?", _AAN)
    assert upd["bepalingsvraag"] == {"bwb_id": IW, "artikel": "9", "lid": "", "live": True, "peildatum": "2020-01-01"}


def test_een_historische_tekst_buiten_de_graaf_neemt_de_peildatum_mee():
    vraag = "Wat stond er op 15 januari 2015 in artikel 8 van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    assert v == wf.Bepalingsvraag(bwb_id=PW, artikel="8", live=True, peildatum="2015-01-15")
    blok = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf()))).blokken[0]
    assert blok.id.startswith(f"bwbt:{PW}:2015-01-01_1") and blok.tekststand == "eerdere tekst"


# --- 5. annoteren ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("stand", [_AAN, _UIT], ids=["connector aan", "connector uit"])
def test_annoteren_van_een_regeling_buiten_de_graaf_geeft_de_vaste_melding(stand):
    upd = _kies("Annoteer artikel 7:610 BW", stand)
    assert upd["afwijzen"] and "Burgerlijk Wetboek Boek 7" in upd["afwijs_melding"]
    assert "staat niet in de kennisgraaf" in upd["afwijs_melding"] and "import" in upd["afwijs_melding"]
    assert "BWB-id" not in upd["afwijs_melding"]
    assert ("Lezen kan wel" in upd["afwijs_melding"]) is (stand is _AAN)


# --- 6. de connector uit ---------------------------------------------------------------------------------------------

def test_met_de_connector_uit_volgt_de_melding_zonder_model(monkeypatch):
    monkeypatch.setattr(MODULES["wetgeving_live"], "_bron", None)
    events: list[dict] = []
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: events.append)
    upd = _kies("Wat staat er in artikel 31 van de Participatiewet?", _UIT)
    assert upd["afwijzen"] and upd["afwijs_melding"].startswith("Participatiewet staat niet in de kennisgraaf.")
    assert "Bronnen en tools" in upd["afwijs_melding"] and "eigen kennis" in upd["afwijs_melding"]
    assert any(e.get("type") == "bron_uit" and e["bronnen"][0]["naam"] == "wetgeving_live" for e in events)


def test_met_de_connector_uit_blijft_een_regeling_uit_de_graaf_bij_de_graaf(monkeypatch):
    from agent import overzicht

    monkeypatch.setattr(overzicht, "regelingen_in_vraag", lambda graph, vraag: [IW])
    assert bg.zonder_zoekdienst("Wat staat er in artikel 9 van de Invorderingswet?", _graaf()) == []
    monkeypatch.setattr(overzicht, "regelingen_in_vraag", lambda graph, vraag: [])
    # "Invorderingswet" is het begin van een graafnaam: geen regeling buiten de graaf.
    assert bg.zonder_zoekdienst("Wat staat er in artikel 9 van de Invorderingswet?", _graaf()) == []
    # Zonder artikel geen melding: dat is een vraag die de agent beantwoordt.
    assert bg.zonder_zoekdienst("Wat regelt de Participatiewet?", _graaf()) == []


# --- de hele beurt ---------------------------------------------------------------------------------------------------

def test_de_hele_beurt_een_modelaanroep_bronnen_en_gegrond(monkeypatch):
    from agent.agent import answer_stream
    from fakes import FakeLLM, make_settings, response, text_block

    llm = FakeLLM([response([text_block("Dit artikel noemt wat tot de middelen hoort, en wat niet.")], "end_turn")])
    settings = make_settings(connector_wetgeving_live=True)
    graaf = _graaf()

    async def alles():
        return [e async for e in answer_stream("Wat staat er in artikel 31 van de Participatiewet?", settings=settings,
                                               llm=llm, graph=graaf, bronnen=["wetgeving_live"])]
    events = asyncio.run(alles())
    assert llm.index == 1 and llm.calls[0]["tools"] == [], "alleen de toelichting"
    antwoord = next(e for e in events if e["type"] == "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "extern" and antwoord["blokken"][0]["brontype"] == "wettekst_live"
    bronnen = next(e for e in events if e["type"] == "sources")["sources"]
    assert [s["brontype"] for s in bronnen] == ["wettekst_live"]
    grounding = next(e for e in events if e["type"] == "grounding")
    assert grounding["grounded"] is True and grounding["niveau"] == "gegrond"
