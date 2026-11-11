"""De bronconnector Rechtspraak (ADR-013) tegen een nep: transport, de versies van een artikel en de twee tools.

Wat de echte diensten doen, toetst `test_rechtspraak_live.py` (bronnenwacht). Hier staat wat de connector zelf moet
doen met wat ze teruggeven, met de gevallen uit de spike van 10 nov 2026: links die aan versies hangen, een XML die
halverwege afbreekt, de Awb die alleen via de jci werkt, een plafond dat zichtbaar is in plaats van stil.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx
import pytest

from agent import tools
from agent.adapters import lido_rechtspraak as L
from agent.adapters.lido_rechtspraak import Koppelingen, Link, LidoRechtspraak, RechtspraakFout
from agent.tools import rechtspraak_tools as R
from agent.tools.stuk_tekst import aangevuld
from tests.fakes import FakeGraph, make_settings

AAN = make_settings(connector_rechtspraak=True)
IW = "BWBR0004770"
V = "http://linkeddata.overheid.nl/terms/bwb/id/BWBR0004770/2910654"
V_NU, V_2016, V_2015 = f"{V}/2026-07-01/2026-07-01", f"{V}/2016-05-01/2016-05-01", f"{V}/2015-01-01/2013-01-01"
J = "http://linkeddata.overheid.nl/terms/jurisprudentie/id/"


def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


ARTIKEL = _tsv(["node", "jci", "labelId", "label", "soort"],
               [["urn:bwb:BWBR0004770:artikel:9", "jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&z=2026-10-01&g=2026-10-01",
                 "2910654", "Artikel 9", "urn:bwb-ns:Artikel"]])
DIVISIE = _tsv(["node", "jci", "labelId", "label", "soort"],
               [["urn:bwb:BWBR0024096:id:9.4", "", "9596314", "9.4", "urn:bwb-ns:Divisie"]])


# --- transport ----------------------------------------------------------------------------------------------------

def _get_links(versie: str, eclis: list[tuple[str, str]], *, wetten: int = 0) -> str:
    """Eén pagina van `get-links` als XML: de versie, dan per ECLI een subject met titel; `wetten` extra items."""
    ins = "".join(f'<subject-ref idref="{J}{e}" groep="Jurisprudentie" label="Door computer herkende referentie"/>'
                  for e, _ in eclis)
    items = "".join(f'<subject id="{J}{e}"><dcterms:title xmlns:dcterms="http://purl.org/dc/terms/">{t}</dcterms:title>'
                    f'</subject>' for e, t in eclis)
    items += "".join(f'<subject id="{V}x{i}"/>' for i in range(wetten))
    return (f'<lido service="get-links"><facetten><facet name="obj_type"><int name="Jurisprudentie">{len(eclis)}</int>'
            f'</facet></facetten><subject id="{versie}"><inkomende-links>{ins}</inkomende-links></subject>{items}</lido>')


def _rdf(versie: str, eclis: list[str]) -> str:
    acts = "".join(
        f'<rdf:Description rdf:about="x{i}"><rdf:type rdf:resource="http://linkeddata.overheid.nl/terms/LinkAct"/>'
        f'<rl:linktVan rdf:resource="{J}{e}"/><rl:linktNaar rdf:resource="{versie}"/>'
        f'<rl:heeftLinktype rdf:resource="http://linkeddata.overheid.nl/terms/linktype/id/lx-referentie"/>'
        f'</rdf:Description>' for i, e in enumerate(eclis))
    return ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            f'xmlns:rl="http://linkeddata.overheid.nl/terms/">{acts}</rdf:RDF>')


@dataclass
class Dienst:
    """Een nep van LiDO, de BWB-zoekdienst en de Rechtspraak, als httpx-transport."""
    ref: dict[str, str] = field(default_factory=dict)        # juriconnect-ref → versie-id
    jci: dict[str, str] = field(default_factory=dict)        # datum in de jci → versie-id
    links: dict[str, str] = field(default_factory=dict)      # versie-id → antwoord van get-links (xml)
    rdf: dict[str, str] = field(default_factory=dict)        # versie-id → antwoord van get-links (rdf)
    toestanden: tuple[str, ...] = ()
    docs: dict[str, str] = field(default_factory=dict)
    hik: int = 0                                              # zoveel keer eerst een 400
    gezien: list[str] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url, p = request.url, dict(request.url.params)
        self.gezien.append(str(url))
        if self.hik:
            self.hik -= 1
            return httpx.Response(400, text="")
        if url.path.endswith("/get-id"):
            if "juriconnect-ref" in p:
                v = self.ref.get(p["juriconnect-ref"])
            else:
                datum = p["juriconnect"].split("&g=")[-1]
                v = self.jci.get(datum)
            # LiDO geeft soms een kapotte tweede id zonder BWB-id: die mag niet tellen.
            ids = f"<id>http://linkeddata.overheid.nl/terms/bwb/id//2910654/x/x</id><id>{v}</id>" if v else ""
            return httpx.Response(200, text=f'<lido service="get-id">{ids}</lido>')
        if url.path.endswith("/get-links"):
            if p.get("output") == "xml":
                return httpx.Response(200, text=self.links.get(p["id"], _get_links(p["id"], [])))
            return httpx.Response(200, text=self.rdf.get(p["id"], _rdf(p["id"], [])))
        if url.host == "zoekservice.overheid.nl":
            recs = "".join(f"<x>https://x/bwb/{IW}/{d}_0/xml/{IW}_{d}_0.xml</x>" for d in self.toestanden)
            return httpx.Response(406, text=f"<searchRetrieveResponse>{recs}</searchRetrieveResponse>")
        if url.host == "data.rechtspraak.nl":
            if p["id"] in self.docs:
                return httpx.Response(200, text=self.docs[p["id"]])
            return httpx.Response(404, text="")
        return httpx.Response(500)


def _bron(dienst: Dienst) -> LidoRechtspraak:
    return LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)))


@pytest.fixture(autouse=True)
def _geen_wachten(monkeypatch):
    monkeypatch.setattr(L, "HERHAAL_S", 0)
    monkeypatch.setattr(L, "PER_SECONDE", 10**9)


def test_de_begrenzer_geeft_elk_verzoek_per_host_een_eigen_tijdvak(monkeypatch):
    """Hoogstens `PER_SECONDE` per host (de Rechtspraak vraagt er hoogstens 10): tien verzoeken achter elkaar kosten
    ruim anderhalve seconde wachten, en een andere host wacht niet op de eerste."""
    monkeypatch.setattr(L, "PER_SECONDE", 5)
    nu, geslapen = [100.0], []

    def slaap(s):
        geslapen.append(round(s, 3))
        nu[0] += s

    bron = LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="x"))),
                           klok=lambda: nu[0], slaap=slaap)
    for _ in range(10):
        bron._get(L.RECHTSPRAAK_URL, id="ECLI:NL:HR:2022:50")
    assert geslapen == [0.2] * 9
    bron._get(L.LIDO_URL + "/get-id")
    assert len(geslapen) == 9, "een andere host heeft een eigen tijdvak"


def test_de_versies_lopen_terug_en_de_links_worden_verenigd():
    ref = f"{IW}&artikel=9"
    d = Dienst(
        ref={ref: V_NU, f"{ref}&g=2026-06-30&z=2026-06-30": V_2016, f"{ref}&g=2016-04-30&z=2016-04-30": V_2015},
        links={V_NU: _get_links(V_NU, [("ECLI:NL:RBNNE:2026:3287", "x")]),
               V_2016: _get_links(V_2016, [("ECLI:NL:HR:2022:50", "y"), ("ECLI:NL:RBNNE:2026:3287", "x")]),
               V_2015: _get_links(V_2015, [("ECLI:NL:GHARN:2004:AR4846", "z")])})
    k = _bron(d).koppelingen(IW, "9")
    assert k.route == "ref" and k.versies == (V_NU, V_2016, V_2015)
    assert {ln.ecli for ln in k.links} == {"ECLI:NL:RBNNE:2026:3287", "ECLI:NL:HR:2022:50", "ECLI:NL:GHARN:2004:AR4846"}
    assert not k.onvolledig and k.totaal_lido[V_2016] == 2


def test_zonder_ref_de_jci_met_de_nieuwste_toestand_die_lido_kent():
    """De Awb: de ref geeft niets. De nieuwste toestand (1 okt) kent LiDO nog niet; die van 1 jul wel."""
    d = Dienst(jci={"2026-07-01": V_NU, "2016-01-01": V_2015}, toestanden=("2016-01-01", "2026-07-01", "2026-10-01"),
               links={V_NU: _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")])})
    k = _bron(d).koppelingen(IW, "9", "jci1.3:c:BWBR0004770&artikel=9&z=2026-10-01&g=2026-10-01")
    assert k.route == "jci" and k.versies == (V_NU, V_2015)


def test_de_titel_van_een_regeling_komt_uit_de_zoekdienst_en_een_storing_is_leeg():
    ok = httpx.MockTransport(lambda r: httpx.Response(
        200, text="<searchRetrieveResponse><dcterms:title>Wet op de omzetbelasting 1968</dcterms:title></searchRetrieveResponse>"))
    assert LidoRechtspraak(client=httpx.Client(transport=ok)).titel("BWBR0002629") == "Wet op de omzetbelasting 1968"
    weg = httpx.MockTransport(lambda r: httpx.Response(500, text=""))
    assert LidoRechtspraak(client=httpx.Client(transport=weg)).titel("BWBR0002629") == ""
    assert LidoRechtspraak(client=httpx.Client(transport=ok)).titel("geen id") == ""


def test_een_buitenlandse_ecli_is_een_stuk_zonder_tekst():
    """Ronde 2, R15: alleen het voorbeeld in de fout, dus het antwoord dat de ECLI noemde was "ongegrond"."""
    from agent.grounding import check_grounding

    raw = tools.dispatch("get_uitspraak", None, {"id": "ECLI:EU:C:2019:123"}, AAN, rechtspraak=NepBron([]))
    uit = json.loads(raw)
    assert uit["status"] == "error" and uit["reden"] == "buiten_bereik"
    assert uit["stuk"]["id"] == "ECLI:EU:C:2019:123" and uit["stuk"]["leesbaar"] is False
    assert check_grounding("ECLI:EU:C:2019:123 is een arrest van het Hof van Justitie.", [("get_uitspraak", raw)]).niveau \
        != "ongegrond"


def test_get_links_vraagt_alleen_jurisprudentie():
    """Zonder filter noemt LiDO bij een veelgebruikt artikel ook wetten met honderden identifiers, en dan breekt het
    antwoord af, ook bij tien rijen (Awb 6:7, meting 11 nov 2026: 0 van de 6772 uitspraken)."""
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")])})
    _bron(d).koppelingen(IW, "9")
    links = [u for u in d.gezien if "/get-links" in u]
    assert links and all("fq=obj_type%3AJurisprudentie" in u for u in links), links


def test_een_afgebroken_xml_valt_terug_op_rdf():
    """Live: HTTP 200 met een JSON-fout midden in de XML, bij 4 % van de versies. Zonder terugval 12 % stil weg."""
    kapot = '<lido service="get-links"><subject id="x">{\n "Error": "The server encountered a problem"\n}'
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: kapot}, rdf={V_NU: _rdf(V_NU, ["ECLI:NL:HR:2022:50"])})
    k = _bron(d).koppelingen(IW, "9")
    assert [ln.ecli for ln in k.links] == ["ECLI:NL:HR:2022:50"] and not k.onvolledig


def test_ook_de_rdf_onleesbaar_is_onvolledig_en_niet_stil():
    kapot = "<lido><subject>{"
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: kapot}, rdf={V_NU: kapot})
    k = _bron(d).koppelingen(IW, "9")
    assert k.links == () and k.onvolledig == ((V_NU, "onleesbaar"),)


def test_het_plafond_per_versie_staat_in_onvolledig(monkeypatch):
    monkeypatch.setattr(L, "MAX_PAGINAS", 2)
    # Een volle pagina (50 items) betekent: er is meer. Na twee pagina's stopt het, zichtbaar.
    vol = _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")], wetten=49)
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: vol})
    k = _bron(d).koppelingen(IW, "9")
    assert k.onvolledig == ((V_NU, "plafond"),)


def test_een_hik_van_lido_wordt_een_keer_herhaald():
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")])}, hik=1)
    assert [ln.ecli for ln in _bron(d).koppelingen(IW, "9").links] == ["ECLI:NL:HR:2022:50"]


def test_alleen_de_vaste_hosts():
    bron = LidoRechtspraak(lido_url="https://elders.example/service",
                           client=httpx.Client(transport=httpx.MockTransport(Dienst())))
    with pytest.raises(RechtspraakFout) as exc:
        bron.koppelingen(IW, "9")
    assert exc.value.code == "geweigerd"


def test_de_cache_vraagt_een_artikel_een_keer():
    d = Dienst(ref={f"{IW}&artikel=9": V_NU}, links={V_NU: _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")])})
    bron = _bron(d)
    bron.koppelingen(IW, "9")
    n = len(d.gezien)
    bron.koppelingen(IW, "9")
    assert len(d.gezien) == n


# --- zoek_uitspraken ----------------------------------------------------------------------------------------------

@dataclass
class NepBron:
    links: list[Link]
    versies: tuple[str, ...] = (V_NU, V_2016)
    onvolledig: tuple = ()
    docs: dict[str, bytes] = field(default_factory=dict)
    meta: dict[str, bytes] = field(default_factory=dict)
    metavragen: list[str] = field(default_factory=list)

    def koppelingen(self, bwb_id, artikel, jci=""):
        return Koppelingen(tuple(self.links), self.versies, self.onvolledig, "ref", {})

    def document(self, ecli):
        if ecli not in self.docs:
            raise RechtspraakFout(f"{ecli} staat niet in de open data", code="niet_gevonden")
        return L.Document(ecli, self.docs[ecli], "h1", "2025-03-22")

    def metadata(self, ecli):
        self.metavragen.append(ecli)
        if ecli not in self.meta:
            raise RechtspraakFout(f"{ecli} staat niet in de open data", code="niet_gevonden")
        return self.meta[ecli]


LINKS = [
    Link("ECLI:NL:RBNNE:2026:3287", "ECLI:NL:RBNNE:2026:3287 - Rechtbank Noord-Nederland, 06-08-2026 / LEE 26/855",
         "Door computer herkende referentie", V_NU),
    Link("ECLI:NL:HR:2022:50", "ECLI:NL:HR:2022:50 - Hoge Raad, 21-01-2022 / 21/00733",
         "Door computer herkende referentie", V_2016),
    Link("ECLI:NL:HR:2022:50", "", "Redactionele referentie", V_NU),
    Link("ECLI:NL:PHR:2009:BD0236", "ECLI:NL:PHR:2009:BD0236 - Parket bij de Hoge Raad, 25-09-2009 / 43874",
         "Door computer herkende referentie", V_2016),
    Link("ECLI:CE:ECHR:2002:0723JUD003698597", "", "Door computer herkende referentie", V_2016),
]


def _zoek(args: dict, links=LINKS, graaf=ARTIKEL, **kw) -> dict:
    return json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=graaf), args, AAN,
                                     rechtspraak=NepBron(links, **kw)))


def test_een_uitspraak_is_een_rij_over_de_versies_met_metadata_uit_de_titel():
    uit = _zoek({"bwb_id": IW, "artikel": "9"})
    assert uit["status"] == "ok" and uit["totaal"] == 4 and uit["dekking"] == "ten minste" and uit["versies"] == 2
    hr = next(r for r in uit["resultaten"] if r["id"] == "ECLI:NL:HR:2022:50")
    assert (hr["datum"], hr["orgaan"], hr["nummer"]) == ("2022-01-21", "Hoge Raad", "21/00733")
    assert hr["link"].startswith("https://deeplink.rechtspraak.nl/")
    # HR 2022:50 is zowel automatisch herkend als redactioneel gelegd: dan telt hij als redactioneel.
    assert uit["koppelingen"] == {"automatisch herkend": 3, "redactioneel": 1}
    assert all("iri" not in r and "uri" not in r for r in uit["resultaten"]), "een uitspraak is geen bepaling"
    assert next(r for r in uit["resultaten"] if r["id"].startswith("ECLI:CE"))["leesbaar"] is False
    assert next(r for r in uit["resultaten"] if r["id"].startswith("ECLI:NL:PHR"))["soort"] == "Conclusie"
    assert uit["per_instantie"]["Hoge Raad"] == 1


def test_nieuwste_eerst_en_de_filters():
    uit = _zoek({"bwb_id": IW, "artikel": "9"})
    assert uit["resultaten"][0]["id"] == "ECLI:NL:RBNNE:2026:3287"
    oud = _zoek({"bwb_id": IW, "artikel": "9", "volgorde": "oudste"})
    assert oud["resultaten"][0]["id"] == "ECLI:CE:ECHR:2002:0723JUD003698597"
    assert [r["id"] for r in _zoek({"bwb_id": IW, "artikel": "9", "instantie": "Hoge Raad"})["resultaten"]] == [
        "ECLI:NL:HR:2022:50"]
    assert [r["id"] for r in _zoek({"bwb_id": IW, "artikel": "9", "soort": "conclusie"})["resultaten"]] == [
        "ECLI:NL:PHR:2009:BD0236"]
    assert [r["id"] for r in _zoek({"bwb_id": IW, "artikel": "9", "vanaf": "2022", "tot": "2022-12"})["resultaten"]] == [
        "ECLI:NL:HR:2022:50"]


def test_pagineren_met_vervolg_tot_alles_er_is():
    links = [Link(f"ECLI:NL:RBZWB:2024:{i}", f"ECLI:NL:RBZWB:2024:{i} - Rechtbank Zeeland-West-Brabant, "
                  f"{(i % 28) + 1:02d}-03-2024 / {i}", "Door computer herkende referentie", V_NU) for i in range(1, 31)]
    args, gezien = {"bwb_id": IW, "artikel": "9", "aantal": 7}, []
    for _ in range(10):
        uit = _zoek(args, links=links)
        gezien += [r["id"] for r in uit["resultaten"]]
        if uit["volledig"]:
            break
        args = uit["vervolg"]["args"]
    assert len(gezien) == 30 and len(set(gezien)) == 30


def test_een_onvolledige_versie_zegt_de_lijst_zelf():
    uit = _zoek({"bwb_id": IW, "artikel": "9"}, onvolledig=((V_2016, "plafond"),))
    assert "niet alles binnen" in uit["toelichting"]


def test_een_divisie_kent_lido_niet():
    uit = _zoek({"bwb_id": "BWBR0024096", "artikel": "9.4"}, graaf=DIVISIE)
    assert uit["status"] == "ok" and uit["resultaten"] == [] and "divisies kent het niet" in uit["toelichting"]


def test_een_artikel_dat_niet_bestaat():
    """De regeling staat in de graaf, het artikel niet: een tikfout, geen zoektocht bij LiDO."""
    graaf = FakeGraph(results=lambda q: (_tsv(["r", "van", "tot"], [[f"urn:bwb:{IW}", "2026-01-01", "9999-12-31"]])
                                         if "geldigVanaf" in q else _tsv(["node"], [])))
    uit = json.loads(tools.dispatch("zoek_uitspraken", graaf, {"bwb_id": IW, "artikel": "999"}, AAN,
                                    rechtspraak=NepBron(LINKS)))
    assert uit["status"] == "error" and uit["reden"] == "niet_gevonden"


def test_een_regeling_buiten_de_graaf_zoekt_lido_op_bwb_id_en_nummer():
    """De Wet IB 2001 staat niet in de kennisgraaf, maar LiDO kent artikel 3.111 wel (meting 11 nov 2026, R09: "staat
    niet in de graaf" bij een artikel met honderden uitspraken). De tekststand is dan niet vast te stellen, en dat staat
    erbij."""
    graaf = FakeGraph(results=lambda q: _tsv(["r", "van", "tot"], []) if "geldigVanaf" in q else _tsv(["node"], []))
    uit = json.loads(tools.dispatch("zoek_uitspraken", graaf, {"bwb_id": "BWBR0011353", "artikel": "3.111"}, AAN,
                                    rechtspraak=NepBron(LINKS)))
    assert uit["status"] == "ok" and uit["totaal"] == 4, uit
    assert "niet in de kennisgraaf" in uit["toelichting"]
    assert all(r.get("tekststand") in (None, "onbekend") for r in uit["resultaten"])
    # De naam komt uit de BWB-zoekdienst, zodat de zoekvraag de regeling noemt (ronde 2, R09).
    bron = NepBron(LINKS)
    bron.titel = lambda b: "Wet inkomstenbelasting 2001"
    met = json.loads(tools.dispatch("zoek_uitspraken", graaf, {"bwb_id": "BWBR0011353", "artikel": "3.111"}, AAN,
                                    rechtspraak=bron))
    assert met["zoekvraag"]["bepaling"] == "artikel 3.111 van Wet inkomstenbelasting 2001"


def test_een_graaf_die_niet_antwoordt_is_geen_regeling_buiten_de_graaf():
    """Een storing van de graaf mag niet stil naar LiDO leiden alsof de regeling er niet in staat."""
    def antwoord(q):
        if "geldigVanaf" in q:
            raise RuntimeError("graaf weg")
        return _tsv(["node"], [])
    uit = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(results=antwoord), {"bwb_id": IW, "artikel": "999"},
                                    AAN, rechtspraak=NepBron(LINKS)))
    assert uit["status"] == "error" and uit["reden"] == "niet_gevonden"


def test_de_tellingen_tellen_binnen_de_andere_filters():
    """Met een filter op instantie telt per_tekststand alleen die instantie, en per_instantie alle instanties binnen de
    overige filters (meting 11 nov 2026, R06: "487 van de gerechtshoven" naast 26 en 869 over alle uitspraken)."""
    alles = _zoek({"bwb_id": IW, "artikel": "9"})
    hr = _zoek({"bwb_id": IW, "artikel": "9", "instantie": "Hoge Raad"})
    assert hr["totaal"] == 1 and sum(hr["per_tekststand"].values()) == 1
    assert hr["per_instantie"] == alles["per_instantie"], "per_instantie negeert alleen het filter op instantie"
    assert hr["bij_het_artikel"] == alles["totaal"] == 4 and "bij_het_artikel" not in alles
    assert sum(v["uitspraken"] for v in hr["tekstversies"]) >= 1
    conclusies = _zoek({"bwb_id": IW, "artikel": "9", "soort": "conclusie"})
    assert conclusies["per_instantie"] == {"Parket bij de Hoge Raad": 1}, "binnen het filter op soort"


def test_een_plafond_noemt_wat_lido_zelf_telt():
    bron = NepBron(LINKS, onvolledig=((V_2016, "plafond"),))
    bron.koppelingen = lambda *a, **k: Koppelingen(tuple(LINKS), (V_NU, V_2016), ((V_2016, "plafond"),), "ref",
                                                   {V_2016: 6772})
    uit = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL), {"bwb_id": IW, "artikel": "9"}, AAN,
                                    rechtspraak=bron))
    assert "LiDO telt bij die versie 6772 uitspraken" in uit["toelichting"]


@pytest.mark.parametrize("meervoud", ["gerechtshoven", "hoven", "Rechtbanken"])
def test_een_soort_gerecht_in_het_meervoud(meervoud):
    links = [*LINKS, Link("ECLI:NL:GHARL:2025:1", "ECLI:NL:GHARL:2025:1 - Gerechtshof Arnhem-Leeuwarden, 01-02-2025 / 1",
                          "Door computer herkende referentie", V_NU),
             Link("ECLI:NL:RBGEL:2025:1", "ECLI:NL:RBGEL:2025:1 - Rechtbank Gelderland, 01-02-2025 / 1",
                  "Door computer herkende referentie", V_NU)]
    uit = _zoek({"bwb_id": IW, "artikel": "9", "instantie": meervoud}, links=links)
    verwacht = "Gerechtshof" if "hoven" in meervoud else "Rechtbank"
    assert uit["status"] == "ok" and uit["resultaten"] and all(r["orgaan"].startswith(verwacht)
                                                               for r in uit["resultaten"]), uit


@pytest.mark.parametrize("args,reden", [
    ({"artikel": "9"}, "ongeldige_argumenten"),
    ({"bwb_id": IW, "artikel": "9", "volgorde": "relevantie"}, "ongeldige_volgorde"),
    ({"bwb_id": IW, "artikel": "9", "vanaf": "gisteren"}, "ongeldige_datum"),
    ({"bwb_id": IW, "artikel": "9", "aantal": 99}, "ongeldig_aantal"),
])
def test_een_invoerfout_zegt_hoe_het_wel_moet(args, reden):
    uit = _zoek(args)
    assert uit["status"] == "error" and uit["reden"] == reden and "bijvoorbeeld" in uit["melding"]


def test_uit_is_uit():
    uit = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=ARTIKEL), {"bwb_id": IW, "artikel": "9"},
                                    make_settings()))
    assert uit["reden"] == "connector_uit"


# --- get_uitspraak ------------------------------------------------------------------------------------------------

def _uitspraak(*, lang: int = 0) -> bytes:
    lange = " ".join(f"Zin {i} over de invordering." for i in range(lang)) if lang else ""
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description>
  <dcterms:identifier>ECLI:NL:HR:2022:50</dcterms:identifier><dcterms:modified>2022-02-01T10:00:00</dcterms:modified>
  <dcterms:issued>2022-01-21</dcterms:issued><dcterms:creator>Hoge Raad</dcterms:creator>
  <dcterms:date>2022-01-21</dcterms:date><psi:zaaknummer>21/00733</psi:zaaknummer><dcterms:type>Uitspraak</dcterms:type>
</rdf:Description></rdf:RDF>
<inhoudsindicatie><para>Invorderingsrente; artikel 9 Iw 1990.</para></inhoudsindicatie>
<uitspraak><section><title>1 Geding in cassatie</title><para>Belanghebbende heeft beroep ingesteld.</para>
<para/></section><section><title>2 Beoordeling</title><parablock><para>Artikel 9 van de Invorderingswet 1990 bepaalt de termijn.</para></parablock>
<para>{lange}</para></section></uitspraak></open-rechtspraak>""".encode()


def test_de_uitspraak_per_alinea_met_kop_en_metadata():
    uit = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ecli:nl:hr:2022:50"}, AAN,
                                    rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": _uitspraak()})))
    assert uit["status"] == "ok"
    assert uit["stuk"]["id"] == "ECLI:NL:HR:2022:50" and uit["stuk"]["datum"] == "2022-01-21"
    assert uit["stuk"]["orgaan"] == "Hoge Raad" and uit["stuk"]["nummer"] == "21/00733" and uit["stuk"]["bron_hash"]
    koppen = [(r["kop"], r["tekst"][:20]) for r in uit["resultaten"]]
    assert koppen[0] == ("Inhoudsindicatie", "Invorderingsrente; a")
    assert ("Uitspraak › 1 Geding in cassatie", "Belanghebbende heeft") in koppen
    assert ("Uitspraak › 2 Beoordeling", "Artikel 9 van de Inv") in koppen, "een para in een parablock telt mee"
    assert len(uit["resultaten"]) == 3, "een lege alinea telt niet"
    assert uit["stuk"]["label"] == "Hoge Raad 21 januari 2022, ECLI:NL:HR:2022:50", "het label uit de metadata"


#: De drie vormen die de Rechtspraak levert (live, 10 nov 2026): genummerde rechtsoverwegingen met een `nr` in de titel
#: (Hoge Raad, CRvB), losse alinea's zonder secties (Raad van State), en alleen metadata (GHARL:2023:5000).
_GENUMMERD = """<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/"
  xmlns="http://www.rechtspraak.nl/schema/rechtspraak-1.0">
<rdf:RDF><rdf:Description>
  <dcterms:identifier>ECLI:NL:HR:2022:50</dcterms:identifier><dcterms:creator>Hoge Raad</dcterms:creator>
  <dcterms:date>2022-01-21</dcterms:date><dcterms:type>Uitspraak</dcterms:type>
  <psi:procedure>Cassatie</psi:procedure>
  <dcterms:subject>Bestuursrecht; Belastingrecht</dcterms:subject>
</rdf:Description></rdf:RDF>
<uitspraak><section><title>
      <nr>2</nr>Uitgangspunten in cassatie</title>
<paragroup><nr>2.1</nr><para>Aan belanghebbende zijn navorderingsaanslagen opgelegd.</para>
<para>In bezwaar heeft hij die bestreden.</para></paragroup>
<paragroup><nr>2.2</nr><para>Het Hof heeft geoordeeld.</para></paragroup></section>
<section><title><nr>3</nr>Beoordeling van de middelen</title>
<paragroup><nr>3.1</nr><parablock><para>Het middel faalt.</para></parablock></paragroup></section></uitspraak>
</open-rechtspraak>"""
_VLAK = _GENUMMERD.split("<uitspraak>")[0] + "<uitspraak>" + "".join(
    f"<para>Overweging {i}.</para>" for i in range(1, 6)) + "</uitspraak></open-rechtspraak>"
_ALLEEN_META = _GENUMMERD.split("<uitspraak>")[0] + "</open-rechtspraak>"


def _lees(xml: str) -> dict:
    return json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50"}, AAN,
                                     rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": xml.encode()})))


def test_een_rechtsoverweging_draagt_haar_nummer_en_de_kop_het_nummer_van_de_sectie():
    uit = _lees(_GENUMMERD)
    rijen = aangevuld(uit)
    assert [r.get("kop") for r in uit["resultaten"]] == [
        "Uitspraak › 2 Uitgangspunten in cassatie", None, None, "Uitspraak › 3 Beoordeling van de middelen"], (
        "de kop staat alleen waar hij verandert")
    assert [(r["kop"], r.get("plek")) for r in rijen] == [
        ("Uitspraak › 2 Uitgangspunten in cassatie", "r.o. 2.1"), ("Uitspraak › 2 Uitgangspunten in cassatie", "r.o. 2.1"),
        ("Uitspraak › 2 Uitgangspunten in cassatie", "r.o. 2.2"), ("Uitspraak › 3 Beoordeling van de middelen", "r.o. 3.1")]
    assert all("2.1" not in r["tekst"] for r in rijen), "het nummer is geen tekst van de alinea"
    assert uit["stuk"]["procedure"] == "Cassatie" and uit["stuk"]["rechtsgebied"] == "Bestuursrecht; Belastingrecht"
    assert uit["inhoud"] == [{"kop": "Uitspraak › 2 Uitgangspunten in cassatie", "offset": 0},
                             {"kop": "Uitspraak › 3 Beoordeling van de middelen", "offset": 3}]


def test_een_vlakke_uitspraak_en_een_uitspraak_zonder_tekst():
    vlak = _lees(_VLAK)
    assert [r["kop"] for r in aangevuld(vlak)] == ["Uitspraak"] * 5 and "inhoud" not in vlak
    assert not any(r.get("plek") for r in vlak["resultaten"])
    leeg = _lees(_ALLEEN_META)
    assert leeg["status"] == "ok" and leeg["resultaten"] == [] and "geen tekst" in leeg["toelichting"]
    assert leeg["stuk"]["leesbaar"] is False, "een stuk zonder tekst is niet leesbaar"
    assert leeg["stuk"]["label"].startswith("Hoge Raad 21 januari 2022")


def test_inhoud_staat_alleen_op_de_eerste_pagina():
    uit = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50", "offset": 1}, AAN,
                                    rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": _GENUMMERD.encode()})))
    assert "inhoud" not in uit


def test_een_lange_alinea_komt_in_delen_binnen_de_begroting():
    doc = _uitspraak(lang=400)
    uit = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50"}, AAN,
                                    rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": doc})))
    delen = [r for r in uit.get("resultaten", []) if r.get("deel")]
    assert uit["status"] == "ok" and delen, uit
    assert all(len(r["tekst"]) <= R.MAX_ALINEA for r in delen)


def test_een_ongeldige_of_onbekende_ecli():
    nep = NepBron([])
    # Een buitenlandse ECLI is een stuk zonder tekst (ronde 2, R15); iets wat geen ECLI is, is een ongeldig id.
    buiten = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:CE:ECHR:2002:1"}, AAN, rechtspraak=nep))
    assert buiten["reden"] == "buiten_bereik" and buiten["stuk"]["leesbaar"] is False
    ongeldig = json.loads(tools.dispatch("get_uitspraak", None, {"id": "kst-36200-1"}, AAN, rechtspraak=nep))
    assert ongeldig["reden"] == "ongeldig_id" and "bijvoorbeeld" in ongeldig["melding"]
    onbekend = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:1900:1"}, AAN, rechtspraak=nep))
    assert onbekend["reden"] == "niet_gevonden" and "zoek_uitspraken" in onbekend["melding"]


def test_de_cache_toetst_na_vers_s_alleen_de_metadata_en_meldt_een_storing(monkeypatch):
    """Het patroon van Kamerstukken: binnen `VERS_S` geen aanroep; daarna `return=META`, en de tekst alleen opnieuw als
    `dcterms:modified` verschilt; bij een storing de bewaarde versie met `gevalideerd: false`, nooit stil."""
    nu = [0.0]
    stand = {"xml": _uitspraak().decode(), "storing": False}
    gezien: list[dict] = []

    def dienst(request: httpx.Request) -> httpx.Response:
        p = dict(request.url.params)
        gezien.append(p)
        if stand["storing"]:
            raise httpx.ConnectError("weg")
        return httpx.Response(200, text=stand["xml"])

    bron = LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)), klok=lambda: nu[0],
                           slaap=lambda _s: None)
    eerste = bron.document("ECLI:NL:HR:2022:50")
    bron.document("ECLI:NL:HR:2022:50")
    assert len(gezien) == 1, "binnen VERS_S geen aanroep"

    nu[0] += L.VERS_S + 1
    assert bron.document("ECLI:NL:HR:2022:50") is eerste
    assert gezien[-1].get("return") == "META" and len(gezien) == 2, "ongewijzigd: alleen de metadata"

    nu[0] += L.VERS_S + 1
    stand["xml"] = stand["xml"].replace("2022-02-01T10:00:00", "2022-03-01T09:00:00").replace(
        "de termijn.", "de termijn, en meer.")
    nieuw = bron.document("ECLI:NL:HR:2022:50")
    assert nieuw.hash != eerste.hash and nieuw.gewijzigd == "2022-03-01T09:00:00"
    assert [g.get("return") for g in gezien[-2:]] == ["META", None], "gewijzigd: de tekst opnieuw"

    nu[0] += L.VERS_S + 1
    stand["storing"] = True
    bewaard = bron.document("ECLI:NL:HR:2022:50")
    assert bewaard.gevalideerd is False and bewaard.hash == nieuw.hash
    uit = json.loads(tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50"}, AAN, rechtspraak=bron))
    assert uit["status"] == "ok" and uit["stuk"]["gevalideerd"] is False


def test_een_verdwenen_uitspraak_is_geen_storing():
    nu = [0.0]
    stand = {"status": 200}

    def dienst(request: httpx.Request) -> httpx.Response:
        return httpx.Response(stand["status"], text=_uitspraak().decode() if stand["status"] == 200 else "")

    bron = LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)), klok=lambda: nu[0],
                           slaap=lambda _s: None)
    bron.document("ECLI:NL:HR:2022:50")
    nu[0] += L.VERS_S + 1
    stand["status"] = 404
    with pytest.raises(RechtspraakFout) as exc:
        bron.document("ECLI:NL:HR:2022:50")
    assert exc.value.code == "niet_gevonden"


