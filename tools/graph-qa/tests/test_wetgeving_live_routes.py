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

    upd = _kies("Wat regelt artikel 31 van de Participatiewet?", _AAN)
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


# --- na de controle (11 nov 2026, `controle.md`) ---------------------------------------------------------------------

@pytest.mark.parametrize("stand", [_AAN, _UIT], ids=["connector aan", "connector uit"])
@pytest.mark.parametrize("vraag", ["Neem artikel 31 van de Participatiewet op in de bronselectie",
                                   "Voeg artikel 31 van de Participatiewet toe aan het werkgebied"])
def test_opnemen_van_een_regeling_buiten_de_graaf_geeft_de_vaste_melding(vraag, stand):
    upd = _kies(vraag, stand)
    assert upd["afwijzen"] and not upd.get("bron_lezen") and not upd.get("bepalingsvraag")
    melding = upd["afwijs_melding"]
    assert "niet opnemen" in melding and "Participatiewet staat niet in de kennisgraaf" in melding
    assert "Er is niets opgenomen." in melding and "import" in melding
    assert ("Lezen kan wel" in melding) is (stand is _AAN)


def test_een_vraag_met_opgenomen_is_geen_opnameverzoek():
    upd = _kies("Wat staat er opgenomen in artikel 31 van de Participatiewet?", _AAN)
    assert not upd.get("afwijzen") and upd["bepalingsvraag"]["live"]


def test_een_onderdeel_draagt_zijn_letter_als_plek():
    vraag = "Wat staat er in artikel 31 van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    blok = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf()))).blokken[0]
    plekken = {p.tekst: p.plek for p in blok.passages}
    assert plekken["de jonggehandicaptenkorting;"] == "onderdeel c"
    # Een lid draagt zijn nummer al in de kop; zijn eigen tekst krijgt geen plek.
    assert plekken["Niet tot de middelen van de belanghebbende worden gerekend:"] == ""
    from bronmodel.antwoord import antwoord_tekst
    assert '> "de jonggehandicaptenkorting;" (onderdeel c)' in antwoord_tekst(wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf()))))


def test_een_subonderdeel_heet_naar_zijn_nummer():
    assert w.onderdeel_plek("1°.") == "1°" and w.onderdeel_plek("b.") == "onderdeel b" and w.onderdeel_plek("") == ""


# --- ronde 1 van de iteraties (11 nov 2026, `docs/architectuur/metingen/wetgeving-live-iteratie-2026-11-11/`) ---------

def test_de_opbouw_en_de_telling_staan_op_de_eerste_pagina():
    """I13/I30: zonder deze velden bladerde het model door alle artikelen (1,0M en 219k tokens)."""
    r = json.loads(tools.dispatch("zoek_artikelen", _graaf(), {"bwb_id": PW}, AAN, wetgeving_live=_bron()))
    assert r["telling"] == {"totaal": 174, "geldend": 150, "vervallen": 20, "nog_niet_in_werking": 4}
    assert r["opbouw"][0] == {"kop": "Hoofdstuk 1 – Algemeen", "artikelen": 15, "van": "Artikel 1", "tot": "Artikel 8d"}
    assert sum(d["artikelen"] for d in r["opbouw"]) == 174
    # Alleen op de eerste pagina, en niet bij zoeken op woorden.
    vervolg = json.loads(tools.dispatch("zoek_artikelen", _graaf(), {"bwb_id": PW, "offset": 30}, AAN, wetgeving_live=_bron()))
    assert "opbouw" not in vervolg
    woorden = json.loads(tools.dispatch("zoek_artikelen", _graaf(), {"bwb_id": PW, "woorden": "kostendelende medebewoner"},
                                        AAN, wetgeving_live=_bron()))
    assert "opbouw" not in woorden


def test_een_onderdeel_met_de_aanhef_van_zijn_lid():
    """I09: "tweede lid, onderdeel c" gaf het hele artikel."""
    vraag = "Wat staat er in artikel 31, tweede lid, onderdeel c, van de Participatiewet?"
    v = wf.lees_buiten(vraag, bg.genoemd(vraag, _graaf(), _bron(), vandaag=VANDAAG))
    assert (v.artikel, v.lid, v.onderdeel) == ("31", "2", "c")
    blok = wf.antwoord(v, wf.haal(_graaf(), v, _voer_uit(_graaf()))).blokken[0]
    assert [(p.plek, p.tekst) for p in blok.passages] == [
        ("", "Niet tot de middelen van de belanghebbende worden gerekend:"), ("onderdeel c", "de jonggehandicaptenkorting;")]
    geen = json.loads(tools.dispatch("get_wettekst", _graaf(), {"bwb_id": PW, "artikel": "31", "lid": "2", "onderdeel": "zz"},
                                     AAN, wetgeving_live=_bron()))
    assert "geen onderdeel zz in lid 2" in geen["toelichting"]


