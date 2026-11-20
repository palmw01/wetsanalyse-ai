"""Lex leest de afleidingsregels (regels herleidbaar, 20 nov 2026, stap 7): zoeken en lezen bij de api, alleen lezen,
afgeleide duiding (nooit grounding), en de regels in het dossier van het gesprek. Zonder regels is het dossier gelijk."""
from __future__ import annotations

import json

import httpx

from agent import tools
from agent.regel_read import RegelReadApi
from agent.tools.begrip_tools import AFGELEIDE_TOOL_NAMEN
from agent.tools.regel_tools import REGEL_TOOL_NAMEN, compact_regel, dispatch_regel
from agent.werkgebied_context import context_tekst
from fakes import make_settings

WG = {"naam": "Termijnen", "analysevraag": "Wanneer is een aanslag invorderbaar?"}

REGEL = {
    "id": "r1", "werkgebied_id": "w1", "status": "concept", "revisie": 3, "naam": "bepalen van de vervaldag",
    "uitvoer": "vervaldag", "begrippen": {"d": {"naam": "dagtekening van het aanslagbiljet"}},
    "inhoud": {"soort": "rekenregel", "brontype": "wet", "invoer": [{"begrip_id": "d", "rol": "invoer"}],
               "voorbeelden": [{"geval": "lid 1", "invoer": "dagtekening 10-05-2026", "uitkomst": "21-06-2026",
                                "oordeel": "juist", "waarden": [{"begrip_id": "d", "waarde": "10-05-2026"}]}]},
    "regeltekst": {"tekst": "De vervaldag …", "gevallen": [{"label": "lid 1", "tekst": "zes weken na …"}]},
    "dragers": [{"rol": "grondslag", "geval": "lid 1", "beoordeling": "akkoord", "actualiteit": "actueel",
                 "bewijs": {"tekst": "invorderbaar zes weken na de dagtekening van het aanslagbiljet",
                            "klasse": "Afleidingsregel", "eigenaar_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1",
                            "vindplaats": "Invorderingswet 1990 – Artikel 9, Lid 1"},
                 "bron": {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "soort": "jci",
                          "jci": "jci1.3:c:BWBR0004770&artikel=9&lid=1"}},
                {"rol": "context", "geval": "lid 5", "beoordeling": "akkoord", "bewijs": {"tekst": "x"},
                 "bron": {"bron_iri": "urn:bwb:BWBR0024096:id:x", "soort": "anker", "bron_url": "https://wetten.example/x"}}],
    "accorderen": {"mag": False, "redenen": ["…"]}, "signalen": [], "gaten": [{"code": "x", "tekst": "Een gat."}],
}


def test_de_regeltools_zijn_afgeleide_duiding_en_staan_in_de_toollaag():
    assert REGEL_TOOL_NAMEN <= AFGELEIDE_TOOL_NAMEN
    assert REGEL_TOOL_NAMEN <= {t["name"] for t in tools.TOOLS}


def test_get_regel_noemt_per_drager_de_weg_naar_de_wettekst():
    uit = compact_regel({**REGEL, "status": "concept"})
    [grond, ctx] = uit["dragers"]
    assert grond["jci"] == "jci1.3:c:BWBR0004770&artikel=9&lid=1" and grond["vindplaats"].endswith("Lid 1")
    assert ctx["anker"] == "https://wetten.example/x" and "jci" not in ctx
    assert uit["voorbeelden"][0]["waarden"] == [{"begrip": "dagtekening van het aanslagbiljet", "waarde": "10-05-2026"}]
    assert uit["regel_status"] == "concept" and uit["gaten"] == ["Een gat."]


class _Port:
    werkgebied_id = "w1"

    def __init__(self):
        self.gevraagd = []

    def zoek(self, q, status, wg):
        self.gevraagd.append(("zoek", q, status, wg))
        return {"status": "ok", "resultaten": [{"id": "r1", "naam": "bepalen van de vervaldag", "status": "concept",
                                                "werkgebied_id": "w1", "regeltekst": "De vervaldag …"}],
                "per_status": {"concept": 1}}

    def regel(self, wg, rid):
        self.gevraagd.append(("regel", wg, rid))
        return {"status": "ok", "regel": REGEL}


def test_zoeken_gebruikt_het_werkgebied_van_het_gesprek():
    port = _Port()
    uit = json.loads(dispatch_regel("search_regels", {"zoekterm": "vervaldag"}, port))
    assert uit["bewijssoort"] == "regel" and uit["aantal"] == 1 and port.gevraagd[0] == ("zoek", "vervaldag", [], "w1")
    uit = json.loads(dispatch_regel("get_regel", {"werkgebied_id": "w1", "regel_id": "r1"}, port))
    assert uit["id"] == "r1" and port.gevraagd[1] == ("regel", "w1", "r1")
    assert json.loads(dispatch_regel("search_regels", {}, None))["reden"] == "regels_api_niet_ingesteld"


def test_de_leesclient_vraagt_alleen_lezen_bij_de_api():
    gezien = []

    def api(req: httpx.Request) -> httpx.Response:
        gezien.append((req.method, req.url.path, dict(req.url.params)))
        return httpx.Response(200, json={"resultaten": []} if req.url.path == "/v1/regels" else REGEL)

    s = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t")
    port = RegelReadApi(s, "jurist", "w1", transport=httpx.MockTransport(api))
    assert port.zoek("x", ["concept"], "w1")["status"] == "ok"
    gelezen = port.regel("w1", "r1")
    assert gelezen["status"] == "ok" and gelezen["regel"]["status"] == "concept"
    assert [g[:2] for g in gezien] == [("GET", "/v1/regels"), ("GET", "/v1/werkgebieden/w1/regels/r1")]
    assert gezien[0][2] == {"q": "x", "status": "concept", "werkgebied_id": "w1"}
    assert RegelReadApi(s, "", "w1").zoek("x", [], "")["reden"] == "regels_gebruikerscontext_ontbreekt"


def test_de_regels_staan_in_het_dossier_en_zonder_regels_is_het_gelijk():
    assert context_tekst(WG) == context_tekst({**WG, "regels": {"telling": {}, "regels": [], "afgekapt": 0}})
    tekst = context_tekst({**WG, "regels": {"regels": [{"id": "r1", "naam": "bepalen van de vervaldag",
                                                        "status": "concept"}], "afgekapt": 2}})
    assert "Afleidingsregels (analyse-uitkomsten; lees een regel met get_regel):" in tekst
    assert "- bepalen van de vervaldag (concept) [r1]" in tekst and "(en 2 meer)" in tekst
