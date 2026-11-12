"""Alleen de connectors die de vraag of het gesprek noemt (`agent/bronkeuze.py`, ronde 6, 12 nov 2026).

Elke aangezette connector kostte per modelronde ~2k tokens aan toolschema's, ook als de vraag over één bron ging
(Staatsblad ronde 5: +7k per leesbeurt met alle vier aan). Nu krijgt alleen een genoemde bron haar tools; zonder genoemde
bron blijft alles aan, en een vervolgvraag houdt de keuze van het gesprek. De bronstand zegt het eerlijk (reden `vraag`).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bronmodel.connectors import CONNECTORS, herkende

from agent import bronkeuze
from agent.agent import answer_stream
from agent.bronstand import bepaal, prompt_blok
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

ALLE = dict(connector_kamerstukken=True, connector_rechtspraak=True, connector_bekendmakingen=True,
            connector_wetgeving_live=True)
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
        "rechtspraak": "vraag", "bekendmakingen": "vraag", "wetgeving_live": "vraag"}


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
    assert "Rechtspraak doet in deze beurt niet mee, omdat je vraag een andere bron noemt." in blok


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


def test_een_wet_buiten_de_graaf_beperkt_alleen_niet():
    """B23: een wijzigingswet die de graaf niet kent, kan over het Staatsblad gaan; alleen een andere genoemde bron beperkt."""
    assert bronkeuze.genoemd(["Wat verandert de Wet X 2025?"], buiten_graaf=True) == set()
    assert bronkeuze.genoemd([MVT], buiten_graaf=True) == {"kamerstukken", "wetgeving_live"}


@pytest.mark.parametrize("bestand,eigen", [
    ("kamerstukken_vragenset_30", "kamerstukken"), ("rechtspraak_vragenset_30", "rechtspraak"),
    ("bekendmakingen_vragenset", "bekendmakingen"), ("wetgeving_live_vragenset", "wetgeving_live")])
def test_geen_vraag_uit_de_vragensets_verliest_haar_eigen_bron(bestand, eigen):
    vragen = json.loads((Path(__file__).parent / "data" / f"{bestand}.json").read_text(encoding="utf-8"))["vragen"]
    for q in vragen:
        vraag = q.get("vraag") or q.get("tekst") or ""
        for buiten in (False, True):
            stand, _ = bronkeuze.kies(_stand(), bronkeuze.genoemd([vraag], buiten_graaf=buiten), None)
            assert eigen in bronkeuze.actief(stand), (q.get("id"), vraag)
