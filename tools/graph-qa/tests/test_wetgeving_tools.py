"""De bronconnector Wetgeving buiten de kennisgraaf (ADR-013, fase 1e), tegen opgenomen antwoorden van overheid.nl.

De opnames in `tests/fixtures/bwb_live/` zijn echte antwoorden van de zoekdienst van de BWB en echte toestanden uit het
repository van KOOP (opgehaald op 11 nov 2026; wettekst is vrij van auteursrecht, Auteurswet art. 11, en de BWB-data
CC0). Per verzoek één bestand, met een index op het verzoek. Opnieuw opnemen: `WETGEVING_OPNEMEN=1 uv run pytest
tests/test_wetgeving_tools.py`; zonder die vlag faalt een verzoek dat niet is opgenomen. Wat de echte dienst nu doet,
toetst `test_wetgeving_live_live.py`.

Vandaag staat vast op `VANDAAG`, zodat de toestand op de dag van de opname gekozen wordt.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from agent import provenance, tools
from agent.adapters import sru_bwb
from agent.adapters.sru_bwb import BwbFout, SruBwb, Toestand, kies_toestand, lees_records
from agent.config import Settings
from agent.tools import wetgeving_tools as w
from bronmodel.extern import bwbt_delen, externe_vindplaats

from fakes import FakeGraph

FIX = Path(__file__).parent / "fixtures" / "bwb_live"
INDEX = FIX / "index.json"
OPNEMEN = os.environ.get("WETGEVING_OPNEMEN") == "1"
VANDAAG = "2026-11-11"
AAN = Settings(connector_wetgeving_live=True)
PW, IW = "BWBR0015703", "BWBR0004770"


def _sleutel(r: httpx.Request) -> str:
    if r.url.host == sru_bwb.REPOSITORY_HOST:
        return r.url.path
    q = parse_qs(urlparse(str(r.url)).query)
    return " | ".join(f"{k}={q[k][0]}" for k in ("query", "startRecord", "maximumRecords") if k in q)


class Dienst:
    """De zoekdienst en het repository over HTTP: speelt de opnames af, of neemt op met `WETGEVING_OPNEMEN=1`."""

    def __init__(self, *, weg: bool = False) -> None:
        self.weg = weg
        self.vragen: list[str] = []
        self.index: dict[str, dict] = json.loads(INDEX.read_text()) if INDEX.exists() else {}
        self._echt = httpx.Client(timeout=60) if OPNEMEN else None

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.weg:
            raise httpx.ConnectError("weg", request=r)
        sleutel = _sleutel(r)
        self.vragen.append(sleutel)
        if OPNEMEN and sleutel not in self.index:
            echt = self._echt.get(str(r.url))
            naam = hashlib.sha1(sleutel.encode()).hexdigest()[:16] + ".xml.gz"
            FIX.mkdir(parents=True, exist_ok=True)
            (FIX / naam).write_bytes(gzip.compress(echt.content, mtime=0))
            self.index[sleutel] = {"bestand": naam, "status": echt.status_code}
            INDEX.write_text(json.dumps(self.index, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
        if sleutel not in self.index:
            pytest.fail(f"niet opgenomen: {sleutel} (neem op met WETGEVING_OPNEMEN=1)")
        plek = self.index[sleutel]
        return httpx.Response(plek["status"], content=gzip.decompress((FIX / plek["bestand"]).read_bytes()))


def _bron(dienst: Dienst | None = None) -> SruBwb:
    return SruBwb(client=httpx.Client(transport=httpx.MockTransport(dienst or Dienst())), slaap=lambda _s: None,
                  vandaag=lambda: VANDAAG)


def _graaf(in_graaf: dict[str, tuple[str, str]] | None = None, *, weg: bool = False) -> FakeGraph:
    """Een graaf met de regelingen die erin staan: standaard de Iw 1990 met de toestand van acceptatie (11 nov 2026)."""
    staat = {IW: ("2026-10-01", "9999-12-31")} if in_graaf is None else in_graaf

    def antwoord(q: str) -> str:
        if weg:
            raise RuntimeError("Repository inning doesn't exist")
        rijen = [f"<urn:bwb:{b}>\t\"{v}\"^^<http://www.w3.org/2001/XMLSchema#date>\t"
                 f"\"{t}\"^^<http://www.w3.org/2001/XMLSchema#date>" for b, (v, t) in staat.items() if f"urn:bwb:{b}>" in q]
        return json.dumps("?r\t?van\t?tot\n" + "".join(r + "\n" for r in rijen))
    return FakeGraph(results=antwoord)


@pytest.fixture(autouse=True)
def _vast(monkeypatch):
    monkeypatch.setattr(w, "_vandaag", lambda: VANDAAG)
    w._graaf_stand.clear()
    yield
    w._graaf_stand.clear()


def _roep(naam: str, args: dict, *, graaf: FakeGraph | None = None, bron: SruBwb | None = None) -> dict:
    uit = tools.dispatch(naam, graaf if graaf is not None else _graaf(), args, AAN, wetgeving_live=bron or _bron())
    return json.loads(uit)


# --- de adapter -------------------------------------------------------------------------------------------------------

def _t(versie: str, van: str, tot: str = "9999-12-31", zicht: str = "") -> Toestand:
    return Toestand(PW, "Participatiewet", "wet", van, tot, zicht or van, "9999-12-31",
                    f"https://{sru_bwb.REPOSITORY_HOST}/bwb/{PW}/{versie}/xml/{PW}_{versie}.xml")


def test_twee_toestanden_op_een_datum_de_nieuwste_zichtbare_wint():
    rijen = [_t("2015-01-01_0", "2015-01-01", "2015-01-31", "2015-01-01"),
             _t("2015-01-01_1", "2015-01-01", "2015-01-31", "2015-02-10")]
    assert kies_toestand(rijen, "2015-01-15", VANDAAG).versie == "2015-01-01_1"
    # Een zichtbaarheid die nog moet beginnen, telt niet zolang er een andere is.
    later = [*rijen, _t("2015-01-01_2", "2015-01-01", "2015-01-31", "2099-01-01")]
    assert kies_toestand(later, "2015-01-15", VANDAAG).versie == "2015-01-01_1"
    assert kies_toestand(rijen, "2016-01-01", VANDAAG) is None


def test_een_diagnose_van_de_zoekdienst_is_een_fout_geen_lege_lijst():
    diag = (b'<diagnostics xmlns="http://docs.oasis-open.org/ns/search-ws/sruResponse"><diagnostic xmlns="http://docs.'
            b'oasis-open.org/ns/search-ws/diagnostic"><uri>info:srw/diagnostic/1/16</uri><details>overheidbwb.citeertitel'
            b'</details><message>Unsupported index</message></diagnostic></diagnostics>')
    with pytest.raises(BwbFout) as e:
        lees_records(diag)
    assert e.value.code == "geweigerd" and "Unsupported index" in str(e.value)


def test_een_toestand_op_een_andere_host_wordt_geweigerd():
    t = _t("2026-07-01_0", "2026-07-01")
    vreemd = Toestand(**{**t.__dict__, "xml_url": "https://elders.example/bwb.xml"})
    with pytest.raises(BwbFout) as e:
        _bron().lees(vreemd)
    assert e.value.code == "geweigerd"


def test_de_toestand_wordt_gelezen_met_de_lezer_van_de_importer_en_volledig():
    bron = _bron()
    g = bron.lees(bron.toestand_op(PW))
    assert g.toestand.versie == "2026-07-01_0" and g.wet.bwb_id == PW and g.wet.citeertitel == "Participatiewet"
    assert g.dekking >= 0.995 and g.xsd_geldig and g.hash


def test_een_onvolledige_lezing_wordt_geweigerd(monkeypatch):
    # Onder de drempel is de toestand als geheel niet te gebruiken (opbouw, zoeken); een artikel alleen als het zelf
    # volledig gelezen is (iteratie ronde 1, I03; `test_wetgeving_live_routes.py`).
    monkeypatch.setattr(sru_bwb, "model_tekens", lambda wet: 10)
    monkeypatch.setattr(sru_bwb, "model_tekens_van", lambda artikel: 0)
    bron = _bron()
    g = bron.lees(bron.toestand_op(PW))
    assert not g.volledig and g.per_artikel
    with pytest.raises(BwbFout) as e:
        g.eis_volledig()
    assert e.value.code == "onvolledig"
    from bronmodel.bwb.boom import artikelen
    artikel = next(b for _, b in artikelen(g.wet))
    assert not g.artikel_volledig(artikel)


def test_de_cache_leest_een_toestand_een_keer_en_blijft_binnen_zijn_grens(monkeypatch):
    dienst = Dienst()
    bron = _bron(dienst)
    t = bron.toestand_op(PW)
    bron.lees(t)
    bron.lees(t)
    assert sum(1 for v in dienst.vragen if v.endswith(".xml")) == 1
    monkeypatch.setattr(sru_bwb, "MAX_CACHE_BYTES", 1)
    bron.lees(bron.toestand_op(PW, "2015-01-15"))
    assert len(bron._gelezen) == 1, "de oudste valt eruit, de laatste blijft"


def test_een_storing_is_een_fout_met_reden():
    uit = _roep("zoek_regelingen", {"naam": "Participatiewet"}, bron=_bron(Dienst(weg=True)))
    assert uit["status"] == "error" and uit["reden"] == "bron_onbereikbaar"


# --- zoek_regelingen --------------------------------------------------------------------------------------------------

def test_op_naam_staat_de_regeling_zelf_bovenaan_ook_tussen_wijzigingswetten():
    uit = _roep("zoek_regelingen", {"naam": "Participatiewet", "aantal": 25})
    assert uit["status"] == "ok"
    eerste = uit["resultaten"][0]
    assert eerste["nummer"] == PW and eerste["titel"] == "Participatiewet" and eerste["in_graaf"] is False
    assert eerste["id"] == f"bwbt:{PW}:2026-07-01_0" and eerste["tekststand"] == "huidige tekst"
    assert [r["titel"] for r in uit["resultaten"][:2]] == ["Participatiewet", "Participatiewet in balans"]


def test_een_regeling_over_een_andere_komt_na_de_rest():
    def t(titel: str, soort: str = "wet") -> Toestand:
        return Toestand("BWBR0000001", titel, soort, "2020-01-01", "9999-12-31", "2020-01-01", "9999-12-31", "x")
    rijen = [t("Wijzigingswet Participatiewet"), t("Invoeringswet Participatiewet"), t("Besluit Participatiewet", "AMvB"),
             t("Participatiewet")]
    gerangschikt = sorted(rijen, key=lambda r: w._rang(r, "Participatiewet", set()))
    assert [r.titel for r in gerangschikt[:2]] == ["Participatiewet", "Besluit Participatiewet"]
    assert {r.titel for r in gerangschikt[2:]} == {"Invoeringswet Participatiewet", "Wijzigingswet Participatiewet"}


def test_een_dubbelzinnige_afkorting_laat_kiezen():
    uit = _roep("zoek_regelingen", {"naam": "Pw"})
    titels = {r["titel"] for r in uit["resultaten"]}
    assert {"Participatiewet", "Pensioenwet"} <= titels
    assert "kies niet zelf" in uit["toelichting"]


def test_een_regeling_in_de_graaf_wijst_naar_de_graaftools():
    uit = _roep("zoek_regelingen", {"bwb_id": IW})
    rij = uit["resultaten"][0]
    assert rij["in_graaf"] is True and rij["nummer"] == IW and "get_artikel" in uit["toelichting"]


def test_niets_gevonden_is_een_leemte_geen_bewijs():
    uit = _roep("zoek_regelingen", {"naam": "Wet op de robotbelasting"})
    assert uit["status"] == "ok" and not uit.get("resultaten") and "bewijst niet" in uit["toelichting"]


def test_zonder_zoekvraag_een_invoerfout_met_voorbeeld():
    uit = _roep("zoek_regelingen", {})
    assert uit["reden"] == "ongeldige_argumenten" and "bijvoorbeeld" in uit["melding"]


# --- de grens met de kennisgraaf --------------------------------------------------------------------------------------

def test_de_huidige_tekst_van_een_regeling_in_de_graaf_komt_uit_de_graaf():
    dienst = Dienst()
    uit = _roep("get_wettekst", {"bwb_id": IW, "artikel": "9"}, bron=_bron(dienst))
    assert uit["status"] == "error" and uit["reden"] == "in_graaf"
    assert uit["graaftool"] == {"tool": "get_artikel", "args": {"bwb_id": IW, "artikel": "9"}}
    assert dienst.vragen == [], "geen verzoek aan overheid.nl als de graaf de tekst heeft"


def test_een_graaf_die_niet_antwoordt_weigert_ook():
    uit = _roep("get_wettekst", {"bwb_id": PW, "artikel": "31"}, graaf=_graaf(weg=True))
    assert uit["reden"] == "graaf_onbereikbaar"


def test_een_eerdere_tekst_van_een_regeling_in_de_graaf_komt_live():
    uit = _roep("get_wettekst", {"bwb_id": IW, "artikel": "9", "peildatum": "2020-01-01"})
    assert uit["status"] == "ok", uit
    stuk = uit["stuk"]
    assert stuk["tekststand"] == "eerdere tekst" and stuk["tekst_vanaf"] <= "2020-01-01" <= stuk["tekst_tot"]
    assert stuk["id"].startswith(f"bwbt:{IW}:") and stuk["id"].endswith(":artikel:9")


# --- get_wettekst -----------------------------------------------------------------------------------------------------

def test_een_artikel_per_lid_en_onderdeel_met_jci_en_eigen_id():
    uit = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8"})
    assert uit["status"] == "ok"
    stuk = uit["stuk"]
    assert stuk["id"] == f"bwbt:{PW}:2026-07-01_0:artikel:8" and stuk["tekststand"] == "huidige tekst"
    assert stuk["label"].startswith("Participatiewet, Artikel 8") and stuk["in_graaf"] is False
    rijen = uit["resultaten"]
    assert rijen[0]["tekst"] == "De gemeenteraad stelt bij verordening regels met betrekking tot:"
    assert rijen[1]["nummer"] == "a." and "&lid=1&o=a" in rijen[1]["jci"]
    assert "niet in de kennisgraaf" in uit["toelichting"]
    vp = externe_vindplaats(stuk["id"])
    assert vp is not None and vp.brontype == "wettekst_live"


def test_het_id_uit_de_opbouw_leest_hetzelfde_als_bwb_id_en_artikel():
    via_id = _roep("get_wettekst", {"id": f"bwbt:{PW}:2026-07-01_0:artikel:8"})
    via_nr = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8"})
    assert via_id["stuk"]["id"] == via_nr["stuk"]["id"] and via_id["resultaten"] == via_nr["resultaten"]


def test_een_lid_alleen_dat_lid():
    uit = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8", "lid": "2"})
    assert uit["resultaten"] and all("lid 2" in r["kop"] for r in uit["resultaten"])


def test_vervallen_en_nog_niet_in_werking_staan_erbij():
    vervallen = _roep("get_wettekst", {"bwb_id": PW, "artikel": "12"})
    assert vervallen["stuk"]["status"].startswith("vervallen") and "geen tekst meer" in vervallen["toelichting"]
    nog_niet = _roep("get_wettekst", {"bwb_id": PW, "artikel": "24a"})
    assert nog_niet["stuk"]["status"] == "nog niet in werking; treedt in werking op 2027-01-01"
    assert "niet als geldend recht" in nog_niet["toelichting"]


def test_een_historische_toestand_op_peildatum():
    uit = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8", "peildatum": "2015-01-15"})
    assert uit["stuk"]["versie"] == "2015-01-01_1" and uit["stuk"]["tekststand"] == "eerdere tekst"


def test_een_artikel_dat_er_niet_is_zegt_dat_en_wijst_de_weg():
    uit = _roep("get_wettekst", {"bwb_id": PW, "artikel": "999"})
    assert uit["reden"] == "niet_gevonden" and "zoek_artikelen" in uit["melding"]


def test_ongeldige_invoer_noemt_een_voorbeeld():
    for args in ({"id": "kst-1-2"}, {"bwb_id": "Participatiewet"}, {"bwb_id": PW}):
        uit = _roep("get_wettekst", args)
        assert uit["status"] == "error" and "bijvoorbeeld" in uit["melding"], args


# --- zoek_artikelen ---------------------------------------------------------------------------------------------------

def test_de_opbouw_in_documentvolgorde_met_koppen():
    uit = _roep("zoek_artikelen", {"bwb_id": PW})
    eerste = uit["resultaten"][0]
    assert eerste["label"] == "Artikel 1" and eerste["reeks"][0] == "Hoofdstuk 1 – Algemeen"
    assert eerste["id"] == f"bwbt:{PW}:2026-07-01_0:artikel:1"


def test_zoeken_op_woorden_in_de_tekst():
    uit = _roep("zoek_artikelen", {"bwb_id": PW, "woorden": '"kostendelende medebewoner"'})
    labels = [r["label"] for r in uit["resultaten"]]
    assert labels == ["Artikel 19a", "Artikel 20", "Artikel 21", "Artikel 22", "Artikel 22a", "Artikel 24",
                      "Artikel 53a"]


def test_de_lijst_onder_het_antwoord_draagt_zoekvraag_totaal_en_links():
    """Ronde 2 (I01, I14, I30): de zoekvraag was een zin, dus het blok `stukken` toonde geen zoekvraag en geen totaal,
    en de rijen hadden geen link. Nu dezelfde vorm als de andere connectors."""
    from agent.sjablonen.extern import lijsten

    woorden = _roep("zoek_artikelen", {"bwb_id": PW, "woorden": "kostendelende medebewoner"})
    assert woorden["zoekvraag"] == {"tekst": "kostendelende medebewoner"}
    assert all(r["link"].startswith("https://wetten.overheid.nl/jci1.3:c:BWBR0015703") for r in woorden["resultaten"])
    trace = [("zoek_artikelen", json.dumps(woorden))]
    blok = lijsten([r["id"] for r in woorden["resultaten"]], trace)[0]
    assert blok.totaal == 7
    assert blok.zoekvraag.startswith("Gezocht op „kostendelende medebewoner” in de tekst. In Participatiewet")

    alles = _roep("zoek_artikelen", {"bwb_id": PW})
    blok = lijsten([r["id"] for r in alles["resultaten"][:3]], [("zoek_artikelen", json.dumps(alles))])[0]
    assert blok.totaal == alles["totaal"] and blok.totaal > 100
    assert blok.zoekvraag.startswith("De artikelen van Participatiewet")

    regelingen = _roep("zoek_regelingen", {"naam": "Participatiewet", "peildatum": "2015-01-15"})
    assert regelingen["zoekvraag"] == {"naam": "Participatiewet", "peildatum": "2015-01-15", "volgorde": "relevantie"}
    assert regelingen["resultaten"][0]["link"].startswith(f"https://wetten.overheid.nl/{PW}/")
    blok = lijsten([regelingen["resultaten"][0]["id"]], [("zoek_regelingen", json.dumps(regelingen))])[0]
    assert "„Participatiewet” in de titel" in blok.zoekvraag and "peildatum 15 januari 2015" in blok.zoekvraag
    assert "vanaf" not in blok.zoekvraag


def test_een_gelezen_lid_is_een_eigen_stuk():
    """Ronde 2, I28: twee apart gelezen leden van één artikel hadden hetzelfde id en allebei nr 1, dus het antwoord kon
    lid 2 niet aanwijzen. Nu heeft een lid (en een onderdeel daarin) een eigen id, label en link, zoals in de graaf."""
    from agent.sjablonen.extern import heel_stuk

    een = _roep("get_wettekst", {"bwb_id": PW, "artikel": "31", "lid": "1"})
    twee = _roep("get_wettekst", {"bwb_id": PW, "artikel": "31", "lid": "2"})
    assert een["stuk"]["id"] == f"bwbt:{PW}:2026-07-01_0:artikel:31:lid:1"
    assert twee["stuk"]["id"] == f"bwbt:{PW}:2026-07-01_0:artikel:31:lid:2"
    assert twee["stuk"]["label"].startswith("Participatiewet, Artikel 31, lid 2 (")
    assert "&lid=2" in twee["stuk"]["link"]
    # Op het id gelezen geeft hetzelfde stuk.
    weer = _roep("get_wettekst", {"id": twee["stuk"]["id"]})
    assert weer["stuk"]["id"] == twee["stuk"]["id"] and weer["resultaten"][0]["tekst"] == twee["resultaten"][0]["tekst"]
    trace = [("get_wettekst", json.dumps(een)), ("get_wettekst", json.dumps(twee))]
    assert heel_stuk(trace, een["stuk"]["id"]).passages[0].tekst.startswith("Tot de middelen worden alle")
    assert heel_stuk(trace, twee["stuk"]["id"]).passages[0].tekst.startswith("Niet tot de middelen")
    c = _roep("get_wettekst", {"bwb_id": PW, "artikel": "31", "lid": "2", "onderdeel": "c"})
    assert c["stuk"]["id"].endswith(":artikel:31:lid:2:o:c") and "onderdeel c" in c["stuk"]["label"]
    # Het hele artikel blijft het artikel.
    assert _roep("get_wettekst", {"bwb_id": PW, "artikel": "31"})["stuk"]["id"].endswith(":artikel:31")


def test_het_label_zegt_dat_het_een_eerdere_tekst_is():
    """Ronde 2, I15/I16: 'eerdere tekst' stond alleen in de metadata; het label in het antwoord zei 'tekst geldig vanaf
    2015-01-01', alsof het de huidige was."""
    oud = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8", "peildatum": "2015-01-15"})["stuk"]
    assert oud["label"] == "Participatiewet, Artikel 8 (eerdere tekst, geldig van 2015-01-01 tot en met 2015-01-31)"
    nu = _roep("get_wettekst", {"bwb_id": PW, "artikel": "8"})["stuk"]
    assert nu["label"] == "Participatiewet, Artikel 8 (tekst geldig vanaf 2026-07-01)"


