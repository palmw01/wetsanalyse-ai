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
from agent.tools.kamerstuk_tools import EERSTE_VERGADERJAAR, MAX_DOSSIER, alineas

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
    assert d["resultaten"][1]["soort"] == "Memorie van toelichting" and d["dossiertitel"] == "Wet x"
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
                     {"nr": 2, "soort": "voetnoot", "kop": "1. Inleiding", "tekst": "Zie de nota."},
                     {"nr": 3, "kop": "1. Inleiding › Doel", "tekst": "Het doel is eenvoud."}]
    assert overgeslagen == {"tabel": 1}


def test_get_kamerstuk_is_een_bron_en_gronding_klopt():
    tekst = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=NepBron(DOSSIER))
    d = json.loads(tekst)
    assert d["stuk"]["id"] == "kst-99001-3" and d["overgeslagen"] == {"tabel": 1}
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
    assert tools.CONNECTORS["kamerstukken"] <= tools.toegestane_tools(None, AAN)


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


def test_een_groot_dossier_wordt_niet_afgekapt_maar_staat_op_de_oudste_eerst():
    """Review ADR-013, punt 1: een dossier boven de grens heette volledig na de eerste 300 stukken."""
    n = MAX_DOSSIER + 1
    bron = NepBron(_veel(n))
    rijen, paginas = _alle({"dossier": "99001"}, bron)
    assert len(rijen) == n and len({r["id"] for r in rijen}) == n, "alle stukken, elk één keer"
    assert all(p["volgorde"] == "oudste" and p["totaal"] == n for p in paginas)
    assert not paginas[0]["volledig"] and "oudste" in paginas[0]["toelichting"]
    # Per pagina één telvraag (zonder records) en één pagina op de documentdatum, met het id als tweede sleutel.
    assert sum(v.endswith(" sortBy dt.date/sort.ascending dt.identifier/sort.ascending") for v in bron.vragen) == len(paginas)


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
from agent.adapters import sru_koop  # noqa: E402


@pytest.fixture(autouse=True)
def _geen_wachttijd(monkeypatch):
    """Het gedeelde herhaalbeleid wacht tussen pogingen (`http_beleid`); in de tests niet."""
    from agent.adapters import http_beleid
    monkeypatch.setattr(http_beleid, "HERHAAL_S", 0)


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
    monkeypatch.setattr(sru_koop, "MAX_CACHE_BYTES", len(XML) * 2 + 1)
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(Dienst())))
    nep = Record(id="", titel="", datum="", vergaderjaar="", dossiers=(), ondernummer="",
                 xml_url="https://repository.overheid.nl/frbr/x.xml")
    monkeypatch.setattr(bron, "record", lambda ident: dataclasses.replace(nep, id=ident))
    for i in range(1, 4):
        bron.document(f"kst-99001-{i}")
    assert list(bron._cache) == ["kst-99001-2", "kst-99001-3"]


def test_het_stuk_noemt_zijn_versie():
    dienst = Dienst()
    d = json.loads(tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN,
                                  kamerstukken=_adapter(dienst, [0.0])))
    assert d["stuk"]["status"] == "Onopgemaakt" and d["stuk"]["gewijzigd"] == "2026-01-02"
    assert d["stuk"]["bron_hash"] and "gevalideerd" not in d["stuk"]


# ── Wat een Kamerstuk echt bevat (acceptatie 8 nov 2026) ─────────────────────────────────────────────────────────
#
# De XML van KOOP gebruikt CALS-tabellen (`table`) en tussenkoppen per artikel. De tabellen kwamen als losse cellen
# mee (de inhoudsopgave en de cijfers van een budgettabel) en de tussenkoppen vielen weg, terwijl juist die zeggen bij
# welk artikel een alinea van de artikelsgewijze toelichting hoort. Zelfgemaakte XML in de opbouw van KOOP.

MVT = """<?xml version="1.0" encoding="UTF-8"?>
<officiele-publicatie><kamerstuk><stuk><titel>MEMORIE VAN TOELICHTING</titel><algemeen><vrije-tekst><tekst>
<table><tgroup cols="2"><tbody><row><entry><al>Inhoudsopgave</al></entry><entry><al>blz.</al></entry></row>
<row><entry><al>1. Inleiding</al></entry><entry><al>1</al></entry></row></tbody></tgroup></table>
<divisie><kop><nr>I.</nr><titel>ALGEMEEN</titel></kop>
<divisie><kop><nr>1.</nr><titel>Inleiding</titel></kop><al>Dit voorstel regelt de rente.</al></divisie>
<divisie><kop><nr>2.</nr><titel>Budgettaire aspecten</titel></kop><al>De opbrengst staat in de tabel.</al>
<table><tgroup cols="2"><tbody><row><entry><al>2014</al></entry><entry><al>50</al></entry></row></tbody></tgroup></table>
</divisie></divisie>
<divisie><kop><nr>II.</nr><titel>ARTIKELSGEWIJZE TOELICHTING</titel></kop>
<tussenkop>Artikel I (artikel 30hb AWR)</tussenkop><al>Het eerste lid regelt de ondergrens.</al><al>Het tweede lid de Vpb.</al>
<tussenkop>Artikel II (artikel 29 Iw)</tussenkop><al>Hetzelfde voor de invorderingsrente.</al>
</divisie></tekst></vrije-tekst></algemeen></stuk></kamerstuk></officiele-publicatie>""".encode()


def test_een_cals_tabel_is_geen_alinea_maar_een_tabelrij():
    _, rijen, overgeslagen = alineas(MVT)
    teksten = [r["tekst"] for r in rijen]
    assert "Inhoudsopgave" not in teksten and "2014" not in teksten and "blz." not in teksten
    assert overgeslagen == {"inhoudsopgave": 1}
    assert [r["soort"] for r in rijen if r.get("soort")] == ["tabel"]
    assert teksten[0] == "Dit voorstel regelt de rente."


def test_een_tussenkop_hoort_bij_de_alineas_erna():
    _, rijen, _ = alineas(MVT)
    kop = {r["tekst"]: r["kop"] for r in rijen}
    assert kop["Het tweede lid de Vpb."] == "II. ARTIKELSGEWIJZE TOELICHTING › Artikel I (artikel 30hb AWR)"
    assert kop["Hetzelfde voor de invorderingsrente."] == "II. ARTIKELSGEWIJZE TOELICHTING › Artikel II (artikel 29 Iw)"
    assert kop["Dit voorstel regelt de rente."] == "I. ALGEMEEN › 1. Inleiding"


