"""De tools en de bron van de connector Kennisgroepstandpunten (plan-connector-kennisgroepen.md stap 4).

Zonder netwerk: de index is een `FakeGraph` die op de vorm van de query antwoordt, de site een `httpx.MockTransport` met
echte publicaties uit `tests/data/kennisgroepen/` (CC0).
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from agent import tools
from agent.adapters import kennisgroepen_bron as kb
from agent.adapters.kennisgroepen_bron import Gelezen, Gevonden, KennisgroepenBron, KennisgroepenFout, Zoekvraag
from bronmodel import kennisgroepen as kg
from fakes import FakeGraph, make_settings

DATA = Path(__file__).parent / "data" / "kennisgroepen"
AAN = make_settings(connector_kennisgroepen=True)


def _item(wp_id: int) -> dict:
    return json.loads((DATA / f"wp-{wp_id}.json").read_text(encoding="utf-8"))


def _tsv(kop: list[str], *rijen: list[str]) -> str:
    def term(w: str) -> str:
        return f"<{w}>" if w.startswith("urn:") else '"' + w.replace('"', '\\"') + '"'
    return "\n".join(["\t".join("?" + k for k in kop)] + ["\t".join(term(w) if w else "" for w in r) for r in rijen])


class NepBron:
    def __init__(self, rijen=None, per_status=None, per_herkomst=None, gelezen=None, per_belastingsoort=None,
                 opvolgers=None):
        self.rijen, self.vragen = rijen or [], []
        self.per_status = per_status if per_status is not None else {"geldend": len(self.rijen)}
        self.per_herkomst, self.gelezen = per_herkomst or {}, gelezen
        self.per_belastingsoort, self._opvolgers = per_belastingsoort or {}, opvolgers or []

    def zoek(self, graph, vraag, *, offset, limit):
        self.vragen.append(vraag)
        return Gevonden(sum(n for s, n in self.per_status.items() if vraag.status in ("alle", s)),
                        self.rijen[offset:offset + limit], self.per_status, self.per_herkomst, self.per_belastingsoort)

    def publicatie(self, graph, ident):
        if self.gelezen is None:
            raise KennisgroepenFout("niet_gevonden", f"{ident} staat niet bij de gepubliceerde kennisgroepstandpunten")
        return self.gelezen

    def opvolgers(self, graph, ident):
        return self._opvolgers


def _roep(naam: str, args: dict, bron, graph=None) -> dict:
    return json.loads(tools.dispatch(naam, graph, args, AAN, kennisgroepen=bron))


# ── de SPARQL ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_een_waarde_van_de_jurist_is_altijd_een_literal():
    q = kb.q_pagina(Zoekvraag(woorden=('x") } } DROP GRAPH <urn:bwb:x> #',), kennisgroep='a"b'), 0, 11)
    assert 'DROP GRAPH <urn:bwb:x>' not in q.replace('\\"', "")  or '\\"' in q
    assert '"x\\") } } drop graph <urn:bwb:x> #"' in q and '"a\\"b"' in q


def test_de_filters_staan_in_de_query():
    q = kb.q_pagina(Zoekvraag(bwb_id="BWBR0004770", artikel="36", lid="2", kennisgroep="Invordering", middel="ib",
                              rubriek="loon", noemt="ECLI:NL:HR:2013:64", vanaf="2024-01-01", tot="2024-12-31"), 0, 11)
    for deel in ('kgo:bwbId "BWBR0004770"', 'kgo:artikel "36"', '?anderlid != "2"', '"invordering"', 'kgo:doel '
                 '"ECLI:NL:HR:2013:64"', '>= "2024-01-01"', '<= "2024-12-31"', 'FILTER(?status = "geldend")',
                 f"GRAPH <{kg.GRAAF}>", "DESC(?datum)"):
        assert deel in q, deel
    assert "urn:bwb:" not in q.split("GRAPH", 1)[0]
    assert 'FILTER(?status' not in kb.q_pagina(Zoekvraag(status="alle"), 0, 1)
    assert "ASC(?datum)" in kb.q_pagina(Zoekvraag(volgorde="oudste"), 0, 1)


# ── zoek_standpunten ────────────────────────────────────────────────────────────────────────────────────────────

RIJ = {"id": "kg:202:2025:26", "kenmerk": "KG:202:2025:26", "titel": "Reiskosten vrijwilliger", "status": "geldend",
       "datum": "2025-06-01", "link": "https://kennisgroepen.belastingdienst.nl/publicaties/x/",
       "kennisgroep": "KG Inkomstenbelasting Niet Winst (IB-NW)", "middelen": "Inkomstenbelasting|Inkomstenbelasting (IB)",
       "rubrieken": "Persoonsgebonden aftrek", "vervangt": "", "vervangen_door": "", "herkomsten": "link|tekst"}


def test_zoeken_per_artikel_met_herkomst_en_tekststand():
    graaf = FakeGraph(results=lambda q: _tsv(["inwerking"], ["2026-01-01"]) if "bwb:inwerking" in q else "")
    bron = NepBron([RIJ], per_status={"geldend": 1, "ingetrokken": 2}, per_herkomst={"link": 1, "tekst": 1})
    data = _roep("zoek_standpunten", {"bwb_id": "BWBR0004770", "artikel": "36"}, bron, graaf)
    assert data["status"] == "ok" and data["totaal"] == 1
    [rij] = data["resultaten"]
    assert rij["id"] == "kg:202:2025:26" and rij["label"] == "KG:202:2025:26"
    assert rij["wetsverwijzing"] == "noemt artikel 36 (een link van de Belastingdienst en in de tekst herkend)"
    assert rij["tekststand"] == "eerdere tekst"
    assert rij["reeks"] == ["Persoonsgebonden aftrek"] and "Inkomstenbelasting (IB)" in rij["rechtsgebied"]
    assert data["per_status"] == {"geldend": 1, "ingetrokken": 2} and data["koppelingen"] == {"link": 1, "tekst": 1}
    # In het blok (`kanttekening`), niet alleen voor het model: de lijstroute toont het zonder model (meting vraag 2).
    assert "2 ingetrokken of vervallen standpunten" in data["kanttekening"]
    assert "1 via een link van de Belastingdienst, 1 in de tekst herkend" in data["kanttekening"]
    assert "ten minste" in data["kanttekening"]
    assert bron.vragen[0].status == "geldend", "standaard alleen geldende standpunten (V5)"


def test_niets_gevonden_is_niet_geen_standpunt():
    data = _roep("zoek_standpunten", {"woorden": "zeppelin"}, NepBron([], per_status={}))
    assert data["totaal"] == 0 if "totaal" in data else True
    assert "dat betekent niet dat er geen standpunt is" in data["toelichting"]
    assert "Niet elk standpunt wordt gepubliceerd" in data["kanttekening"]


@pytest.mark.parametrize("args,reden", [
    ({"artikel": "36"}, "ongeldige_argumenten"), ({"bwb_id": "BWBR0004770", "lid": "2"}, "ongeldige_argumenten"),
    ({"bwb_id": "Iw"}, "ongeldig_id"), ({"status": "vervangen"}, "ongeldige_status"),
    ({"noemt": "artikel 36"}, "ongeldig_id"), ({"vanaf": "vorig jaar"}, "ongeldige_datum"),
    ({"woorden": "a b"}, "ongeldige_tekst"), ({"aantal": 99}, "ongeldig_aantal"),
])
def test_invoerfouten_met_een_voorbeeld(args, reden):
    data = _roep("zoek_standpunten", args, NepBron([RIJ]))
    assert data["status"] == "error" and data["reden"] == reden and "bijvoorbeeld" in data["melding"]


def test_noemt_wordt_canoniek():
    bron = NepBron([RIJ])
    _roep("zoek_standpunten", {"noemt": "ecli:nl:hr:2013:64"}, bron)
    _roep("zoek_standpunten", {"noemt": "KG:013:2018:0173"}, bron)
    assert [v.noemt for v in bron.vragen] == ["ECLI:NL:HR:2013:64", "kg:013:2018:173"]


def test_connector_uit():
    data = json.loads(tools.dispatch("zoek_standpunten", None, {"woorden": "loon"}, make_settings()))
    assert data["reden"] == "connector_uit"


# ── get_standpunt ───────────────────────────────────────────────────────────────────────────────────────────────

def test_lezen_geeft_het_stuk_en_de_rijen():
    gelezen = Gelezen(kg.lees_publicatie(_item(22819)), [], [{"soort": "geactualiseerd", "datum": "2026-11-12"}])
    data = _roep("get_standpunt", {"id": "KG:013:2026:4"}, NepBron(gelezen=gelezen))
    assert data["status"] == "ok"
    stuk = data["stuk"]
    assert (stuk["id"], stuk["label"], stuk["status"], stuk["datum"]) == ("kg:013:2026:4", "KG:013:2026:4", "geldend",
                                                                          "2026-11-12")
    assert stuk["vervangt"] == ["kg:013:2018:173"] and "ECLI:NL:HR:2013:64" in stuk["noemt"]
    assert stuk["gebeurtenissen"][0]["soort"] == "geactualiseerd" and len(stuk["bron_hash"]) == 64
    assert data["resultaten"][0]["kop"] == "Aanleiding"


def test_een_ingetrokken_standpunt_zegt_het():
    gelezen = Gelezen(kg.lees_publicatie(_item(4785)), ["kg:070:2024:9"], [])
    data = _roep("get_standpunt", {"id": gelezen.standpunt.kenmerk}, NepBron(gelezen=gelezen))
    assert data["stuk"]["status"] == "ingetrokken" and data["stuk"]["vervangen_door"] == ["kg:070:2024:9"]
    assert "geen geldend beleid" in data["toelichting"] and "KG:070:2024:9" in data["toelichting"]


def test_lezen_vraagt_een_kenmerk():
    data = _roep("get_standpunt", {"id": "ECLI:NL:HR:2013:64"}, NepBron())
    assert data["reden"] == "ongeldig_id"


# ── de bron: index, site, cache ─────────────────────────────────────────────────────────────────────────────────

def _site(teller: list, *, faal: bool = False) -> httpx.Client:
    def antwoord(req: httpx.Request) -> httpx.Response:
        teller.append(str(req.url))
        if faal:
            raise httpx.ConnectError("weg")
        if "search=" in str(req.url):
            return httpx.Response(200, json=[{"id": 22819, "title": {"rendered": "KG:013:2026:4 Aangifte BPM"}},
                                             {"id": 1, "title": {"rendered": "KG:013:2026:44 Iets anders"}}])
        return httpx.Response(200, json=_item(22819))
    return httpx.Client(transport=httpx.MockTransport(antwoord))


def test_het_wp_id_komt_uit_de_index():
    teller: list = []
    graaf = FakeGraph(results=lambda q: _tsv(["wp", "vervangen_door"], ["22819", ""]) if "kgo:id" in q
                      else _tsv(["soort", "datum", "link", "titel"], ["geactualiseerd", "2026-11-12", "https://x", "t"]))
    bron = KennisgroepenBron(client=_site(teller), slaap=lambda _: None)
    g = bron.publicatie(graaf, "kg:013:2026:4")
    assert g.standpunt.id == "kg:013:2026:4" and g.gevalideerd and g.gebeurtenissen[0]["soort"] == "geactualiseerd"
    assert teller == [kg.item_url(22819)]


def test_zonder_index_zoekt_de_bron_het_kenmerk_bij_de_site():
    teller: list = []
    bron = KennisgroepenBron(client=_site(teller), slaap=lambda _: None)
    assert bron.publicatie(None, "kg:013:2026:4").standpunt.wp_id == 22819
    assert "search=KG%3A013%3A2026%3A4" in teller[0]


def test_cache_en_bewaarde_versie_bij_een_storing():
    teller: list = []
    klok = [0.0]
    bron = KennisgroepenBron(client=_site(teller), slaap=lambda _: None, klok=lambda: klok[0])
    graaf = FakeGraph(results=lambda q: _tsv(["wp", "vervangen_door"], ["22819", ""]) if "kgo:id" in q else "")
    bron.publicatie(graaf, "kg:013:2026:4")
    bron.publicatie(graaf, "kg:013:2026:4")
    assert len(teller) == 1, "binnen VERS_S geen tweede verzoek"
    klok[0] = kb.VERS_S + 1
    bron._http = _site(teller, faal=True)
    g = bron.publicatie(graaf, "kg:013:2026:4")
    assert not g.gevalideerd and g.standpunt.id == "kg:013:2026:4"


def test_een_lege_index_is_geen_geen_standpunten():
    graaf = FakeGraph(results=lambda q: "?status\t?n\n" if "COUNT" in q else "?s\n")
    with pytest.raises(KennisgroepenFout) as exc:
        KennisgroepenBron(client=_site([])).zoek(graaf, Zoekvraag(woorden=("loon",)), offset=0, limit=11)
    assert exc.value.code == "geen_index"
    data = json.loads(tools.dispatch("zoek_standpunten", graaf, {"woorden": "loon"}, AAN,
                                     kennisgroepen=KennisgroepenBron(client=_site([]))))
    assert data["reden"] == "bron_onbereikbaar" and "get_standpunt" in data["melding"]


# ── in het antwoord (stap 5) ────────────────────────────────────────────────────────────────────────────────────

def _trace(gelezen) -> list:
    return [("get_standpunt", tools.dispatch("get_standpunt", None, {"id": gelezen.standpunt.kenmerk}, AAN,
                                             kennisgroepen=NepBron(gelezen=gelezen)))]


def test_het_blok_draagt_de_statusregel_uit_de_code():
    from bronmodel.antwoord import Antwoord, antwoord_tekst
    from agent import sjablonen
    from agent.grounding import check_grounding

    trace = _trace(Gelezen(kg.lees_publicatie(_item(22819)), [], []))
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "De Belastingdienst laat de aangifte toe.",
                                          "extern": [{"id": "kg:013:2026:4", "van_nr": 3, "tot_nr": 4}], "twijfel": []},
                      trace)
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert blok.brontype == "standpunt" and blok.kop == "Uit het beleid van de Belastingdienst (kennisgroepstandpunt)"
    assert blok.status_regel == ("Beleid van de Belastingdienst, bindend voor de inspecteur; geen wet en geen rechtspraak. "
                                 "Stand op 12 november 2026.")
    assert blok.status == "geldend" and blok.datum == "2026-11-12"
    Antwoord.model_validate(a.model_dump())
    tekst = antwoord_tekst(a)
    assert tekst.index("*Beleid van de Belastingdienst") < tekst.index('> "')
    assert check_grounding(tekst, trace).grounded


def test_een_ingetrokken_standpunt_in_het_antwoord():
    from bronmodel.antwoord import antwoord_tekst
    from agent import sjablonen

    gelezen = Gelezen(kg.lees_publicatie(_item(4785)), ["kg:070:2024:9"], [])
    a = sjablonen.vul("antwoord_extern", {"kort_antwoord": "Dit standpunt gold vroeger.",
                                          "extern": [{"id": gelezen.standpunt.id, "van_nr": 1, "tot_nr": 1}],
                                          "twijfel": []}, _trace(gelezen))
    blok = next(b for b in a.blokken if b.soort == "extern")
    assert blok.status == "ingetrokken" and blok.vervangen_door == ["kg:070:2024:9"]
    assert "**Dit standpunt is ingetrokken en is geen geldend beleid; ingetrokken door KG:070:2024:9.**" in antwoord_tekst(a)


def test_andere_connectors_houden_hun_blok():
    """Zonder `status_regel` verandert er niets: Kamerstukken krijgt geen regel en geen melding."""
    from bronmodel.connectors import CONNECTORS
    from agent.sjablonen.extern import status_velden

    assert status_velden(CONNECTORS["kamerstukken"], {"datum": "2024-01-01", "status": "opgemaakt"}) == {"status": "opgemaakt"}



# ── na de meting van 14 nov 2026 ────────────────────────────────────────────────────────────────────────────────

def test_een_telvraag_krijgt_de_verdeling_uit_de_index():
    """Vraag 8: zonder verdeling bladerde het model door 93 standpunten en schatte het per belastingsoort."""
    bron = NepBron([RIJ] * 3, per_status={"geldend": 30}, per_belastingsoort={"Inkomstenbelasting (IB)": 20, "AWR": 12})
    data = _roep("zoek_standpunten", {"bwb_id": "BWBR0002320", "aantal": 2}, bron)
    assert data["per_belastingsoort"] == {"Inkomstenbelasting (IB)": 20, "AWR": 12}
    assert "blader daarvoor niet" in data["toelichting"]


def test_de_verdeling_telt_in_de_index_met_de_status():
    q = kb.q_verdeling(Zoekvraag(bwb_id="BWBR0002320"), "belastingsoort")
    assert "COUNT(DISTINCT ?s)" in q and "GROUP BY ?w" in q and 'FILTER(?status = "geldend")' in q
    # Belastingsoort en middel zijn twee indelingen van de site: niet samentellen (meting ronde 2, vraag 8).
    assert "kgo:belastingsoort ?w" in q and "kgo:middel" not in q
    assert "?s kgo:middel ?w" in kb.q_verdeling(Zoekvraag(), "middel")
    assert "kgo:kennisgroep ?w" in kb.q_verdeling(Zoekvraag(), "kennisgroep")


def test_een_niet_gepubliceerd_kenmerk_noemt_zijn_opvolger():
    """Vraag 10: KG:013:2018:0173 staat niet op de site; KG:013:2026:4 trekt het in."""
    data = _roep("get_standpunt", {"id": "KG:013:2018:0173"}, NepBron(opvolgers=[("kg:013:2026:4", "geldend")]))
    assert data["status"] == "error" and data["reden"] == "niet_gevonden"
    assert data["vervangen_door"] == ["kg:013:2026:4"] and "KG:013:2026:4 (geldend)" in data["melding"]
    assert "Woo" in data["melding"]
    zonder = _roep("get_standpunt", {"id": "KG:013:2018:0174"}, NepBron())
    assert zonder["reden"] == "niet_gevonden" and "vervangen_door" not in zonder


def test_de_tekststand_per_genoemd_artikel_komt_uit_de_code():
    """Vraag 13: het model las 1 oktober 2026 als toekomst. De code vergelijkt: tekst van na het standpunt of niet."""
    gelezen = Gelezen(kg.lees_publicatie(_item(22819)), [], [])

    def antwoord(q):
        if "bwb:inwerking" not in q:
            return ""
        return _tsv(["a", "inwerking"], ["urn:bwb:BWBR0005806:artikel:10", "2027-01-01"],
                    ["urn:bwb:BWBR0005806:artikel:6", "2020-01-01"])

    data = _roep("get_standpunt", {"id": "KG:013:2026:4"}, NepBron(gelezen=gelezen), FakeGraph(results=antwoord))
    standen = {t["artikel"]: t["tekststand"] for t in data["stuk"]["tekststanden"]}
    assert standen["10"].startswith("het artikel is gewijzigd na dit standpunt") and "lid" in standen["10"]
    assert standen["6"] == "het artikel is ongewijzigd sinds dit standpunt"
    assert {t["niveau"] for t in data["stuk"]["tekststanden"]} == {"artikel"}, "de graaf kent geen inwerking per lid"
    assert "tekststanden" not in _roep("get_standpunt", {"id": "KG:013:2026:4"}, NepBron(gelezen=gelezen))["stuk"]
