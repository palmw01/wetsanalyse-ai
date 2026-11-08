"""ADR-013 fase 1a: de bronconnector Kamerstukken.

Tegen een nepbron met de vorm van de SRU-dienst van KOOP; de XML hieronder is zelfgemaakt in de opbouw van een
Kamerstuk (kamerstuk › stuk › divisie › kop/al), niet overgenomen. De live-proef tegen de echte dienst staat in
`test_kamerstukken_live.py` (`BRONNEN_LIVE=1`).
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

import httpx
import pytest

from agent import tools
from agent.adapters.sru_kamerstukken import Document, KamerstukFout, Record, SruKamerstukken, lees_records
from agent.config import Settings
from agent.grounding import check_grounding
from agent.provenance import collect_sources
from agent.resultaat import BUDGET
from agent.sjablonen.vullen import bron_rijen
from agent.tools.kamerstuk_tools import MAX_DOSSIER, alineas

AAN = Settings(connector_kamerstukken=True)

XML = """<?xml version="1.0" encoding="UTF-8"?>
<officiele-publicatie><kamerstuk><dossier><dossiernummer><dossiernr>99 001</dossiernr></dossiernummer></dossier>
<stuk><stuknr>Nr. <ondernummer>3</ondernummer></stuknr><titel>MEMORIE VAN TOELICHTING</titel>
<algemeen><vrije-tekst>
<divisie><kop><nr>1.</nr><titel>Inleiding</titel></kop>
<al>Dit voorstel regelt de <nadruk>invorderingsrente</nadruk> opnieuw.<noot><al>Zie de nota.</al></noot></al>
<divisie><kop><titel>Doel</titel></kop><al>Het doel is   eenvoud.</al><tabel><al>1</al></tabel></divisie>
</divisie></vrije-tekst></algemeen></stuk></kamerstuk></officiele-publicatie>""".encode()


def rec(ident: str, titel: str, nr: str) -> Record:
    return Record(id=ident, titel=titel, datum="2026-01-02", vergaderjaar="2025-2026", dossiers=("99001",),
                  ondernummer=nr, xml_url=f"https://repository.overheid.nl/x/{ident}.xml")


@dataclass
class NepBron:
    records: list[Record]
    xml: bytes = XML

    def __post_init__(self):
        self.vragen: list[str] = []

    def zoek(self, cql, *, start=1, maximum=50):
        self.vragen.append(cql)
        return len(self.records), self.records[start - 1:start - 1 + maximum]

    def document(self, ident):
        return Document(ident, self.xml, "h")


DOSSIER = [rec("kst-99001-3", "Wet x; Memorie van toelichting", "3"), rec("kst-99001-10", "Wet x; Verslag", "10"),
           rec("kst-99001-2", "Wet x; Voorstel van wet", "2"), rec("blg-123", "Bijlage", "3")]


def roep(naam, args, bron=None):
    return json.loads(tools.dispatch(naam, None, args, AAN, kamerstukken=bron or NepBron(DOSSIER)))


def test_dossier_op_nummer_zonder_bijlagen():
    d = roep("zoek_kamerstukken", {"dossier": "99001"})
    assert d["status"] == "ok" and d["volledig"]
    assert [r["id"] for r in d["resultaten"]] == ["kst-99001-2", "kst-99001-3", "kst-99001-10"]
    assert d["resultaten"][1]["stuk"] == "Memorie van toelichting" and d["dossiertitel"] == "Wet x"
    assert d["resultaten"][1]["link"] == "https://zoek.officielebekendmakingen.nl/kst-99001-3"


def test_de_query_komt_uit_de_code():
    # Alleen woorden van drie letters of meer gaan de CQL in, als eigen term tussen aanhalingstekens.
    bron = NepBron(DOSSIER)
    roep("zoek_kamerstukken", {"woorden": 'Invorderingswet") OR (x'}, bron)
    assert bron.vragen == ['c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND '
                           'dt.type==Kamerstuk AND dt.title any "invorderingswet"']


@pytest.mark.parametrize("args,reden", [({"dossier": "drop table"}, "ongeldig_dossier"), ({}, "ongeldige_argumenten"),
                                        ({"woorden": "a b"}, "ongeldige_argumenten")])
def test_ongeldige_vraag_is_een_foutresultaat(args, reden):
    d = roep("zoek_kamerstukken", args)
    assert (d["status"], d["reden"]) == ("error", reden)


def test_alineas_in_volgorde_met_kop_en_zonder_noten():
    kop, rijen, overgeslagen = alineas(XML)
    assert kop == {"documenttitel": "MEMORIE VAN TOELICHTING"}
    assert rijen == [{"nr": 1, "kop": "1. Inleiding", "tekst": "Dit voorstel regelt de invorderingsrente opnieuw."},
                     {"nr": 2, "kop": "1. Inleiding › Doel", "tekst": "Het doel is eenvoud."}]
    assert overgeslagen == {"voetnoot": 1, "tabel": 1}


def test_get_kamerstuk_is_een_bron_en_gronding_klopt():
    tekst = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=NepBron(DOSSIER))
    d = json.loads(tekst)
    assert d["stuk"]["id"] == "kst-99001-3" and d["overgeslagen"] == {"voetnoot": 1, "tabel": 1}
    [bron] = collect_sources([("get_kamerstuk", tekst)])
    assert (bron.uri, bron.brontype) == ("kst-99001-3", "kamerstuk")
    goed = check_grounding('De MvT (kst-99001-3): "Dit voorstel regelt de invorderingsrente opnieuw."',
                           [("get_kamerstuk", tekst)])
    assert goed.niveau == "gegrond"
    fout = check_grounding('Volgens kst-99001-3: "Dit voorstel schaft de invorderingsrente af."',
                           [("get_kamerstuk", tekst)])
    assert fout.niveau == "ongegrond" and fout.niet_letterlijk


def test_een_kamerstuk_is_geen_passage_van_een_bepaling():
    # Een sjabloon citeert uit rijen met de iri van een bepaling (`bron_rijen`); een Kamerstuk draagt `id`.
    tekst = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=NepBron(DOSSIER))
    assert bron_rijen([("get_kamerstuk", tekst)]) == {}


def test_lang_stuk_pagineert_op_hele_alineas():
    lang = XML.replace(b"<al>Het doel", b"".join(b"<al>" + (b"woord " * 200) + b"</al>" for _ in range(10)) + b"<al>Het doel")
    bron = NepBron(DOSSIER, xml=lang)
    eerste = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=bron)
    d = json.loads(eerste)
    assert len(eerste) <= BUDGET and not d["volledig"] and d["vervolg"]["tool"] == "get_kamerstuk"
    rest = json.loads(tools.dispatch("get_kamerstuk", None, d["vervolg"]["args"], AAN, kamerstukken=bron))
    assert rest["resultaten"][0]["nr"] == d["resultaten"][-1]["nr"] + 1


def test_uit_is_uit():
    assert json.loads(tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, Settings()))["reden"] == "connector_uit"
    assert not (tools.toegestane_tools(None, Settings()) & tools.CONNECTOR_TOOLS)
    assert tools.CONNECTOR_TOOLS <= tools.toegestane_tools(None, AAN)


def test_een_storing_is_zichtbaar():
    class Weg(NepBron):
        def zoek(self, cql, **_):
            raise KamerstukFout("de officiële publicaties zijn niet bereikbaar: ConnectError")
    d = roep("zoek_kamerstukken", {"dossier": "99001"}, Weg(DOSSIER))
    assert d["status"] == "error" and d["reden"] == "bron_onbereikbaar"


def test_adapter_weigert_een_vreemde_host_en_leest_een_diagnose():
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b""))))
    with pytest.raises(KamerstukFout, match="allowlist"):
        bron._get("https://evil.example/sru")
    diag = (b'<r xmlns:diag="http://docs.oasis-open.org/ns/search-ws/diagnostic"><diag:diagnostic>'
            b'<diag:message>Unsupported index</diag:message></diag:diagnostic></r>')
    with pytest.raises(KamerstukFout, match="Unsupported index"):
        lees_records(diag)


def _veel(n: int, dossier: str = "99001") -> list[Record]:
    return [rec(f"kst-{dossier}-{i}", f"Wet x; Stuk {i}", str(i)) for i in range(1, n + 1)]


def _alle(args: dict, bron: NepBron) -> tuple[list[dict], list[dict]]:
    """Alle pagina's van een zoekvraag: (rijen, contracten)."""
    rijen, paginas = [], []
    d = roep("zoek_kamerstukken", args, bron)
    for _ in range(200):
        paginas.append(d)
        rijen += d["resultaten"]
        if d["volledig"]:
            return rijen, paginas
        d = roep(d["vervolg"]["tool"], d["vervolg"]["args"], bron)
    raise AssertionError("geen einde")


