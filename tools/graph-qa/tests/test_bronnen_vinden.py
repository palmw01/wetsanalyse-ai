"""Bronnen vinden met Lex (spoor D, fase A): de ontdekmethoden, de functie van een verwijzing, de run
en de bronnenroute in het gesprek.

Bewaakt:
1. de functie van een verwijzing per patroon, op letterlijke formuleringen;
2. per methode: rol, bewijs, wat al in de selectie staat valt weg, het plafond geeft `volledig: false`,
   een falende methode laat de rest staan;
3. de uitkomst past in het api-contract (`api/app/bronnen_run_contracts.py`, uit de bron gelezen);
4. het verloop van run en route tegen een nep-api, en de grens met de overzichtsvraag.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

from agent import bronnen_run, bronnen_vinden, overzicht
from agent.bronnen_run import bronnen_artefact, is_bronnenvraag, samenvatting
from agent.bronnen_vinden import vind, verwijzingsfunctie
from agent.models import ChatRequest
from agent.runstore import Run
from fakes import FakeGraph, make_settings

IW = "urn:bwb:BWBR0004770"
ART9, L1 = f"{IW}:artikel:9", f"{IW}:artikel:9:lid:1"
ART8, ART10, ART2K = f"{IW}:artikel:8", f"{IW}:artikel:10", f"{IW}:artikel:2:lid:1:o:k"
AWR = "urn:bwb:BWBR0002320:artikel:11"
H2 = f"{IW}:hoofdstuk:II"


# --- 1. de functie van een verwijzing ------------------------------------------------------------

@pytest.mark.parametrize("tekst, anker, functie", [
    ("In afwijking van artikel 9, eerste lid, is een belastingaanslag direct invorderbaar.", "artikel 9", "uitzondering"),
    ("Met uitzondering van artikel 10 is deze afdeling van toepassing.", "artikel 10", "uitzondering"),
    ("Bij ministeriële regeling kunnen regels worden gesteld omtrent de toepassing van artikel 9.", "artikel 9", "delegatie"),
    ("De belastingaanslag, bedoeld in artikel 11 van de Algemene wet inzake rijksbelastingen, wordt ...",
     "artikel 11 van de Algemene wet inzake rijksbelastingen", "toepassing"),
    ("Artikel 8 is van overeenkomstige toepassing.", "Artikel 8", "onbekend"),
    ("De ontvanger stelt de belastingschuldige in kennis.", "artikel 9", "onbekend"),
])
def test_de_functie_van_een_verwijzing(tekst, anker, functie):
    assert verwijzingsfunctie(tekst, anker) == functie


def test_een_verwijzing_uit_een_definitie_is_een_definitie():
    assert verwijzingsfunctie("belastingaanslag: aanslag als bedoeld in artikel 11", "artikel 11", definieert=True) == "definitie"


# --- 2. de methoden --------------------------------------------------------------------------------

def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


UITGAAND = _tsv(["kern", "vanuit", "tekst", "anker", "naar", "label", "def"], [
    [ART9, L1, "In afwijking van artikel 8 is een belastingaanslag invorderbaar.", "artikel 8", ART8, "Artikel 8", ""],
    [ART9, L1, "De aanslag, bedoeld in artikel 11 AWR, wordt ...", "artikel 11 AWR", AWR, "Artikel 11", ""],
    [ART9, L1, "Zie lid 1.", "lid 1", L1, "Lid 1", ""],                          # binnen de kern: weg
])
INKOMEND = _tsv(["kern", "doel", "bron", "tekst", "anker", "label", "def"], [
    [ART9, L1, ART10, "Artikel 9 is van toepassing.", "Artikel 9", "Artikel 10", ""],
])
TEKSTEN = _tsv(["kern", "deel", "tekst"], [
    [ART9, L1, "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."],
])
DEFINITIES = _tsv(["node", "begrip", "label"], [
    [ART2K, "belastingaanslag", "Onderdeel k"], [f"{IW}:artikel:2:lid:1:o:i", "belastingschuldige", "Onderdeel i"],
])
OPBOUW = _tsv(["kern", "artikel", "ouder", "buur", "label"], [
    [ART9, ART9, H2, ART8, "Artikel 8"], [ART9, ART9, H2, ART10, "Artikel 10"],
])


class Graaf(FakeGraph):
    def __init__(self, faal: str = "", **vervang: str) -> None:
        super().__init__(results=self._antwoord)
        self.faal, self.vervang = faal, vervang

    def _antwoord(self, q: str) -> str:
        if "bwb:opschrift" in q:                                   # regelingnamen
            return _tsv(["r", "citeertitel", "opschrift"], [["urn:bwb:BWBR0002320", "Algemene wet inzake rijksbelastingen", ""]])
        soort = ("uitgaand" if "?vanuit bwb:heeftVerwijzing" in q else "inkomend" if "?bron bwb:heeftVerwijzing" in q
                 else "definities" if "?node bwb:definieertBegrip" in q else "opbouw" if "?buur a bwb:Artikel" in q
                 else "teksten" if "?deel bwb:tekst ?tekst" in q else "")
        if not soort:
            raise AssertionError(f"onverwachte query: {q[:200]}")
        if soort == self.faal:
            raise RuntimeError("graaf hapert")
        return self.vervang.get(soort) or {"uitgaand": UITGAAND, "inkomend": INKOMEND, "definities": DEFINITIES,
                                           "opbouw": OPBOUW, "teksten": TEKSTEN}[soort]


INVOER = {"naam": "Invorderbaarheid", "analysevraag": "Wanneer is een belastingaanslag invorderbaar?",
          "kern": [{"bron_iri": ART9, "label": "Artikel 9", "bwb_id": "BWBR0004770", "bereik": "onderliggend"}],
          "context": []}


@pytest.fixture
def geen_overzicht(monkeypatch):
    monkeypatch.setattr(overzicht, "bouw_overzicht", lambda *_a, **_k: {"volledig": True, "regelingen": [],
                                                                         "onderwerp_tekst": "invorderbaar"})


def _per_iri(uit: dict) -> dict:
    return {k["bron_iri"]: k for k in uit["kandidaten"]}


ALLE = ("overzicht", "verwijzing_uit", "verwijzing_in", "definitie", "opbouw")


def test_de_standaard_volgt_de_meting():
    assert bronnen_vinden.standaard_voor(INVOER) == ("verwijzing_uit", "definitie", "opbouw")
    assert bronnen_vinden.standaard_voor({**INVOER, "kern": []}) == ("overzicht",)


def test_elke_methode_levert_kandidaten_met_bewijs(geen_overzicht):
    uit = vind(Graaf(), INVOER, methoden=ALLE)
    k = _per_iri(uit)
    assert L1 not in k and ART9 not in k                                    # in de selectie: weg
    # Artikel 8: verwezen met "in afwijking van" (afhankelijkheid) én in hetzelfde deel (aanverwant).
    assert k[ART8]["rol"] == "afhankelijkheid"
    assert {b["methode"] for b in k[ART8]["bewijs"]} == {"verwijzing_uit", "opbouw"}
    assert next(b for b in k[ART8]["bewijs"] if b["methode"] == "verwijzing_uit")["detail"]["functie"] == "uitzondering"
    assert k[AWR]["rol"] == "afhankelijkheid" and k[AWR]["bwb_id"] == "BWBR0002320"
    # Een leesbare vindplaats met de regeling, niet het kale label uit de graaf.
    assert k[AWR]["label"] == "Artikel 11 – Algemene wet inzake rijksbelastingen"
    assert k[ART2K]["label"].startswith("Artikel 2, lid 1, onderdeel k")
    # Artikel 10 verwijst naar de kern én staat in hetzelfde deel: aanverwant.
    assert k[ART10]["rol"] == "aanverwant" and len(k[ART10]["bewijs"]) == 2
    # Alleen de definitie van een term die letterlijk in de kern staat.
    assert k[ART2K]["rol"] == "afhankelijkheid" and k[ART2K]["bewijs"][0]["detail"] == {"begrip": "belastingaanslag"}
    assert f"{IW}:artikel:2:lid:1:o:i" not in k
    assert all(m["volledig"] for m in uit["meting"].values())
    assert set(uit["meting"]) == set(ALLE)
    # Sterkste rol eerst.
    assert [x["rol"] for x in uit["kandidaten"]] == sorted((x["rol"] for x in uit["kandidaten"]),
                                                           key=bronnen_vinden.ROL_VOLGORDE.get)


def test_het_overzicht_levert_kernbepalingen(monkeypatch):
    ov = {"volledig": True, "onderwerp_tekst": "invorderbaar", "regelingen": [
        {"delen": [{"bepalingen": [{"iri": ART8, "label": "Artikel 8", "naam": "art. 8"},
                                   {"iri": ART9, "label": "Artikel 9", "naam": "art. 9"}]}], "ook_genoemd": []}]}
    gevraagd = {}
    monkeypatch.setattr(overzicht, "bouw_overzicht", lambda g, vraag, **kw: gevraagd.update(vraag=vraag, **kw) or ov)
    uit = vind(Graaf(), INVOER, methoden=("overzicht",))
    assert gevraagd["vraag"] == INVOER["analysevraag"]
    # Geen onderwerp in "Wanneer is … invorderbaar?": de naam van het werkgebied is het onderwerp.
    assert gevraagd["onderwerp"] == "Invorderbaarheid"
    assert _per_iri(uit)[ART8]["rol"] == "kern" and ART9 not in _per_iri(uit)
    vind(Graaf(), {**INVOER, "analysevraag": "Welke artikelen gaan over invorderingsrente?"}, methoden=("overzicht",))
    assert gevraagd["onderwerp"] == "invorderingsrente"


@pytest.mark.parametrize("vraag, onderwerp", [
    ("Wanneer is een aanslag invorderbaar?", "een aanslag invorderbaar"),
    ("Wie is de belastingschuldige?", "de belastingschuldige"),
    ("Onder welke voorwaarden kan uitstel worden verleend?", "uitstel worden verleend"),
    ("Welke artikelen gaan over invorderingsrente?", "invorderingsrente"),
    ("Wat?", ""),
])
def test_het_onderwerp_van_een_deelvraag(vraag, onderwerp):
    assert bronnen_vinden.onderwerp_van_deelvraag(vraag) == onderwerp


def test_met_deelvragen_zoekt_lex_ook_per_deelvraag(monkeypatch):
    dv = [{"id": "d1", "vraag": "Wanneer is een aanslag invorderbaar?"}, {"id": "d2", "vraag": "Wat?"}]
    assert bronnen_vinden.standaard_voor({**INVOER, "deelvragen": dv})[-1] == "deelvraag"
    assert bronnen_vinden.standaard_voor({**INVOER, "kern": [], "deelvragen": dv}) == ("overzicht", "deelvraag")
    ov = {"volledig": True, "onderwerp_tekst": "aanslag invorderbaar", "regelingen": [
        {"delen": [{"bepalingen": [{"iri": ART8, "label": "Artikel 8"}, {"iri": ART9, "label": "Artikel 9"}]}],
         "ook_genoemd": [{"iri": ART10, "label": "Artikel 10"}]}]}
    gevraagd: list[str] = []
    monkeypatch.setattr(overzicht, "bouw_overzicht", lambda g, vraag, **kw: gevraagd.append(kw["onderwerp"]) or ov)
    uit = vind(Graaf(), {**INVOER, "deelvragen": dv}, methoden=("deelvraag",))
    assert gevraagd == ["een aanslag invorderbaar"], "een deelvraag zonder onderwerp zoekt niets"
    k = _per_iri(uit)
    # Met een kern: aanverwant, met de deelvraag in het bewijs; de selectie zelf valt weg.
    assert ART9 not in k and k[ART8]["rol"] == "aanverwant"
    assert k[ART8]["bewijs"][0]["detail"] == {"deelvraag_id": "d1", "vraag": dv[0]["vraag"],
                                              "onderwerp": "aanslag invorderbaar"}
    assert uit["meting"]["deelvraag"] == {"aantal": 2, "volledig": True, "ms": uit["meting"]["deelvraag"]["ms"]}
    # Zonder kern: kern, en het plafond per deelvraag maakt de methode onvolledig.
    monkeypatch.setattr(bronnen_vinden, "MAX_PER_DEELVRAAG", 1)
    uit = vind(Graaf(), {**INVOER, "kern": [], "deelvragen": dv}, methoden=("deelvraag",))
    assert [x["rol"] for x in uit["kandidaten"]] == ["kern"] and uit["meting"]["deelvraag"]["volledig"] is False


def test_een_geraakt_plafond_is_onvolledig(geen_overzicht, monkeypatch):
    monkeypatch.setattr(bronnen_vinden, "MAX_PER_METHODE", 1)
    uit = vind(Graaf(), INVOER, methoden=("verwijzing_uit",))
    assert uit["meting"]["verwijzing_uit"]["volledig"] is False


def test_een_falende_methode_laat_de_rest_staan(geen_overzicht):
    uit = vind(Graaf(faal="inkomend"), INVOER, methoden=ALLE)
    assert (uit["meting"]["verwijzing_in"]["aantal"], uit["meting"]["verwijzing_in"]["volledig"]) == (0, False)
    assert ART8 in _per_iri(uit)


def test_zonder_kern_alleen_het_overzicht(geen_overzicht):
    g = Graaf()
    uit = vind(g, {**INVOER, "kern": []})
    assert uit["kandidaten"] == [] and g.queries == []


# --- 3. het api-contract ----------------------------------------------------------------------------

def test_de_uitkomst_past_in_het_api_contract(geen_overzicht):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
    try:
        from app.bronnen_run_contracts import BronnenUitkomst
        from app.gesprek_contracts import Artefact
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    uit = vind(Graaf(), INVOER)
    BronnenUitkomst(invoer_id="I1", **uit)
    # De methode deelvraag kent de api ook.
    BronnenUitkomst(invoer_id="I1", kandidaten=[{"bron_iri": ART8, "rol": "aanverwant", "bewijs": [
        {"methode": "deelvraag", "detail": {"deelvraag_id": "d1"}}]}], meting={"deelvraag": {"aantal": 1}})
    Artefact(**bronnen_artefact("wg1", "r1", "Invorderbaarheid"))


# --- 4. run en route --------------------------------------------------------------------------------

@pytest.mark.parametrize("vraag", ["Zoek bepalingen", "Welke bepalingen horen erbij?", "Welke bronnen ontbreken nog?",
                                   "Vind artikelen die erbij horen"])
def test_vragen_om_bronnen(vraag):
    assert is_bronnenvraag(vraag)


@pytest.mark.parametrize("vraag", ["Welke artikelen gaan over invordering?", "Zoek bepalingen over termijnen",
                                   "Annoteer artikel 9", "Stel begrippen voor", "Wat regelt artikel 9?"])
def test_geen_vraag_om_bronnen(vraag):
    assert not is_bronnenvraag(vraag)


def test_het_request_model():
    assert ChatRequest(question="Zoek bepalingen", werkgebied_id="wg1").is_bronnenbeurt
    assert not ChatRequest(question="Zoek bepalingen", werkgebied_id="wg1").is_begrippenbeurt
    assert ChatRequest(question="x", werkgebied_id="wg1", modus="bronnen").is_bronnenbeurt
    assert not ChatRequest(question="Zoek bepalingen").is_bronnenbeurt
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="bronnen")


def test_de_samenvatting_telt_open_voorstellen_en_noemt_onvolledig():
    ks = [{"status": "voorgesteld", "rol": "kern"}, {"status": "voorgesteld", "rol": "afhankelijkheid"},
          {"status": "uitgesloten", "rol": "kern"}, {"status": "voorgesteld", "rol": "kern", "in_selectie": True}]
    tekst = samenvatting("Inv", ks, {"opbouw": {"volledig": False}, "definitie": {"volledig": True}})
    assert "**2** bepalingen" in tekst and "1 kern, 1 afhankelijkheid" in tekst and "opbouw van de wet" in tekst
    assert "geen nieuwe" in samenvatting("Inv", [], {})


class NepApi:
    def __init__(self, run_status: str = "wacht", weiger: tuple[int, dict] | None = None):
        self.run_status, self.weiger = run_status, weiger
        self.berichten: list[dict] = []
        self.uitkomst: dict | None = None
        self.mislukt: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pad, m = request.url.path, request.method
        if pad == "/v1/werkgebieden/wg1" and m == "GET":
            return httpx.Response(200, json={"id": "wg1", "naam": "Invorderbaarheid"})
        if pad == "/v1/werkgebieden/wg1/bronnen-runs" and m == "POST":
            if self.weiger:
                return httpx.Response(self.weiger[0], json={"detail": self.weiger[1]})
            return httpx.Response(200, json={"id": "r1", "status": self.run_status})
        if pad.endswith("/bronnen-runs/r1") and m == "GET":
            return httpx.Response(200, json={"id": "r1", "invoer_id": "I1", "invoer": INVOER,
                                             "status": "klaar" if self.uitkomst else "loopt"})
        if pad.endswith("/loopt"):
            return httpx.Response(200, json={})
        if pad.endswith("/uitkomst"):
            self.uitkomst = json.loads(request.content)
            return httpx.Response(200, json={"status": "klaar"})
        if pad.endswith("/mislukt"):
            self.mislukt = json.loads(request.content)["reden"]
            return httpx.Response(200, json={})
        if pad.endswith("/kandidaten"):
            ks = [{**k, "status": "voorgesteld"} for k in (self.uitkomst or {}).get("kandidaten", [])]
            return httpx.Response(200, json={"run": {"meting": (self.uitkomst or {}).get("meting")}, "kandidaten": ks})
        if pad == "/v1/gesprekken/g1/berichten":
            self.berichten.append(json.loads(request.content))
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(500)


@pytest.fixture
def nep(monkeypatch, geen_overzicht):
    def maak(**kw) -> NepApi:
        api = NepApi(**kw)
        echte = bronnen_run.WetsanalyseApi

        class MetTransport(echte):
            def __init__(self, settings, user_id):
                super().__init__(settings, user_id)
                self._client = httpx.AsyncClient(transport=httpx.MockTransport(api))

        monkeypatch.setattr(bronnen_run, "WetsanalyseApi", MetTransport)
        monkeypatch.setattr(bronnen_run, "PEIL_S", 0.0)
        return api
    return maak


def _settings():
    return make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q")


def _stroom(run: Run, graph=None) -> list[dict]:
    async def verzamel():
        return [e async for e in bronnen_run.bronnen_stroom("wg1", "r1", run, settings=_settings(), user_id="jurist",
                                                            graph=graph or Graaf())]
    return asyncio.run(verzamel())


def test_de_run_zoekt_en_zet_de_kandidaten_terug(nep):
    api = nep()
    events = _stroom(Run(run_id="x", conversation_id="werkgebied:wg1:bronnen"))
    assert [e["type"] for e in events][-2:] == ["opgeslagen", "done"]
    assert any("Verwijzingen vanuit de kern" in e.get("message", "") for e in events)
    assert api.uitkomst["invoer_id"] == "I1" and {k["bron_iri"] for k in api.uitkomst["kandidaten"]} >= {ART8, AWR}


def test_een_onbereikbare_graaf_is_een_mislukte_run(nep, monkeypatch):
    api = nep()

    class Kapot(Graaf):
        def sparql(self, query):
            raise RuntimeError("weg")

    def ook_weg(*_a, **_k):
        raise RuntimeError("weg")

    # Elke methode faalt, ook het overzicht: geen lege uitkomst maar een storing.
    monkeypatch.setattr(overzicht, "bouw_overzicht", ook_weg)
    events = _stroom(Run(run_id="x", conversation_id="c"), graph=Kapot())
    assert events[-1]["type"] == "error" and events[-1]["soort"] == "graaf"
    assert api.uitkomst is None and api.mislukt


def test_een_falende_methode_haalt_de_run_niet_onderuit(nep):
    api = nep()
    _stroom(Run(run_id="x", conversation_id="c"), graph=Graaf(faal="opbouw"))
    assert api.uitkomst["meting"]["opbouw"]["volledig"] is False
    assert all("fout" not in m for m in api.uitkomst["meting"].values())


def test_de_route_legt_een_bronnenartefact_vast(nep):
    api = nep()
    request = ChatRequest(question="Zoek bepalingen", conversation_id="g1", werkgebied_id="wg1")

    async def verzamel():
        return [e async for e in bronnen_run.bronnen_beurt(request, Run(run_id="b1", conversation_id="g1"),
                                                           settings=_settings(), user_id="jurist", graph=Graaf())]
    events = asyncio.run(verzamel())
    artefact = {"soort": "bronnen", "titel": "Invorderbaarheid", "ref": {"werkgebied_id": "wg1", "run_id": "r1"}}
    assert events[-2] == {"type": "opgeslagen", "run_id": "b1", "artefact": artefact}
    [bericht] = api.berichten
    assert bericht["artefact"] == artefact and "bepalingen voor in werkgebied" in bericht["tekst"]
    assert "Verwijzingen vanuit de kern" in bericht["denk"]


def test_zonder_vertrekpunt_een_antwoord_zonder_artefact(nep):
    api = nep(weiger=(409, {"fout": "geen_vertrekpunt", "melding": "…"}))
    request = ChatRequest(question="Zoek bepalingen", conversation_id="g1", werkgebied_id="wg1")

    async def verzamel():
        return [e async for e in bronnen_run.bronnen_beurt(request, Run(run_id="b1", conversation_id="g1"),
                                                           settings=_settings(), user_id="jurist", graph=Graaf())]
    events = asyncio.run(verzamel())
    assert events[-2] == {"type": "opgeslagen", "run_id": "b1"}
    assert "analysevraag" in api.berichten[0]["tekst"] and "artefact" not in api.berichten[0]


# --- het endpoint ----------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import api.main as main

    async def langzaam(werkgebied_id, run_id, run, **_kw):
        await asyncio.sleep(0.3)
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "bronnen_stroom", langzaam)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        yield c, main


def test_een_bronnenrun_per_werkgebied_naast_begrippen(client, monkeypatch):
    c, main = client
    assert c.post("/v1/bronnen-runs", json={"werkgebied_id": "wg1", "run_id": "r1"}).status_code == 503
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
    eerste = c.post("/v1/bronnen-runs", json={"werkgebied_id": "wg1", "run_id": "r1"})
    assert eerste.status_code == 201 and eerste.json()["conversation_id"] == "werkgebied:wg1:bronnen"
    assert c.post("/v1/bronnen-runs", json={"werkgebied_id": "wg1", "run_id": "r2"}).status_code == 409
    assert c.post("/v1/chat", json={"question": "x", "modus": "bronnen", "werkgebied_id": "wg1"}).status_code == 422