def test_de_zoekvraag_in_woorden_noemt_de_bepaling():
    """Een lijst uitspraken zegt bij wélke bepaling er gezocht is, in woorden: niet "bwb_id BWBR0004770, artikel 36"."""
    from bronmodel.connectors import RECHTSPRAAK
    from agent.sjablonen.extern import zoekvraag_tekst
    zin = zoekvraag_tekst(RECHTSPRAAK, {"bwb_id": IW, "artikel": "36", "volgorde": "nieuwste",
                                        "bepaling": "artikel 36 van Invorderingswet 1990", "instantie": "Hoge Raad"})
    assert zin.startswith("Gezocht bij artikel 36 van Invorderingswet 1990"), zin
    assert "BWBR" not in zin and "bwb_id" not in zin
    assert R._in_woorden("Artikel 36", "Invorderingswet 1990") == "artikel 36 van Invorderingswet 1990"


def test_een_regelafbreking_in_de_bron_blijft_een_spatie():
    """Meting 10 nov 2026: "bankrekeningen.In bezwaar" – de parser gooit `<?linebreak?>` weg en plakte de zinnen."""
    xml = _GENUMMERD.replace("navorderingsaanslagen opgelegd.", "navorderingsaanslagen opgelegd.<?linebreak?>In bezwaar ging het mis.")
    rijen = _lees(xml)["resultaten"]
    assert "opgelegd. In bezwaar ging het mis." in rijen[0]["tekst"]


