"""De leesroute voor afleidingsregels (ADR-010; lichte meting #1792, 20 nov 2026): een vraag over de vastgelegde regels
gaat zonder model naar de route, de code zoekt en leest de regels, en het profiel `regels_lezen` formuleert. Een vraag
naar markeringen van de klasse Afleidingsregel blijft een vraag over annotaties."""
from __future__ import annotations

import asyncio

import pytest

from agent.agent import answer_stream
from agent.sjablonen.vullen import artikel_in_trace
from agent.tools.regel_tools import is_regel_leesvraag, zoekterm_regel
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block
from test_regel_tools import REGEL

VRAAG = "Welke afleidingsregels bepalen de vervaldag van een termijn, en op welke artikelen rusten ze?"


@pytest.mark.parametrize("vraag, lees, term", [
    (VRAAG, True, "vervaldag"),
    ("Welke afleidingsregels hebben we in Termijnen?", True, ""),
    ("Wat zegt de rekenregel voor het termijnbedrag?", True, "termijnbedrag"),
    ("Welke formuleringen zijn als afleidingsregel gemarkeerd in artikel 9?", False, ""),
    ("Stel een afleidingsregel op voor het termijnbedrag", False, "termijnbedrag"),
    ("Accordeer de afleidingsregel voor de vervaldag", False, "vervaldag"),
    ("Wanneer vervalt een termijn?", False, ""),
    # De stand en de opvolging van regels (herhaalmeting na #1796, run 9b6d4e23).
    ("Welke regels zijn vervangen, en door welke regel?", True, ""),
    ("Welke regels zijn al geaccordeerd?", True, ""),
    ("Welke regels staan nog als concept?", True, ""),
    ("Welke regels zijn afgewezen?", True, ""),
    ("Wat is de opvolger van de regel voor de vervaldag?", True, "vervaldag"),
    # Wettekst, of een opdracht: niet.
    ("Welke regels gelden voor de invordering?", False, ""),
    ("Welke regels van de Invorderingswet zijn vervangen?", False, ""),
    ("Welke regels uit artikel 9 zijn vervangen?", False, ""),
    ("Welke afleidingsregels zijn gemarkeerd en vervangen?", False, ""),
    ("Wijs de regel af, hij is vervangen", False, ""),
])
def test_herkennen(vraag, lees, term):
    assert is_regel_leesvraag(vraag) is lees
    if lees:
        assert zoekterm_regel(vraag) == term


class _Port:
    werkgebied_id = "w1"

    def __init__(self, rijen):
        self.rijen, self.calls = rijen, []

    def zoek(self, q, status, wg):
        self.calls.append(("zoek", q, wg))
        rijen = [r for r in self.rijen if not q or q in r["naam"]]
        return {"status": "ok", "resultaten": rijen, "per_status": {}}

    def regel(self, wg, rid):
        self.calls.append(("regel", wg, rid))
        return {"status": "ok", "regel": REGEL}