def test_get_wettekst_noemt_de_bekendmaking_van_het_artikel():
    """I06: zonder dit veld zocht Lex zeven rondes naar het Staatsblad van artikel 24a."""
    r = json.loads(tools.dispatch("get_wettekst", _graaf(), {"bwb_id": PW, "artikel": "24a"}, AAN, wetgeving_live=_bron()))
    assert r["stuk"]["publicatie"] == "Stb. 2025, 312"
    assert w.publicatie("Stcrt.2024-1234") == "Stcrt. 2024, 1234" and w.publicatie("") == ""
    assert w.publicatie("Trb. 2001, 5 en later") == "Trb. 2001, 5 en later"


class _Bron:
    """Een zoekdienst met vaste antwoorden voor `_buiten_de_peildatum`."""

    def __init__(self, vandaag=(), altijd=(), toestanden=()):
        self._vandaag, self._altijd, self._toestanden = list(vandaag), list(altijd), list(toestanden)

    def zoek(self, cql, *, start=1, maximum=50):
        rijen = self._vandaag if "geldigheidsdatum" in cql else self._altijd
        return len(rijen), rijen

    def toestanden(self, bwb_id):
        return self._toestanden


def _toestand(titel, van, tot="9999-12-31", bwb="BWBR0000001"):
    from agent.adapters.sru_bwb import Toestand
    return Toestand(bwb, titel, "wet", van, tot, van, "9999-12-31", f"https://x/{bwb}/{van}.xml")


def test_een_regeling_zonder_tekst_op_de_peildatum_krijgt_haar_periode():
    """I20: zonder deze zin gokte Lex achttien rondes naar BWB-id's (509k)."""
    weg = w._buiten_de_peildatum(_Bron(), "Wet op de inkomstenbelasting 1964", "1995-01-01")
    assert "geen regeling met precies de titel" in weg and "Raad geen BWB-id's" in weg
    t = [_toestand("Participatiewet", "2004-01-01", "2004-12-31"), _toestand("Participatiewet", "2026-07-01")]
    later = w._buiten_de_peildatum(_Bron(vandaag=t[-1:], toestanden=t), "Participatiewet", "2001-01-01")
    assert "teksten van 2004-01-01 tot nu, niet op 2001-01-01" in later
    binnen = w._buiten_de_peildatum(_Bron(vandaag=t[-1:], toestanden=t), "Participatiewet", "2010-01-01")
    assert "mogelijk onder een andere titel" in binnen


def test_een_toekomstige_peildatum_zonder_andere_tekst_zegt_dat(monkeypatch):
    """I17: "per 1 januari 2028" gaf stil de tekst van nu."""
    stuk = {"tekststand": "huidige tekst", "tekst_vanaf": "2026-01-01"}
    zin = wf.toekomst_zin(stuk, "2028-01-01")
    assert "Voor 1 januari 2028 is in het Basiswettenbestand geen andere tekst bekend" in zin and "1 januari 2026" in zin
    assert wf.toekomst_zin(stuk, "2020-01-01") == "" and wf.toekomst_zin(stuk, "") == ""
    assert wf.toekomst_zin({**stuk, "tekststand": "toekomstige tekst"}, "2028-01-01") == ""


@pytest.mark.parametrize("vraag,naam", [
    ("Wat staat er in artikel 1:1 van de Algemene douanewet?", "Algemene douanewet"),
    ("Wat staat er in artikel 1 van het Uitvoeringsbesluit inkomstenbelasting 2001?", "Uitvoeringsbesluit inkomstenbelasting 2001"),
    ("Wat staat er in artikel 1 van de Uitvoeringsregeling inkomstenbelasting 2001?", "Uitvoeringsregeling inkomstenbelasting 2001"),
    ("Hoe is het Besluit Bestuurlijke Boeten Belastingdienst opgebouwd?", "Besluit Bestuurlijke Boeten Belastingdienst"),
])
def test_ook_besluiten_regelingen_en_algemene_wetten_worden_herkend(vraag, naam):
    """I03/I10/I11/I12: alleen titels op -wet of met "Wet" werden herkend, de rest zocht het model zelf."""
    assert naam in [k[0] for k in bg._kandidaten(vraag)]


_ALLE = {**_AAN, **{n: {"naam": n, "label": n, "aan": True, "reden": "aan"}
                    for n in ("kamerstukken", "bekendmakingen", "rechtspraak")}}


@pytest.mark.parametrize("vraag,leestool,ident", [
    ("Wat zegt de MvT bij Kamerstuk 33755, nr. 3 over artikel 29 IW?", "get_kamerstuk", "kst-33755-3"),
    ("Wat staat er in Stb. 2025, 312 over artikel 24a van de Participatiewet?", "get_bekendmaking", "stb-2025-312"),
    ("Wat zegt ECLI:NL:HR:2026:586 over artikel 36 van de Invorderingswet 1990?", "get_uitspraak", "ECLI:NL:HR:2026:586"),
])
def test_een_genoemd_stuk_gaat_voor_de_bepalingsroute(vraag, leestool, ident):
    """R28b en K14 (Kamerstukken): met een artikel erbij las Lex alleen de wettekst, en het stuk niet."""
    upd = _kies(vraag, _ALLE)
    assert not upd.get("bepalingsvraag")
    aanroepen = upd["bron_lezen"]
    assert [a["name"] for a in aanroepen] == [leestool]
    assert ident in aanroepen[0]["input"].values()