def test_een_dossier_tot_de_grens_staat_op_nummer_en_is_compleet():
    bron = NepBron(list(reversed(_veel(MAX_DOSSIER))))
    rijen, paginas = _alle({"dossier": "99001"}, bron)
    assert [r["id"] for r in rijen] == [f"kst-99001-{i}" for i in range(1, MAX_DOSSIER + 1)]
    assert all(p["volgorde"] == "nummer" and p["totaal"] == MAX_DOSSIER for p in paginas)


def test_een_groot_dossier_wordt_niet_afgekapt_maar_staat_op_datum():
    """Review ADR-013, punt 1: een dossier boven de grens heette volledig na de eerste 300 stukken."""
    n = MAX_DOSSIER + 1
    bron = NepBron(_veel(n))
    rijen, paginas = _alle({"dossier": "99001"}, bron)
    assert len(rijen) == n and len({r["id"] for r in rijen}) == n, "alle stukken, elk één keer"
    assert all(p["volgorde"] == "datum" and p["totaal"] == n for p in paginas)
    assert not paginas[0]["volledig"] and "datum" in paginas[0]["toelichting"]
    # Per pagina één telvraag (zonder records) en één pagina op datum.
    assert sum(v.endswith(" sortBy dt.available/sort.ascending") for v in bron.vragen) == len(paginas)