def run(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def test_de_route_zoekt_en_leest_de_regels_voor_het_model():
    llm = FakeLLM([response([text_block("De regel bepalen van de vervaldag (concept) rust op artikel 9, lid 1.")],
                            "end_turn")])
    port = _Port([{"id": "r1", "naam": "bepalen van de vervaldag", "status": "concept", "werkgebied_id": "w1"}])
    events = run(answer_stream(VRAAG, llm=llm, graph=FakeGraph(), regels=port, werkgebied_id="w1",
                               settings=make_settings(), run_id="r1"))
    assert not [e for e in events if e["type"] == "error"], events
    aanroepen = [e["tool"] for e in events if e["type"] == "tool_execution" and e.get("fase", "einde") != "start"]
    assert "search_regels" in aanroepen and "get_regel" in aanroepen
    assert port.calls[0] == ("zoek", "vervaldag", "w1") and ("regel", "w1", "r1") in port.calls
    # Het model kreeg het kleine profiel, met de regeltools en de wettekst om te citeren, en niet meer_tools.
    namen = {t["name"] for t in llm.calls[0]["tools"]}
    assert {"search_regels", "get_regel", "get_artikel", "get_lid"} <= namen and "meer_tools" not in namen


def test_vindt_de_term_niets_dan_zoekt_de_route_alle_regels():
    llm = FakeLLM([response([text_block("Er liggen geen regels over dat onderwerp.")], "end_turn")])
    port = _Port([{"id": "r1", "naam": "bepalen van het termijnbedrag", "status": "concept", "werkgebied_id": "w1"},
                  {"id": "r2", "naam": "x", "status": "concept", "werkgebied_id": "w1"},
                  {"id": "r3", "naam": "y", "status": "concept", "werkgebied_id": "w1"},
                  {"id": "r4", "naam": "z", "status": "concept", "werkgebied_id": "w1"}])
    run(answer_stream(VRAAG, llm=llm, graph=FakeGraph(), regels=port, werkgebied_id="w1", settings=make_settings()))
    assert [c[:2] for c in port.calls] == [("zoek", "vervaldag"), ("zoek", "")]   # vier treffers: niet elk lezen


def test_een_drager_van_een_regel_wijst_het_artikel_aan_om_op_te_halen():
    """Gat 2 van de meting: "artikel 9" uit de dragers van een regel was voor het duidingssjabloon onbekend. Een afgeleid
    resultaat is nooit de bron, maar wijst wel aan wat de code ophaalt."""
    trace = [("get_regel", '{"dragers": [{"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1"}]}')]
    assert artikel_in_trace("9", trace) == ""
    assert artikel_in_trace("9", trace, ook_afgeleid=True) == "urn:bwb:BWBR0004770:artikel:9"


def test_het_duidingssjabloon_haalt_zo_n_artikel_op_in_plaats_van_het_onbekend_te_noemen():
    from agent.sjablonen.duiding import _genoemd_is_gelezen
    trace = [("get_regel", '{"dragers": [{"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1"}]}')]
    fout = _genoemd_is_gelezen(["artikel 9"], {}, trace)
    assert fout.code == "genoemd_op_te_halen" and fout.ophalen == [{"bwb_id": "BWBR0004770", "artikel": "9"}]


def test_de_dragers_van_een_gelezen_regel_staan_in_de_bronnen():
    """Ook een Leidraad-divisie zonder jci (herhaalmeting na #1796: LI 9.1 en 9.5 geciteerd, niet in de bronnen)."""
    import json
    from agent.provenance import collect_sources
    li = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.1"
    raw = json.dumps({"dragers": [{"bron_iri": li, "vindplaats": "Leidraad Invordering 2008 – Artikel 9, 9.1"},
                                  {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "jci": "jci1.3:c:BWBR0004770&artikel=9&lid=1",
                                   "vindplaats": "Invorderingswet 1990 – Artikel 9, Lid 1"},
                                  {"bron_iri": li, "vindplaats": "dubbel"}]})
    bronnen = collect_sources([("get_regel", raw)])
    assert [(b.uri, b.label) for b in bronnen] == [(li, "Leidraad Invordering 2008 – Artikel 9, 9.1"),
        ("urn:bwb:BWBR0004770:artikel:9:lid:1", "Invorderingswet 1990 – Artikel 9, Lid 1")]
    assert bronnen[1].jci and not bronnen[0].jci
    # De zoektool en een fout zijn geen bron.
    assert collect_sources([("search_regels", raw)]) == []
    assert collect_sources([("get_regel", json.dumps({"status": "error", "reden": "x"}))]) == []


def test_de_opvolging_staat_met_namen_in_het_resultaat():
    from agent.tools.regel_tools import compact_regel
    r = {**REGEL, "opvolging": {"vervangen_door": None, "vervangt": [{"id": "r2", "naam": "bepalen van de vervaldag bij betaling ineens"}]}}
    assert compact_regel(r)["vervangt"] == [{"id": "r2", "naam": "bepalen van de vervaldag bij betaling ineens"}]
    oud = compact_regel({**REGEL, "status": "vervangen", "vervangen_door": "r1"})
    assert oud["vervangen_door"] == {"id": "r1", "naam": ""}


def test_een_aankondiging_zonder_scheidingslijn_is_een_aanloop():
    from agent.narratie import zonder_aanloop
    antwoord, aanloop = zonder_aanloop("Hieronder volgt het volledige antwoord op basis van de opgehaalde regels.\n\nDe regel …")
    assert antwoord == "De regel …" and aanloop.startswith("Hieronder volgt")
    for tekst in ("Hier is de regeling die geldt: artikel 9.\n\nMeer.", "Hieronder staat per regel de stand.\n\n- a"):
        assert zonder_aanloop(tekst) == (tekst, "")
