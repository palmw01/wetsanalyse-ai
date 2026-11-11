"""WP-C: bronnen komen uit de tool-trace, niet uit prozatekst."""
from __future__ import annotations

from agent.provenance import collect_sources

ART_IRI = "urn:bwb:BWBR0004770:artikel:9"
JCI = "jci1.3:c:BWBR0004770&artikel=9&lid=1"


def test_iri_uit_toolresultaat_wordt_bron():
    sources = collect_sources([("graphdb_sparql", f"resultaat: <{ART_IRI}> bwb:nummer 9")])
    uris = [s.uri for s in sources]
    assert ART_IRI in uris
    src = next(s for s in sources if s.uri == ART_IRI)
    assert src.iri == ART_IRI
    assert src.origin_tool == "graphdb_sparql"


def test_jci_vindplaats_wordt_bron():
    # De jci wordt de bronnode: `uri` is de graaf-IRI, de jci blijft bewaard voor de link.
    sources = collect_sources([("graphdb_sparql", f'"{JCI}"')])
    assert [s.uri for s in sources] == [f"{ART_IRI}:lid:1"]
    assert sources[0].jci == JCI
    assert (sources[0].label, sources[0].soort, sources[0].bwb_id) == ("Artikel 9, lid 1", "lid", "BWBR0004770")


def test_iri_en_jci_van_dezelfde_bepaling_zijn_een_bron():
    # Een zoektool levert per treffer de graaf-IRI én de jci; dat waren twee bronnen.
    awb = "urn:bwb:BWBR0005537:artikel:4%3A94a"
    jci = "jci1.3:c:BWBR0005537&artikel=4:94a&z=2026-08-15&g=2026-08-15"
    sources = collect_sources([("search_wetgeving", f"<{awb}> {jci}"), ("get_artikel", jci)])
    assert len(sources) == 1
    assert (sources[0].uri, sources[0].iri, sources[0].jci) == (awb, awb, jci)
    assert sources[0].label == "Artikel 4:94a"


def test_hoofdstuk_valt_niet_samen_met_de_regeling():
    hoofdstuk = "urn:bwb:BWBR0004770:hoofdstuk:I"
    sources = collect_sources([("t", f"{hoofdstuk} jci1.3:c:BWBR0004770&hoofdstuk=I&z=2026-07-01&g=2026-07-01")])
    assert [(s.uri, s.label) for s in sources] == [(hoofdstuk, "Hoofdstuk I")]


def test_verwijzing_zonder_node_blijft_als_vangnet():
    jci = "jci1.3:c:BWBR0005537&bijlage=1&o=a&z=2026-08-15&g=2026-08-15"
    sources = collect_sources([("t", jci)])
    assert [(s.uri, s.label, s.bron_iri) for s in sources] == [(jci, jci, None)]


def test_prozatekst_is_geen_bron():
    # collect_sources krijgt de modeltekst nooit; een gehallucineerde citatie
    # in het eindantwoord kan dus per definitie niet als bron opduiken.
    sources = collect_sources([])
    assert sources == []


def test_vocabulaire_namespace_telt_niet_mee():
    # urn:bwb-ns:... zijn predicaten, geen vindplaatsen.
    sources = collect_sources([("t", "?s <urn:bwb-ns:heeftLid> ?o")])
    assert sources == []


def test_kale_bwb_niet_dubbel_als_al_in_iri():
    sources = collect_sources([("t", f"{ART_IRI} hoort bij BWBR0004770")])
    uris = [s.uri for s in sources]
    assert uris == [ART_IRI]  # geen losse BWBR0004770 erbij


def test_dedup_over_meerdere_rondes():
    sources = collect_sources([("t1", ART_IRI), ("t2", ART_IRI)])
    assert len([s for s in sources if s.uri == ART_IRI]) == 1


