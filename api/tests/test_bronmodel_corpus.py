"""CorpusMap en Span: de enige rekenregel tussen analysecorpus en lokale bronankers."""
import dataclasses
import itertools

import pytest
from bronmodel import CorpusMap, Span, SpanFout, tekst_hash


def seg(iri, tekst):
    return {"bron_iri": iri, "tekst": tekst, "bron_hash": tekst_hash(tekst), "type": "Lid"}


SEGMENTEN = [seg("urn:bwb:B:lid:1", "De ontvanger 😀 handelt."),
             seg("urn:bwb:B:lid:1a", "   "),                    # leeg: telt niet mee
             seg("urn:bwb:B:onderdeel:a", "Eerste onderdeel."),
             seg("urn:bwb:B:lid:2", "Binnen zes weken.")]


def test_corpus_is_de_niet_lege_segmenten_met_een_lege_regel_ertussen():
    kaart = CorpusMap(SEGMENTEN)
    assert kaart.corpus == "De ontvanger 😀 handelt.\n\nEerste onderdeel.\n\nBinnen zes weken."
    assert [s.bron_iri for s in kaart.segmenten] == [
        "urn:bwb:B:lid:1", "urn:bwb:B:onderdeel:a", "urn:bwb:B:lid:2"]
    for s in kaart.segmenten:
        assert kaart.corpus[s.corpus_start:s.corpus_eind] == s.tekst


def test_als_dicts_behoudt_de_bronvelden_en_voegt_offsets_toe():
    dicts = CorpusMap(SEGMENTEN).als_dicts()
    assert dicts[0]["type"] == "Lid" and dicts[0]["corpus_start"] == 0
    assert CorpusMap(dicts).corpus == CorpusMap(SEGMENTEN).corpus


def test_elke_corpusrange_splitst_letterlijk_en_keert_terug():
    """Uitputtend over alle bereiken: elke span is letterlijk en rekent terug naar zijn corpusplek."""
    kaart = CorpusMap(SEGMENTEN)
    n = len(kaart.corpus)
    in_node = {i for s in kaart.segmenten for i in range(s.corpus_start, s.corpus_eind)}
    for start, eind in itertools.combinations(range(n + 1), 2):
        spans = kaart.naar_spans(start, eind)
        verwacht = "".join(kaart.corpus[i] for i in range(start, eind) if i in in_node)
        assert "".join(s.tekst for s in spans) == verwacht
        for s in spans:
            a, z = kaart.naar_corpus(s)
            assert kaart.corpus[a:z] == s.tekst
            assert start <= a < z <= eind


def test_codepoints_niet_utf16():
    kaart = CorpusMap(SEGMENTEN)
    s = kaart.span("urn:bwb:B:lid:1", 13, 14)
    assert s.tekst == "😀"


def test_alleen_scheiding_geeft_geen_span():
    kaart = CorpusMap(SEGMENTEN)
    eerste = kaart.segmenten[0]
    assert kaart.naar_spans(eerste.corpus_eind, eerste.corpus_eind + 2) == []


@pytest.mark.parametrize("start,eind", [(-1, 2), (3, 3), (5, 2), (0, 999), (0.0, 2)])
def test_ongeldige_posities_worden_geweigerd(start, eind):
    with pytest.raises(SpanFout):
        CorpusMap(SEGMENTEN).span("urn:bwb:B:lid:2", start, eind)


def test_onbekende_of_lege_node_valt_buiten_het_corpus():
    kaart = CorpusMap(SEGMENTEN)
    for iri in ("urn:bwb:B:lid:9", "urn:bwb:B:lid:1a"):
        with pytest.raises(SpanFout):
            kaart.segment(iri)


def test_span_van_gewijzigde_bron_wordt_geweigerd():
    kaart = CorpusMap(SEGMENTEN)
    oud = kaart.span("urn:bwb:B:lid:2", 0, 6)
    nieuw = CorpusMap([seg("urn:bwb:B:lid:2", "Buiten zes weken.")])
    with pytest.raises(SpanFout):
        nieuw.naar_corpus(oud)


def test_span_is_onveranderlijk_en_levert_het_ankercontract():
    s = CorpusMap(SEGMENTEN).span("urn:bwb:B:lid:2", 7, 16)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.start = 0  # type: ignore[misc]
    assert s.anker() == {"bron_iri": "urn:bwb:B:lid:2", "start": 7, "eind": 16,
                         "tekst": "zes weken", "bron_hash": tekst_hash("Binnen zes weken.")}
    assert isinstance(s, Span)