def test_een_stukvraag_leest_de_wettekst_niet_vooraf():
    """I02: bij "welke uitspraken … over artikel 31 Pw" las de code eerst de wettekst."""
    from agent.bepaling_workflow import wijst_stuk_aan
    vraag = "Welke uitspraken van de Centrale Raad van Beroep gaan over artikel 31 van de Participatiewet?"
    assert wijst_stuk_aan(vraag)
    from test_routering import ModelGevraagd
    with pytest.raises(ModelGevraagd):  # geen vooraf-lezing: de beurt gaat naar het model, met de connectors
        _kies(vraag, _AAN)


def test_een_herschreven_vervolgvraag_buiten_de_graaf_gaat_de_workflow_in():
    """I25: "En wat staat er in artikel 32?" na artikel 31 Pw."""
    zelfstandig = "Wat staat er in artikel 32 van de Participatiewet?"
    genoemd = bg.genoemd(zelfstandig, _graaf(), _bron(), vandaag=VANDAAG)
    assert wf.lees_buiten(zelfstandig, genoemd, getypt="En wat staat er in artikel 32?") == \
        wf.Bepalingsvraag(bwb_id=PW, artikel="32", live=True)
    # Een datum uit de herschrijving (van een stuk uit de vorige beurt) is geen peildatum.
    met_datum = "Wat staat er op 10 april 2026 in artikel 32 van de Participatiewet?"
    assert wf.lees_buiten(met_datum, genoemd, getypt="En artikel 32?") is None


def test_een_onbekende_wet_krijgt_de_vaste_melding():
    """I07: drie rondes en vier niet-gerelateerde bronnen voor een wet die niet bestaat."""
    upd = _kies("Wat staat er in artikel 3 van de Wet op de robotbelasting?", _AAN)
    assert upd["afwijzen"] and "„Wet op de robotbelasting”" in upd["afwijs_melding"]
    assert "Basiswettenbestand kent geen geldende regeling" in upd["afwijs_melding"]


def test_een_volledig_gelezen_artikel_uit_een_onvolledige_toestand_is_te_lezen():
    """I03: de Algemene douanewet (dekking 98,5%) weigerde elk artikel, ook een dat zelf volledig gelezen is. De toestand
    als geheel blijft onvolledig voor de opbouw; de importer meet de toestand als geheel, en dat verandert niet."""
    adw = "BWBR0023746"
    r = json.loads(tools.dispatch("get_wettekst", _graaf(), {"bwb_id": adw, "artikel": "1:1"}, AAN, wetgeving_live=_bron()))
    assert r["status"] == "ok" and r["resultaten"], r
    assert "niet volledig te lezen" in r["toelichting"] and "volledig en te citeren" in r["toelichting"]
    opbouw = json.loads(tools.dispatch("zoek_artikelen", _graaf(), {"bwb_id": adw}, AAN, wetgeving_live=_bron()))
    assert opbouw["status"] == "error" and opbouw["reden"] == "toestand_onvolledig"


def test_een_artikel_van_overheid_in_extern_is_onderbouwd_in_de_duiding():
    """I28: het duiding-sjabloon weigerde "artikel 2:9 BW" zes keer, terwijl het met get_wettekst gelezen was."""
    from agent.sjablonen import duiding

    raw = tools.dispatch("get_wettekst", _graaf(), {"bwb_id": "BWBR0003045", "artikel": "9"}, AAN, wetgeving_live=_bron())
    ident = json.loads(raw)["stuk"]["id"]
    trace = [("get_wettekst", raw)]
    assert duiding.live_artikelen(trace) == {"9": ident, "2:9": ident}
    uitleg = "Artikel 2:9 BW legt de aansprakelijkheid bij de rechtspersoon."
    assert duiding._niet_onderbouwd(uitleg, [], frozenset({ident}), trace) == []
    # Zonder aanwijzing in 'extern' zegt de weigering hoe het wél moet: het id, niet get_artikel.
    los = duiding._niet_onderbouwd(uitleg, [], frozenset(), trace)
    assert los == ["artikel 2:9"]
    melding = str(duiding._genoemd_is_gelezen(los, {}, trace))
    assert ident in melding and "'extern'" in melding and "get_artikel" not in melding


def test_een_interne_weigering_komt_nooit_bij_de_jurist():
    """I28: het model schreef "Het sjabloon detecteert elke verwijzing …" als antwoord."""
    from agent.nodes.antwoord import zonder_interne_taal

    tekst = ("Het sjabloon detecteert elke verwijzing naar artikel 2:9 en blokkeert de afronding. Ik geef het antwoord "
             "hieronder.\n\n**Vergelijking**\n\nDe bepalingen verschillen op vier punten.")
    assert zonder_interne_taal(tekst) == "Ik geef het antwoord hieronder.\n\n**Vergelijking**\n\nDe bepalingen verschillen op vier punten."
    assert zonder_interne_taal("De wet gebruikt geen modelbepaling.") == "De wet gebruikt geen modelbepaling."