def test_de_rechtsoverweging_staat_als_plek_in_het_antwoordblok():
    from agent.sjablonen.extern import blokken
    uit = tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50"}, AAN,
                         rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": _GENUMMERD.encode()}))
    blok, = blokken([{"id": "ECLI:NL:HR:2022:50", "van_nr": 1, "tot_nr": 1}], [("get_uitspraak", uit)])
    assert blok.passages[0].plek == "r.o. 2.1" and blok.passages[0].kop == "Uitspraak › 2 Uitgangspunten in cassatie"


def test_het_label_van_een_zoekrij_noemt_gerecht_en_datum():
    rij = R.rij_van("ECLI:NL:HR:2026:586", "ECLI:NL:HR:2026:586 - Hoge Raad, 10-04-2026 / 25/01557")
    assert rij["label"] == "Hoge Raad 10 april 2026, ECLI:NL:HR:2026:586"
    feed = R.rij_van("ECLI:NL:RBGEL:2026:1", "ECLI:NL:RBGEL:2026:1, Rechtbank Gelderland, 02-10-2026, 26/1")
    assert feed["label"] == "Rechtbank Gelderland 2 oktober 2026, ECLI:NL:RBGEL:2026:1"
    assert R.rij_van("ECLI:NL:HR:2026:1", "")["label"] == "ECLI:NL:HR:2026:1", "zonder titel de ECLI"


