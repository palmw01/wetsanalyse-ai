"""Alleen de connectors die de vraag of het gesprek noemt (`agent/bronkeuze.py`, ronde 6, 12 nov 2026).

Elke aangezette connector kostte per modelronde ~2k tokens aan toolschema's, ook als de vraag over één bron ging
(Staatsblad ronde 5: +7k per leesbeurt met alle vier aan). Nu krijgt alleen een genoemde bron haar tools; zonder genoemde
bron blijft alles aan, en een vervolgvraag houdt de keuze van het gesprek. De bronstand zegt het eerlijk (reden `vraag`).
"""
from __future__ import annotations

import asyncio
import re
import json
from pathlib import Path

import pytest

from bronmodel.connectors import CONNECTORS, herkende

from agent import bronkeuze
from agent.agent import answer_stream
from agent.bronstand import bepaal, prompt_blok
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

ALLE = dict(connector_kamerstukken=True, connector_rechtspraak=True, connector_bekendmakingen=True,
            connector_wetgeving_live=True, connector_kennisgroepen=True)
KIES = response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: zoek")], "end_turn")
MVT = "Wat zegt de memorie van toelichting over de bestuurdersaansprakelijkheid?"
ZONDER = "Hoe werkt de bestuurdersaansprakelijkheid?"


def _stand():
    return bepaal(make_settings(**ALLE), None)


def _run(vraag, gid=None, settings=None, *rondes):
    llm = FakeLLM([KIES, *(rondes or [response([text_block("Klaar.")], "end_turn")])])

    async def alles():
        return [e async for e in answer_stream(vraag, gid, settings=settings or make_settings(enable_planning=True, **ALLE),
                                               llm=llm, graph=FakeGraph(result=""))]

    return asyncio.run(alles()), llm


def _toolnamen(llm) -> set[str]:
    return {t["name"] for t in llm.calls[1]["tools"]}


def _connectortools(*namen: str) -> set[str]:
    return {t for n in namen for t in CONNECTORS[n].tools}


def test_de_testvragen_noemen_wat_ze_moeten_noemen():
    assert herkende(MVT) == ("kamerstukken",)
    assert herkende(ZONDER) == ()


def test_een_genoemde_bron_houdt_alleen_zijn_eigen_tools():
    stand, keuze = bronkeuze.kies(_stand(), {"kamerstukken"}, None)
    assert keuze == ["kamerstukken"]
    assert bronkeuze.actief(stand) == ["kamerstukken"]
    assert {n: s["reden"] for n, s in stand.items() if not s["aan"]} == {
        "rechtspraak": "niet_nodig", "bekendmakingen": "niet_nodig", "kennisgroepen": "niet_nodig",
        "wetgeving_live": "niet_nodig"}


def test_zonder_genoemde_bron_blijft_alles_aan():
    stand = _stand()
    nieuw, keuze = bronkeuze.kies(stand, set(), None)
    assert nieuw is stand and keuze is None


def test_een_vervolgvraag_houdt_de_keuze_van_het_gesprek():
    nieuw, keuze = bronkeuze.kies(_stand(), set(), ["rechtspraak"])
    assert keuze == ["rechtspraak"] and bronkeuze.actief(nieuw) == ["rechtspraak"]


def test_een_nieuwe_genoemde_bron_vervangt_de_keuze():
    _, keuze = bronkeuze.kies(_stand(), {"bekendmakingen"}, ["rechtspraak"])
    assert keuze == ["bekendmakingen"]


def test_een_bron_die_uit_staat_gaat_niet_aan():
    stand = bepaal(make_settings(**ALLE), ["rechtspraak"])
    nieuw, keuze = bronkeuze.kies(stand, {"kamerstukken"}, None)
    assert nieuw is stand and keuze is None
    assert bronkeuze.actief(nieuw) == ["rechtspraak"]


def test_het_promptblok_zegt_waarom_een_bron_deze_beurt_niet_meedoet():
    stand, _ = bronkeuze.kies(_stand(), {"kamerstukken"}, None)
    blok = prompt_blok(stand, MVT)
    assert "- Kamerstukken: aan." in blok
    assert "- Rechtspraak: staat aan, maar is niet nodig voor deze vraag" in blok
    assert "Rechtspraak: uit" not in blok, "niet nodig is iets anders dan uit (Staatsblad ronde 6, B18)"


