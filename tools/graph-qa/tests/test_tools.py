"""WP-D: de registry levert schema's en dispatcht naar de juiste bouwer."""
from __future__ import annotations

import json

from agent import tools
from agent.graph import schema
from agent.mcp_client import MCPError
from fakes import FakeGraph, make_settings

EXPECTED = {
    "search_annotaties", "overzicht_annotaties", "get_annotatie", "get_annotatiedekking",
    "search_wetgeving", "semantic_search", "get_artikel", "get_lid", "get_bepaling", "list_regelingen",
    "get_regeling_info", "follow_verwijzingen", "verwijst_naar_deze", "referenced_by",
    "inhoudsopgave", "zoek_definitie", "grondslagen", "geldigheid", "bijlagen", "get_context",
    "resolve_begrip", "graph_schema", "raw_sparql", "zoek_opbouw", "overzicht_onderwerp",
    "search_begrippen", "get_begrip",
}


def test_schemas_compleet_en_welgevormd():
    schemas = tools.anthropic_schemas()
    namen = {t["name"] for t in schemas}
    assert namen == EXPECTED
    for t in schemas:
        assert t["input_schema"]["type"] == "object"
        assert t["description"]


def test_anthropic_schemas_filter():
    assert len(tools.anthropic_schemas()) == len(EXPECTED)
    subset = tools.anthropic_schemas(only={"get_artikel", "search_wetgeving"})
    assert {t["name"] for t in subset} == {"get_artikel", "search_wetgeving"}


def test_dispatch_onbekende_tool():
    assert "Onbekende tool" in tools.dispatch("bestaat_niet", FakeGraph(), {})


def test_dispatch_list_regelingen_voert_query_uit():
    g = FakeGraph(result='?regeling\t?citeertitel\n<urn:bwb:BWBR0004770>\t"Invorderingswet 1990"\n')
    out = json.loads(tools.dispatch("list_regelingen", g, {}))
    assert out["resultaten"] == [{"regeling": "urn:bwb:BWBR0004770", "citeertitel": "Invorderingswet 1990"}]
    assert g.queries and "bwb:Regeling" in g.queries[0]


def test_dispatch_get_artikel():
    lid = "urn:bwb:BWBR0004770:artikel:9:lid:1"
    g = FakeGraph(result=f'?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\n\t"jci1.3:c:BWBR0004770&artikel=9"\t<{lid}>\t"1"\t"De ontvanger vordert in."\n')
    out = json.loads(tools.dispatch("get_artikel", g, {"bwb_id": "BWBR0004770", "artikel": "9"}))
    assert out["artikel"]["iri"] == "urn:bwb:BWBR0004770:artikel:9"
    assert out["resultaten"] == [{"lid": lid, "nummer": "1", "tekst": "De ontvanger vordert in."}]
    assert ":artikel:9>" in g.queries[0]


_LID3 = "urn:bwb:BWBR0004770:artikel:22:lid:3"
_INT = "^^<http://www.w3.org/2001/XMLSchema#integer>"


def _lid3(*rijen: tuple[str, str, str, int | None]) -> FakeGraph:
    kop = "?tekst\t?o\t?onummer\t?otekst\t?ovolg\n"
    regels = [f'"Behoudens …, kunnen derden nimmer verzet in rechte doen tegen:"\t<{iri}>\t"{nr}"\t"{tekst}"\t'
              + (f'"{volg}"{_INT}' if volg is not None else "") for iri, nr, tekst, volg in rijen]
    return FakeGraph(result=kop + "\n".join(regels) + "\n")


def test_een_slottekst_staat_na_de_onderdelen_zoals_in_de_wet():
    """Acceptatie 7 nov 2026: Iw 22 lid 3 stond als aanhef, slotzin, a, b. De query sorteerde op `bwb:volgnummer`, maar
    de handler sorteerde daarna op de IRI, en een slottekst heeft geen `:o:` in zijn IRI."""
    slot = f"urn:bwb:BWBR0004770:id:BWBR0004770%2FLid3%2FSlottekst1"
    g = _lid3((slot, "", "indien de vruchten zich op de bodem bevinden.", 9),
              (f"{_LID3}:o:a", "a.", "de beslaglegging ter zake van naheffingsaanslagen in:", 1),
              (f"{_LID3}:o:a:o:1", "1°.", "de loonbelasting;", 2),
              (f"{_LID3}:o:b", "b.", "de beslaglegging ter zake van:", 6))
    uit = json.loads(tools.dispatch("get_lid", g, {"bwb_id": "BWBR0004770", "artikel": "22", "lid": "3"}))
    assert [r.get("nummer", "") for r in uit["resultaten"]] == ["a.", "1°.", "b.", ""]
    assert "?ovolg" in g.queries[0].split("WHERE")[0], "het volgnummer moet in de SELECT staan, niet alleen in ORDER BY"