def test_een_ehrm_uitspraak_waar_de_tekst_naar_verwijst_is_geen_bron_tenzij_het_antwoord_haar_noemt():
    """Nameting 10 nov 2026: de bronnenlijst bij ECLI:NL:HR:2022:50 noemde ECLI:CE:ECHR:2002:…, die het antwoord niet
    noemde. Een extern id zonder connector staat er alleen als het antwoord het noemt."""
    from agent.grounding import alleen_gelezen_extern
    from agent.models import Source
    hr = Source(uri="ECLI:NL:HR:2022:50", label="x", brontype="uitspraak", origin_tool="get_uitspraak")
    ehrm = Source(uri="ECLI:CE:ECHR:2002:0723JUD003698597", label="y", brontype="uitspraak", origin_tool="get_uitspraak")
    trace = [("get_uitspraak", json.dumps({"stuk": {"id": "ECLI:NL:HR:2022:50"},
                                           "resultaten": [{"tekst": "zie ECLI:CE:ECHR:2002:0723JUD003698597"}]}))]
    assert [s.uri for s in alleen_gelezen_extern([hr, ehrm], trace, "In ECLI:NL:HR:2022:50 oordeelt de HR")] == [hr.uri]
    assert len(alleen_gelezen_extern([hr, ehrm], trace, "ECLI:NL:HR:2022:50 volgt ECLI:CE:ECHR:2002:0723JUD003698597")) == 2


