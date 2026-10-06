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
