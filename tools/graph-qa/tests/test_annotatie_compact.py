"""Wat het model van een annotatiezoekresultaat ziet.

Het volledige record droeg per element de run van zijn hele batch mee (`geproduceerd_door`, met de
meting). 25 treffers werden zo een resultaat dat het historievenster verdrong; samen met het
inkorten van het verse resultaat gaf dat de zoeklus bij "welke rechtssubjecten ken je nog meer".
"""
from __future__ import annotations

import json

import httpx
import pytest

from agent.annotatie_read import AnnotatieReadApi
from agent.tools.annotatie_tools import dispatch_annotatie, vindplaats_label
from fakes import make_settings

ELEMENT = {
    "id": "e1", "klasse": "Rechtssubject", "tekst": "de ontvanger", "toelichting": "x" * 1000,
    "eigenaar_iri": "urn:bwb:BWBR0004770:artikel:3:lid:1", "aandacht": "geel", "lifecycle": "voorgesteld",
    "alternatieven": ["Rechtsobject"], "trace": {"bewijs": ["D-1"]},
    "ankers": [{"bron_iri": "urn:bwb:BWBR0004770:artikel:3:lid:1", "start": 0, "eind": 11,
                "tekst": "de ontvanger", "bron_hash": "h"}],
    "geproduceerd_door": {"run": {"instellingen": {"meting": {"veel": "y" * 50_000}}}},
}


class Poort:
    def __init__(self):
        self.filters = None

    def zoeken(self, filters):
        self.filters = filters
        return {"manifest_revisie": 7, "resultaten": [ELEMENT] * 25, "status": "ok", "volledig": True,
                "volgende_offset": None}

    def element(self, _id):
        return {"status": "ok", "element": ELEMENT, "laag": {"status": "in_review"}}


def test_zoekresultaat_is_compact_en_leesbaar():
    raw = dispatch_annotatie("search_annotaties", {"jas_klassen": ["Rechtssubject"]}, Poort())
    assert len(raw) < 25 * 1000, "25 treffers horen ruim in het venster te passen"
    data = json.loads(raw)
    assert list(data)[:3] == ["bewijssoort", "status", "volledig"], "status vóór de treffers"
    treffer = data["resultaten"][0]
    assert treffer["vindplaats"] == "BWBR0004770 art. 3 lid 1"
    assert treffer["bron_iri"] == ELEMENT["eigenaar_iri"]
    assert treffer["alternatieven"] == ["Rechtsobject"] and treffer["aandacht"] == "geel"
    assert len(treffer["toelichting"]) <= 301
    assert "geproduceerd_door" not in raw and "ankers" not in treffer


def test_detail_houdt_het_spoor_maar_niet_de_batchrun():
    data = json.loads(dispatch_annotatie("get_annotatie", {"id": "e1"}, Poort()))
    assert data["element"]["trace"] == {"bewijs": ["D-1"]}, "het spoor beantwoordt 'waarom deze klasse'"
    assert "geproduceerd_door" not in data["element"]


def test_klassenamen_zoals_een_jurist_ze_zegt():
    poort = Poort()
    dispatch_annotatie("search_annotaties", {"jas_klassen": ["rechtssubjecten", "Voorwaarde"],
                                             "klasse": "rechtsobject"}, poort)
    assert poort.filters["jas_klassen"] == ["Rechtssubject", "Voorwaarde"]
    assert poort.filters["klasse"] == "Rechtsobject"
    poort.filters = None
    with pytest.raises(ValueError):
        dispatch_annotatie("search_annotaties", {"jas_klassen": ["Onzin"]}, poort)
    assert poort.filters is None, "een onbekende klasse gaat niet naar de api"


def test_vindplaats_label():
    assert vindplaats_label("urn:bwb:BWBR0004770:artikel:9") == "BWBR0004770 art. 9"
    assert vindplaats_label("urn:jas:x") == "urn:jas:x"


def test_een_ongeldige_zoekvraag_zegt_waarom():
    body = {"detail": [{"loc": ["body", "jas_klassen", 0], "msg": "onbekende klasse"}]}
    port = AnnotatieReadApi(make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t"),
                            "jurist", transport=httpx.MockTransport(lambda r: httpx.Response(422, json=body)))
    result = port.zoeken({})
    assert result["status"] == "invalid_request"
    assert result["detail"] == "jas_klassen.0: onbekende klasse"


def test_een_adviesvraag_is_geen_leesvraag():
    from agent.tools.annotatie_tools import is_leesvraag

    vraag = "Welke klasse past het best bij dit fragment?"
    assert is_leesvraag(vraag)
    assert not is_leesvraag(vraag, "advies")