def test_de_eerste_pagina_wijst_met_offsets_naar_elk_deel():
    bron = NepBron(DOSSIER, MVT)
    d = roep("get_kamerstuk", {"id": "kst-99001-3"}, bron)
    assert [i["kop"] for i in d["inhoud"]] == [
        "I. ALGEMEEN › 1. Inleiding", "I. ALGEMEEN › 2. Budgettaire aspecten",
        "II. ARTIKELSGEWIJZE TOELICHTING › Artikel I (artikel 30hb AWR)",
        "II. ARTIKELSGEWIJZE TOELICHTING › Artikel II (artikel 29 Iw)"]
    for i in d["inhoud"]:
        sprong = roep("get_kamerstuk", {"id": "kst-99001-3", "offset": i["offset"]}, bron)
        assert sprong["resultaten"][0]["kop"] == i["kop"]
        assert ("inhoud" in sprong) is (i["offset"] == 0), "de inhoud staat alleen op de eerste pagina"
    assert "inhoud_ingekort" not in d


def test_een_inhoud_die_niet_past_gaat_een_niveau_omhoog_en_zegt_het_als_hij_ingekort_is():
    from agent.tools.kamerstuk_tools import MAX_INHOUD, inhoud

    veel = [{"nr": i + 1, "kop": f"Deel {i // 20} › Paragraaf {i}", "tekst": "x"} for i in range(400)]
    lijst, alle = inhoud(veel)
    assert alle and [x["kop"] for x in lijst][:2] == ["Deel 0", "Deel 1"]
    te_veel = [{"nr": i + 1, "kop": f"Hoofdstuk {i} met een lange titel over de invordering", "tekst": "x"} for i in range(400)]
    lijst, alle = inhoud(te_veel)
    assert not alle and 1 < len(lijst) <= MAX_INHOUD
    d = roep("get_kamerstuk", {"id": "kst-99001-3"}, NepBron(DOSSIER, MVT))
    assert d["status"] == "ok"


# ── Voetnoten als rij (plan tabellen en voetnoten, PR 1) ─────────────────────────────────────────────────────────

NOTEN = """<?xml version="1.0" encoding="UTF-8"?>
<officiele-publicatie><kamerstuk><stuk><titel>MEMORIE VAN TOELICHTING</titel><algemeen><vrije-tekst><tekst>
<divisie><kop><nr>1.</nr><titel>Inleiding</titel></kop>
<al>In het regeerakkoord<noot id="n1" type="voet"><noot.nr>1</noot.nr><noot.al>Regeerakkoord, Kamerstuk
<extref doc="kst-33410-15" soort="document" status="actief">33 410, nr. 15</extref>, bijlage B; zie ook
<extref doc="https://www.rijksoverheid.nl/x" soort="URL">rijksoverheid.nl</extref>.</noot.al></noot> is dit
afgesproken.<noot id="n2" type="voet"><noot.nr>2</noot.nr><noot.al>Zie <extref doc="geen-id" soort="document">x</extref>.
</noot.al></noot></al>
<al>Een tweede alinea.</al><al><noot id="n3" type="voet"><noot.nr>3</noot.nr></noot></al>
</divisie></tekst></vrije-tekst></algemeen></stuk></kamerstuk></officiele-publicatie>""".encode()


def test_een_voetnoot_staat_als_rij_direct_na_zijn_alinea():
    _, rijen, overgeslagen = alineas(NOTEN)
    assert [(r["nr"], r.get("soort", "alinea"), r.get("noot", "")) for r in rijen] == [
        (1, "alinea", ""), (2, "voetnoot", "1"), (3, "voetnoot", "2"), (4, "alinea", "")]
    # De alinea houdt haar letterlijke tekst, zonder ingevoegd teken, en noemt haar noten.
    assert rijen[0]["tekst"] == "In het regeerakkoord is dit afgesproken." and rijen[0]["noten"] == ["1", "2"]
    assert rijen[1]["tekst"].startswith("Regeerakkoord, Kamerstuk 33 410, nr. 15, bijlage B")
    assert rijen[1]["kop"] == "1. Inleiding"
    # Een lege noot valt niet stil weg.
    assert overgeslagen == {"voetnoot": 1}


def test_alleen_een_geldig_document_wordt_een_verwijzing():
    _, rijen, _ = alineas(NOTEN)
    assert rijen[1]["verwijst_naar"] == ["kst-33410-15"], "een URL wordt geen vindplaats"
    assert "verwijst_naar" not in rijen[2], "een extref zonder geldig id wordt geen vindplaats"


def test_uit_een_voetnoot_citeren_is_gegrond():
    tekst = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3"}, AAN, kamerstukken=NepBron(DOSSIER, NOTEN))
    goed = check_grounding('Voetnoot 1 van kst-99001-3: "Regeerakkoord, Kamerstuk 33 410, nr. 15, bijlage B"',
                           [("get_kamerstuk", tekst)])
    assert goed.niveau == "gegrond"



# ── Tabellen via `openen` (plan tabellen en voetnoten, PR 2) ─────────────────────────────────────────────────────