def test_een_uitspraak_zonder_tekst_is_een_melding_uit_code_zonder_model(monkeypatch):
    """Nameting 10 nov 2026: bij een ECLI met alleen metadata duidde het model zelf ("dus een verkeersboete") en zei het
    "Het systeem meldt". De code zegt nu dat de tekst niet bij de bron staat, met het stuk en zijn gegevens."""
    import asyncio
    from agent import tools as t
    from agent.agent import answer_stream
    from tests.fakes import FakeGraph, FakeLLM

    monkeypatch.setattr(t.CONNECTORMODULES["rechtspraak"], "_bron", NepBron([], docs={"ECLI:NL:HR:2022:50": _ALLEEN_META.encode()}))
    llm = FakeLLM([])

    async def verzamel():
        return [e async for e in answer_stream("Wat staat er in ECLI:NL:HR:2022:50?", settings=AAN, llm=llm,
                                               graph=FakeGraph(result=""), bronnen=["rechtspraak"])]

    events = asyncio.run(verzamel())
    assert llm.calls == [], "geen model"
    antwoord, = [e["antwoord"] for e in events if e["type"] == "antwoord"]
    leemte, lijst = antwoord["blokken"]
    assert leemte["soort"] == "leemte" and "staat niet bij de bron" in leemte["tekst"]
    assert lijst["soort"] == "stukken" and lijst["kop"] == "Uit de rechtspraak"
    assert lijst["items"][0]["label"].startswith("Hoge Raad 21 januari 2022")