def test_wet_lokale_id_node_krijgt_het_label_uit_het_toolresultaat():
    """Leidraad 26.5 stond in de bronnenlijst als kale IRI: een `id:`-node draagt geen label in zijn
    IRI, maar de rij van zoek_opbouw had het wel."""
    from agent.resultaat import resultaat

    iri = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.5"
    tekst = resultaat([{"node": iri, "soort": "Divisie", "bwbId": "BWBR0024096",
                        "label": "Voortzetting van de invordering na afwijzing verzoek om kwijtschelding"}])
    [bron] = collect_sources([("zoek_opbouw", tekst)])
    assert bron.uri == iri
    assert bron.label == "Voortzetting van de invordering na afwijzing verzoek om kwijtschelding"


def test_id_node_zonder_label_houdt_zijn_iri():
    iri = "urn:bwb:BWBR0024096:id:BWBR0024096%2FCirculaire.divisie26%2FCirculaire.divisie26.5"
    [bron] = collect_sources([("raw_sparql", f"?s\n<{iri}>\n")])
    assert bron.label == iri


def test_structuurdeel_krijgt_zijn_titel_uit_het_toolresultaat():
    from agent.resultaat import resultaat

    hfd = "urn:bwb:BWBR0004770:hoofdstuk:II"
    afd = "urn:bwb:BWBR0005537:hoofdstuk:4:titeldeel:4.4:afdeling:4.4.4"
    tekst = resultaat([
        {"node": hfd, "label": "Hoofdstuk II – Invordering in eerste aanleg"},
        {"node": afd, "label": "Afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel"},
        # Een label dat een ánder deel aanduidt, telt niet.
        {"node": "urn:bwb:BWBR0004770:hoofdstuk:III", "label": "Hoofdstuk IV – Iets anders"},
    ])
    labels = {b.uri: b.label for b in collect_sources([("zoek_opbouw", tekst)])}
    assert labels[hfd] == "Hoofdstuk II – Invordering in eerste aanleg"
    assert labels[afd] == "Hoofdstuk 4, titeldeel 4.4, afdeling 4.4.4 – Aanmaning en invordering bij dwangbevel"
    assert labels["urn:bwb:BWBR0004770:hoofdstuk:III"] == "Hoofdstuk III"


# --- een foutresultaat is geen bron (meting Rechtspraak R14, 11 nov 2026) ------------------------------------------

import json as _json  # noqa: E402

import pytest as _pytest  # noqa: E402


@_pytest.mark.parametrize("tool,args", [
    ("zoek_uitspraken", {"artikel": "9"}),                      # Rechtspraak: het voorbeeld BWBR0004770
    ("zoek_bekendmakingen", {"artikel": "36"}),                 # Staatsblad en Staatscourant: idem
    ("zoek_regelingen", {"bwb_id": "geen-id"}),                 # Wetgeving buiten de graaf: BWBR0015703
])
def test_het_voorbeeld_in_een_foutmelding_is_geen_bron(tool, args):
    from agent import tools
    from fakes import FakeGraph, make_settings

    aan = make_settings(connector_rechtspraak=True, connector_bekendmakingen=True, connector_wetgeving_live=True)
    raw = tools.dispatch(tool, FakeGraph(result=""), args, aan)
    data = _json.loads(raw)
    assert data["status"] == "error" and "BWBR" in data["melding"], data
    assert collect_sources([(tool, raw)]) == []


def test_een_gewoon_resultaat_blijft_een_bron():
    raw = _json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                       "resultaten": [{"iri": "urn:bwb:BWBR0004770:artikel:9"}]})
    assert [s.bwb_id for s in collect_sources([("get_artikel", raw)])] == ["BWBR0004770"]


# --- een stuk dat het antwoord in een citeervorm noemt (meting Kamerstukken ronde 2, K18) ---------------------------