TABELLEN = """<?xml version="1.0" encoding="UTF-8"?>
<officiele-publicatie><kamerstuk><stuk><titel>MEMORIE VAN TOELICHTING</titel><algemeen><vrije-tekst><tekst>
<table><tgroup cols="2"><tbody><row><entry><al>Inhoudsopgave</al></entry><entry><al>blz.</al></entry></row></tbody>
</tgroup></table>
<divisie><kop><nr>5.</nr><titel>Budgettaire aspecten</titel></kop><al>De opbrengst staat in tabel 1.</al>
<table><title>Tabel 1 Opbrengst (€ mln)</title><tgroup cols="4">
<colspec colname="c1"/><colspec colname="c2"/><colspec colname="c3"/><colspec colname="c4"/>
<thead><row><entry colname="c1"/><entry colname="c2"><al>2014</al></entry><entry colname="c3"><al>2015</al></entry>
<entry colname="c4"><al>struc</al></entry></row></thead>
<tbody><row><entry colname="c1"><al>Totaal</al></entry><entry colname="c2"><al>12</al></entry>
<entry colname="c3"><al>106</al></entry><entry colname="c4"><al>267</al></entry></row>
<row><entry colname="c1" morerows="1"><al>Waarvan Vpb<noot id="t1" type="tabel"><noot.nr>a</noot.nr><noot.al>Raming.</noot.al>
</noot></al></entry><entry namest="c2" nameend="c3"><al>nvt</al></entry><entry colname="c4"><al>8</al></entry></row>
<row><entry colname="c2"><al>1</al></entry><entry colname="c3"><al>2</al></entry><entry colname="c4"><al>3</al></entry></row>
</tbody></tgroup></table><al>Na de tabel.</al></divisie></tekst></vrije-tekst></algemeen></stuk></kamerstuk>
</officiele-publicatie>""".encode()


def _tabel(args=None):
    bron = NepBron(DOSSIER, TABELLEN)
    tekst = roep("get_kamerstuk", {"id": "kst-99001-3"}, bron)
    [rij] = [r for r in tekst["resultaten"] if r.get("soort") == "tabel"]
    return bron, tekst, rij, roep("get_kamerstuk", args or rij["openen"]["args"], bron)


def test_een_tabel_is_een_rij_met_openen_en_de_inhoudsopgave_niet():
    _, tekst, rij, _ = _tabel()
    assert [r.get("soort", "alinea") for r in tekst["resultaten"]] == ["alinea", "tabel", "alinea"]
    assert rij["tekst"] == "Tabel 1 Opbrengst (€ mln)" and rij["omvang"] == "3 rijen, 4 kolommen"
    assert rij["openen"] == {"tool": "get_kamerstuk", "args": {"id": "kst-99001-3", "tabel": rij["nr"]}}
    assert tekst["overgeslagen"] == {"inhoudsopgave": 1}
    # Eén nummering per stuk: de alinea na de tabel komt na de rijen en de tabelnoot.
    assert tekst["resultaten"][2]["nr"] == rij["tot_nr"] + 1


def test_de_tabel_zelf_met_kolommen_cellen_samengevoegde_cellen_en_tabelnoten():
    _, _, rij, tab = _tabel()
    kop, *rijen, noot = tab["resultaten"]
    assert kop == {"nr": rij["nr"], "soort": "tabel", "kop": "5. Budgettaire aspecten", "tekst": "Tabel 1 Opbrengst (€ mln)",
                   "cellen": ["", "2014", "2015", "struc"]}
    assert [r["cellen"] for r in rijen] == [["Totaal", "12", "106", "267"], ["Waarvan Vpb", "nvt", "", "8"],
                                            ["", "1", "2", "3"]]
    assert rijen[0]["tekst"] == "Totaal | 12 | 106 | 267"
    assert noot["soort"] == "voetnoot" and noot["noot"] == "a" and noot["tekst"] == "Raming."
    assert tab["samengevoegd"] == 2 and tab["volledig"] and tab["stuk"]["id"] == "kst-99001-3"


def test_een_onbekende_tabel_is_een_fout_met_een_voorbeeld():
    _, _, rij, tab = _tabel({"id": "kst-99001-3", "tabel": 999})
    assert tab["status"] == "error" and tab["reden"] == "ongeldige_tabel"
    assert f'"tabel": {rij["nr"]}' in tab["melding"]


def test_uit_een_tabelrij_citeren_is_gegrond():
    bron = NepBron(DOSSIER, TABELLEN)
    tekst = tools.dispatch("get_kamerstuk", None, {"id": "kst-99001-3", "tabel": 2}, AAN, kamerstukken=bron)
    assert check_grounding('Tabel 1 van kst-99001-3: "Totaal | 12 | 106 | 267"', [("get_kamerstuk", tekst)]).niveau == "gegrond"


def test_de_capaciteit_in_de_beschrijving_is_wat_de_leestool_levert():
    """Bundel 22 gaf voetnoten en tabellen, maar de beschrijving zei nog "staan er niet in" (acceptatie 8 nov 2026). Wat
    `get_kamerstuk` op deze fixtures teruggeeft, moet de beschrijving noemen; wat hij overslaat, ook. Vergeleken op de
    stam (`voetnoot` ↔ "voetnoten")."""
    from bronmodel.connectors import KAMERSTUKKEN

    soorten = set()
    for xml in (XML, NOTEN, TABELLEN):
        soorten |= {r.get("soort", "alinea") for r in roep("get_kamerstuk", {"id": "kst-99001-3"},
                                                          NepBron(DOSSIER, xml))["resultaten"]}
    levert = " ".join(KAMERSTUKKEN.levert)
    for soort in soorten - {"tabelrij"}:
        assert soort[:6] in levert, f"de leestool levert {soort}, de beschrijving zegt het niet"
    plaatjes = XML.replace(b"<al>Het doel is", b"<illustratie/><al>Het doel is")
    overgeslagen = roep("get_kamerstuk", {"id": "kst-99001-3"}, NepBron(DOSSIER, plaatjes)).get("overgeslagen") or {}
    niet = " ".join(KAMERSTUKKEN.niet_in_tekst)
    # Een tabel buiten CALS (`<tabel>`) telt nog als overgeslagen; tabellen als soort levert de tool wel.
    for soort in set(overgeslagen) - {"inhoudsopgave"} - soorten:
        assert soort[:6] in niet, f"de leestool slaat {soort} over, de beschrijving zegt het niet"
    assert not any(s[:6] in niet for s in soorten), "de beschrijving zegt dat iets ontbreekt wat de leestool levert"


# ── Metadata uit KOOP (9 nov 2026: gesprek e906567a op acceptatie) ──────────────────────────────────────────────────
# Records in de vorm die de SRU werkelijk teruggaf (live, 9 nov 2026); de waarden zijn verzonnen.

