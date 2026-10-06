"""Wat het model van een annotatiezoekresultaat ziet.

Het volledige record droeg per element de run van zijn hele batch mee (`geproduceerd_door`, met de
meting). 25 treffers werden zo een resultaat dat het historievenster verdrong; samen met het
inkorten van het verse resultaat gaf dat de zoeklus bij "welke rechtssubjecten ken je nog meer".
"""
from __future__ import annotations

import json

import httpx

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
    dispatch_annotatie("search_annotaties", {"jas_klassen": ["Onzin"]}, poort)
    assert poort.filters["jas_klassen"] == ["Onzin"], "onherkenbaar blijft staan; de api weigert het"


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
