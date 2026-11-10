"""De live-proef van de bronconnector Kamerstukken (ADR-013): het contract met de echte zoekdienst van KOOP.

De suite draait tegen een nep-SRU (`test_kamerstuk_tools.py`). Een nep bevestigt niet wat de connector van de
echte dienst aanneemt: welke indexen er zijn en of ze sorteren, de vorm van een record, waar het XML-document staat,
de versievelden. Deze proef toetst dat, zonder graaf, model of secrets, en kost niets.

Hij draait niet in de poort: dan hangt elke PR af van overheid.nl. Dagelijks draait hij in
`.github/workflows/bronnenwacht.yml`; lokaal met `BRONNEN_LIVE=1 uv run pytest -m live`.

Een storing van de dienst is iets anders dan een veranderd contract. Is de dienst na één herhaling onbereikbaar, dan
falen de tests met `DIENST ONBEREIKBAAR` vooraan; anders zegt de melding welk deel van het contract brak.
"""
from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET

import httpx
import pytest

from agent import tools
from agent.adapters.sru_kamerstukken import _NS, SRU_URL, KamerstukFout, SruKamerstukken
from agent.config import Settings
from agent.tools.kamerstuk_tools import alineas

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("BRONNEN_LIVE"), reason="live: zet BRONNEN_LIVE=1"),
]

AAN = Settings(connector_kamerstukken=True)
BASIS = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk"
#: Een vaste memorie van toelichting (Invorderingswet, dossier 33755).
MVT = "kst-33755-3"
#: Een klein dossier, een groot dossier (meer dan duizend stukken) en een subdossier van een begroting.
KLEIN, GROOT, SUB = "33755", "31066", "36200-IX"
#: Wat de connector gebruikt om te zoeken en te sorteren; elk moet in de explain staan, doorzoekbaar en sorteerbaar.
INDEXEN = ("dt.identifier", "dt.available", "dt.modified", "dt.type", "dt.title", "w.publicatienaam",
           "w.dossiernummer", "w.ondernummer", "w.documentstatus", "w.versieinformatie", "w.versienummer",
           # De metadata uit de beschrijving (`KAMERSTUKKEN.metadata`, 9 nov 2026).
           "dt.date", "dt.creator", "w.vergaderjaar", "w.subrubriek", "w.documenttitel", "w.dossiertitel", "w.indiener")
#: Een herdruk: kst-32740-1 bestaat niet bij KOOP, kst-32740-1-n1 wel (de Fiscale agenda van april 2011).
HERDRUK = ("kst-32740-1", "kst-32740-1-n1")


def _haal(params: dict) -> bytes:
    """Eén GET op de zoekdienst, met één herhaling bij een storing. Onbereikbaar is een eigen melding."""
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


def _records(cql: str, *, maximum: int = 50, start: int = 1) -> tuple[int, list[ET.Element]]:
    root = ET.fromstring(_haal({"query": cql, "maximumRecords": maximum, "startRecord": start}))
    diag = root.find(".//diag:message", _NS)
    assert diag is None, f"de zoekdienst weigerde '{cql}': {diag.text if diag is not None else ''}"
    totaal = int(root.findtext("sru:numberOfRecords", "0", _NS))
    return totaal, list(root.iterfind(".//sru:record", _NS))


def _veld(rec: ET.Element, pad: str) -> str:
    return (rec.findtext(pad, "", _NS) or "").strip()


def _ids(recs: list[ET.Element]) -> list[str]:
    return [_veld(r, ".//dcterms:identifier") for r in recs]


def test_de_explain_kent_elke_index_doorzoekbaar_en_sorteerbaar():
    root = ET.fromstring(_haal({"operation": "explain", "version": "2.0"}))
    indexen = {e.get("id"): e for e in root.iter() if e.tag.endswith("}index") and e.get("id")}
    for naam in INDEXEN:
        assert naam in indexen, f"de explain kent de index {naam} niet meer"
        assert indexen[naam].get("search") == "true", f"{naam} is niet meer doorzoekbaar"
        assert indexen[naam].get("sort") == "true", f"{naam} is niet meer sorteerbaar"