def _sru(*records: str) -> bytes:
    return (f"""<sru:searchRetrieveResponse xmlns:sru="http://docs.oasis-open.org/ns/search-ws/sruResponse"
        xmlns:dcterms="http://purl.org/dc/terms/" xmlns:ow="http://standaarden.overheid.nl/wetgeving/"
        xmlns:gzd="http://standaarden.overheid.nl/sru"><sru:numberOfRecords>{len(records)}</sru:numberOfRecords>
        <sru:records>{''.join(f'<sru:record>{r}</sru:record>' for r in records)}</sru:records>
        </sru:searchRetrieveResponse>""").encode()


def _record_xml(ident: str, *, dossiers=("99001",), nummer="342", status="Onopgemaakt", xml=False, versie="",
                datum="2026-09-25", gepubliceerd="2026-11-09") -> str:
    url = f"https://repository.overheid.nl/frbr/officielepublicaties/kst/{ident}/1"
    return (f"<dcterms:identifier>{ident}</dcterms:identifier><dcterms:title>Wet x; Brief regering; Stand van zaken"
            f"</dcterms:title><dcterms:creator>Tweede Kamer der Staten-Generaal</dcterms:creator>"
            f"<dcterms:modified>2026-11-09</dcterms:modified><dcterms:available>{gepubliceerd}</dcterms:available>"
            f"<dcterms:date>{datum}</dcterms:date><ow:documentstatus>{status}</ow:documentstatus>"
            f"<ow:documenttitel>Stand van zaken</ow:documenttitel><ow:dossiertitel>Wet x</ow:dossiertitel>"
            f"<ow:indiener>A.B. de Vries</ow:indiener><ow:indiener>C.D. Jansen</ow:indiener>"
            f"<ow:ondernummer>{nummer}</ow:ondernummer><ow:vergaderjaar>2026-2027</ow:vergaderjaar>"
            + "".join(f"<ow:dossiernummer>{d}</ow:dossiernummer>" for d in dossiers)
            + f"<ow:subrubriek>Brief regering</ow:subrubriek>"
            + (f"<ow:versieinformatie>{versie}</ow:versieinformatie>" if versie else "")
            + f'<gzd:itemUrl manifestation="pdf">{url}/pdf/{ident}.pdf</gzd:itemUrl>'
            + (f'<gzd:itemUrl manifestation="xml">{url}/xml/{ident}.xml</gzd:itemUrl>' if xml else ""))


def test_het_record_leest_elk_veld_apart():
    _, [r] = lees_records(_sru(_record_xml("kst-1278484", dossiers=("32140", "32141"))))
    # Eerst stond hier `available or date`: twee datums door elkaar.
    assert (r.datum, r.gepubliceerd) == ("2026-09-25", "2026-11-09")
    assert r.dossiers == ("32140", "32141") and r.ondernummer == "342" and r.vergaderjaar == "2026-2027"
    assert (r.soort, r.documenttitel, r.dossiertitel) == ("Brief regering", "Stand van zaken", "Wet x")
    assert r.indieners == ("A.B. de Vries", "C.D. Jansen") and r.kamer.startswith("Tweede Kamer")
    assert not r.leesbaar and r.pdf_url.endswith(".pdf") and r.documentstatus == "Onopgemaakt"


def test_de_rij_draagt_de_metadata_uit_koop():
    _, [r] = lees_records(_sru(_record_xml("kst-1278484", dossiers=("32140", "32141"))))
    rij = roep("zoek_kamerstukken", {"dossier": "32140"}, NepBron([r]))["resultaten"][0]
    # Het label komt uit dossier en nummer, niet uit het id van het onopgemaakte stuk.
    assert rij["label"] == "Kamerstukken 32140, nr. 342" and rij["id"] == "kst-1278484"
    assert rij["datum"] == "2026-09-25" and rij["gepubliceerd"] == "2026-11-09" and rij["jaar"] == "2026-2027"
    assert rij["soort"] == "Brief regering" and rij["titel"] == "Stand van zaken" and rij["orgaan"] == "Tweede Kamer"
    assert rij["indieners"] == ["A.B. de Vries", "C.D. Jansen"] and rij["reeks"] == ["32140", "32141"]
    assert rij["status"] == "Onopgemaakt" and rij["leesbaar"] is False


def test_een_gewone_rij_noemt_geen_uitzonderingen():
    _, [r] = lees_records(_sru(_record_xml("kst-99001-3", nummer="3", status="Opgemaakt na onopgemaakt", xml=True,
                                           gepubliceerd="2026-09-25")))
    rij = roep("zoek_kamerstukken", {"dossier": "99001"}, NepBron([r]))["resultaten"][0]
    assert not {"gepubliceerd", "reeks", "status", "leesbaar"} & set(rij)


@pytest.mark.parametrize("ident,verwacht", [
    ("kst-32140-342", ("32140", "342")), ("kst-36200-IX-2", ("36200-IX", "2")), ("kst-32740-1-n1", ("32740", "1")),
    ("kst-21501-08-525", ("21501-08", "525")), ("kst-35348-E", ("35348", "E")), ("kst-1278484", None)])
def test_dossier_en_nummer_uit_het_id(ident, verwacht):
    assert sru.dossier_en_nummer(ident) == verwacht


class Koop:
    """De SRU van KOOP: `per_id` antwoordt op dt.identifier, `per_nummer` op dossier en nummer."""

    def __init__(self, per_id: dict[str, str], per_nummer: dict[tuple[str, str], list[str]] | None = None, weg=False):
        self.per_id, self.per_nummer, self.weg, self.vragen = per_id, per_nummer or {}, weg, []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.weg:
            raise httpx.ConnectError("weg")
        if r.url.path.endswith(".xml"):
            return httpx.Response(200, content=XML)
        q = r.url.params["query"]
        self.vragen.append(q)
        if "dt.identifier==" in q:
            ident = q.rsplit("==", 1)[1]
            return httpx.Response(200, content=_sru(*([self.per_id[ident]] if ident in self.per_id else [])))
        d, n = q.split('w.dossiernummer=="')[1].split('"')[0], q.split('w.ondernummer=="')[1].split('"')[0]
        return httpx.Response(200, content=_sru(*self.per_nummer.get((d, n), [])))


def _koop(dienst: Koop) -> SruKamerstukken:
    return SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(dienst)))