def test_zonder_volgnummer_blijft_de_volgorde_uit_de_iri():
    """Een graaf van vóór het volgnummer: dan a … z vóór aa en genest direct na de ouder, zoals altijd."""
    g = _lid3((f"{_LID3}:o:aa", "aa.", "x", None), (f"{_LID3}:o:b", "b.", "y", None), (f"{_LID3}:o:a", "a.", "z", None))
    uit = json.loads(tools.dispatch("get_lid", g, {"bwb_id": "BWBR0004770", "artikel": "22", "lid": "3"}))
    assert [r["nummer"] for r in uit["resultaten"]] == ["a.", "b.", "aa."]


def test_een_bepaling_die_nog_niet_geldt_zegt_dat_bij_de_tekst():
    g = FakeGraph(result='?tekst\t?status\n"Tekst."\t"nogniet"\n')
    uit = {"artikel": ("get_artikel", {"artikel": "57a"}), "lid": ("get_lid", {"artikel": "6f", "lid": "1"})}
    for kop, (tool, args) in uit.items():
        assert json.loads(tools.dispatch(tool, g, {"bwb_id": "BWBR0004770", **args}))[kop]["nog_niet_in_werking"] is True
    g = FakeGraph(result='?node\t?status\n<urn:bwb:BWBR0004770:artikel:9>\t"nogniet"\n')
    assert json.loads(tools.dispatch("get_bepaling", g, {"bwb_id": "BWBR0004770", "nummer": "9"}))["bepaling"]["nog_niet_in_werking"] is True
    g = FakeGraph(result='?tekst\t?status\n"Tekst."\t"goed"\n')
    assert "nog_niet_in_werking" not in json.dumps(json.loads(tools.dispatch("get_artikel", g, {"bwb_id": "BWBR0004770", "artikel": "9"})))


def test_dispatch_vangt_validatiefout_op():
    g = FakeGraph()
    out = tools.dispatch("get_artikel", g, {"bwb_id": "kwaadaardig", "artikel": "9"})
    assert out.startswith("Fout bij tool 'get_artikel'")
    assert not g.queries  # query is nooit uitgevoerd


def test_dispatch_vangt_transportfout_op():
    # F1: een httpx-transportfout (timeout/connection-reset) tijdens een tool-call mag de agent-beurt
    # niet breken – dispatch geeft 'm als tool-resultaat terug zodat de agent kan herstellen.
    import httpx

    def _kapot(_q: str) -> str:
        raise httpx.ConnectError("connection refused")

    g = FakeGraph(results=_kapot)
    out = tools.dispatch("get_artikel", g, {"bwb_id": "BWBR0004770", "artikel": "9"})
    assert out.startswith("Fout bij tool 'get_artikel'")
    assert "onbereikbaar" in out.lower()


def test_dispatch_raw_sparql_forwards_query():
    g = FakeGraph(result="?s\n<urn:bwb:BWBR0004770>\n")
    query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 5"
    out = json.loads(tools.dispatch("raw_sparql", g, {"query": query}))
    assert g.queries == [query]
    assert out["resultaten"] == [{"s": "urn:bwb:BWBR0004770"}]


def test_dispatch_get_context():
    g = FakeGraph(result='?relatie\t?a\t?b\n"1-zelf-label"\t"Artikel 9"\t""\n')
    out = json.loads(tools.dispatch("get_context", g, {"bwb_id": "BWBR0004770", "artikel": "9"}))
    assert out["resultaten"] == [{"relatie": "1-zelf-label", "a": "Artikel 9"}]
    q = g.queries[0]
    assert "verwijzingDoor" in q and "heeftVerwijzing" in q
    assert "bwb:bevat" not in q and "bwb:heeftHoofdstuk" in q


def test_semantic_search_zonder_index_degradeert():
    g = FakeGraph(result="treffers")
    out = tools.dispatch("semantic_search", g, {"query": "belasting te laat"}, make_settings())
    assert "niet geconfigureerd" in out.lower()
    assert g.semantic_queries == []  # graaf niet geraakt


def test_semantic_search_met_index_roept_graaf():
    # De index levert Turtle (subject + typen); de tool maakt er rijen van in het resultaatcontract.
    turtle = ("@prefix bwb: <urn:bwb-ns:> .\n\n<urn:bwb:BWBR0004770:artikel:25> a bwb:Artikel, bwb:Citeerbaar .\n"
              "<urn:bwb:BWBR0004770:artikel:19:lid:2:o:a> a bwb:Onderdeel .")
    g = FakeGraph(result=turtle)
    settings = make_settings(similarity_index="bwb_similarity")
    out = json.loads(tools.dispatch("semantic_search", g, {"query": "belasting te laat"}, settings))
    assert out["volledig"] is True
    assert out["resultaten"] == [{"node": "urn:bwb:BWBR0004770:artikel:25", "soort": "Artikel"},
                                 {"node": "urn:bwb:BWBR0004770:artikel:19:lid:2:o:a", "soort": "Onderdeel"}]
    assert g.semantic_queries == ["belasting te laat"]