def test_een_record_heeft_de_velden_die_de_connector_leest():
    totaal, recs = _records(f"{BASIS} AND dt.identifier=={MVT}", maximum=1)
    assert totaal == 1 and recs, f"{MVT} staat niet (meer) in de zoekdienst"
    rec = recs[0]
    assert _veld(rec, ".//dcterms:identifier") == MVT
    assert _veld(rec, ".//dcterms:title")
    assert _veld(rec, ".//dcterms:available") or _veld(rec, ".//dcterms:date")
    assert _veld(rec, ".//dcterms:modified"), "dt.modified ontbreekt: de cache kan dan geen versie toetsen"
    assert _veld(rec, ".//ow:dossiernummer") == KLEIN and _veld(rec, ".//ow:ondernummer") == "3"
    urls = [u for u in rec.iterfind(".//gzd:itemUrl", _NS) if u.get("manifestation") == "xml"]
    assert urls, "geen itemUrl met manifestation='xml'"
    assert httpx.URL((urls[0].text or "").strip()).host == "repository.overheid.nl", "het document staat elders"


def test_documentstatus_staat_op_het_record():
    """Een stuk verschijnt eerst onopgemaakt en wordt later vervangen door de opgemaakte versie (handleiding SRU 2.0)."""
    _, recs = _records(f"{BASIS} AND w.dossiernummer=={KLEIN}", maximum=20)
    statussen = {_veld(r, ".//ow:documentstatus") for r in recs}
    assert statussen - {""}, "geen w.documentstatus op de records"
    assert all(s.lower().startswith(("opgemaakt", "onopgemaakt")) for s in statussen - {""}), statussen


def test_de_metadata_van_de_beschrijving_staat_op_het_record():
    """De velden die `KAMERSTUKKEN.metadata` belooft, op een echt record; en de twee datums apart."""
    from agent.adapters.sru_kamerstukken import lees_records

    _, [rec] = lees_records(_haal({"query": f"{BASIS} AND dt.identifier=={MVT}", "maximumRecords": 1}))
    assert rec.datum and rec.gepubliceerd, "dt.date of dt.available ontbreekt"
    assert rec.soort, "w.subrubriek ontbreekt"  # bij dit oudere stuk "Overig"; de tool neemt dan de titel
    assert rec.dossiertitel and rec.kamer and rec.vergaderjaar and rec.leesbaar
    rij = next(r for r in json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": KLEIN}, AAN))["resultaten"]
               if r["id"] == MVT)
    assert rij["soort"].lower() == "memorie van toelichting" and rij["datum"] == rec.datum


def test_sorteren_op_documentdatum_gaat_met_sortby():
    """`sortBy` in de CQL sorteert; de parameter `sortKeys` negeert de dienst stil (live, 9 nov 2026)."""
    _, recs = _records(f"{BASIS} AND dt.type==Kamerstuk AND w.dossiernummer=={KLEIN} sortBy dt.date/sort.descending",
                       maximum=20)
    datums = [_veld(r, ".//dcterms:date") for r in recs]
    assert datums == sorted(datums, reverse=True), datums


def test_een_herdruk_wordt_gevonden_op_dossier_en_nummer():
    gevraagd, echt = HERDRUK
    totaal, _ = _records(f"{BASIS} AND dt.identifier=={gevraagd}", maximum=1)
    assert totaal == 0, f"{gevraagd} staat nu zelf bij KOOP: kies een andere herdruk voor deze proef"
    rec = SruKamerstukken().record(gevraagd)
    assert rec.id == echt and "herdruk" in rec.versie.lower()


def test_de_nieuwste_stukken_in_een_aanroep():
    """De vraag uit gesprek e906567a: het laatste stuk van een dossier is het nieuwste, niet het hoogste nummer."""
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"volgorde": "nieuwste", "aantal": 10}, AAN))
    assert d["status"] == "ok" and d["aantal"] == 10 and d["totaal"] > 100000
    datums = [r["datum"] for r in d["resultaten"]]
    assert datums == sorted(datums, reverse=True) and d["zoekvraag"] == {"aantal": 10, "volgorde": "nieuwste"}
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": "32140", "volgorde": "nieuwste", "aantal": 1},
                                  AAN))
    assert d["resultaten"][0]["datum"] >= "2026-10-16", d["resultaten"][0]  # nr. 342, of iets nieuwers


def test_filters_op_soort_periode_vergaderjaar_en_kamer():
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": KLEIN, "soort": "memorie van toelichting"},
                                  AAN))
    assert MVT in [r["id"] for r in d["resultaten"]], "het soort in de titel (rubriek 'Overig') wordt gevonden"
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"kamer": "Eerste Kamer", "vergaderjaar": "2025-2026",
                                                               "vanaf": "2026-01", "tot": "2026-03", "aantal": 5}, AAN))
    assert d["status"] == "ok" and d["resultaten"]
    assert all(r["orgaan"] == "Eerste Kamer" and "2026-01-01" <= r["datum"] <= "2026-03-31" for r in d["resultaten"])