def test_een_herdruk_wordt_gevonden_op_dossier_en_nummer():
    # kst-32740-1 bestaat niet bij KOOP; de herdruk heet kst-32740-1-n1.
    herdruk = _record_xml("kst-32740-1-n1", dossiers=("32740",), nummer="1", status="Opgemaakt na onopgemaakt",
                          xml=True, versie="Herdruk")
    dienst = Koop({}, {("32740", "1"): [herdruk]})
    d = roep("get_kamerstuk", {"id": "kst-32740-1"}, _koop(dienst))
    assert d["status"] == "ok" and d["stuk"]["id"] == "kst-32740-1-n1"
    assert d["stuk"]["label"] == "Kamerstukken 32740, nr. 1 (herdruk)" and d["stuk"]["versie"] == "Herdruk"
    assert "kst-32740-1-n1" in d["toelichting"]
    assert d["stuk"]["datum"] == "2026-09-25" and d["stuk"]["soort"] == "Brief regering"


def test_een_motie_in_meer_dossiers_telt_alleen_in_haar_hoofddossier():
    elders = _record_xml("kst-33752-L", dossiers=("33752", "33755"), nummer="1", xml=True)
    dienst = Koop({}, {("33755", "1"): [elders]})
    d = roep("get_kamerstuk", {"id": "kst-33755-1"}, _koop(dienst))
    assert d["status"] == "error" and d["reden"] == "niet_gevonden" and "bijvoorbeeld" in d["melding"]


def test_een_stuk_met_alleen_een_pdf_bestaat():
    # 32140 nr. 342 heette "bron_onbereikbaar", en Lex zei dat het misschien niet bestond.
    pdf = _record_xml("kst-1278484", dossiers=("32140",), datum="2026-10-16", gepubliceerd="2026-10-16")
    d = roep("get_kamerstuk", {"id": "kst-32140-342"}, _koop(Koop({}, {("32140", "342"): [pdf]})))
    assert d["status"] == "error" and d["reden"] == "alleen_pdf"
    assert d["stuk"]["id"] == "kst-1278484" and d["stuk"]["label"] == "Kamerstukken 32140, nr. 342"
    assert d["stuk"]["datum"] == "2026-10-16" and d["stuk"]["leesbaar"] is False
    assert "2026-10-16" in d["melding"] and "https://zoek.officielebekendmakingen.nl/kst-1278484" in d["melding"]


def test_de_foutcode_zegt_de_oorzaak():
    d = roep("get_kamerstuk", {"id": "kst-99001-7"}, _koop(Koop({})))
    assert d["reden"] == "niet_gevonden"
    d = roep("get_kamerstuk", {"id": "kst-99001-7"}, _koop(Koop({}, weg=True)))
    assert d["reden"] == "bron_onbereikbaar"

    class Weigert(NepBron):
        def zoek(self, cql, **_):
            return lees_records(b'<r xmlns:diag="http://docs.oasis-open.org/ns/search-ws/diagnostic"><diag:diagnostic>'
                                b'<diag:message>Unsupported index</diag:message></diag:diagnostic></r>')
    assert roep("zoek_kamerstukken", {"dossier": "99001"}, Weigert(DOSSIER))["reden"] == "zoekvraag_geweigerd"


def test_alleen_een_storing_geeft_de_bewaarde_versie(monkeypatch):
    # Een stuk dat bij KOOP verdween, is geen storing: dan geen oude tekst met gevalideerd: false.
    leesbaar = _record_xml("kst-99001-3", nummer="3", xml=True)
    dienst = Koop({"kst-99001-3": leesbaar})
    nu = [0.0]
    bron = SruKamerstukken(client=httpx.Client(transport=httpx.MockTransport(dienst)), klok=lambda: nu[0])
    bron.document("kst-99001-3")
    dienst.per_id, nu[0] = {}, sru.VERS_S + 1
    with pytest.raises(KamerstukFout) as fout:
        bron.document("kst-99001-3")
    assert fout.value.code == "niet_gevonden"


@pytest.mark.parametrize("titel,dossiertitel,documenttitel,verwacht", [
    # kst-33755-3 (live): subrubriek "Overig", het soort staat midden in de titel.
    ("Wet x (y; z); Memorie van toelichting; 33755 MvT inzake Wet x", "Wet x (y; z)", "33755 MvT inzake Wet x",
     "Memorie van toelichting"),
    ("Wet x; Verslag", "Wet x", "", "Verslag"),
    ("Wet x; Brief regering; Stand van zaken", "", "", "Brief regering"),
])
def test_het_soort_uit_de_titel_als_de_rubriek_overig_is(titel, dossiertitel, documenttitel, verwacht):
    r = dataclasses.replace(rec("kst-99001-3", titel, "3"), soort="Overig", dossiertitel=dossiertitel,
                            documenttitel=documenttitel)
    assert roep("zoek_kamerstukken", {"dossier": "99001"}, NepBron([r]))["resultaten"][0]["soort"] == verwacht


# ── Filters en volgorde (PR 3 van metadata in het connectorcontract) ─────────────────────────────────────────────────

BASIS = "c.product-area==officielepublicaties AND w.publicatienaam==Kamerstuk AND dt.type==Kamerstuk"


