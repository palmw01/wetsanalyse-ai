"""Lex leest begrippen (spoor D, fase F4): herkenning, `search_begrippen`/`get_begrip`, de leesroute en de
kaartacties vanuit het gesprek."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest
from rdflib import Dataset

from agent import tools
from agent.agent import answer_stream
from agent.kaart_beurt import begrip_artefact, kaartactie_uit, kies, termen_uit
from agent.nodes.begrippen_lezen import zoekfilters, zoekterm_uit
from agent.provenance import collect_sources
from agent.tools.begrip_tools import (
    MAX_KANDIDATEN, Q_REGISTER, STATUSSEN, begrens_begrippen_antwoord, dispatch_begrip, is_begrip_leesvraag,
    q_begrippen,
)
from agent.wetsanalyse_api import WetsanalyseApiFout
from fakes import FakeGraph, FakeLLM, agent_ctx, make_settings, response, text_block

API = Path(__file__).resolve().parents[3] / "api" / "app"
WG, WG2 = "wg-termijnen", "wg-invordering"


def run(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def rij(id_, naam, wg=WG, status="concept", **extra):
    return {"id": id_, "naam": naam, "status": status, "werkgebied_id": wg,
            "werkgebied_naam": {WG: "Termijnen", WG2: "Invordering"}[wg], "alternatieve_termen": [],
            "definitie": "", "aantal_dragend": 1, "vervangen_door": None, **extra}


class Port:
    """Nep-api voor `BegripReadApi`: de stand in Postgres en de hashes die de api nu zou projecteren."""

    def __init__(self, rijen, hashes=None, werkgebied_id="", status="ok"):
        self.rijen, self.hashes, self.werkgebied_id, self.status = {r["id"]: r for r in rijen}, hashes or {}, werkgebied_id, status
        self.calls = []

    def verifieer(self, ids, werkgebieden):
        self.calls.append(("verifieer", ids, werkgebieden))
        if self.status != "ok":
            return {"status": self.status, "volledig": False, "reden": "begrippen_api_onbereikbaar"}
        return {"status": "ok", "begrippen": {i: self.rijen.get(i) for i in ids},
                "werkgebieden": {w: {"projectie_hash": self.hashes.get(w)} for w in werkgebieden}}

    def begrip(self, begrip_id):
        self.calls.append(("begrip", begrip_id))
        return {"status": "ok", "werkgebied": {"id": WG, "naam": "Termijnen"},
                "begrip": {"id": begrip_id, "status": "geaccordeerd", "revisie": 4,
                           "inhoud": {"naam": "Termijn", "definitie": "Een tijdvak.", "definitie_herkomst": "geformuleerd",
                                      "voorbeelden": [{"tekst": "zes weken", "oordeel": "wel"}]},
                           "koppelingen": [{"rol": "duiding", "beoordeling": "akkoord", "actualiteit": "actueel",
                                            "bewijs": {"tekst": "zes weken", "klasse": "Tijdsaanduiding",
                                                       "eigenaar_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1",
                                                       "vindplaats": "Artikel 9 · Lid 1"}}]},
                "relaties": [{"type": "hierarchie", "van_naam": "Termijn", "naar_naam": "Betalingstermijn"}]}


def graaf(kandidaten, register):
    """FakeGraph die de kandidaatquery en het register beantwoordt, in TSV zoals de MCP."""
    def antwoord(q):
        if "projectieHash" in q and "Concept" not in q:
            return "?wid\t?hash\n" + "".join(f'"{w}"\t"{h}"\n' for w, h in register.items())
        return "?c\t?wid\n" + "".join(f'<urn:wa:begrip:{i}>\t"{w}"\n' for i, w in kandidaten)
    return FakeGraph(results=antwoord)


# --- herkenning ---------------------------------------------------------------------------------

@pytest.mark.parametrize("vraag", ["welke begrippen hebben we al geaccordeerd?", "toon de begrippen met status concept",
                                   "staat termijn als begrip in het werkgebied?", "welke begrippen kennen we?"])
def test_leesvraag_over_vastgelegde_begrippen(vraag):
    assert is_begrip_leesvraag(vraag)


@pytest.mark.parametrize("vraag", ["welke begrippen zitten in dit werkgebied?", "Stel begrippen voor",
                                   "wat betekent het begrip termijn?", "geef voorbeelden bij het begrip termijn",
                                   "wat zegt artikel 9 lid 1?"])
def test_geen_leesvraag(vraag):
    assert not is_begrip_leesvraag(vraag)


@pytest.mark.parametrize("vraag, verwacht", [
    ("zoek de brondefinitie van termijn", ("brondefinitie", ["termijn"])),
    ("Zoek de brondefinitie van het begrip “belastingschuldige”", ("brondefinitie", ["belastingschuldige"])),
    ("maak de definitie van termijn scherper", ("scherper", ["termijn"])),
    ("geef voorbeelden bij het begrip termijn?", ("voorbeelden", ["termijn"])),
    ("wat is het betekenisverschil tussen termijn en betalingstermijn?", ("betekenisverschil", ["termijn", "betalingstermijn"])),
    ("wat zegt artikel 9?", None),
    ("geef voorbeelden", None),
])
def test_kaartactie_uit(vraag, verwacht):
    assert kaartactie_uit(vraag) == verwacht


def test_de_term_bij_een_gegeven_taak():
    """De supervisor kiest de taak; code leest de term uit de vraag."""
    assert termen_uit("wat is het betekenisverschil met betalingstermijn?", "betekenisverschil") == ["betalingstermijn"]
    assert termen_uit("werk het begrip termijn volledig uit", "brondefinitie") == ["termijn"]
    assert termen_uit("werk het begrip volledig uit", "brondefinitie") == []
    assert termen_uit("zoek de brondefinitie van 'termijn'", "brondefinitie") == ["termijn"]


def test_zoekterm_en_status_uit_de_vraag():
    assert zoekterm_uit("staat het begrip termijn al in het werkgebied?") == "termijn"
    assert zoekterm_uit("staat termijn als begrip vastgelegd?") == "termijn"
    assert zoekterm_uit("welke begrippen zijn er over 'uitstel van betaling'?") == "uitstel van betaling"
    assert zoekterm_uit("welke begrippen hebben we?") == ""
    assert zoekfilters({"question": "welke begrippen zijn al geaccordeerd?"}) == {"limit": 25, "status": ["geaccordeerd"]}


# --- de query tegen de projectie -----------------------------------------------------------------

PROJECTIE = """
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix wa: <urn:wa-ns:> .
<urn:wa:graph:werkgebied:wg-termijnen> {
  <urn:wa:kader:wg-termijnen> a skos:ConceptScheme ; dct:title "Termijnen"@nl ; wa:werkgebiedId "wg-termijnen" ;
      wa:projectieHash "h1" .
  <urn:wa:begrip:b1> a skos:Concept ; skos:inScheme <urn:wa:kader:wg-termijnen> ; skos:prefLabel "Termijn"@nl ;
      skos:altLabel "Tijdvak"@nl ; skos:definition "Een periode waarbinnen betaald moet worden."@nl ; wa:status "geaccordeerd" .
  <urn:wa:begrip:b2> a skos:Concept ; skos:inScheme <urn:wa:kader:wg-termijnen> ; skos:prefLabel "Uitstel van betaling"@nl ;
      wa:status "concept" .
}
<urn:wa:graph:register:begrippen> {
  <urn:wa:kader:wg-termijnen> wa:werkgebiedId "wg-termijnen" ; wa:projectieHash "h1" ; wa:inGraaf <urn:wa:graph:werkgebied:wg-termijnen> .
}
<urn:jas:graph:v2:laag1> { <urn:wa:begrip:vals> a <http://www.w3.org/2004/02/skos/core#Concept> }
"""


def _ids(query: str) -> set[str]:
    ds = Dataset()
    ds.parse(data=PROJECTIE, format="trig")
    return {str(r[0]).removeprefix("urn:wa:begrip:") for r in ds.query(query)}


def test_kandidaatquery_vindt_naam_term_en_definitie_in_de_projectie():
    assert _ids(q_begrippen("termijn", [], "", 50)) == {"b1"}
    assert _ids(q_begrippen("TIJDVAK", [], "", 50)) == {"b1"}
    assert _ids(q_begrippen("betaald", [], "", 50)) == {"b1"}
    assert _ids(q_begrippen("betaling uitstel", [], "", 50)) == {"b2"}
    assert _ids(q_begrippen("", ["concept"], "", 50)) == {"b2"}
    assert _ids(q_begrippen("", [], "wg-anders", 50)) == set()
    # Alleen de begrippengraphs: niets uit een annotatielaag of het register.
    assert _ids(q_begrippen("", [], "", 50)) == {"b1", "b2"}
    ds = Dataset()
    ds.parse(data=PROJECTIE, format="trig")
    assert [(str(a), str(b)) for a, b in ds.query(Q_REGISTER)] == [("wg-termijnen", "h1")]


def test_een_zoekterm_wordt_geen_sparql():
    q = q_begrippen('x") } DROP ALL #', [], "", 50)
    assert '"x\\")"' in q and "DROP ALL" not in q


# --- search_begrippen ----------------------------------------------------------------------------

def test_zoeken_bevestigt_bij_de_api_en_ordent():
    port = Port([rij("b1", "Termijn", status="geaccordeerd"), rij("b3", "Termijn", WG2, status="geaccordeerd"),
                 rij("b2", "Betalingstermijn")], hashes={WG: "h1", WG2: "h2"}, werkgebied_id=WG2)
    g = graaf([("b1", WG), ("b2", WG), ("b3", WG2), ("weg", WG)], {WG: "h1", WG2: "h2"})
    out = json.loads(dispatch_begrip("search_begrippen", {"zoekterm": "termijn"}, g, port))
    assert out["bewijssoort"] == "begrip" and out["status"] == "ok" and out["volledig"] is True
    # Exacte naam vóór "in de naam"; bij gelijke treffer het werkgebied van het gesprek eerst; "weg" bestaat niet meer.
    assert [r["id"] for r in out["resultaten"]] == ["b3", "b1", "b2"]
    assert out["resultaten"][0]["werkgebied"] == "Invordering"
    assert port.calls[0] == ("verifieer", ["b1", "b2", "b3", "weg"], sorted([WG, WG2]))
    assert "geen wettelijke definities" in out["toelichting"]


def test_status_telt_zoals_de_api_hem_nu_kent():
    port = Port([rij("b1", "Termijn", status="vervangen", vervangen_door={"begrip_id": "b9", "naam": "Termijn"})])
    out = json.loads(dispatch_begrip("search_begrippen", {"status": ["geaccordeerd"]}, graaf([("b1", WG)], {}), port))
    assert out["resultaten"] == []          # de graaf zei nog geaccordeerd, de api zegt vervangen
    out = json.loads(dispatch_begrip("search_begrippen", {}, graaf([("b1", WG)], {}), port))
    assert out["resultaten"][0]["vervangen_door"] == {"begrip_id": "b9", "naam": "Termijn"}


def test_een_te_herbeoordelen_begrip_draagt_dat_mee():
    port = Port([rij("b1", "Termijn", status="geaccordeerd", herbeoordelen=2), rij("b2", "Uitstel", herbeoordelen=0)])
    out = json.loads(dispatch_begrip("search_begrippen", {}, graaf([("b1", WG), ("b2", WG)], {}), port))
    per = {r["id"]: r for r in out["resultaten"]}
    assert per["b1"]["herbeoordelen"] == 2 and "herbeoordelen" not in per["b2"]
    from agent.prompts import SYSTEM_PROMPT
    assert "`herbeoordelen`" in SYSTEM_PROMPT, "de prompt zegt Lex wat hij ermee doet"


def test_een_achterlopende_projectie_is_onvolledig():
    port = Port([rij("b1", "Termijn")], hashes={WG: "nieuw"})
    out = json.loads(dispatch_begrip("search_begrippen", {}, graaf([("b1", WG)], {WG: "oud"}), port))
    assert out["status"] == "partial" and out["volledig"] is False and "achterstand" in out
    # Een werkgebied zonder graph (nog nooit geprojecteerd) dat de vrager opende telt ook.
    port = Port([], hashes={WG: "h"}, werkgebied_id=WG)
    out = json.loads(dispatch_begrip("search_begrippen", {}, graaf([], {}), port))
    assert out["volledig"] is False and port.calls[0][2] == [WG]


def test_storingen_zijn_nooit_een_lege_lijst():
    def kapot(q):
        raise RuntimeError("graaf weg")
    out = json.loads(dispatch_begrip("search_begrippen", {}, FakeGraph(results=kapot), Port([])))
    assert out["status"] == "unavailable" and out["volledig"] is False
    out = json.loads(dispatch_begrip("search_begrippen", {}, graaf([("b1", WG)], {}), Port([], status="unavailable")))
    assert out["status"] == "unavailable"
    assert "niet betrouwbaar" in begrens_begrippen_antwoord("Er zijn geen begrippen.", [("search_begrippen", json.dumps(out))])
    assert "niet in de vastgelegde begrippen gezocht" in begrens_begrippen_antwoord("x", [])


def test_ongeldige_argumenten():
    for args in ({"status": ["onbekend"]}, {"limit": 0}, {"limit": MAX_KANDIDATEN + 1}, {"user_id": "x"}):
        out = json.loads(tools.dispatch("search_begrippen", FakeGraph(), args, begrippen=Port([])))
        assert out["status"] == "invalid_request", args


def test_get_begrip_compact_en_geen_bron():
    raw = tools.dispatch("get_begrip", FakeGraph(), {"begrip_id": "b1"}, begrippen=Port([]))
    out = json.loads(raw)
    assert out["begrip_status"] == "geaccordeerd" and out["werkgebied"] == "Termijnen"
    assert out["passages"][0]["vindplaats"] == "Artikel 9 · Lid 1"
    assert out["relaties"] == [{"type": "hierarchie", "van": "Termijn", "naar": "Betalingstermijn"}]
    # Een begrip is geen vindplaats: de passage-IRI's tellen niet als bron.
    assert collect_sources([("get_begrip", raw)]) == []


# --- contract met de api -------------------------------------------------------------------------

def test_contract_met_de_api():
    bron = (API / "begrip_contracts.py").read_text(encoding="utf-8")
    status = re.search(r"class BegripStatus\(str, Enum\):(.*?)\n\n", bron, re.S).group(1)
    assert set(re.findall(r'= "(\w+)"', status)) == set(STATUSSEN)
    verificatie = re.search(r"class BegripVerificatie\(BaseModel\):(.*?)(\n\n\n|\Z)", bron, re.S).group(1)
    assert f"max_length={MAX_KANDIDATEN}" in verificatie
    gesprek = (API / "gesprek_contracts.py").read_text(encoding="utf-8")
    assert '"begrip_id"' in gesprek          # het artefact van een kaartactie
    assert set(begrip_artefact(WG, "b1", "Termijn", "k", "voorbeelden")["ref"]) == {
        "werkgebied_id", "begrip_id", "kaart_run_id", "actie"}


# --- de leesroute ----------------------------------------------------------------------------------

def test_leesroute_zoekt_eerst_en_noemt_het_werkgebied_van_het_gesprek():
    llm = FakeLLM([response([text_block("Termijn (geaccordeerd, werkgebied Termijnen).")], "end_turn")])
    port = Port([rij("b1", "Termijn", status="geaccordeerd")], hashes={WG: "h1"}, werkgebied_id=WG)
    events = run(answer_stream("welke begrippen hebben we al geaccordeerd?", llm=llm,
                               graph=graaf([("b1", WG)], {WG: "h1"}), begrippen=port, werkgebied_id=WG,
                               settings=make_settings(), run_id="r1"))
    assert not [e for e in events if e["type"] == "error"], events
    trace = [e for e in events if e["type"] == "tool_execution"]
    assert trace[0]["tool"] == "search_begrippen" and trace[0]["actie"] == "begrippen_lezen"
    assert trace[-1]["aantal"] == 1
    assert port.calls[0][0] == "verifieer" and WG in port.calls[0][2]
    antwoord = " ".join(e.get("content", "") for e in events if e["type"] == "token")
    assert "Termijn" in antwoord and "niet in de vastgelegde begrippen gezocht" not in antwoord
    # Het model kreeg alleen de leestools, niet de annotatieschrijvers.
    namen = {t["name"] for t in llm.calls[0]["tools"]}
    assert {"search_begrippen", "get_begrip"} <= namen and "search_annotaties" not in namen


def test_leesroute_meldt_een_storing_eerlijk():
    llm = FakeLLM([response([text_block("Er zijn geen begrippen.")], "end_turn")])
    events = run(answer_stream("welke begrippen kennen we?", llm=llm, graph=graaf([("b1", WG)], {}),
                               begrippen=Port([], status="unavailable"), settings=make_settings()))
    antwoord = " ".join(e.get("content", "") for e in events if e["type"] == "token")
    assert "betekent niet" in antwoord and "Er zijn geen begrippen." not in antwoord


# --- kaartacties vanuit het gesprek -----------------------------------------------------------------

def test_kies_exact_eigen_werkgebied_vervangen():
    rijen = [rij("b1", "Termijn"), rij("b3", "Termijn", WG2)]
    assert kies("termijn", rijen, WG)[0]["id"] == "b1"
    gekozen, zin = kies("termijn", rijen, "")
    assert gekozen is None and "Termijnen" in zin and "Invordering" in zin
    gekozen, zin = kies("termijn", [rij("b1", "Termijn", status="vervangen",
                                        vervangen_door={"begrip_id": "b2", "naam": "Termijn (nieuw)"})], WG)
    assert gekozen is None and "Termijn (nieuw)" in zin
    assert kies("tijdvak", [rij("b1", "Termijn", alternatieve_termen=["Tijdvak"])], "")[0]["id"] == "b1"
    assert kies("term", [rij("b1", "Termijn")], "") == (None, "")      # alleen exact


class KaartApi:
    def __init__(self, rijen, start=None, standen=(), begrip=None):
        self.rijen, self.start, self.standen, self.begrip = rijen, start, list(standen), begrip
        self.calls = []

    async def zoek_begrippen(self, q, eerst=""):
        self.calls.append(("zoek", q, eerst))
        return {"resultaten": [r for r in self.rijen if q.casefold() in r["naam"].casefold()]}

    async def haal_begrip(self, wid, bid):
        if self.begrip is None:
            raise WetsanalyseApiFout("404", 404, "")
        return self.begrip

    async def haal_werkgebied(self, wid):
        return {"id": wid, "naam": "Invordering"}

    async def start_kaart_run(self, wid, bid, actie, ander=None):
        self.calls.append(("start", wid, bid, actie, ander))
        if isinstance(self.start, Exception):
            raise self.start
        return self.start or {"id": "k1", "status": "wacht", "nieuw": True}

    async def haal_kaartrun_stand(self, wid, bid, rid):
        return self.standen.pop(0)

    async def haal_relaties(self, wid, bid=""):
        return {"relaties": [{"id": "x1", "van_naam": "Termijn", "naar_naam": "Betalingstermijn", "type": "hierarchie",
                              "beoordeling": "akkoord"}],
                "voorstellen": [{"id": "R1", "van_naam": "Termijn", "naar_naam": "Aanslag", "type": "kwalificatie"}]}

    async def aclose(self):
        pass


async def _stroom(wid, bid, rid, run, **_):
    yield {"type": "status", "message": "Lex · Voorbeelden voor “Termijn”"}
    yield {"type": "opgeslagen", "kaart_run": rid, "voorstellen": 2, "melding": ""}
    yield {"type": "done"}


@pytest.fixture(autouse=True)
def _nep_kaartrun(monkeypatch):
    from agent import kaart_beurt as kb
    monkeypatch.setattr(kb, "kaart_stroom", _stroom)
    monkeypatch.setattr(kb, "PEIL_S", 0)


def _taak(api, taak, vraag="", wg=WG, **invoer):
    from agent.agents import begrippen as ba, register
    params = {**register.parameters("begrippen", taak, vraag=vraag, werkgebied_id=wg or ""), **invoer}
    return asyncio.run(ba.voer_uit(register.invoer("begrippen", taak, params), agent_ctx(api)))


def test_kaartactie_start_de_kaartrun_en_wijst_naar_het_begrip():
    api = KaartApi([rij("b1", "Termijn")])
    uit = _taak(api, "voorbeelden", "geef voorbeelden van termijn")
    assert ("start", WG, "b1", "voorbeelden", None) in api.calls
    assert uit.artefact == {"soort": "begrip", "titel": "Termijn", "ref": {
        "werkgebied_id": WG, "begrip_id": "b1", "kaart_run_id": "k1", "actie": "voorbeelden"}}
    assert "2 voorstellen staan bij de voorbeelden" in uit.tekst and uit.status == "ok"
    # Spoor I7: Lex noemt het volgende logische stuk.
    assert uit.tekst.endswith("Daarna kan ik relaties met andere begrippen voorstellen.")


def test_het_aangewezen_begrip_gaat_voor_de_term():
    api = KaartApi([rij("b2", "Betalingstermijn")],
                   begrip={"status": "concept", "inhoud": {"naam": "Termijn", "definitie": ""}})
    _taak(api, "betekenisverschil", "wat is het betekenisverschil met betalingstermijn?", begrip_id="b1")
    assert ("start", WG, "b1", "betekenisverschil", "b2") in api.calls


def test_betekenisverschil_vergelijkt_binnen_een_werkgebied():
    api = KaartApi([rij("b1", "Termijn"), rij("b2", "Betalingstermijn")])
    _taak(api, "betekenisverschil", "wat is het betekenisverschil tussen termijn en betalingstermijn?")
    assert ("start", WG, "b1", "betekenisverschil", "b2") in api.calls
    api = KaartApi([rij("b1", "Termijn"), rij("b2", "Betalingstermijn", WG2)])
    uit = _taak(api, "betekenisverschil", "wat is het betekenisverschil tussen termijn en betalingstermijn?", wg="")
    assert uit.status == "geweigerd" and "verschillende werkgebieden" in uit.reden


def test_twee_kandidaten_een_vraag_en_geen_start():
    api = KaartApi([rij("b1", "Termijn"), rij("b3", "Termijn", WG2)])
    uit = _taak(api, "brondefinitie", "zoek de brondefinitie van het begrip termijn", wg=None)
    assert not [c for c in api.calls if c[0] == "start"]
    assert uit.status == "geweigerd" and uit.artefact is None and "welk werkgebied" in uit.reden


def test_geen_begrip_is_een_vraag_van_lex():
    uit = _taak(KaartApi([]), "brondefinitie", "zoek de brondefinitie van het begrip invorderingsrente")
    assert uit.status == "geweigerd" and "geen vastgelegd begrip" in uit.reden
    uit = _taak(KaartApi([]), "brondefinitie", "zoek de brondefinitie")
    assert uit.status == "geweigerd" and "Over welk begrip" in uit.reden


def test_een_weigering_van_de_api_is_een_antwoord():
    api = KaartApi([rij("b1", "Termijn")], start=WetsanalyseApiFout("409", 409, "geen_definitie"))
    uit = _taak(api, "voorbeelden", "geef voorbeelden van termijn")
    assert uit.status == "geweigerd" and "geef het begrip eerst een definitie" in uit.reden


def test_loopt_de_actie_al_dan_wacht_lex():
    api = KaartApi([rij("b1", "Termijn")], start={"id": "k0", "status": "loopt", "nieuw": False},
                   standen=[{"status": "loopt"}, {"status": "klaar", "melding": ""}])
    uit = _taak(api, "voorbeelden", "geef voorbeelden van termijn")
    assert uit.artefact["ref"]["kaart_run_id"] == "k0" and "al gedaan" in uit.tekst


def test_uitwerken_volgt_de_methode():
    # Zonder definitie: eerst de brondefinitie, dan een definitievoorstel, en nog geen voorbeelden.
    api = KaartApi([], start={"id": "k1", "status": "klaar", "nieuw": False},
                   begrip={"status": "concept", "inhoud": {"naam": "Termijn", "definitie": ""}})
    uit = _taak(api, "uitwerken", begrip_id="b1")
    assert [c[3] for c in api.calls if c[0] == "start"] == ["brondefinitie", "scherper"]
    assert "neem een definitie over" in uit.tekst
    # Met een definitie op de kaart (spoor I2): de brondefinitie, de uitleg in B1 en de voorbeelden.
    api = KaartApi([], begrip={"status": "concept", "inhoud": {"naam": "Termijn", "definitie": "Een tijdvak."}})
    uit = _taak(api, "uitwerken", begrip_id="b1")
    assert [c[3] for c in api.calls if c[0] == "start"] == ["brondefinitie", "uitleg", "voorbeelden"]
    assert "Nog open: neem de uitleg en de voorbeelden over" in uit.tekst
    # Staat er al een uitleg, dan schrijft Lex er geen nieuwe.
    api = KaartApi([], begrip={"status": "concept", "inhoud": {"naam": "Termijn", "definitie": "Een tijdvak.",
                                                                "uitleg": "Zo lang heb je."}})
    _taak(api, "uitwerken", begrip_id="b1")
    assert [c[3] for c in api.calls if c[0] == "start"] == ["brondefinitie", "voorbeelden"]


def test_relaties_zonder_model():
    api = KaartApi([], begrip={"status": "concept", "inhoud": {"naam": "Termijn"}})
    uit = _taak(api, "relaties", begrip_id="b1")
    assert "*Termijn* is een soort van *Betalingstermijn*" in uit.tekst and "Ik stel 1 relatie voor" in uit.tekst
    assert uit.voorstellen == ["R1"] and uit.meting["model"] is False