def test_een_subdossier_zoekt_op_zijn_eigen_nummer():
    """`36200-IX` staat als eigen waarde in w.dossiernummer; zoeken op 36200 en achteraf filteren vond niets."""
    bron = NepBron(_veel(3, "36200-IX"))
    d = roep("zoek_kamerstukken", {"dossier": "36200-ix"}, bron)
    assert d["status"] == "ok" and d["aantal"] == 3 and d["volledig"]
    assert all('w.dossiernummer=="36200-IX"' in v for v in bron.vragen)


def test_een_onvolledig_antwoord_van_de_dienst_is_een_fout():
    class Hapert(NepBron):
        def zoek(self, cql, *, start=1, maximum=50):
            totaal, deel = super().zoek(cql, start=start, maximum=maximum)
            return totaal, deel if start == 1 else []

    d = roep("zoek_kamerstukken", {"dossier": "99001"}, Hapert(_veel(400)))
    assert d["status"] == "error" and d["reden"] == "onvolledig_antwoord"


# ── Het cachebeleid (review ADR-013, punt 3) ─────────────────────────────────────────────────────────────────────
#
# Een Kamerstuk kan na publicatie veranderen: de onopgemaakte versie wordt vervangen door de opgemaakte, en er zijn
# herdruk en rectificatie. De adapter valideert een hit daarom na VERS_S met een lichte metadatavraag.

from agent.adapters import sru_kamerstukken as sru  # noqa: E402


class Dienst:
    """Een nep-SRU-dienst over HTTP: één record met `dt.modified` en documentstatus, en het document zelf."""

    def __init__(self) -> None:
        self.gewijzigd, self.status, self.xml = "2026-01-02", "Onopgemaakt", XML
        self.vragen: list[str] = []
        self.weg = False

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.weg:
            raise httpx.ConnectError("weg", request=r)
        if r.url.path.endswith(".xml"):
            self.vragen.append("document")
            return httpx.Response(200, content=self.xml)
        self.vragen.append("record")
        return httpx.Response(200, content=f"""<sru:searchRetrieveResponse
            xmlns:sru="http://docs.oasis-open.org/ns/search-ws/sruResponse" xmlns:dcterms="http://purl.org/dc/terms/"
            xmlns:ow="http://standaarden.overheid.nl/wetgeving/" xmlns:gzd="http://standaarden.overheid.nl/sru">
            <sru:numberOfRecords>1</sru:numberOfRecords><sru:records><sru:record>
            <dcterms:identifier>kst-99001-3</dcterms:identifier><dcterms:title>Wet x; MvT</dcterms:title>
            <dcterms:modified>{self.gewijzigd}</dcterms:modified><ow:documentstatus>{self.status}</ow:documentstatus>
            <gzd:itemUrl manifestation="xml">https://repository.overheid.nl/frbr/kst-99001-3.xml</gzd:itemUrl>
            </sru:record></sru:records></sru:searchRetrieveResponse>""".encode())