@pytest.mark.parametrize("args,verwacht", [
    ({"volgorde": "nieuwste"}, " sortBy dt.date/sort.descending dt.identifier/sort.ascending"),
    ({"dossier": "32140", "volgorde": "nieuwste", "aantal": 1},
     ' AND w.dossiernummer=="32140" sortBy dt.date/sort.descending dt.identifier/sort.ascending'),
    ({"dossier": "32140", "nummer": "342"},
     ' AND w.dossiernummer=="32140" AND w.ondernummer=="342" sortBy dt.date/sort.descending dt.identifier/sort.ascending'),
    ({"soort": "Memorie van toelichting", "vanaf": "2024", "tot": "2024-06"},
     " AND dt.date>=2024-01-01 AND dt.date<=2024-06-30"
     ' AND (w.subrubriek all "memorie van toelichting" OR dt.identifier=="kst-99001-3")'
     " sortBy dt.date/sort.descending dt.identifier/sort.ascending"),
    ({"vergaderjaar": "2025/26", "kamer": "Eerste Kamer", "volgorde": "oudste"},
     ' AND w.vergaderjaar=="2025-2026" AND dt.creator=="Eerste Kamer der Staten-Generaal"'
     " sortBy dt.date/sort.ascending dt.identifier/sort.ascending"),
    ({"woorden": "Invorderingswet"}, ' AND dt.title any "invorderingswet"'),
    # Zoeken in de hele tekst: een zinsdeel tussen aanhalingstekens als zinsdeel, losse woorden allemaal.
    ({"tekst": '"één bankrekeningnummer" toeslagen'},
     ' AND cql.textAndIndexes adj "één bankrekeningnummer" AND cql.textAndIndexes all "toeslagen"'),
    ({"tekst": "POBR1", "vanaf": "2011", "tot": "2016", "volgorde": "oudste"},
     ' AND cql.textAndIndexes all "pobr1" AND dt.date>=2011-01-01 AND dt.date<=2016-12-31'
     " sortBy dt.date/sort.ascending dt.identifier/sort.ascending"),
])
def test_de_filters_worden_cql_uit_de_code(args, verwacht):
    bron = NepBron(DOSSIER)
    d = roep("zoek_kamerstukken", args, bron)
    assert d["status"] == "ok", d
    assert bron.vragen[-1] == BASIS + verwacht
    assert d["zoekvraag"]["volgorde"] == (args.get("volgorde") or ("relevantie" if {"woorden", "tekst"} & set(args)
                                                                   else "nieuwste"))


def test_het_aantal_begrenst_de_pagina_en_het_vervolg_houdt_de_zoekvraag():
    bron = NepBron(_veel(30))
    d = roep("zoek_kamerstukken", {"volgorde": "nieuwste", "aantal": 10}, bron)
    assert d["aantal"] == 10 and not d["volledig"] and d["totaal"] == 30
    assert d["vervolg"]["args"] == {"volgorde": "nieuwste", "aantal": 10, "offset": 10}
    assert d["zoekvraag"] == {"aantal": 10, "volgorde": "nieuwste"}


def test_een_dossier_alleen_staat_nog_op_nummer():
    d = roep("zoek_kamerstukken", {"dossier": "99001"})
    assert d["volgorde"] == "nummer" and d["zoekvraag"] == {"dossier": "99001", "volgorde": "nummer"}


@pytest.mark.parametrize("args,reden", [
    ({"nummer": "342"}, "ongeldig_nummer"),
    ({"dossier": "32140", "nummer": "3/4"}, "ongeldig_nummer"),
    ({"vanaf": "vorig jaar"}, "ongeldige_datum"),
    ({"vanaf": "2024-13"}, "ongeldige_datum"),
    ({"vanaf": "2025", "tot": "2024"}, "ongeldige_datum"),
    ({"vergaderjaar": "2025-2027"}, "ongeldig_vergaderjaar"),
    ({"kamer": "Senaat", "volgorde": "nieuwste"}, "ongeldige_kamer"),
    ({"volgorde": "willekeurig"}, "ongeldige_volgorde"),
    ({"volgorde": "nummer"}, "ongeldige_volgorde"),
    ({"soort": "motie", "volgorde": "relevantie"}, "ongeldige_volgorde"),
    ({"volgorde": "nieuwste", "aantal": 0}, "ongeldig_aantal"),
    ({"volgorde": "nieuwste", "aantal": 26}, "ongeldig_aantal"),
    ({}, "ongeldige_argumenten"),
    ({"tekst": "a b"}, "ongeldige_tekst"),
    ({"tekst": '"een twee drie vier vijf" zes zeven'}, "ongeldige_tekst"),
])
def test_een_invoerfout_zegt_wat_wel_kan(args, reden):
    d = roep("zoek_kamerstukken", args)
    assert d["status"] == "error" and d["reden"] == reden and "bijvoorbeeld" in d["melding"], d


# ── Ronde 1 van de Kamerstukken-iteratie (11 nov 2026) ───────────────────────────────────────────────────────────────

def _met_rubriek(ident: str, titel: str, rubriek: str, nr: str) -> Record:
    return dataclasses.replace(rec(ident, titel, nr), soort=rubriek, dossiers=("36602",))


def test_het_soort_uit_de_titel_geldt_alleen_voor_een_stuk_zonder_rubriek():
    """K10: "Belastingplan 2025; Brief regering; Uitvoeringstoetsen aangenomen amendementen" is geen amendement."""
    kandidaten = [_met_rubriek("kst-36602-166", "Belastingplan 2025; Brief regering; Uitvoeringstoetsen aangenomen "
                               "amendementen", "Brief regering", "166"),
                  _met_rubriek("kst-36602-9", "Belastingplan 2025; Amendement van het lid X", "", "9"),
                  _met_rubriek("kst-36602-10", "Belastingplan 2025; Amendement; tweede", "Overig", "10")]
    bron = NepBron(kandidaten)
    roep("zoek_kamerstukken", {"dossier": "36602", "soort": "amendement", "volgorde": "nieuwste"}, bron)
    assert bron.vragen[0] == (BASIS + ' AND w.dossiernummer=="36602" AND dt.title all "amendement"'
                              ' NOT w.subrubriek all "amendement"'), "eerst de stukken waarvan alleen de titel het draagt"
    assert ('(w.subrubriek all "amendement" OR dt.identifier=="kst-36602-9" OR dt.identifier=="kst-36602-10")'
            in bron.vragen[-1]), "de brief valt af, de stukken zonder rubriek blijven"


def test_zonder_kandidaat_in_de_titel_alleen_de_rubriek():
    bron = NepBron([_met_rubriek("kst-36602-166", "Belastingplan 2025; Brief regering; Over amendementen",
                                 "Brief regering", "166")])
    roep("zoek_kamerstukken", {"dossier": "36602", "soort": "amendement", "volgorde": "nieuwste"}, bron)
    assert bron.vragen[-1].startswith(BASIS + ' AND w.dossiernummer=="36602" AND w.subrubriek all "amendement" sortBy')


def test_te_veel_kandidaten_in_de_titel_houdt_de_titel_als_filter_en_zegt_het():
    from agent.tools.kamerstuk_tools import MAX_SOORT_TITEL
    bron = NepBron([_met_rubriek(f"kst-36602-{i}", "Wet; Motie", "", str(i)) for i in range(MAX_SOORT_TITEL + 1)])
    d = roep("zoek_kamerstukken", {"soort": "motie", "volgorde": "nieuwste", "aantal": 5}, bron)
    assert '(w.subrubriek all "motie" OR dt.title all "motie")' in bron.vragen[-1]
    assert "alleen in de titel" in d["toelichting"]