@_pytest.mark.parametrize("leestool,ident,brontype,tekst", [
    ("get_bekendmaking", "stb-2013-568", "bekendmaking", "Het wetsvoorstel staat in Stb. 2013, 568."),
    ("get_bekendmaking", "stcrt-2026-37344", "bekendmaking", "De wijziging staat in Staatscourant 2026, nr. 37344."),
    ("get_kamerstuk", "kst-32140-342", "kamerstuk", "Zie Kamerstuk 32140, nr. 342."),
    ("get_uitspraak", "ECLI:NL:HR:2022:50", "uitspraak", "Zo oordeelde de Hoge Raad (ecli nl hr 2022 50)."),
])
def test_een_gelezen_stuk_in_een_citeervorm_blijft_een_bron(leestool, ident, brontype, tekst):
    from agent.grounding import alleen_gelezen_extern, curate_sources, genoemd_extern
    from agent.models import Source

    assert ident in genoemd_extern(tekst)
    bron = Source(uri=ident, label=ident, brontype=brontype, origin_tool=leestool)
    trace = [(leestool, _json.dumps({"status": "ok", "stuk": {"id": ident}, "resultaten": []}))]
    assert alleen_gelezen_extern([bron], trace, tekst) == [bron]
    wet = Source(uri="urn:bwb:BWBR0004770", label="Iw", origin_tool="get_artikel")
    assert bron in curate_sources([wet, bron], f"{tekst} Zie ook BWBR0004770.")


# --- een regeling uit een zoekresultaat is geen bron (meting wetgeving_live ronde 2, I03/I20) ------------------------

def test_een_regeling_die_alleen_gezocht_is_is_geen_bron_maar_een_gevonden_bepaling_wel():
    gezocht = _json.dumps({"status": "ok", "volledig": True, "aantal": 2, "resultaten": [
        {"bwb_id": "BWBR0005537", "citeertitel": "Algemene wet bestuursrecht"},
        {"iri": "urn:bwb:BWBR0004770:artikel:9", "bwb_id": "BWBR0004770", "tekst": "De belastingschuldige …"}]})
    uris = [s.uri for s in collect_sources([("search_wetgeving", gezocht)])]
    assert "urn:bwb:BWBR0005537" not in uris, "de Awb is alleen gezocht"
    assert any("artikel:9" in u for u in uris), "een gevonden bepaling met tekst is een bron"
    # Een lijst regelingen is wel een bron: daar zijn de regelingen het antwoord ("welke regelingen zitten erin?").
    lijst = _json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                         "resultaten": [{"iri": "urn:bwb:BWBR0018472", "citeertitel": "Awir"}]})
    assert [s.uri for s in collect_sources([("list_regelingen", lijst)])] == ["urn:bwb:BWBR0018472"]
    gelezen = _json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{"iri": "urn:bwb:BWBR0018472"}]})
    assert [s.uri for s in collect_sources([("get_artikel", gelezen)])] == ["urn:bwb:BWBR0018472"]


@_pytest.mark.parametrize("vindplaats,genoemd", [
    ("jci1.3:c:BWBR0005291&boek=6&titel=3&afdeling=1&artikel=162&z=2026-01-01&g=2026-01-01", "artikel 6:162"),
    ("jci1.3:c:BWBR0003045&boek=2&titel=1&artikel=9&z=2026-01-01&g=2026-01-01", "artikel 2:9"),
    ("urn:bwb:BWBR0005537:artikel:4%3A86", "artikel 4:86"),
])
def test_een_artikel_met_boeknummer_is_bekend(vindplaats, genoemd):
    """Meting wetgeving_live ronde 2, I24/I28: uit `boek=6&…&artikel=162` kwam alleen "162"."""
    from agent.grounding import _bekende_artikelen

    assert genoemd.removeprefix("artikel ") in _bekende_artikelen([("get_wettekst", _json.dumps({"jci": vindplaats}))])


@_pytest.mark.parametrize("leestool,stuk", [
    ("get_kamerstuk", {"id": "kst-1278484", "label": "Kamerstukken 32140, nr. 342", "leesbaar": False}),
    ("get_bekendmaking", {"id": "stb-1990-222", "label": "Stb. 1990, 222", "leesbaar": False}),
])
def test_een_stuk_in_een_fout_houdt_zijn_label(leestool, stuk):
    """Meting Kamerstukken ronde 3, K12: een stuk dat alleen als PDF bestaat stond met zijn kale id in de bronnenlijst."""
    raw = _json.dumps({"status": "error", "reden": "alleen_pdf", "melding": "alleen als pdf", "stuk": stuk})
    bronnen = collect_sources([(leestool, raw)])
    assert [(s.uri, s.label) for s in bronnen] == [(stuk["id"], stuk["label"])]