def _relatie(i, van, naar, **extra):
    return {"id": f"R{i}", "type": "plichthebbende", "leesvorm": "is plichthebbende van", "lifecycle": "human_approved",
            "volgorde": None, "laag_id": "l1", "stand_van": "a", "stand_naar": "b",
            "beslissingen": [{"type": "markering", "actor": "jurist"}], "veranderd": False,
            "van": van, "naar": naar, **extra}


ONTVANGER = {"soort": "element", "id": "e1", "bestaat": True, "klasse": "Rechtssubject", "tekst": "de ontvanger",
             "laag_id": "l1", "actueel": True}
ZIN = {"soort": "element", "id": "e2", "bestaat": True, "klasse": "Rechtsbetrekking",
       "tekst": "De ontvanger stelt de aanslag vast", "laag_id": "l1", "actueel": True}


class RelatiePoort(Poort):
    def __init__(self, relaties):
        super().__init__()
        self.relaties = relaties

    def element(self, _id):
        return {**super().element(_id), "relaties": self.relaties}


def test_detail_noemt_de_vastgelegde_relaties_kort():
    """ADR-011, *Gevolgen*: Lex leest relaties via de leesroute. Per relatie de zin, de leesvorm, de andere kant, de
    beoordeling en `veranderd`; niet de stand, de beslissingen of de laag."""
    relaties = [_relatie(1, ONTVANGER, ZIN),
                _relatie(2, {"soort": "impliciet", "id": "I1", "bestaat": True, "klasse": "Rechtssubject",
                             "tekst": "de belastingplichtige"}, ONTVANGER, type="vertegenwoordiging",
                         leesvorm="vertegenwoordigt", lifecycle="voorgesteld", veranderd=True)]
    data = json.loads(dispatch_annotatie("get_annotatie", {"id": "e1"}, RelatiePoort(relaties)))
    eerste, tweede = data["relaties"]
    assert eerste == {"zin": "deze markering is plichthebbende van «De ontvanger stelt de aanslag vast»",
                      "leesvorm": "is plichthebbende van", "andere_kant": "De ontvanger stelt de aanslag vast",
                      "klasse_andere_kant": "Rechtsbetrekking", "beoordeling": "akkoord"}
    assert tweede["zin"] == "«de belastingplichtige» vertegenwoordigt deze markering"
    assert tweede["impliciete_partij"] is True and tweede["veranderd"] is True
    assert tweede["beoordeling"] == "voorstel van Lex"


def test_detail_begrenst_de_relaties():
    from agent.resultaat import BUDGET
    from agent.tools.annotatie_tools import MAX_RELATIES

    lang = {**ZIN, "tekst": "woord " * 400}
    relaties = [_relatie(i, ONTVANGER, lang) for i in range(MAX_RELATIES + 5)]
    raw = dispatch_annotatie("get_annotatie", {"id": "e1"}, RelatiePoort(relaties))
    data = json.loads(raw)
    assert len(data["relaties"]) == MAX_RELATIES and data["relaties_meer"] == 5
    assert all(len(r["andere_kant"]) <= 161 for r in data["relaties"])
    relatiedeel = json.dumps(data["relaties"], ensure_ascii=False, separators=(",", ":"))
    assert len(relatiedeel) <= BUDGET, "de relaties passen binnen de begroting van één toolresultaat"


def test_een_relatie_is_duiding_en_geen_bron():
    """Een relatie is vastgelegde duiding: haar tekst onderbouwt geen citaat, en ze wordt geen bron of registerregel."""
    from agent.bronregister import bij
    from agent.grounding import check_grounding
    from agent.provenance import collect_sources
    from agent.tools.begrip_tools import AFGELEIDE_TOOL_NAMEN

    assert "get_annotatie" in AFGELEIDE_TOOL_NAMEN
    tekst = "De ontvanger stelt de aanslag vast op grond van urn:bwb:BWBR0004770:artikel:9:lid:1"
    raw = dispatch_annotatie("get_annotatie", {"id": "e1"},
                             RelatiePoort([_relatie(1, ONTVANGER, {**ZIN, "tekst": tekst})]))
    trace = [("get_annotatie", raw)]
    rapport = check_grounding('Volgens de relatie: "De ontvanger stelt de aanslag vast op grond van"', trace)
    assert rapport.niet_letterlijk, "een citaat dat alleen in een relatie staat, is niet onderbouwd"
    assert collect_sources(trace) == []
    assert bij([], trace) == []


def test_het_model_leest_de_beoordeling_in_de_woorden_van_de_werkplek():
    """Acceptatie 7 nov 2026: "lifecycle `voorgesteld`" en "human_approved" stonden letterlijk in de toelichting."""
    treffer = json.loads(dispatch_annotatie("search_annotaties", {}, Poort()))["resultaten"][0]
    assert treffer["beoordeling"] == "voorstel van Lex" and "lifecycle" not in treffer
