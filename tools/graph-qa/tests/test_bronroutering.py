"""Scope en routering kennen de bronconnectors (ADR-013), uit de beschrijving en niet per connector.

Aanleiding (acceptatie, 8 nov 2026): "wat kun je nog vinden in de kamerstukken?" kreeg de scope-weigering, en een vraag
naar de memorie van toelichting bij een Kamerstuk kreeg zonder één toolaanroep "maakt geen deel uit van de
kennisgraaf". Nu:

- een vraag die alleen over een uitgezette bron gaat, krijgt zonder model een melding met wie hem aanzet;
- een vraag over een bron naast de wet wordt nooit afgewezen, ook niet als het model AFWIJZEN zegt;
- staat de bron aan, dan krijgt de specialist haar tools;
- de supervisor kent elke bekende connector als scope, ook een die uit staat.
"""
from __future__ import annotations

import asyncio

import pytest
from bronmodel import connectors as bm

from agent import bronstand, supervisor
from agent.agent import answer_stream
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

AAN = make_settings(connector_kamerstukken=True)
UIT = make_settings()
INCIDENT_1 = "wat kun je nog vinden in de kamerstukken?"
INCIDENT_2 = "Wat staat er in de memorie van toelichting bij Kamerstuk 33755, nummer 3, over de aansprakelijkheid?"
AFWIJZEN = response([text_block("WORKERS: antwoord\nSPECIALIST: algemeen\nTAAK:\nPLAN: AFWIJZEN")], "end_turn")


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


@pytest.mark.parametrize("settings,bronnen,herkomst,zin", [
    (AAN, [], "gesprek", "staat uit in dit gesprek"),
    (AAN, [], "werkgebied", "standaard van dit werkgebied"),
    (UIT, None, None, "op deze omgeving niet beschikbaar"),
])
@pytest.mark.parametrize("vraag", [INCIDENT_1, INCIDENT_2])
def test_een_uitgezette_bron_krijgt_een_eerlijke_melding_zonder_model(settings, bronnen, herkomst, zin, vraag):
    llm = FakeLLM([])
    graaf = FakeGraph(result="")
    events = _run(answer_stream(vraag, settings=settings, llm=llm, graph=graaf, bronnen=bronnen,
                                bronnen_herkomst=herkomst))
    tekst = _tekst(events)
    assert zin in tekst and "Kamerstukken" in tekst
    assert "niet over Nederlandse wet- en regelgeving" not in tekst, "dit is geen afwijzing"
    assert llm.calls == [] and graaf.queries == [], "geen model en geen graaf: de melding komt uit code"
    assert events[-1]["type"] == "done"


def test_een_vraag_over_een_bron_wordt_nooit_afgewezen_en_krijgt_de_tools():
    llm = FakeLLM([AFWIJZEN, response([text_block("Ik zocht het stuk op.")], "end_turn")])
    events = _run(answer_stream(INCIDENT_2, settings=AAN, llm=llm, graph=FakeGraph(result=""),
                                bronnen=["kamerstukken"], bronnen_herkomst="gesprek"))
    assert len(llm.calls) == 2, "het model zei AFWIJZEN, de code liet de worker toch zoeken"
    namen = {t["name"] for t in llm.calls[1]["tools"]}
    assert bm.KAMERSTUKKEN.tools <= namen
    assert "AFWIJZEN" not in str(llm.calls[1]["system"]), "het plan van een afwijzing hoort niet bij de worker"
    assert "Ik zocht" in _tekst(events)


def test_een_gemengde_vraag_gaat_naar_het_model_ook_met_de_bron_uit():
    """Een artikel is wetgeving om te zoeken; wat er uit staat, zegt het promptblok (PR 4)."""
    llm = FakeLLM([response([text_block("WORKERS: antwoord\nSPECIALIST: duiding\nTAAK:\nPLAN: zoek art. 36")],
                            "end_turn"),
                   response([text_block("Artikel 36 gaat over aansprakelijkheid.")], "end_turn")])
    events = _run(answer_stream("Wat bedoelde de wetgever met artikel 36 van de Invorderingswet 1990?",
                                settings=AAN, llm=llm, graph=FakeGraph(result=""), bronnen=[]))
    assert len(llm.calls) == 2 and "aansprakelijkheid" in _tekst(events)