def _adapter(dienst: Dienst, nu: list[float]) -> SruKamerstukken:
    return SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(dienst)), klok=lambda: nu[0])


def test_binnen_het_venster_geen_aanroep_daarna_alleen_de_metadata():
    dienst, nu = Dienst(), [0.0]
    bron = _adapter(dienst, nu)
    eerste = bron.document("kst-99001-3")
    assert dienst.vragen == ["record", "document"] and eerste.documentstatus == "Onopgemaakt"
    nu[0] = sru.VERS_S - 1
    assert bron.document("kst-99001-3") is eerste and len(dienst.vragen) == 2, "binnen het venster geen aanroep"
    nu[0] = sru.VERS_S + 1
    assert bron.document("kst-99001-3") is eerste and dienst.vragen[2:] == ["record"], "niets veranderd: geen XML"


def test_een_nieuwe_versie_wordt_opnieuw_opgehaald_en_gelogd(caplog):
    dienst, nu = Dienst(), [0.0]
    bron = _adapter(dienst, nu)
    oud = bron.document("kst-99001-3")
    dienst.gewijzigd, dienst.status, dienst.xml = "2026-02-01", "Opgemaakt na onopgemaakt", XML.replace(b"eenvoud", b"helderheid")
    nu[0] = sru.VERS_S + 1
    with caplog.at_level("INFO", logger="graph_qa.kamerstukken"):
        nieuw = bron.document("kst-99001-3")
    assert dienst.vragen[2:] == ["record", "document"]
    assert nieuw.hash != oud.hash and nieuw.gewijzigd == "2026-02-01" and nieuw.documentstatus == "Opgemaakt na onopgemaakt"
    melding = next(r for r in caplog.records if r.getMessage() == "kamerstuk_gewijzigd")
    assert melding.oude_hash == oud.hash and melding.bron_hash == nieuw.hash


def test_een_storing_bij_het_valideren_geeft_de_bewaarde_versie_met_de_vlag():
    dienst, nu = Dienst(), [0.0]
    bron = _adapter(dienst, nu)
    oud = bron.document("kst-99001-3")
    dienst.weg, nu[0] = True, sru.VERS_S + 1
    doc = bron.document("kst-99001-3")
    assert doc.hash == oud.hash and doc.gevalideerd is False
    with pytest.raises(KamerstukFout):
        bron.document("kst-99001-4")  # een miss zonder dienst blijft een fout
    d = json.loads(tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=bron))
    assert d["stuk"]["gevalideerd"] is False and d["stuk"]["bron_hash"] == oud.hash


def test_de_bytegrens_zet_de_oudste_eruit(monkeypatch):
    monkeypatch.setattr(sru, "MAX_CACHE_BYTES", len(XML) * 2 + 1)
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(Dienst())))
    nep = Record(id="", titel="", datum="", vergaderjaar="", dossiers=(), ondernummer="",
                 xml_url="https://repository.overheid.nl/frbr/x.xml")
    monkeypatch.setattr(bron, "_record", lambda ident: dataclasses.replace(nep, id=ident))
    for i in range(1, 4):
        bron.document(f"kst-99001-{i}")
    assert list(bron._cache) == ["kst-99001-2", "kst-99001-3"]


def test_het_stuk_noemt_zijn_versie():
    dienst = Dienst()
    d = json.loads(tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN,
                                  kamerstukken=_adapter(dienst, [0.0])))
    assert d["stuk"]["documentstatus"] == "Onopgemaakt" and d["stuk"]["gewijzigd"] == "2026-01-02"
    assert d["stuk"]["bron_hash"] and "gevalideerd" not in d["stuk"]