# --- herkomst: nooit een graafbron ------------------------------------------------------------------------------------

def test_de_bronnenlijst_kent_alleen_het_gelezen_stuk_geen_graafbron():
    lezing = tools.dispatch("get_wettekst", _graaf(), {"bwb_id": PW, "artikel": "8"}, AAN, wetgeving_live=_bron())
    zoek = tools.dispatch("zoek_regelingen", _graaf(), {"naam": "Participatiewet"}, AAN, wetgeving_live=_bron())
    bronnen = provenance.collect_sources([("zoek_regelingen", zoek), ("get_wettekst", lezing)])
    assert [(b.uri, b.brontype) for b in bronnen] == [(f"bwbt:{PW}:2026-07-01_0:artikel:8", "wettekst_live")]


def test_het_id_draagt_de_staart_van_de_graaf_iri():
    assert bwbt_delen(f"bwbt:{PW}:2026-07-01_0:artikel:8:lid:1") == (PW, "2026-07-01_0", (("artikel", "8"), ("lid", "1")))


def test_een_beleidsregel_met_paragrafen_is_te_lezen():
    """I12 (iteratie 11 nov 2026): het BBBB deelt zijn tekst in paragrafen met een `<structuurtekst>`, zonder artikelen.
    De lezer las er niets van (dekking 0%). Nu is elke paragraaf een divisie met haar nummer, titel en plek."""
    bbbb = "BWBR0038145"
    rij = _roep("zoek_artikelen", {"bwb_id": bbbb})["resultaten"][0]
    assert (rij["label"], rij["titel"], rij["reeks"]) == ("§ 1", "Reikwijdte", ["Hoofdstuk 1 – Algemene bepalingen"])
    r = _roep("get_wettekst", {"bwb_id": bbbb, "artikel": "1"})
    assert r["status"] == "ok" and r["stuk"]["label"].startswith("Besluit Bestuurlijke Boeten Belastingdienst, § 1")
    assert r["resultaten"][0]["kop"] == "Hoofdstuk 1 – Algemene bepalingen › § 1 – Reikwijdte"
    assert r["resultaten"][0]["tekst"].startswith("In dit besluit is het beleid neergelegd")


def test_een_bwb_id_zonder_toestand_op_de_peildatum_noemt_zijn_regeling():
    """Ronde 3, I20: het model raadde BWBR0002471 voor de Wet op de inkomstenbelasting 1964; de fout noemde alleen de
    periode, niet dat dat id de Wet op de loonbelasting 1964 is."""
    uit = _roep("get_wettekst", {"bwb_id": "BWBR0002471", "artikel": "1", "peildatum": "1995-01-01"})
    assert uit["status"] == "error" and uit["reden"] == "niet_gevonden"
    assert "Wet op de loonbelasting 1964" in json.dumps(uit, ensure_ascii=False)
