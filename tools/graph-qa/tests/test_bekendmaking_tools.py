"""De bronconnector Staatsblad en Staatscourant (ADR-013), tegen opgenomen antwoorden van KOOP.

De fixtures in `tests/fixtures/koop/` zijn echte antwoorden van de SRU en echte publicaties (opgehaald op 10 nov 2026;
wetten en besluiten zijn vrij van auteursrecht, Auteurswet art. 11): het inwerkingtredingsbesluit Stb. 2010, 176, de
wijzigingswet Stb. 2009, 610 (Iw art. 36), een wijziging van de Leidraad Invordering 2008 (Stcrt. 2026, 37344) en de
Invoeringswet Invorderingswet 1990 (Stb. 1990, 222), die bij KOOP alleen als PDF staat. Wat de echte dienst nu doet, toetst
`test_bekendmakingen_live.py`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from bronmodel import connectors as bm

from agent import tools
from agent.adapters.sru_bekendmakingen import SruBekendmakingen, blad_jaar_nummer
from agent.adapters.sru_koop import KoopFout, lees_records
from agent.config import Settings
from agent.tools import bekendmaking_tools as b
from agent.tools.op_xml import lees
from bronmodel.connectors import BEKENDMAKINGEN, genoemde_stukken
from bronmodel.extern import externe_vindplaats, koop_id_uit_bron

from fakes import FakeGraph

FIX = Path(__file__).parent / "fixtures" / "koop"
AAN = Settings(connector_bekendmakingen=True)
IW = "BWBR0004770"


def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return v if v.startswith('"') else json.dumps(v, ensure_ascii=False)
    return json.dumps("\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n"
                                                                       for r in rijen))


#: Wat de graaf bij Iw art. 36 zegt (acceptatie, 10 nov 2026): de wijziging Stb. 2009, 610, in werking via Stb. 2010, 176.
ART36 = _tsv(["waarde", "rol", "inwerking", "aantal"], [
    ["Stb.2009-610", "wijziging", '"2010-07-04"^^<http://www.w3.org/2001/XMLSchema#date>', '"1"^^<http://www.w3.org/2001/XMLSchema#integer>'],
    ["Stb.2010-176", "inwerkingtreding", '"2010-07-04"^^<http://www.w3.org/2001/XMLSchema#date>', '"1"^^<http://www.w3.org/2001/XMLSchema#integer>'],
])


class Koop:
    """Een nep-SRU van KOOP over HTTP: antwoordt met de opgenomen records en documenten."""

    def __init__(self, *, weg: bool = False) -> None:
        self.vragen: list[str] = []
        self.weg = weg

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.weg:
            raise httpx.ConnectError("weg", request=r)
        if r.url.path.endswith(".xml") and "/frbr/" in r.url.path:
            naam = Path(r.url.path).name
            self.vragen.append(naam)
            return httpx.Response(200, content=(FIX / naam).read_bytes())
        query = parse_qs(urlparse(str(r.url)).query)["query"][0]
        self.vragen.append(query)
        ids = re.findall(r"dt\.identifier==([\w-]+)", query)
        if len(ids) == 2 and set(ids) == {"stb-2009-610", "stb-2010-176"}:
            return httpx.Response(200, content=(FIX / "sru-iw36.xml").read_bytes())
        if len(ids) == 1 and (FIX / f"sru-{ids[0]}.xml").exists():
            return httpx.Response(200, content=(FIX / f"sru-{ids[0]}.xml").read_bytes())
        return httpx.Response(200, content=b'<sru:searchRetrieveResponse xmlns:sru="http://docs.oasis-open.org/ns/'
                                           b'search-ws/sruResponse"><sru:numberOfRecords>0</sru:numberOfRecords>'
                                           b'</sru:searchRetrieveResponse>')


def _bron(dienst: Koop | None = None) -> SruBekendmakingen:
    return SruBekendmakingen(client=httpx.Client(transport=httpx.MockTransport(dienst or Koop())))


def roep(naam: str, args: dict, bron=None, graph=None) -> dict:
    return json.loads(tools.dispatch(naam, graph, args, AAN, bekendmakingen=bron or _bron()))


# ── Ids en citeervormen ────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bron,verwacht", [
    ("Stb.2009-610", "stb-2009-610"), ("Stcrt.2016-69107", "stcrt-2016-69107"), ("Stb. 2010, 176", "stb-2010-176"),
    ("Trb.2001-1", None), ("", None), ("Stb.2009", None)])
def test_de_vorm_van_de_bwb_wordt_een_id(bron, verwacht):
    assert koop_id_uit_bron(bron) == verwacht


@pytest.mark.parametrize("ident,label", [
    ("stb-2010-176", "Stb. 2010, 176"), ("stcrt-2026-37344", "Stcrt. 2026, 37344"),
    ("stcrt-2008-122-p18-SC86213", "Stcrt. 2008, 122, p. 18"), ("stb-2023-1-n1", "Stb. 2023, 1 (versie n1)")])
def test_het_label_van_een_bekendmaking(ident, label):
    vp = externe_vindplaats(ident)
    assert vp is not None and vp.brontype == "bekendmaking" and vp.label == label


def test_een_citeervorm_wordt_het_id():
    tekst = "Wat staat er in Stb. 2010, 176, en wat in Staatscourant 2026, nr. 37344? En Stb.2009-610."
    assert [i for _, i in genoemde_stukken(tekst)] == ["stb-2010-176", "stcrt-2026-37344", "stb-2009-610"]


def test_blad_jaar_en_nummer_uit_het_id():
    assert blad_jaar_nummer("stb-2010-176") == ("Staatsblad", "2010", "176")
    assert blad_jaar_nummer("stcrt-2026-37344-n1") == ("Staatscourant", "2026", "37344")
    assert blad_jaar_nummer("stcrt-2008-122-p18-SC86213") is None, "een oud Stcrt-nummer wijst geen stuk aan"


# ── Het record ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_het_record_draagt_de_velden_van_een_bekendmaking():
    _, [rec] = lees_records((FIX / "sru-stb-2010-176.xml").read_bytes())
    assert rec.publicatienaam == "Staatsblad" and rec.jaargang == "2010" and rec.publicatienummer == "176"
    assert rec.type and rec.datum and rec.ondertekend and rec.leesbaar


def test_een_datum_die_niet_kan_kloppen_telt_als_onbekend():
    xml = (FIX / "sru-stb-2010-176.xml").read_bytes()
    _, [rec] = lees_records(re.sub(rb"<dcterms:date>[^<]+", b"<dcterms:date>0004-03-01", xml))
    assert rec.datum == rec.gepubliceerd and rec.datum.startswith("2010"), "stb-2019-129 heeft dt.date 0004-03-01"


# ── Zoeken bij een bepaling ────────────────────────────────────────────────────────────────────────────────────────

def test_bij_een_artikel_de_wijziging_en_het_inwerkingtredingsbesluit():
    graaf = FakeGraph(result=ART36)
    d = roep("zoek_bekendmakingen", {"bwb_id": IW, "artikel": "36"}, graph=graaf)
    assert d["status"] == "ok" and [r["id"] for r in d["resultaten"]] == ["stb-2009-610", "stb-2010-176"]
    wijziging, iwt = d["resultaten"]
    assert wijziging["wetsverwijzing"] == f"laatste wijziging van artikel 36 van {IW}"
    assert iwt["wetsverwijzing"] == f"inwerkingtreding van artikel 36 van {IW}"
    assert wijziging["inwerking"] == "2010-07-04" and wijziging["publicatie"] == "Staatsblad"
    assert iwt["label"] == "Stb. 2010, 176" and iwt["soort"] and iwt["link"].endswith("/stb-2010-176")
    assert "eerdere toestanden" in d["toelichting"], "de grens: alleen de toestand die Lex leest"
    assert "bwb:inwerkingtredingsbron" in graaf.queries[0] and "bwb:bron" in graaf.queries[0]


def test_een_bepaling_zonder_publicatie_is_een_lege_lijst_met_de_reden():
    d = roep("zoek_bekendmakingen", {"bwb_id": IW, "artikel": "1"}, graph=FakeGraph(result=_tsv(
        ["waarde", "rol", "inwerking", "aantal"], [])))
    assert d["status"] == "ok" and d["resultaten"] == [] and "geen publicatie" in d["toelichting"]


def test_zonder_graaf_geen_koppeling_maar_een_fout():
    d = json.loads(tools.dispatch("zoek_bekendmakingen", None, {"bwb_id": IW, "artikel": "36"}, AAN,
                                  bekendmakingen=_bron()))
    assert d["status"] == "error" and d["reden"] == "graaf_onbereikbaar"


def test_een_publicatie_die_koop_niet_kent_staat_er_toch_met_de_reden():
    graaf = FakeGraph(result=_tsv(["waarde", "rol", "inwerking", "aantal"], [["Stb.1899-1", "wijziging", "", "1"]]))
    d = roep("zoek_bekendmakingen", {"bwb_id": IW, "artikel": "1"}, graph=graaf)
    assert d["resultaten"][0]["id"] == "stb-1899-1" and d["resultaten"][0]["leesbaar"] is False
    assert "Niet gevonden bij KOOP: stb-1899-1" in d["toelichting"]


def test_bij_een_bepaling_geen_andere_filters():
    d = roep("zoek_bekendmakingen", {"bwb_id": IW, "artikel": "36", "woorden": "invordering"}, graph=FakeGraph(ART36))
    assert d["reden"] == "ongeldige_argumenten" and "bijvoorbeeld" in d["melding"]


# ── Zoeken bij KOOP ────────────────────────────────────────────────────────────────────────────────────────────────

def test_de_zoekvraag_bouwt_de_tool():
    dienst = Koop()
    roep("zoek_bekendmakingen", {"publicatie": "Staatscourant", "woorden": "Leidraad Invordering", "soort": "beleidsregel",
                                  "orgaan": "Financiën", "vanaf": "2024", "volgorde": "nieuwste"}, _bron(dienst))
    cql = dienst.vragen[-1]
    assert "w.publicatienaam==Staatscourant" in cql and 'dt.title any "leidraad"' in cql
    assert 'dt.type all "beleidsregel"' in cql and 'dt.creator all "financiën"' in cql
    assert "dt.date>=2024-01-01" in cql and cql.endswith("sortBy dt.date/sort.descending dt.identifier/sort.ascending")


def test_zonder_blad_beide_bladen_en_het_kamerdossier():
    dienst = Koop()
    roep("zoek_bekendmakingen", {"dossier": "33755"}, _bron(dienst))
    cql = dienst.vragen[-1]
    assert "(w.publicatienaam==Staatsblad OR (w.publicatienaam==Staatscourant AND (" in cql
    assert 'dt.type=="beleidsregel"' in cql and 'dt.type=="Overig"' in cql, "een gerichte vraag telt ook Overig"
    assert 'w.behandeldDossier=="33755"' in dienst.vragen[-1]


@pytest.mark.parametrize("args,reden", [
    ({}, "ongeldige_argumenten"), ({"artikel": "36"}, "ongeldige_argumenten"), ({"bwb_id": "x"}, "ongeldige_argumenten"),
    ({"publicatie": "Tractatenblad"}, "ongeldige_argumenten"), ({"jaar": "10"}, "ongeldige_datum"),
    ({"vanaf": "2024-13"}, "ongeldige_datum"), ({"volgorde": "nummer"}, "ongeldige_volgorde"),
    ({"woorden": "stb-2010-176"}, "is_een_id"), ({"dossier": "abc"}, "ongeldig_dossier")])
def test_een_invoerfout_noemt_de_reden(args, reden):
    d = roep("zoek_bekendmakingen", args)
    assert d["status"] == "error" and d["reden"] == reden


# ── Lezen ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_het_inwerkingtredingsbesluit_is_te_lezen():
    d = roep("get_bekendmaking", {"id": "stb-2010-176"})
    assert d["status"] == "ok", d
    stuk = d["stuk"]
    assert stuk["label"] == "Stb. 2010, 176" and stuk["publicatie"] == "Staatsblad" and stuk["bron_hash"]
    assert "inwerkingtreding" in stuk["titel"].lower()
    teksten = " ".join(r["tekst"] for r in d["resultaten"])
    assert "in werking" in teksten, "het besluit zegt wanneer de wet in werking treedt"


def test_een_wijziging_van_de_leidraad_heeft_koppen_per_onderdeel():
    _, rijen, overgeslagen, _ = lees((FIX / "stcrt-2026-37344.xml").read_bytes())
    koppen = [r.get("kop", "") for r in rijen]
    assert "Artikel I – Wijziging › A" in koppen and "Artikel I – Wijziging › B" in koppen
    a = next(r for r in rijen if r.get("kop") == "Artikel I – Wijziging › A")
    assert a["tekst"].startswith("In artikel 1.1.5 worden"), "de wijzigingsopdracht (`wat`) is een rij"
    assert any(r["tekst"].startswith("– Bezwaarschriften") for r in rijen), "het nummer van een opsomming staat ervoor"
    assert overgeslagen.get("ondertekening"), "een ondertekening valt niet stil weg"


def test_met_een_artikel_alleen_de_onderdelen_die_het_wijzigen():
    d = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "1.1.5"})
    assert d["status"] == "ok" and d["resultaten"]
    assert {r.get("kop", "").split(" › ")[1] for r in d["resultaten"] if r.get("kop")} == {"A"}, (
        "1.1.5b (B) en 1.1.5c (C) zijn een ander artikel")
    assert "onderdeel" not in json.dumps(d["resultaten"]).replace("wijzigingsonderdeel", "")
    c = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "1.1.5c"})
    assert c["resultaten"][0]["tekst"].startswith("Artikel 1.1.5c wordt als volgt gewijzigd")
    niets = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "99.9"})
    assert niets["resultaten"] == [] and "noemt artikel 99.9" in niets["toelichting"]


def test_met_een_regeling_alleen_de_artikelen_die_haar_wijzigen():
    """Een verzamelwet lezen zonder haar door te bladeren (meting bekendmakingen B03/B16: 338–376k tokens)."""
    d = roep("get_bekendmaking", {"id": "stb-2009-610", "regeling": "Invorderingswet 1990"})
    assert d["status"] == "ok" and d["resultaten"] and d["totaal"] == 30, "30 van de 490 rijen"
    assert {r.get("kop", "").split(" › ")[0] for r in d["resultaten"] if r.get("kop")} == {"Artikel XVII"}
    assert d["resultaten"][0]["tekst"] == "De Invorderingswet 1990 wordt als volgt gewijzigd:"
    assert d["toelichting"].startswith("Alleen het artikel waarvan de aanhef Invorderingswet 1990 noemt")
    # Zonder hoofdletters vindt hij hetzelfde.
    assert roep("get_bekendmaking", {"id": "stb-2009-610", "regeling": "invorderingswet 1990"})["totaal"] == 30
    niets = roep("get_bekendmaking", {"id": "stb-2009-610", "regeling": "Wet op de omzetbelasting 1968"})
    assert niets["resultaten"] == [] and "noemt Wet op de omzetbelasting 1968" in niets["toelichting"]


def test_de_inhoud_van_een_verzamelwet_noemt_per_artikel_de_aanhef():
    """Hermeting 11 nov 2026, B16: de eerste pagina had 11 van de 30 artikelen, en een aanhef boven 160 tekens viel weg.
    Nu zegt de eerste pagina waar de hele inhoud staat, en daar staat elk artikel met het begin van zijn aanhef."""
    d = roep("get_bekendmaking", {"id": "stb-2009-610"})
    assert not d["volledig"], "de wet past niet op één pagina"
    assert len(d["inhoud"]) == 30 and "inhoud_ingekort" not in d, "alle artikelen, voor het bronvenster en de sprong"
    assert d["inhoud_zonder_begin"] and d["inhoud_openen"] == {"tool": "get_bekendmaking",
                                                              "args": {"id": "stb-2009-610", "inhoud": True}}
    alles = roep(d["inhoud_openen"]["tool"], d["inhoud_openen"]["args"])
    assert alles["status"] == "ok" and alles["volledig"] and alles["totaal"] == 30
    aanhef = {i["kop"]: i for i in alles["resultaten"]}
    assert aanhef["Artikel XVI"]["tekst"] == "De Algemene wet inzake rijksbelastingen wordt als volgt gewijzigd:"
    assert aanhef["Artikel XVII"]["tekst"] == "De Invorderingswet 1990 wordt als volgt gewijzigd:"
    vii = aanhef["Artikel VII"]
    assert len(vii["tekst"]) > 160 and vii["tekst"].startswith(
        "Aan artikel 15, eerste lid, van de Wet op belastingen van rechtsverkeer wordt"), "ook een lange aanhef, helemaal"
    _, rijen, _, _ = lees((FIX / "stb-2009-610.xml").read_bytes())
    assert all(rijen[i["offset"]]["nr"] == i["nr"] and rijen[i["offset"]]["tekst"] == i["tekst"]
               for i in alles["resultaten"] if "tekst" in i), "letterlijk de rij, met haar nr, op de offset"
    assert all(" › " not in i["kop"] for i in alles["resultaten"]), "het bovenste niveau, zoals een ingekorte inhoud"


def test_de_aanhef_op_de_inhoudpagina_is_te_citeren():
    """Controle 11 nov 2026, B16: de aanhef per artikel stond alleen in de inhoud, en het blok extern citeerde de hele
    eerste pagina. Een rij van de inhoudpagina draagt nr en tekst, dus het model wijst haar aan."""
    from agent.sjablonen import extern

    alles = roep("get_bekendmaking", {"id": "stb-2009-610", "inhoud": True})
    xvii = next(i for i in alles["resultaten"] if i["kop"] == "Artikel XVII")
    trace = [("get_bekendmaking", json.dumps(alles, ensure_ascii=False))]
    [blok] = extern.blokken([{"id": "stb-2009-610", "van_nr": xvii["nr"], "tot_nr": xvii["nr"]}], trace)
    assert [(p.kop, p.tekst) for p in blok.passages] == [("Artikel XVII", "De Invorderingswet 1990 wordt als volgt gewijzigd:")]


def test_een_gefilterde_lezing_wijst_de_rest_van_de_publicatie_aan():
    """Hermeting 11 nov 2026, B08: na de lezing met artikel las het model het hele stuk om de inwerkingtreding te vinden
    (86k tegen 24k). Nu draagt de lezing de inhoud van de hele publicatie, met de offsets voor een lezing zonder filter."""
    d = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "1.1.5"})
    assert d["status"] == "ok" and d["resultaten"] and "inhoud" not in d
    delen = {i["kop"]: i for i in d["inhoud_publicatie"]}
    ii = delen["Artikel II – Inwerkingtreding"]
    assert ii["begint"].startswith("Dit besluit treedt op 1 januari 2027 in werking")
    vanaf = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "offset": ii["offset"]})
    assert vanaf["resultaten"][0]["tekst"] == ii["begint"], "de offset wijst in de lezing zonder filter"
    assert "inhoud_publicatie" in d["toelichting"]
    r = roep("get_bekendmaking", {"id": "stb-2009-610", "regeling": "Invorderingswet 1990"})
    assert r["inhoud_publicatie"] and r["inhoud_openen"]["args"] == {"id": "stb-2009-610", "inhoud": True}
    niets = roep("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "99.9"})
    assert niets["resultaten"] == [] and niets["inhoud_publicatie"] and niets["stuk"].get("leesbaar") is not False


@pytest.mark.parametrize("tekst,artikel,ja", [
    ("In artikel 1.1.5 worden …", "1.1.5", True), ("In artikel 1.1.5b. wordt …", "1.1.5", False),
    ("Artikel 25 wordt als volgt gewijzigd:", "25", True), ("In artikel 25a vervalt …", "25", False),
    ("In de artikelen 24 en 25 wordt …", "25", True), ("Artikel 25.1 komt te luiden:", "25", False)])
def test_noemt_artikel(tekst, artikel, ja):
    assert b._noemt_artikel(tekst, artikel) is ja


def test_alleen_een_pdf_is_een_fout_met_de_metadata():
    d = roep("get_bekendmaking", {"id": "stb-1990-222"})
    assert d["status"] == "error" and d["reden"] == "alleen_pdf"
    assert d["stuk"]["id"] == "stb-1990-222" and d["stuk"]["leesbaar"] is False and d["stuk"]["datum"].startswith("1990")
    assert "alleen als PDF" in d["melding"] and "https://zoek.officielebekendmakingen.nl/stb-1990-222" in d["melding"]


def test_een_onbekend_id_en_een_storing():
    assert roep("get_bekendmaking", {"id": "stb-2099-1"})["reden"] == "niet_gevonden"
    assert roep("get_bekendmaking", {"id": "stb-2010-176"}, _bron(Koop(weg=True)))["reden"] == "bron_onbereikbaar"
    assert roep("get_bekendmaking", {"id": "kst-33755-3"})["reden"] == "ongeldig_id"


def test_de_cache_deelt_de_versiecontrole_met_kamerstukken():
    dienst = Koop()
    bron = _bron(dienst)
    eerste = bron.document("stb-2010-176")
    assert bron.document("stb-2010-176") is eerste and dienst.vragen.count("stb-2010-176.xml") == 1
    with pytest.raises(KoopFout):
        _bron(Koop(weg=True)).document("stb-2010-176")


def test_uit_is_niet_aangeboden():
    d = json.loads(tools.dispatch("get_bekendmaking", None, {"id": "stb-2010-176"}, Settings(),
                                  bekendmakingen=_bron()))
    assert d["reden"] == "connector_uit"
    assert BEKENDMAKINGEN.naam == b.CONNECTOR and BEKENDMAKINGEN.tools == {t["name"] for t in b.BEKENDMAKING_TOOLS}


def test_geldigheid_noemt_het_id_van_de_publicatie():
    """De BWB-vorm "Stb.2009-610" leest de connector niet; `geldigheid` noemt daarom ook stb-2009-610."""
    rij = _tsv(["bron", "inwerkingtredingsbron", "bepalingInwerking"],
               [["Stb.2009-610", "Stb.2010-176", '"2010-07-04"^^<http://www.w3.org/2001/XMLSchema#date>']])
    d = json.loads(tools.dispatch("geldigheid", FakeGraph(result=rij), {"bwb_id": IW, "artikel": "36"}, AAN))
    assert d["resultaten"][0]["bekendmakingen"] == ["stb-2009-610", "stb-2010-176"]


def test_een_inwerkingtredingsbesluit_staat_in_de_titel():
    dienst = Koop()
    roep("zoek_bekendmakingen", {"publicatie": "Staatsblad", "soort": "inwerkingtredingsbesluit", "volgorde": "nieuwste"},
         _bron(dienst))
    assert 'dt.title all "inwerkingtreding"' in dienst.vragen[-1] and "dt.type" not in dienst.vragen[-1]


@pytest.mark.parametrize("vraag,args", [
    ("Geef de 5 nieuwste beleidsregels in de Staatscourant",
     {"volgorde": "nieuwste", "aantal": 5, "soort": "beleidsregel", "publicatie": "Staatscourant"}),
    ("de laatste 3 inwerkingtredingsbesluiten in het Staatsblad",
     {"volgorde": "nieuwste", "aantal": 3, "soort": "inwerkingtredingsbesluit", "publicatie": "Staatsblad"}),
    ("Welke bekendmakingen horen bij artikel 36 van de Invorderingswet 1990?", {"bwb_id": IW, "artikel": "36"}),
])
def test_een_lijstvraag_leest_de_code(vraag, args):
    from agent.bron_lijst import lees as lijst

    def regelingen(t):
        return [(IW, {"Invorderingswet 1990"})] if "Invorderingswet" in t else []
    uit = lijst(vraag, frozenset({"bekendmakingen"}), regelingen)
    assert uit is not None and uit.connector == "bekendmakingen" and uit.args == args


def _stream(vraag, monkeypatch, llm):
    import asyncio

    from agent.agent import answer_stream
    from fakes import FakeGraph, make_settings

    monkeypatch.setattr(tools.CONNECTORMODULES["bekendmakingen"], "_bron", _bron())

    async def verzamel():
        return [e async for e in answer_stream(vraag, settings=make_settings(connector_bekendmakingen=True), llm=llm,
                                               graph=FakeGraph(result=""),
                                               bronnen=["bekendmakingen"])]
    return asyncio.run(verzamel())


def _gelezen(llm):
    return [(b["name"], b["input"]) for m in llm.calls[-1]["messages"]
            for b in (m["content"] if isinstance(m["content"], list) else []) if b.get("type") == "tool_use"]


def test_de_voorlezing_neemt_het_genoemde_artikel_mee(monkeypatch):
    """Meting bekendmakingen B08: de code las het stuk zonder het artikel uit de vraag, dus bij een artikel achteraan
    moest het model verder lezen."""
    from fakes import FakeLLM, response, text_block

    llm = FakeLLM([response([text_block("duiding")], "end_turn"),
                   response([text_block("Onderdeel A voegt twee gedachtestreepjes in.")], "end_turn")])
    _stream("Wat veranderde stcrt-2026-37344 aan artikel 1.1.5 van de Leidraad Invordering 2008?", monkeypatch, llm)
    assert _gelezen(llm) == [("get_bekendmaking", {"id": "stcrt-2026-37344", "artikel": "1.1.5"})]


def test_raakt_het_artikel_geen_onderdeel_dan_het_hele_stuk(monkeypatch):
    from fakes import FakeLLM, response, text_block

    llm = FakeLLM([response([text_block("duiding")], "end_turn"),
                   response([text_block("Het besluit zet de wijziging in werking.")], "end_turn")])
    _stream("Wat staat er in Stb. 2010, 176 over artikel 36?", monkeypatch, llm)
    assert _gelezen(llm) == [("get_bekendmaking", {"id": "stb-2010-176"})], "één lezing in de historie, zonder filter"


def test_een_stuk_waaruit_extern_citeert_staat_in_de_bronnen():
    """Meting bekendmakingen B04: met doelen in het sjabloon hield de bronnenlijst alleen de doelen, en het gelezen
    inwerkingtredingsbesluit viel weg."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from agent.nodes.antwoord import finalize_node
    from fakes import FakeGraph, make_settings

    gelezen = json.dumps(roep("get_bekendmaking", {"id": "stb-2010-176"}), ensure_ascii=False)
    antwoord = {"sjabloon": "duiding", "versie": 1,
                "doelen": [{"iri": "urn:bwb:BWBR0004770:artikel:36:lid:2", "label": "Artikel 36, lid 2"}],
                "blokken": [{"soort": "extern", "door": "bron", "brontype": "bekendmaking", "id": "stb-2010-176",
                             "label": "Stb. 2010, 176", "passages": []}]}
    state = {"answer": "De datum staat in Stb. 2010, 176.", "antwoord": antwoord, "question": "Sinds wanneer?",
             "source_trace": [("get_bekendmaking", gelezen)]}
    b = SimpleNamespace(graph=FakeGraph(result=""), settings=make_settings(connector_bekendmakingen=True))
    with patch("agent.nodes.antwoord.get_stream_writer", return_value=lambda _: None):
        uit = finalize_node(b, state)
    assert "stb-2010-176" in [s["uri"] for s in uit["sources"]]