def test_semantic_search_limit_geclampt():
    # L5: limit clampen 1–50 en niet-int gracieus terugvallen op de default (10). De index telt
    # triples, niet treffers: de tool vraagt (offset + limit + 1) × _TRIPLES_PER_TREFFER op.
    from types import SimpleNamespace

    from agent.tools import _TRIPLES_PER_TREFFER as T, _h_semantic_search

    captured: dict[str, int] = {}

    class G:
        def semantic_search(self, query: str, limit: int = 10) -> str:
            captured["limit"] = limit
            return ""

    s = SimpleNamespace(similarity_index="bwb_similarity")
    _h_semantic_search(G(), {"query": "x", "limit": 100000}, s)
    assert captured["limit"] == (50 + 1) * T
    _h_semantic_search(G(), {"query": "x", "limit": 0}, s)
    assert captured["limit"] == (1 + 1) * T
    _h_semantic_search(G(), {"query": "x", "limit": "abc"}, s)
    assert captured["limit"] == (10 + 1) * T


# ------------------------------------------------- de graaf is leeg opgekomen
def _graaf_zonder_repository() -> FakeGraph:
    """Een graaf die antwoordt zoals GraphDB doet vlak na een herstart: de repository bestaat niet."""
    def kapot(_query: str) -> str:
        raise MCPError("MCP-fout: {'message': \"Repository inning doesn't exist\"}")

    return FakeGraph(results=kapot)


def test_ontbrekende_repository_krijgt_een_eigen_melding():
    """Een lege GraphDB mag de jurist niet de kale GraphDB-foutmelding geven.

    De weigering om uit eigen kennis te antwoorden blijft — die was juist correct — maar het
    tool-resultaat zegt nu wát er speelt en dat het vanzelf overgaat.
    """
    out = tools.dispatch("list_regelingen", _graaf_zonder_repository(), {})
    assert "niet beschikbaar" in out
    assert "herstart" in out
    assert "NIET uit eigen kennis" in out


def test_ontbrekende_repository_wordt_apart_gelogd(caplog):
    """`graaf_weg` is het veld waarop het Grafana-alarm filtert; zonder dat ziet niemand de uitval."""
    import logging

    with caplog.at_level(logging.ERROR, logger="graph_qa.tools"):
        tools.dispatch("list_regelingen", _graaf_zonder_repository(), {})
    assert [r for r in caplog.records if getattr(r, "graaf_weg", False) is True]


def test_een_gewone_mcp_fout_blijft_een_gewone_fout():
    """Een tikfout in een query mag niet als 'de graaf is weg' lezen — dan is het alarm ruis."""
    def kapot(_query: str) -> str:
        raise MCPError("The following IRIs are not used in the data stored in GraphDB")

    out = tools.dispatch("list_regelingen", FakeGraph(results=kapot), {})
    assert "niet beschikbaar" not in out
    assert out.startswith("Fout bij tool 'list_regelingen'")


def test_semantic_search_leest_het_echte_turtle_antwoord():
    """Zo antwoordt de index echt (fixture van 7 okt 2026): JSON-string-omhuld, het subject op een eigen
    regel, typen over meerdere regels, en een blok zonder type met alleen structuurrelaties. Een
    regex die `<iri> a …` op één regel verwachtte vond hier niets – 0 treffers, terwijl de index er
    wel gaf (de golden-case 'Kan de ontvanger een betalingsregeling weigeren?' zakte erop)."""
    from pathlib import Path

    from agent.tools import _semantische_treffers

    turtle = (Path(__file__).parent / "fixtures" / "semantic_search_turtle.txt").read_text(encoding="utf-8")
    treffers = _semantische_treffers(turtle)
    assert [t["node"] for t in treffers] == [
        "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie36%2FCirculaire.divisie36.5%2F"
        "Circulaire.divisie36.5.1%2FTekst%2FOnderdeel._1",
        "urn:bwb:BWBR0004766:artikel:2:lid:3:o:a",
    ], "rangorde van de index, zonder het structuurblok"
    assert treffers[0]["soort"] == "Onderdeel" and treffers[0]["tekst"].startswith("onvoldoende liquide middelen")
    assert treffers[1]["jci"].startswith("jci1.3:c:BWBR0004766&") and treffers[1]["label"] == "Onderdeel a."