def test_zoeken_in_de_tekst_vindt_wat_de_titel_niet_draagt():
    """Meting kamerstukken-tekstzoeken-2026-11-09: de Fiscale agenda van 2011 heet 'Brief regering', maar gaat over één
    bankrekeningnummer. In de titel vindt de dienst haar niet, in de tekst wel, en op de oudste eerst staat ze bovenaan."""
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"tekst": '"één bankrekeningnummer"', "vanaf": "2011",
                                                               "tot": "2016", "volgorde": "oudste", "aantal": 10}, AAN))
    assert d["status"] == "ok" and d["resultaten"][0]["id"] == "kst-32740-1-n1", [r["id"] for r in d["resultaten"]]
    assert "kst-33004-3" in [r["id"] for r in d["resultaten"]], "de memorie van toelichting bij Overige fiscale maatregelen 2012"
    titel = json.loads(tools.dispatch("zoek_kamerstukken", None, {"woorden": "bankrekeningnummer", "vanaf": "2011",
                                                                   "tot": "2011"}, AAN))
    assert "kst-32740-1-n1" not in [r["id"] for r in titel.get("resultaten") or []]


def test_meer_dan_duizend_records_is_een_diagnose():
    with pytest.raises(KamerstukFout) as fout:
        SruKamerstukken().zoek(BASIS, maximum=1001)
    assert fout.value.code == "geweigerd"


def test_een_ongeldige_query_is_een_diagnose():
    with pytest.raises(KamerstukFout, match="weigerde"):
        SruKamerstukken().zoek("dt.bestaatniet==1 AND (")


def test_de_memorie_van_toelichting_is_te_lezen():
    d = json.loads(tools.dispatch("get_kamerstuk", None, {"id": MVT}, AAN))
    assert d["status"] == "ok", d
    assert d["stuk"]["titel"] == "MEMORIE VAN TOELICHTING" and d["stuk"]["bron_hash"]
    assert d["resultaten"] and all(r["tekst"] for r in d["resultaten"])
    xml = SruKamerstukken().document(MVT).xml
    _, rijen, overgeslagen = alineas(xml)
    assert len(rijen) >= 15, "de XML-opbouw (stuk › divisie › al) levert bijna geen alinea's meer op"
    # De tabellen (CALS `table`) zijn geen alinea's: de inhoudsopgave telt apart, de budgettabel is een tabelrij.
    assert overgeslagen.get("inhoudsopgave") == 1 and any(r.get("soort") == "tabel" for r in rijen), (
        "de tabellen heten geen `table` meer")
    assert not any(r["tekst"] in {"Inhoudsopgave", "blz."} for r in rijen)
    # De tussenkop per artikel draagt de artikelsgewijze toelichting.
    assert any("Artikel II (artikel 29 van de Invorderingswet 1990)" in r.get("kop", "") for r in rijen)
    assert len(d["inhoud"]) > 1 and all(isinstance(i["offset"], int) for i in d["inhoud"])


def test_een_subdossier_staat_in_de_index_van_het_dossiernummer():
    """`36200-IX` staat als eigen waarde in `w.dossiernummer`, niet onder het hoofdnummer 36200."""
    totaal, recs = _records(f'{BASIS} AND w.dossiernummer=="{SUB}"', maximum=50)
    assert totaal > 0, f"het subdossier {SUB} vindt niets meer"
    kst = [i for i in _ids(recs) if i.startswith("kst-")]
    assert kst and all(i.upper().startswith(f"KST-{SUB}-") for i in kst), kst[:5]


def test_een_groot_dossier_sorteert_op_datum_en_pagineert_stabiel():
    # Dezelfde sortering als de tool (`_OP_VOLGORDE["oudste"]`): de documentdatum, met het id als tweede sleutel.
    from agent.tools.kamerstuk_tools import _OP_DATUM
    cql = f"{BASIS} AND dt.type==Kamerstuk AND w.dossiernummer=={GROOT}{_OP_DATUM}"
    totaal, p1 = _records(cql, maximum=25)
    assert totaal > 1000, f"{GROOT} telt {totaal} stukken; kies een groter dossier voor deze proef"
    _, p2 = _records(cql, maximum=25, start=26)
    _, p1_opnieuw = _records(cql, maximum=25)
    assert _ids(p1) == _ids(p1_opnieuw), "dezelfde pagina geeft een andere volgorde"
    assert not set(_ids(p1)) & set(_ids(p2)), "twee pagina's overlappen"
    datums = [_veld(r, ".//dcterms:date") for r in p1 + p2]
    assert datums == sorted(datums), f"'{_OP_DATUM.strip()}' sorteert niet op de documentdatum"