def test_de_beurt_biedt_alleen_de_genoemde_connector_aan():
    events, llm = _run(MVT)
    tools = _toolnamen(llm)
    assert _connectortools("kamerstukken") <= tools
    assert not tools & _connectortools("rechtspraak", "bekendmakingen", "wetgeving_live")
    standen = [e for e in events if e["type"] == "bronstand"]
    assert standen[-1]["bronnen"] == list(bronkeuze.kies(_stand(), {"kamerstukken"}, None)[0].values())


def test_zonder_genoemde_bron_krijgt_de_beurt_alle_connectors():
    events, llm = _run(ZONDER)
    assert _connectortools("kamerstukken", "rechtspraak", "bekendmakingen", "wetgeving_live") <= _toolnamen(llm)
    assert len([e for e in events if e["type"] == "bronstand"]) == 1, "geen tweede stand als er niets verandert"


def test_een_vervolgvraag_in_het_gesprek_houdt_de_bron(tmp_path):
    settings = make_settings(enable_planning=True, checkpoint_db_path=str(tmp_path / "cp.db"), **ALLE)
    _run(MVT, "g-bron", settings)
    _, llm = _run("En wat staat er over de meldingsplicht?", "g-bron", settings,
                  response([text_block("Klaar.")], "end_turn"))
    tools = _toolnamen(llm)
    assert _connectortools("kamerstukken") <= tools
    assert not tools & _connectortools("rechtspraak", "bekendmakingen", "wetgeving_live")


def test_een_orgaan_noemt_zijn_bron():
    """Uit de beschrijving (`organen`), niet uit een lijst per vraag: Kamerstukken K03."""
    assert bronkeuze.genoemd(["de laatste vijf moties van de Eerste Kamer"]) == {"kamerstukken"}
    assert bronkeuze.genoemd(["Hoeveel uitspraken deed de Hoge Raad?"]) == {"rechtspraak"}


def test_een_wet_buiten_de_graaf_of_een_filter_beperkt_alleen_niet():
    """B23: een wijzigingswet die de graaf niet kent, kan over het Staatsblad gaan; een filterwaarde zegt wat er gezocht
    wordt, niet waar. Ze komen alleen bij een keuze, en beperken nooit zelf."""
    stand, keuze = bronkeuze.kies(_stand(), set(), None, erbij={"wetgeving_live", "rechtspraak"})
    assert keuze is None and len(bronkeuze.actief(stand)) == len(ALLE)
    stand, _ = bronkeuze.kies(_stand(), {"kamerstukken"}, None, erbij={"wetgeving_live"})
    assert bronkeuze.actief(stand) == ["kamerstukken", "wetgeving_live"]


B18 = "Welke publicaties horen bij Kamerdossier 36602?"
K16 = "Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?"


def test_een_filterwaarde_neemt_elke_connector_met_dat_filter_mee():
    """B18: het dossiernummer is een filter van Kamerstukken én van het Staatsblad (`w.behandeldDossier`). Uit de
    beschrijving, niet per connector: elke connector waarvan een veld het filter `dossier` draagt."""
    met_dossier = {n for n, c in CONNECTORS.items() if any("dossier" in v.filters for v in c.metadata)}
    assert bronkeuze.filters_in([B18]) == met_dossier == {"kamerstukken", "bekendmakingen"}
    stand, _ = bronkeuze.kies(_stand(), bronkeuze.genoemd([B18]), None, bronkeuze.filters_in([B18]))
    assert set(bronkeuze.actief(stand)) == {"kamerstukken", "bekendmakingen"}
    assert bronkeuze.filters_in(["uitspraken in het belastingrecht"]) == {"rechtspraak"}


def test_een_artikel_of_datum_is_geen_filter_van_een_bron():
    """Daar gaat elke vraag aan Lex over; anders zou elke vraag over een artikel Rechtspraak en het Staatsblad erbij nemen."""
    assert bronkeuze.filters_in(["Wat zegt de MvT over artikel 29 van de Invorderingswet 1990 sinds 2024?"]) == set()


