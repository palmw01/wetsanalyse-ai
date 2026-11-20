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


# --- het regelantwoord (laatste meting na #1797) -----------------------------------------------------------------------

def _trace_regels():
    import json
    zoek = json.dumps({"status": "ok", "resultaten": [
        {"id": "r1", "naam": "bepalen van de vervaldag", "uitvoer": "vervaldag", "regel_status": "concept",
         "werkgebied_id": "w1", "werkgebied": "Termijnen"},
        {"id": "r2", "naam": "bepalen van de vervaldag bij betaling ineens", "regel_status": "vervangen",
         "werkgebied_id": "w1", "werkgebied": "Termijnen"}]})
    from agent.tools.regel_tools import compact_regel
    lees = json.dumps({"bewijssoort": "regel", **compact_regel({**REGEL, "opvolging": {
        "vervangen_door": None, "vervangt": [{"id": "r2", "naam": "bepalen van de vervaldag bij betaling ineens"}]}})})
    return [("search_regels", zoek), ("get_regel", lees)]


def test_het_sjabloon_vult_de_feiten_uit_de_api():
    from agent.sjablonen import vul
    a = vul("antwoord_regels", {"kort_antwoord": "Eén regel bepaalt de vervaldag.", "regels": ["r1", "r2"], "twijfel": []},
            _trace_regels())
    blok = next(b for b in a.blokken if b.soort == "regels")
    r1, r2 = blok.items
    assert (r1.naam, r1.status, r1.gelezen, r1.open_punten) == ("bepalen van de vervaldag", "concept", True, 0)
    assert r1.vervangt[0].naam == "bepalen van de vervaldag bij betaling ineens" and r1.dragers[0].jci
    assert r1.gevallen == [{"label": "lid 1", "tekst": "zes weken na …"}]
    assert (r2.status, r2.gelezen) == ("vervangen", False)
    # De doelen zijn de bronnodes van elke drager die niet is afgewezen, ook context (slotmeting na #1798: LI 9.5).
    assert [d.iri for d in a.doelen] == ["urn:bwb:BWBR0004770:artikel:9:lid:1", "urn:bwb:BWBR0024096:id:x"]


def test_een_onbekende_regel_weigert_het_sjabloon():
    from agent.sjablonen import Onvulbaar, vul
    with pytest.raises(Onvulbaar) as fout:
        vul("antwoord_regels", {"kort_antwoord": "x", "regels": ["verzonnen"], "twijfel": []}, _trace_regels())
    assert fout.value.code == "regel_onbekend"
    with pytest.raises(Onvulbaar):
        vul("antwoord_regels", {"kort_antwoord": "x", "regels": [], "twijfel": []}, [])


def test_een_tekstantwoord_in_de_route_wordt_het_regelsjabloon():
    llm = FakeLLM([response([text_block("Hieronder volgt het antwoord.\n\nDe regel bepalen van de vervaldag is een "
                                        "concept en rust op artikel 9, lid 1.")], "end_turn")])
    port = _Port([{"id": "r1", "naam": "bepalen van de vervaldag", "status": "concept", "werkgebied_id": "w1"}])
    events = run(answer_stream(VRAAG, llm=llm, graph=FakeGraph(), regels=port, werkgebied_id="w1",
                               settings=make_settings(), run_id="r1"))
    assert not [e for e in events if e["type"] == "error"], events
    antwoord = next(e["antwoord"] for e in events if e["type"] == "antwoord")
    assert antwoord["sjabloon"] == "regels" and [b["soort"] for b in antwoord["blokken"]] == ["toelichting", "regels"]
    assert not antwoord["blokken"][0]["tekst"].startswith("Hieronder")
    assert len(llm.calls) == 1                                      # geen extra modelronde
    bronnen = next(e["sources"] for e in events if e["type"] == "sources")
    assert any(b.get("brontype") == "regel" and b["link"] == "/werkgebieden/w1/regels/r1" for b in bronnen)
    assert any(b["uri"] == "urn:bwb:BWBR0004770:artikel:9:lid:1" for b in bronnen)


def test_een_regelnaam_tussen_aanhalingstekens_is_geen_wetcitaat():
    from agent.grounding import check_grounding
    trace = _trace_regels() + [("get_lid", '{"tekst": "Een belastingaanslag is invorderbaar zes weken na de dagtekening."}')]
    goed = check_grounding('De regel "bepalen van de vervaldag bij betaling ineens" is vervangen.', trace)
    assert goed.niet_letterlijk == []
    fout = check_grounding('De wet zegt "een aanslag is altijd na vier weken invorderbaar".', trace)
    assert fout.niet_letterlijk


def test_een_zoekrij_draagt_dezelfde_opvolging_als_een_gelezen_regel():
    import json
    from agent.sjablonen.regels import regels_in_trace
    from agent.tools.regel_tools import _rij
    rij = _rij({"id": "r2", "naam": "oud", "status": "vervangen", "werkgebied_id": "w1",
                "opvolging": {"vervangen_door": {"id": "r1", "naam": "bepalen van de vervaldag"}, "vervangt": []}})
    assert rij["vervangen_door"] == {"id": "r1", "naam": "bepalen van de vervaldag"}
    regel = regels_in_trace([("search_regels", json.dumps({"status": "ok", "resultaten": [rij]}))])["r2"]
    assert regel.vervangen_door.naam == "bepalen van de vervaldag" and not regel.gelezen


def test_een_drager_staat_per_geval_een_keer_per_element_en_rol():
    import json
    from agent.sjablonen.regels import regels_in_trace
    d = {"element_id": "e1", "rol": "voorwaarde", "geval": "lid 5", "passage": "Indien de toepassing …",
         "vindplaats": "Artikel 9, lid 5", "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:5"}
    r = {"status": "ok", "id": "r1", "naam": "x", "regel_status": "concept",
         "dragers": [d, dict(d), {**d, "geval": "lid 1"}, {**d, "rol": "grondslag"}]}
    regel = regels_in_trace([("get_regel", json.dumps(r))])["r1"]
    assert [(x.geval, x.rol) for x in regel.dragers] == [("lid 5", "voorwaarde"), ("lid 1", "voorwaarde"), ("lid 5", "grondslag")]


def test_de_regeltekst_als_lijst_houdt_de_voorwaarden_van_een_geval():
    from bronmodel.antwoord import Regels, VastgelegdeRegel, antwoord_tekst, Antwoord
    r = VastgelegdeRegel(id="r1", naam="bepalen van de vervaldag", status="concept",
                         gevallen=[{"label": "lid 1", "tekst": "indien aan alle volgende voorwaarden is voldaan:\n• niet: a\ndan: zes weken."}])
    tekst = antwoord_tekst(Antwoord(sjabloon="regels", blokken=[Regels(items=[r])]))
    assert "lid 1: indien aan alle volgende voorwaarden is voldaan:" in tekst and "• niet: a" in tekst and "dan: zes weken." in tekst