def test_het_spoor_toont_de_filters_van_elke_connector():
    """Bevinding 6 van de meting: alleen `tekst` en `offset` stonden in het `tool_execution`-event."""
    from agent.tool_execution import FILTERS

    for c in bm.CONNECTORS.values():
        for veld in c.metadata:
            assert set(veld.filters) - {"bwb_id", "artikel", "id"} <= FILTERS, (c.naam, veld.sleutel)
    assert {"publicatie", "soort", "woorden", "vanaf", "tot", "orgaan", "volgorde", "regeling"} <= FILTERS
    # Elk argument van een connectortool staat in het spoor, behalve wat in `doel` staat (controle 11 nov 2026: `inhoud`
    # ontbrak, en dan was niet te zien dat Lex de inhoudpagina las).
    for c in bm.CONNECTORS.values():
        for naam in c.tools:
            schema = next(t for t in tools.TOOLS if t["name"] == naam)["input_schema"]
            assert set(schema["properties"]) - {"id", "bwb_id", "artikel"} <= FILTERS, naam


@pytest.mark.parametrize("versie,label", [("Herdruk", "Stb. 2010, 185 (herdruk)"), ("n1", "Stb. 2010, 185 (versie n1)"),
                                          ("Verbeterblad n1", "Stb. 2010, 185 (verbeterblad n1)"), ("", "Stb. 2010, 185")])
def test_het_label_noemt_de_versie_van_koop(versie, label):
    from types import SimpleNamespace

    from agent.tools.bekendmaking_tools import _vp, label_van

    rec = SimpleNamespace(publicatienaam="Staatsblad", jaargang="2010", publicatienummer="185", versie=versie)
    assert label_van(rec, _vp("stb-2010-185-n1")) == label


def test_de_bron_draagt_het_label_van_het_gelezen_stuk():
    from agent.provenance import collect_sources

    tekst = json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [],
                        "stuk": {"id": "stb-2010-185-n1", "label": "Stb. 2010, 185 (herdruk)"}})
    assert [s.label for s in collect_sources([("get_bekendmaking", tekst)])] == ["Stb. 2010, 185 (herdruk)"]