def test_een_dossier_op_nummer_met_een_aantal_geeft_de_eerste():
    """K07, K17: 'volgorde: nummer' met 'aantal' was een invoerfout."""
    d = roep("zoek_kamerstukken", {"dossier": "99001", "volgorde": "nummer", "aantal": 2})
    assert d["status"] == "ok" and [r["id"] for r in d["resultaten"]] == ["kst-99001-2", "kst-99001-3"]
    assert d["totaal"] == 3 and d["volgorde"] == "nummer"


def _beurt(vraag: str, bron, monkeypatch):
    import asyncio
    from agent import tools as t
    from agent.agent import answer_stream
    from tests.fakes import FakeGraph, FakeLLM

    monkeypatch.setattr(t.CONNECTORMODULES["kamerstukken"], "_bron", bron)
    llm = FakeLLM([])

    async def verzamel():
        return [e async for e in answer_stream(vraag, settings=AAN, llm=llm, graph=FakeGraph(result=""),
                                               bronnen=["kamerstukken"])]

    events = asyncio.run(verzamel())
    assert llm.calls == [], "geen model"
    antwoord, = [e["antwoord"] for e in events if e["type"] == "antwoord"]
    return antwoord["blokken"]


def test_een_genoemd_stuk_met_alleen_een_pdf_is_een_melding_uit_code(monkeypatch):
    """K12 (ronde 1, 11 nov 2026): het model formuleerde zelf wat de code al wist."""
    pdf = _record_xml("kst-1278484", dossiers=("32140",), datum="2026-10-16", gepubliceerd="2026-10-16")
    leemte, lijst = _beurt("Wat staat er in kst-32140-342?", _koop(Koop({}, {("32140", "342"): [pdf]})), monkeypatch)
    assert leemte["soort"] == "leemte" and "alleen als PDF (onopgemaakt):" in leemte["tekst"]
    assert lijst["soort"] == "stukken" and lijst["kop"] == "Uit de parlementaire geschiedenis"
    assert lijst["items"][0]["id"] == "kst-1278484" and lijst["items"][0]["label"] == "Kamerstukken 32140, nr. 342"


def test_een_genoemd_stuk_dat_niet_bestaat_is_een_melding_uit_code(monkeypatch):
    """K27: "kst-99999-99" ging langs het model en stond daarna in de bronnen."""
    [leemte] = _beurt("Wat staat er in kst-99001-7?", _koop(Koop({})), monkeypatch)
    assert leemte["soort"] == "leemte" and leemte["tekst"].startswith("kst-99001-7 is bij Kamerstukken niet gevonden.")


@pytest.mark.parametrize("args", [{"dossier": "20588"}, {"tekst": "xyzzyquux"}])
def test_een_lege_uitkomst_noemt_de_grens_van_de_zoekdienst(args):
    """Ronde 2 Kamerstukken (11 nov 2026, K16 en K17): dossier 20588 (de Invorderingswet 1990) gaf niets, en het model
    schreef twee keer dat die stukken "alleen als PDF" bij KOOP staan. Ze staan er helemaal niet in."""
    d = roep("zoek_kamerstukken", args, NepBron([]))
    assert d["status"] == "ok" and d["aantal"] == 0
    assert EERSTE_VERGADERJAAR in d["toelichting"] and "ook niet als PDF" in d["toelichting"]


def test_een_stuk_uit_een_gezamenlijke_behandeling_zegt_dat_in_de_lijst():
    """Ronde 2 Kamerstukken (K04, K21, K25): in de lijst van dossier 33755 stond "Kamerstukken 33752, nr. L" zonder uitleg."""
    from bronmodel.antwoord import Antwoord, Stuk, Stukken, antwoord_tekst
    blok = Stukken(brontype="kamerstuk", kop="Gevonden Kamerstukken", totaal=2, items=[
        Stuk(id="kst-33755-3", label="Kamerstukken 33755, nr. 3"),
        Stuk(id="kst-33752-L", label="Kamerstukken 33752, nr. L", gezamenlijk=["33752", "33753", "33754", "33755"])])
    regels = [r for r in antwoord_tekst(Antwoord(sjabloon="extern", blokken=[blok])).splitlines() if r.startswith("- ")]
    assert regels[0] == "- Kamerstukken 33755, nr. 3"
    assert regels[1] == "- Kamerstukken 33752, nr. L (gezamenlijk behandeld: 33752–33755)"


@pytest.mark.parametrize("connector,verwacht", [
    ("kamerstukken", " (onopgemaakt)"),     # "onopgemaakt, alleen PDF": alleen wat nieuw is
    ("bekendmakingen", ""),                 # "alleen als PDF": niets nieuws, dus geen haakjes (B07, Staatsblad ronde 3)
    ("rechtspraak", " (geen tekst in de open data)"),
    ("wetgeving_live", " (niet volledig te lezen)"),
])
def test_de_vaste_pdf_zin_herhaalt_de_connector_niet(connector, verwacht):
    from agent.nodes.bron_lezen import _wat_nieuw
    from bronmodel.connectors import CONNECTORS
    c = CONNECTORS[connector]
    extra = _wat_nieuw(c.zonder_tekst, "alleen als PDF")
    assert (f" ({extra})" if extra else "") == verwacht


@pytest.mark.parametrize("connector", ["kamerstukken", "bekendmakingen", "rechtspraak", "wetgeving_live"])
def test_een_onbereikbare_bron_is_een_melding_uit_code_voor_elke_connector(connector):
    """Ronde 3 Kamerstukken (12 nov 2026, K11): bij een storing van KOOP verwees het model naar "kamerstukken.nl …
    onderdeel 3", en de controle zei ongegrond. De code zegt het nu zelf, met het id dat gevraagd was."""
    from agent.nodes.bron_lezen import _zonder_tekst
    from bronmodel.connectors import CONNECTORS
    c = CONNECTORS[connector]
    resultaten = [{"content": json.dumps({"status": "error", "reden": "bron_onbereikbaar", "melding": "time-out"})}]
    gebruik = [{"name": c.leestool, "input": {c.lees_argument: c.voorbeeld_id}}]
    antwoord = _zonder_tekst(resultaten, [], gebruik)
    assert antwoord is not None
    [leemte] = antwoord.blokken
    assert leemte.tekst == (f"{c.label} is nu niet te bereiken, dus {c.voorbeeld_id} kan ik niet lezen. Vraag het over "
                            "een paar minuten opnieuw; zonder tekst zeg ik er niets over.")


