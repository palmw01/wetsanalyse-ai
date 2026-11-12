"""De prompt kent de bronnen van de beurt (ADR-013), uit de beschrijving en de bronstand.

Het stabiele deel van de prompt (binnen de cache) is generiek: BRONSOORTEN zegt hoe een bron naast de wet zich tot de
wet verhoudt, zonder één connector te noemen. Welke connectors aanstaan en waarom niet, staat in BRONNEN IN DEZE BEURT,
in het variabele deel. Zonder aangeboden connector en zonder genoemde bron is dat blok leeg: de prompt is dan gelijk
aan een straat zonder connectors.
"""
from __future__ import annotations

import asyncio

from bronmodel import connectors as bm

from agent import bronstand
from agent.agent import answer_stream
from agent.prompts import SYSTEM_PROMPT
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

AAN = make_settings(connector_kamerstukken=True, enable_planning=False)
UIT = make_settings(enable_planning=False)


def _system(settings, bronnen, vraag="Wat zegt artikel 9?"):
    llm = FakeLLM([response([text_block("Antwoord.")], "end_turn")])

    async def loop():
        async for _ in answer_stream(vraag, settings=settings, llm=llm, graph=FakeGraph(result=""), bronnen=bronnen,
                                     bronnen_herkomst="gesprek"):
            pass

    asyncio.run(loop())
    # De nep plakt [stabiel, variabel] aaneen; het stabiele deel begint met SYSTEM_PROMPT en het blok komt erna.
    tekst = llm.prompts[0]
    i = tekst.find("BRONNEN IN DEZE BEURT –")
    return (tekst, "") if i < 0 else (tekst[:i], tekst[i:])


def test_het_stabiele_deel_noemt_geen_connector():
    for c in bm.CONNECTORS.values():
        for woord in (c.label, c.groep):
            assert woord.lower() not in SYSTEM_PROMPT.lower(), f"{woord} hoort in het variabele blok"
    assert "BRONSOORTEN" in SYSTEM_PROMPT and "onderbouwt nooit wat de wet zegt" in SYSTEM_PROMPT


def test_het_stabiele_deel_is_gelijk_bij_elke_bronstand():
    for settings, bronnen in ((AAN, ["kamerstukken"]), (AAN, []), (UIT, None)):
        stabiel, _ = _system(settings, bronnen)
        assert stabiel.startswith(SYSTEM_PROMPT), "het blok hoort na het cachepunt, niet erin"


def test_aan_noemt_wat_de_bron_dekt_en_zijn_grenzen():
    variabel = _system(AAN, ["kamerstukken"])[1]
    c = bm.KAMERSTUKKEN
    assert "BRONNEN IN DEZE BEURT" in variabel and f"{c.label}: aan" in variabel
    assert c.dekt in variabel and c.grenzen in variabel and c.rol_in_antwoord in variabel and "kst-…" in variabel


def test_uit_zegt_waarom_en_wie_hem_aanzet():
    variabel = _system(AAN, [])[1]
    assert "Kamerstukken: uit" in variabel and "Bronnen en tools" in variabel and "eigen kennis" in variabel


def test_zonder_aangeboden_connector_geen_blok_tenzij_de_vraag_hem_noemt():
    assert _system(UIT, None)[1] == ""
    variabel = _system(UIT, None, "Wat zegt de memorie van toelichting bij artikel 9?")[1]
    assert "Kamerstukken: uit" in variabel and "niet beschikbaar" in variabel


def test_een_nieuwe_connector_staat_zonder_code_in_het_blok(monkeypatch):
    nep = bm.ConnectorBeschrijving(
        naam="testbron", label="Testbron", brontype="uitspraak", groep="Uitspraken", dekt="uitspraken van een test",
        signalen=(r"\btestgerecht\b",), tools=frozenset({"zoek_testbron"}), leestool="zoek_testbron", lees_argument="id",
        id_prefixen=("ECLI:",), specialisten=frozenset({"duiding"}), rol_in_antwoord="onderbouwt een uitleg", kop_in_antwoord="Uit de testrechtspraak", levert=("uitspraken",), niet_in_tekst=(),
        werkwoorden={"zoek_testbron": ("zoekt uitspraken over „{zoekterm}”", "zoekt uitspraken")},
        grenzen="alleen een test", beheer="Nep.", voorbeeldvragen=("Wat zei het testgerecht?",))
    monkeypatch.setitem(bm.CONNECTORS, nep.naam, nep)
    s = AAN.model_copy(update={"connector_testbron": True}) if "connector_testbron" in AAN.model_fields else AAN
    stand = bronstand.bepaal(s, None)
    stand["testbron"] = {"naam": "testbron", "label": "Testbron", "aan": True, "reden": "aan"}
    blok = bronstand.prompt_blok(stand)
    assert "Testbron: aan. Dekt uitspraken van een test" in blok and "ECLI:…" in blok