def test_het_gelezen_stuk_staat_in_de_bronnen_als_de_vraag_het_noemt():
    """Derde meting 10 nov 2026: een vrije samenvatting van ECLI:NL:HR:2022:50 noemde die ECLI niet meer, en de
    bronnenlijst noemde alleen de uitspraken waar de tekst naar verwijst. Het gelezen stuk zelf hoort erin."""
    from agent.grounding import alleen_gelezen_extern
    from agent.models import Source
    hr = Source(uri="ECLI:NL:HR:2022:50", label="x", brontype="uitspraak", origin_tool="get_uitspraak")
    oud = Source(uri="ECLI:NL:HR:1996:AA2050", label="y", brontype="uitspraak", origin_tool="get_uitspraak")
    trace = [("get_uitspraak", json.dumps({"status": "ok", "volledig": True, "aantal": 1,
                                           "stuk": {"id": "ECLI:NL:HR:2022:50"},
                                           "resultaten": [{"nr": 1, "tekst": "zie ECLI:NL:HR:1996:AA2050"}]}))]
    antwoord = "De Hoge Raad oordeelt dat de rente mag (r.o. 3.2)."
    assert alleen_gelezen_extern([hr, oud], trace, antwoord) == []
    assert [s.uri for s in alleen_gelezen_extern([hr, oud], trace, antwoord,
                                                 "Wat staat er in ECLI:NL:HR:2022:50?")] == [hr.uri]
    # Een stuk dat alleen genoemd wordt in de tekst van het gelezen stuk, is niet gelezen: de vraag maakt het geen bron.
    assert alleen_gelezen_extern([oud], trace, antwoord, "Wat staat er in ECLI:NL:HR:1996:AA2050?") == []