def test_een_aanwijzing_noemt_geen_bron():
    """K16: "wat bedoelde de wetgever" wijst naar Kamerstukken, maar een uitspraak is net zo goed de weg (een memorie van
    vóór 1994 staat niet bij KOOP). Het mechanisme: een `aanwijzing` in de beschrijving telt bij `herkent`, niet bij `noemt`."""
    assert herkende(K16) == ("kamerstukken",)
    assert bronkeuze.genoemd([K16]) == set()
    assert all(not c.noemt(K16) or not any(re.search(p, K16, re.IGNORECASE) for p in c.aanwijzingen)
               for c in CONNECTORS.values())
    stand, keuze = bronkeuze.kies(_stand(), bronkeuze.genoemd([K16]), None, bronkeuze.filters_in([K16]))
    assert keuze is None and len(bronkeuze.actief(stand)) == len(ALLE)


def test_de_vraag_van_k16_krijgt_alle_connectors():
    events, llm = _run(K16)
    assert _connectortools("kamerstukken", "rechtspraak", "bekendmakingen", "wetgeving_live") <= _toolnamen(llm)
    assert len([e for e in events if e["type"] == "bronstand"]) == 1


def test_het_denkproces_zegt_wat_niet_nodig_is():
    events, _ = _run(MVT)
    regels = [e["message"] for e in events if e["type"] == "status"]
    assert any("zoekt voor deze vraag in de wetgeving en Kamerstukken" in r and "niet nodig" in r for r in regels), regels
    assert not any("uit" in r.split(";")[-1].split() for r in regels if "niet nodig" in r)


@pytest.mark.parametrize("bestand,eigen", [
    ("kamerstukken_vragenset_30", "kamerstukken"), ("rechtspraak_vragenset_30", "rechtspraak"),
    ("bekendmakingen_vragenset", "bekendmakingen"), ("wetgeving_live_vragenset", "wetgeving_live")])
def test_geen_vraag_uit_de_vragensets_verliest_haar_eigen_bron(bestand, eigen):
    vragen = json.loads((Path(__file__).parent / "data" / f"{bestand}.json").read_text(encoding="utf-8"))["vragen"]
    for q in vragen:
        vraag = q.get("vraag") or q.get("tekst") or ""
        for buiten in (False, True):
            erbij = bronkeuze.filters_in([vraag]) | ({"wetgeving_live"} if buiten else set())
            stand, _ = bronkeuze.kies(_stand(), bronkeuze.genoemd([vraag]), None, erbij)
            assert eigen in bronkeuze.actief(stand), (q.get("id"), vraag)


def test_een_route_in_code_houdt_haar_connector():
    """Meting ronde 6, B18: de vraag noemt het Staatsblad, de lijstroute koos Kamerstukken. Die connector hoort erbij."""
    upd = {"bron_lijst": {"connector": "kamerstukken", "tool": "zoek_kamerstukken", "args": {"dossier": "36602"}}}
    assert bronkeuze.van_route(upd) == {"kamerstukken"}
    assert bronkeuze.van_route({"bron_lezen": [{"name": "get_bekendmaking", "input": {"id": "stb-2010-176"}}]}) == {"bekendmakingen"}
    stand, _ = bronkeuze.kies(_stand(), {"bekendmakingen"} | bronkeuze.van_route(upd), None)
    assert set(bronkeuze.actief(stand)) == {"bekendmakingen", "kamerstukken"}


def test_de_lijstroute_krijgt_haar_eigen_bron_ook_als_de_vraag_een_andere_noemt(monkeypatch):
    from agent.nodes import supervisie

    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    state = {"question": "Welke publicaties horen bij Kamerdossier 36602?", "bronstand": _stand()}
    upd = {"bron_lijst": {"connector": "kamerstukken", "tool": "zoek_kamerstukken", "args": {"dossier": "36602"}}}

    class _B:
        graph = FakeGraph(result="")

    uit = supervisie._bronkeuze(_B(), state, upd)
    assert set(uit["bronnen"]) == {"bekendmakingen", "kamerstukken"}
