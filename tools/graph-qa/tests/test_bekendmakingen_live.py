"""De live-proef van de bronconnector Staatsblad en Staatscourant (ADR-013): het contract met de echte zoekdienst.

De suite draait tegen opgenomen antwoorden (`test_bekendmaking_tools.py`). Deze proef toetst wat de connector van de
echte dienst aanneemt – de indexen, de recordvorm, de XML-vorm, het sorteren en de terugval voor een herdruk – zonder
graaf, model of secrets, en kost niets. Hij draait niet in de poort maar dagelijks in `bronnenwacht.yml`; lokaal met
`BRONNEN_LIVE=1 uv run pytest -m live tests/test_bekendmakingen_live.py`.

Een storing van de dienst is iets anders dan een veranderd contract: na één herhaling falen de tests met
`DIENST ONBEREIKBAAR` vooraan.
"""
from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET

import httpx
import pytest

from agent import tools
from agent.adapters.sru_bekendmakingen import SruBekendmakingen
from agent.adapters.sru_koop import _NS, SRU_URL, lees_records
from agent.config import Settings
from agent.tools.op_xml import lees

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("BRONNEN_LIVE"), reason="live: zet BRONNEN_LIVE=1"),
]

AAN = Settings(connector_bekendmakingen=True)
BASIS = "c.product-area==officielepublicaties"
#: Het inwerkingtredingsbesluit van Iw art. 36 (Stb. 2010, 176) en een wijziging van de Leidraad Invordering 2008.
IWT, LEIDRAAD = "stb-2010-176", "stcrt-2026-37344"
#: De Invorderingswet 1990 zelf: bij KOOP alleen een PDF.
PDF = "stb-1990-222"
INDEXEN = ("dt.identifier", "dt.date", "dt.available", "dt.modified", "dt.type", "dt.title", "dt.creator",
           "w.publicatienaam", "w.jaargang", "w.publicatienummer", "w.datumOndertekening", "w.behandeldDossier")


def _haal(params: dict) -> bytes:
    fout: Exception | None = None
    for poging in range(2):
        try:
            r = httpx.get(SRU_URL, params=params, timeout=60)
            if r.status_code < 500:
                r.raise_for_status()
                return r.content
            fout = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            fout = exc
        if poging == 0:
            time.sleep(5)
    pytest.fail(f"DIENST ONBEREIKBAAR: {SRU_URL} gaf {type(fout).__name__}: {fout}")


def _records(cql: str, maximum: int = 10):
    return lees_records(_haal({"query": cql, "maximumRecords": maximum}))


def test_de_explain_kent_elke_index():
    root = ET.fromstring(_haal({"operation": "explain", "version": "2.0"}))
    indexen = {e.get("id"): e for e in root.iter() if e.tag.endswith("}index") and e.get("id")}
    for naam in INDEXEN:
        assert naam in indexen, f"de explain kent de index {naam} niet meer"
        assert indexen[naam].get("search") == "true", f"{naam} is niet meer doorzoekbaar"


def test_een_record_heeft_de_velden_die_de_connector_leest():
    totaal, [rec] = _records(f"{BASIS} AND dt.identifier=={IWT}", 1)
    assert totaal == 1 and rec.id == IWT
    assert rec.publicatienaam == "Staatsblad" and rec.jaargang == "2010" and rec.publicatienummer == "176"
    assert rec.type and rec.datum and rec.ondertekend and rec.gewijzigd and rec.kamer
    assert httpx.URL(rec.xml_url).host == "repository.overheid.nl", "het document staat elders"


def test_een_oud_stuk_staat_er_alleen_als_pdf():
    _, [rec] = _records(f"{BASIS} AND dt.identifier=={PDF}", 1)
    assert not rec.xml_url and rec.pdf_url, f"{PDF} heeft nu XML: kies een ander PDF-stuk voor deze proef"
    d = json.loads(tools.dispatch("get_bekendmaking", None, {"id": PDF}, AAN))
    assert d["reden"] == "alleen_pdf" and d["stuk"]["leesbaar"] is False


def test_sorteren_gaat_met_sortby():
    """`sortBy` in de CQL sorteert; de parameter `sortKeys` negeert de dienst stil (ook voor het Staatsblad)."""
    _, recs = _records(f"{BASIS} AND w.publicatienaam==Staatsblad AND w.jaargang==\"2010\" "
                       "sortBy dt.date/sort.descending", 20)
    datums = [r.datum for r in recs]
    assert datums == sorted(datums, reverse=True), datums


def test_het_kamerdossier_vindt_de_wet():
    _, recs = _records(f'{BASIS} AND w.publicatienaam==Staatsblad AND w.behandeldDossier=="33755"', 5)
    assert recs and all("33755" in r.behandeld_dossiers for r in recs)


def test_zoeken_op_blad_soort_en_woorden():
    d = json.loads(tools.dispatch("zoek_bekendmakingen", None, {
        "publicatie": "Staatscourant", "woorden": "Leidraad Invordering", "vanaf": "2024", "volgorde": "nieuwste",
        "aantal": 10}, AAN))
    assert d["status"] == "ok" and d["resultaten"], d
    assert LEIDRAAD in [r["id"] for r in d["resultaten"]] or d["resultaten"][0]["datum"] >= "2026-11-02"
    assert all(r["publicatie"] == "Staatscourant" for r in d["resultaten"])
    d = json.loads(tools.dispatch("zoek_bekendmakingen", None, {"publicatie": "Staatscourant", "soort": "beleidsregel",
                                                                 "volgorde": "nieuwste", "aantal": 3}, AAN))
    assert d["status"] == "ok" and all(r["soort"].lower() == "beleidsregel" for r in d["resultaten"])


def test_de_xml_heeft_de_vorm_die_de_lezer_kent():
    bron = SruBekendmakingen()
    _, rijen, _, _ = lees(bron.document(IWT).xml)
    assert rijen and any("in werking" in r["tekst"] for r in rijen)
    _, rijen, _, _ = lees(bron.document(LEIDRAAD).xml)
    assert any(r.get("kop", "").startswith("Artikel I") and " › " in r.get("kop", "") for r in rijen), (
        "de wijzigingsonderdelen (wijzig-artikel › wijzig-lid) heten anders")


def test_een_onbekend_id_valt_terug_op_blad_jaargang_en_nummer():
    """Een herdruk of herplaatsing draagt een eigen id. Zonder herdruk bij de hand toetst dit de terugval zelf: het
    nummer zonder achtervoegsel bestaat, met een verzonnen achtervoegsel niet, en dan vindt de adapter het origineel."""
    rec = SruBekendmakingen().record(f"{IWT}-n9")
    assert rec.id == IWT


def test_de_staatscourant_geeft_alleen_regelgevende_soorten():
    """De witte lijst (`REGELGEVENDE_SOORTEN`) is een geldige zoekvraag, en de nieuwste publicaties bevatten geen
    aankondigingen over personen (deurwaardersexploten, faillissementen, curatele)."""
    from agent.tools.bekendmaking_tools import REGELGEVENDE_SOORTEN

    d = json.loads(tools.dispatch("zoek_bekendmakingen", None, {"publicatie": "Staatscourant", "volgorde": "nieuwste",
                                                                 "aantal": 25}, AAN))
    assert d["status"] == "ok" and d["aantal"] >= 5 and d["totaal"] > 10000, d  # de begroting kan eerder knippen
    assert {r["soort"] for r in d["resultaten"]} <= set(REGELGEVENDE_SOORTEN)