def test_een_uitspraak_zonder_tekst_zegt_dat_in_haar_eigen_woorden():
    """Vierde meting 10 nov 2026: de lijstregel zei "(onopgemaakt, alleen PDF)", de vorm van Kamerstukken. De tekst komt
    uit de beschrijving van de connector (`zonder_tekst`)."""
    from bronmodel.antwoord import antwoord_tekst
    from agent import sjablonen
    trace = [("get_uitspraak", tools.dispatch("get_uitspraak", None, {"id": "ECLI:NL:HR:2022:50"}, AAN,
                                              rechtspraak=NepBron([], docs={"ECLI:NL:HR:2022:50": _ALLEEN_META.encode()})))]
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "Er is geen tekst.", "extern": [],
                                          "stukken": ["ECLI:NL:HR:2022:50"], "twijfel": []}, trace)
    [x] = next(b for b in a.blokken if b.soort == "stukken").items
    assert x.leesbaar is False and x.zonder_tekst == "geen tekst in de open data"
    tekst = antwoord_tekst(a)
    assert "(geen tekst in de open data)" in tekst and "PDF" not in tekst


def test_het_totaal_van_een_lijst_heeft_een_punt_voor_de_duizendtallen():
    from bronmodel.antwoord import Antwoord, Stuk, Stukken, antwoord_tekst
    blok = Stukken(brontype="uitspraak", kop="Gevonden Rechtspraak", totaal=19523,
                   items=[Stuk(id=f"ECLI:NL:HR:2026:{i}", label=str(i)) for i in range(10)])
    assert "10 van de 19.523 stukken." in antwoord_tekst(Antwoord(sjabloon="extern", blokken=[blok]))


# --- de versie van het artikel (review ADR-013, 10 nov 2026) -------------------------------------------------------

V_2010, V_2023 = f"{V}/2010-01-01/2010-01-01", f"{V}/2023-01-01/2023-01-01"
DRIE = (V_2023, V_2016, V_2010)


def _artikel(inwerking: str = "", terugwerkend: str = "") -> str:
    kop = ["node", "jci", "labelId", "label", "soort", "inwerking", "terugwerkendTot"]
    return _tsv(kop, [["urn:bwb:BWBR0004770:artikel:9", "", "2910654", "Artikel 9", "urn:bwb-ns:Artikel",
                       inwerking, terugwerkend]])


VERSIELINKS = [
    Link("ECLI:NL:HR:2024:1", "ECLI:NL:HR:2024:1 - Hoge Raad, 12-03-2024 / 23/001", "Door computer herkende referentie", V_2023),
    Link("ECLI:NL:HR:2018:2", "ECLI:NL:HR:2018:2 - Hoge Raad, 05-06-2018 / 17/002", "Door computer herkende referentie", V_2016),
    Link("ECLI:NL:RBGEL:2012:3", "ECLI:NL:RBGEL:2012:3 - Rechtbank Gelderland, 01-02-2012 / 11/3", "Redactionele referentie", V_2010),
    # Een uitspraak die LiDO aan twee versies hangt: ze telt bij de huidige tekst, met de vroegste begindatum.
    Link("ECLI:NL:GHARL:2023:4", "ECLI:NL:GHARL:2023:4 - Gerechtshof Arnhem-Leeuwarden, 20-12-2022 / 22/4",
         "Door computer herkende referentie", V_2016),
    Link("ECLI:NL:GHARL:2023:4", "", "Door computer herkende referentie", V_2023),
]


def _rij(uit: dict, ecli: str) -> dict:
    return next(r for r in uit["resultaten"] if r["id"] == ecli)


def test_tekstversies_lopen_van_nieuw_naar_oud_met_een_periode():
    versies, achter = R.tekstversies(DRIE, ("2023-01-01",))
    assert not achter
    assert [(t.vanaf, t.tot, t.huidig) for t in versies] == [
        ("2023-01-01", "", True), ("2016-05-01", "2022-12-31", False), ("2010-01-01", "2016-04-30", False)]


def test_elke_uitspraak_noemt_de_tekst_van_het_artikel_waaraan_lido_haar_koppelde():
    uit = _zoek({"bwb_id": IW, "artikel": "9"}, links=VERSIELINKS, graaf=_artikel("2023-01-01"), versies=DRIE)
    hr24 = _rij(uit, "ECLI:NL:HR:2024:1")
    assert (hr24["tekst_vanaf"], hr24["tekststand"]) == ("2023-01-01", "huidige tekst")
    assert "tekst_tot" not in _rij(uit, "ECLI:NL:HR:2024:1"), "een tekst die nog geldt heeft geen einde"
    hr18 = _rij(uit, "ECLI:NL:HR:2018:2")
    assert (hr18["tekst_vanaf"], hr18["tekst_tot"], hr18["tekststand"]) == ("2016-05-01", "2022-12-31", "eerdere tekst")
    twee = _rij(uit, "ECLI:NL:GHARL:2023:4")
    assert (twee["tekst_vanaf"], twee.get("tekst_tot"), twee["tekststand"]) == ("2016-05-01", None, "huidige tekst")
    assert uit["huidige_tekst"] == {"vanaf": "2023-01-01"}
    assert uit["per_tekststand"] == {"huidige tekst": 2, "eerdere tekst": 2}
    assert uit["tekstversies"][0] == {"vanaf": "2023-01-01", "uitspraken": 2}
    assert uit["tekstversies"][1] == {"vanaf": "2016-05-01", "tot": "2022-12-31", "uitspraken": 2}
    assert "2 van de 4 uitspraken noemen een eerdere tekst van artikel 9, die gold vóór 1 januari 2023" in uit["toelichting"]


def test_filter_op_tekststand_en_peildatum():
    args = {"bwb_id": IW, "artikel": "9"}
    kw = {"links": VERSIELINKS, "graaf": _artikel("2023-01-01"), "versies": DRIE}
    huidig = _zoek({**args, "tekststand": "huidige tekst"}, **kw)
    assert {r["id"] for r in huidig["resultaten"]} == {"ECLI:NL:HR:2024:1", "ECLI:NL:GHARL:2023:4"}
    eerder = _zoek({**args, "tekststand": "eerdere tekst"}, **kw)
    assert {r["id"] for r in eerder["resultaten"]} == {"ECLI:NL:HR:2018:2", "ECLI:NL:RBGEL:2012:3"}
    peil = _zoek({**args, "peildatum": "2015-01-01"}, **kw)
    assert peil["peildatum"] == "2015-01-01"
    assert _rij(peil, "ECLI:NL:RBGEL:2012:3")["op_peildatum"] is True
    assert _rij(peil, "ECLI:NL:HR:2024:1")["op_peildatum"] is False
    op = _zoek({**args, "tekststand": "op peildatum", "peildatum": "2015"}, **kw)
    assert [r["id"] for r in op["resultaten"]] == ["ECLI:NL:RBGEL:2012:3"]


def test_lido_kent_de_huidige_tekst_nog_niet():
    uit = _zoek({"bwb_id": IW, "artikel": "9"}, links=VERSIELINKS, graaf=_artikel("2026-10-01"), versies=DRIE)
    assert {r["tekststand"] for r in uit["resultaten"]} == {"eerdere tekst"}
    assert _rij(uit, "ECLI:NL:HR:2024:1")["tekst_tot"] == "2026-09-30"
    assert "LiDO kent de huidige tekst van artikel 9 (geldig vanaf 1 oktober 2026) nog niet" in uit["toelichting"]