def test_een_gewone_vraag_buiten_de_wet_blijft_afgewezen():
    events = _run(answer_stream("Hoeveel is 17 maal 23?", settings=AAN, llm=FakeLLM([AFWIJZEN]),
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    assert "niet over Nederlandse wet- en regelgeving" in _tekst(events)


def test_de_scope_van_de_supervisor_noemt_elke_bekende_connector():
    for c in bm.CONNECTORS.values():
        assert c.label in supervisor.SUPERVISOR_SYSTEM and c.dekt in supervisor.SUPERVISOR_SYSTEM
    # De grens voor wat wél wordt afgewezen staat er nog letterlijk.
    assert "AFWIJZEN als de vraag niet over Nederlandse wet- en regelgeving gaat" in supervisor.SUPERVISOR_SYSTEM


def test_elke_reden_heeft_een_zin():
    stand = bronstand.bepaal(UIT, None)
    for reden in ("straat", "register_onleesbaar", "beheerder", "gesprek", "werkgebied"):
        stand["kamerstukken"]["reden"] = reden
        zin = bronstand.uit_zin(stand, "kamerstukken")
        assert "Kamerstukken" in zin and "{" not in zin


# --- het generieke bewijs -------------------------------------------------------------------------------------

def test_een_nieuwe_connector_wordt_herkend_en_gemeld_zonder_code(monkeypatch):
    nep = bm.ConnectorBeschrijving(
        naam="testbron", label="Testbron", brontype="uitspraak", groep="Uitspraken",
        dekt="uitspraken van een testgerecht", signalen=(r"\btestgerecht\b",), tools=frozenset({"zoek_testbron"}),
        leestool="zoek_testbron", id_prefixen=("ECLI:",), specialisten=frozenset({"duiding"}),
        rol_in_antwoord="een uitspraak onderbouwt een uitleg", kop_in_antwoord="Uit de testrechtspraak", levert=("uitspraken",), niet_in_tekst=(),
        werkwoorden={"zoek_testbron": ("zoekt uitspraken over „{zoekterm}”", "zoekt uitspraken")}, grenzen="alleen een test", beheer="Nep.",
        voorbeeldvragen=("Wat zei het testgerecht?",))
    monkeypatch.setitem(bm.CONNECTORS, nep.naam, nep)
    assert "uitspraken van een testgerecht" in supervisor._scope_bronnen()
    llm = FakeLLM([])
    events = _run(answer_stream("Wat zei het testgerecht erover?", settings=AAN, llm=llm,
                                graph=FakeGraph(result=""), bronnen=["kamerstukken"]))
    assert "Testbron is op deze omgeving niet beschikbaar" in _tekst(events) and llm.calls == []


def test_de_melding_draagt_een_event_waarmee_de_werkplek_hem_aanzet():
    events = _run(answer_stream(INCIDENT_1, settings=AAN, llm=FakeLLM([]), graph=FakeGraph(result=""), bronnen=[],
                                bronnen_herkomst="gesprek"))
    uit, = [e for e in events if e["type"] == "bron_uit"]
    assert uit["bronnen"] == [{"naam": "kamerstukken", "label": "Kamerstukken", "reden": "gesprek"}]


def test_het_endpoint_noemt_elke_connector_met_de_straat(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    monkeypatch.setattr(main.settings, "qa_api_token", "", raising=False)
    for aan in (False, True):
        monkeypatch.setattr(main.settings, "connector_kamerstukken", aan, raising=False)
        # Zonder `with`: de lifespan (graaf, api) hoort niet bij deze lichte route.
        r = TestClient(main.app).get("/v1/bronnen")
        assert r.status_code == 200
        assert r.json()["bronnen"] == [{"naam": n, "label": b.label, "brontype": b.brontype, "groep": b.groep,
                                        "straat": aan} for n, b in bm.CONNECTORS.items()]