def test_het_type_kamerstuk_laat_de_bijlagen_weg():
    met, _ = _records(f"{BASIS} AND w.dossiernummer=={GROOT}", maximum=1)
    zonder, recs = _records(f"{BASIS} AND dt.type==Kamerstuk AND w.dossiernummer=={GROOT}", maximum=50)
    assert 0 < zonder < met, "dt.type==Kamerstuk filtert de bijlagen niet meer"
    assert all(i.startswith("kst-") for i in _ids(recs))


def test_zoeken_op_woorden_in_de_titel():
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"woorden": "Invorderingswet"}, AAN))
    assert d["status"] == "ok" and d["resultaten"], d
    assert all(r["id"].startswith("kst-") for r in d["resultaten"])


def test_de_tool_zet_een_klein_dossier_op_nummer():
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": KLEIN}, AAN))
    assert d["status"] == "ok" and d["volgorde"] == "nummer" and d["volledig"], d.get("toelichting")
    eigen = [r["id"] for r in d["resultaten"] if r["id"].startswith(f"kst-{KLEIN}-")]
    assert eigen[:3] == [f"kst-{KLEIN}-1", f"kst-{KLEIN}-2", f"kst-{KLEIN}-3"]


def test_de_tool_pagineert_een_groot_dossier_op_datum_met_het_echte_totaal():
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": GROOT}, AAN))
    assert d["status"] == "ok" and d["volgorde"] == "oudste" and not d["volledig"] and d["totaal"] > 1000
    v = json.loads(tools.dispatch("zoek_kamerstukken", None, d["vervolg"]["args"], AAN))
    assert not {r["id"] for r in d["resultaten"]} & {r["id"] for r in v["resultaten"]}


def test_de_tool_vindt_een_subdossier():
    d = json.loads(tools.dispatch("zoek_kamerstukken", None, {"dossier": SUB}, AAN))
    assert d["status"] == "ok" and d["resultaten"], "het subdossier gaf niets (zoeken op het hoofdnummer?)"
    assert all(r["id"].upper().startswith(f"KST-{SUB}-") for r in d["resultaten"])


def test_de_adapter_leest_de_versie_van_het_document():
    """De cache valideert op dt.modified, documentstatus en versie (review ADR-013, punt 3)."""
    doc = SruKamerstukken().document(MVT)
    assert doc.gewijzigd and doc.documentstatus and doc.hash and doc.gevalideerd


def test_een_voetnoot_is_een_rij_met_zijn_verwijzing():
    _, rijen, overgeslagen = alineas(SruKamerstukken().document(MVT).xml)
    noten = [r for r in rijen if r.get("soort") == "voetnoot"]
    assert noten, "geen voetnoten meer: heet het element nog `noot` met `noot.nr` en `noot.al`?"
    assert any("kst-33410-15" in r.get("verwijst_naar", []) for r in noten), "de extref naar het regeerakkoord"
    assert overgeslagen.get("inhoudsopgave") == 1


def test_de_budgettabel_van_de_mvt_is_te_lezen():
    args, rij = {"id": MVT}, None
    for _ in range(10):
        d = json.loads(tools.dispatch("get_kamerstuk", None, args, AAN))
        rij = next((r for r in d["resultaten"] if r.get("soort") == "tabel"), None)
        if rij or d["volledig"]:
            break
        args = d["vervolg"]["args"]
    assert rij, "geen tabelrij in de MvT"
    tab = json.loads(tools.dispatch(rij["openen"]["tool"], None, rij["openen"]["args"], AAN))
    kop, totaal = tab["resultaten"][:2]
    assert kop["tekst"].startswith("Tabel 1") and len(kop["cellen"]) == 6, kop
    assert totaal["cellen"][0].startswith("Totaal") and totaal["cellen"][1] == "12", totaal


def test_de_grootste_tabel_van_een_begroting_pagineert_compleet():
    from agent.tools.kamerstuk_tools import lees

    _, _, _, tabellen = lees(SruKamerstukken().document("kst-36200-IX-2").xml)
    nr = max(tabellen, key=lambda n: len(tabellen[n][0]))
    args, gezien = {"id": "kst-36200-IX-2", "tabel": nr}, 0
    for _ in range(200):
        d = json.loads(tools.dispatch("get_kamerstuk", None, args, AAN))
        assert d["status"] == "ok", d
        gezien += d["aantal"]
        if d["volledig"]:
            break
        args = d["vervolg"]["args"]
    assert gezien == len(tabellen[nr][0]) > 100