def test_zonder_inwerking_in_de_graaf_is_de_stand_onbekend_maar_de_periode_staat_er():
    uit = _zoek({"bwb_id": IW, "artikel": "9"}, links=VERSIELINKS, graaf=_artikel(), versies=DRIE)
    assert {r["tekststand"] for r in uit["resultaten"]} == {"onbekend"}
    assert _rij(uit, "ECLI:NL:HR:2018:2")["tekst_tot"] == "2022-12-31"
    assert "niet vast te stellen" in uit["toelichting"] and "huidige_tekst" not in uit


def test_terugwerkende_kracht_telt_als_de_huidige_tekst():
    versies, _ = R.tekstversies((f"{V}/2022-07-01/2023-01-15", V_2016), ("2023-01-15", "2022-07-01"))
    assert versies[0].huidig is True


@pytest.mark.parametrize("args,reden", [
    ({"bwb_id": IW, "artikel": "9", "tekststand": "op peildatum"}, "ongeldige_argumenten"),
    ({"bwb_id": IW, "artikel": "9", "tekststand": "oud"}, "ongeldige_argumenten"),
    ({"bwb_id": IW, "artikel": "9", "peildatum": "morgen"}, "ongeldige_datum"),
    ({"instantie": "Hoge Raad", "peildatum": "2015-01-01"}, "ongeldige_argumenten"),
])
def test_een_invoerfout_bij_de_tekststand(args, reden):
    uit = _zoek(args, links=VERSIELINKS, graaf=_artikel("2023-01-01"), versies=DRIE)
    assert uit["status"] == "error" and uit["reden"] == reden and "bijvoorbeeld" in uit["melding"]


def _meta(ecli: str, gerecht: str, datum: str, zaak: str) -> bytes:
    """Het antwoord van de Rechtspraak op `return=META`: alleen de RDF-beschrijving."""
    d, m, j = datum.split("-")
    return f"""<open-rechtspraak xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dcterms="http://purl.org/dc/terms/" xmlns:psi="http://psi.rechtspraak.nl/">
<rdf:RDF><rdf:Description>
  <dcterms:identifier>{ecli}</dcterms:identifier><dcterms:creator>{gerecht}</dcterms:creator>
  <dcterms:date>{j}-{m}-{d}</dcterms:date><psi:zaaknummer>{zaak}</psi:zaaknummer>
  <dcterms:title>{ecli}, {gerecht}, {datum}, {zaak}</dcterms:title>
</rdf:Description></rdf:RDF></open-rechtspraak>""".encode()


def test_een_uitspraak_zonder_titel_krijgt_datum_en_gerecht_uit_de_metadata():
    """Meting 11 nov 2026 (`rechtspraak-versies-2026-11-11`, vraag 3): bij de tekst op peildatum 2015 gaf LiDO de
    koppelingen alleen in RDF, zonder titel, en de rijen droegen alleen het jaar en "rechtbank". Nu vult de metadata van
    de Rechtspraak ze aan, vóór het sorteren; lukt dat niet, dan blijft het jaar staan."""
    links = [Link("ECLI:NL:RBDHA:2015:2495", "", "Door computer herkende referentie", V_2010),
             Link("ECLI:NL:RBGEL:2015:5487", "", "Door computer herkende referentie", V_2010),
             Link("ECLI:NL:PHR:2015:354", "", "Redactionele referentie", V_2010)]
    bron = NepBron(links, versies=DRIE, meta={
        "ECLI:NL:RBDHA:2015:2495": _meta("ECLI:NL:RBDHA:2015:2495", "Rechtbank Den Haag", "03-03-2015", "AWB 14/1"),
        "ECLI:NL:RBGEL:2015:5487": _meta("ECLI:NL:RBGEL:2015:5487", "Rechtbank Gelderland", "01-09-2015", "AWB 14/2")})
    uit = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=_artikel("2023-01-01")),
                                    {"bwb_id": IW, "artikel": "9", "peildatum": "2015-01-01",
                                     "tekststand": "op peildatum"}, AAN, rechtspraak=bron))
    assert uit["status"] == "ok"
    gel, dha, phr = uit["resultaten"]
    assert (gel["id"], gel["datum"], gel["orgaan"], gel["nummer"]) == (
        "ECLI:NL:RBGEL:2015:5487", "2015-09-01", "Rechtbank Gelderland", "AWB 14/2"), "nieuwste eerst, op de dag"
    assert gel["label"] == "Rechtbank Gelderland 1 september 2015, ECLI:NL:RBGEL:2015:5487"
    assert dha["datum"] == "2015-03-03" and dha["titel"].startswith("ECLI:NL:RBDHA:2015:2495, Rechtbank Den Haag")
    assert phr["datum"] == "2015" and phr["orgaan"] == "Parket bij de Hoge Raad", "zonder metadata blijft het jaar"
    assert all(r["op_peildatum"] is True for r in uit["resultaten"])
    assert sorted(bron.metavragen) == sorted(l.ecli for l in links), "één vraag per uitspraak zonder titel"


def test_een_rij_met_titel_vraagt_geen_metadata():
    bron = NepBron(VERSIELINKS, versies=DRIE)
    json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=_artikel("2023-01-01")), {"bwb_id": IW, "artikel": "9"},
                              AAN, rechtspraak=bron))
    assert bron.metavragen == []


def test_de_adapter_vraagt_alleen_de_metadata_en_bewaart_die():
    gezien: list[dict] = []

    def dienst(request: httpx.Request) -> httpx.Response:
        gezien.append(dict(request.url.params))
        return httpx.Response(200, text=_meta("ECLI:NL:HR:2015:1", "Hoge Raad", "02-02-2015", "14/1").decode())

    bron = LidoRechtspraak(client=httpx.Client(transport=httpx.MockTransport(dienst)), slaap=lambda _s: None)
    eerste = bron.metadata("ECLI:NL:HR:2015:1")
    assert bron.metadata("ECLI:NL:HR:2015:1") == eerste and b"<dcterms:date>2015-02-02" in eerste
    assert gezien == [{"id": "ECLI:NL:HR:2015:1", "return": "META"}], "één aanroep, alleen de metadata"


def test_een_regeling_zonder_artikel_zoekt_de_uitspraken_bij_de_regeling():
    """Ronde 2, R26: "Welke uitspraken noemen de Leidraad Invordering 2008?" gaf de zoekfeed van het belastingrecht.
    LiDO koppelt een uitspraak die de regeling noemt zonder artikel aan de regeling zelf."""
    bron = NepBron(LINKS)
    vragen = []
    bron.koppelingen = lambda b, a, jci="": vragen.append((b, a)) or Koppelingen(tuple(LINKS), (V_NU,), (), "ref", {})
    bron.titel = lambda b: "Leidraad Invordering 2008"
    uit = json.loads(tools.dispatch("zoek_uitspraken", FakeGraph(result=""), {"bwb_id": "BWBR0024096"}, AAN,
                                    rechtspraak=bron))
    assert uit["status"] == "ok" and uit["totaal"] == 4 and vragen == [("BWBR0024096", "")]
    assert uit["zoekvraag"]["bepaling"] == "Leidraad Invordering 2008 als geheel"
    assert "als geheel noemen" in uit["kanttekening"]


def test_lido_zoekt_de_regeling_op_haar_ref_zonder_artikel():
    d = Dienst(ref={IW: V_NU}, links={V_NU: _get_links(V_NU, [("ECLI:NL:HR:2022:50", "y")])})
    k = _bron(d).koppelingen(IW, "")
    assert [ln.ecli for ln in k.links] == ["ECLI:NL:HR:2022:50"]