def test_een_genoemd_stuk_bij_een_storing_gaat_niet_langs_het_model(monkeypatch):
    [leemte] = _beurt("Wat staat er in kst-33755-3?", _koop(Koop({}, weg=True)), monkeypatch)
    assert leemte["tekst"].startswith("Kamerstukken is nu niet te bereiken, dus kst-33755-3 kan ik niet lezen.")


def test_woorden_geeft_de_alineas_van_een_stuk_die_ze_noemen_met_hun_offset():
    """Ronde 3 Kamerstukken (12 nov 2026, K07): het model zocht de passages met tien offsets in drie stukken, 779k tokens.
    Een woord telt ook in een vervoeging of samenstelling (de stam van zeven letters), en ook in de kop."""
    d = roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "invorderingsrenten"})
    assert d["status"] == "ok" and d["volledig"]
    assert [(r["offset"], r["tekst"]) for r in d["resultaten"]] == [(0, "Dit voorstel regelt de invorderingsrente opnieuw.")]
    assert d["totaal"] == 1 and d["alineas"] == 3 and "1 van de 3 alinea's" in d["toelichting"]
    kop = roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "doel eenvoud"})
    assert [r["offset"] for r in kop["resultaten"]] == [2], "elk woord, in tekst of kop"
    niets = roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "bestuurder"})
    assert niets["aantal"] == 0 and "inhoud: true" in niets["toelichting"]
    assert roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "of"})["reden"] == "ongeldige_argumenten"


def test_woorden_zonder_treffer_zegt_per_woord_hoe_vaak_het_los_staat():
    """Ronde 4 Kamerstukken (12 nov 2026, K07 en K16): vijf keer nul treffers op woorden die samen nergens staan, en het
    model raadde telkens opnieuw welk woord eruit moest. De code telt het per woord."""
    d = roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "invorderingsrente bestuurder"})
    assert d["status"] == "ok" and d["aantal"] == 0
    assert d["per_woord"] == {"invorde": 1, "bestuur": 0}
    assert "„invorde…” 1, „bestuur…” 0" in d["toelichting"] and "laat „bestuur…” weg" in d["toelichting"]
    beide = roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "invorderingsrente eenvoud"})
    assert beide["aantal"] == 0 and "geef minder woorden tegelijk" in beide["toelichting"], "elk woord staat er, los"
    assert "per_woord" not in roep("get_kamerstuk", {"id": "kst-99001-3", "woorden": "bestuurder"}), "één woord: niets te tellen"


def test_een_lettercode_in_een_gezamenlijke_behandeling_vindt_het_stuk_in_het_eerste_dossier():
    """Ronde 3 Kamerstukken (12 nov 2026, K22): de lijst van dossier 33755 noemde 33752 nr. L, en de vervolgvraag "wat staat
    erin?" werd kst-33755-L, dat KOOP niet kent. Een lettercode van de Eerste Kamer geldt voor de hele reeks."""
    motie = _record_xml("kst-33752-L", dossiers=("33752", "33753", "33754", "33755"), nummer="L", xml=True)
    d = roep("get_kamerstuk", {"id": "kst-33755-L"}, _koop(Koop({}, {("33755", "L"): [motie]})))
    assert d["status"] == "ok" and d["stuk"]["id"] == "kst-33752-L" and "kst-33752-L" in d["toelichting"]


@pytest.mark.parametrize("brontype,velden,zin", [
    ("kamerstuk", {"reeks": ["33752", "33755"], "gezamenlijk": ["33752", "33755"]}, " (gezamenlijk behandeld: 33752 en 33755)"),
    ("wettekst_live", {"reeks": ["Hoofdstuk 2", "§ 2.1"]}, ""),       # de plek in de regeling (wetgeving_live ronde 3, I13)
    ("bekendmaking", {"reeks": ["36602"]}, ""),                      # het Kamerdossier
    ("uitspraak", {}, ""),
])
def test_alleen_gezamenlijk_geeft_de_zin_niet_reeks(brontype, velden, zin):
    """`reeks` betekent per connector iets anders; alleen het eigen veld `gezamenlijk` zegt dat dossiers samen zijn
    behandeld (wetgeving_live ronde 3, I13/I14: elke artikelrij kreeg "gezamenlijk behandeld: Hoofdstuk 2–§ 2.1")."""
    from bronmodel.antwoord import Antwoord, Stuk, Stukken, antwoord_tekst
    blok = Stukken(brontype=brontype, kop="Gevonden", items=[Stuk(id="x-1", label="Stuk 1", **velden)])
    regel = next(r for r in antwoord_tekst(Antwoord(sjabloon="extern", blokken=[blok])).splitlines() if r.startswith("- "))
    assert regel == f"- Stuk 1{zin}"


def test_de_metadata_van_een_kamerstuk_draagt_gezamenlijk_bij_meer_dossiers():
    from agent.tools.kamerstuk_tools import metadata
    from bronmodel.connectors import externe_vindplaats
    een = Record(id="kst-33755-3", titel="MvT", datum="2013-09-17", vergaderjaar="2013-2014", dossiers=("33755",),
                 ondernummer="3", xml_url="https://repository.overheid.nl/x.xml")
    meer = Record(id="kst-33752-L", titel="Motie", datum="2013-12-17", vergaderjaar="2013-2014",
                  dossiers=("33752", "33753", "33754", "33755"), ondernummer="L", xml_url="https://repository.overheid.nl/y.xml")
    assert "gezamenlijk" not in metadata(een, externe_vindplaats("kst-33755-3"))
    assert metadata(meer, externe_vindplaats("kst-33752-L"))["gezamenlijk"] == ["33752", "33753", "33754", "33755"]
