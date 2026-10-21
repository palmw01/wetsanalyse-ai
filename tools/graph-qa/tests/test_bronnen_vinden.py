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
from agent.bronnen_run import bronnen_artefact, samenvatting
from agent.bronnen_vinden import vind, verwijzingsfunctie
from agent.models import ChatRequest
from agent.runstore import Run
from fakes import FakeGraph, agent_ctx, make_settings

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


# --- bepalingen bij één deelvraag (F3f): de intake en de deelvragen-agent delen `bepaling_opties` ---

IWB = "BWBR0004770"
L9_2, ART12_1 = f"{IW}:artikel:9:lid:2", f"{IW}:artikel:12:lid:1"
FTS_KOP = ["node", "score", "soort", "label", "tekst", "jci", "bwbId", "citeertitel"]


def _fts(*rijen):
    return _tsv(FTS_KOP, [[n, "1.0", "", "", t, "", b, ""] for n, t, b in rijen])


TREFFERS = {
    "Lid": _fts((L1, "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.", IWB),
                (L9_2, "In afwijking van het eerste lid is een navorderingsaanslag invorderbaar één maand na de dagtekening.", IWB),
                (ART12_1, "De kosten van vervolging zijn invorderbaar.", IWB),
                ("urn:bwb:BWBR0002320:artikel:30:lid:1", "Een belastingaanslag ...", "BWBR0002320")),
    # Artikel 9 zelf valt weg: er is een lid van geraakt. Artikel 10 heeft geen geraakt lid.
    "Artikel": _fts((ART9, "Een belastingaanslag is invorderbaar ...", IWB),
                    (ART10, "In afwijking van artikel 9 is een belastingaanslag terstond invorderbaar.", IWB)),
    # Een onderdeel telt voor zijn lid.
    "Onderdeel": _fts((f"{IW}:artikel:8:lid:1:o:a", "de aanslag wordt bekendgemaakt door het aanslagbiljet;", IWB)),
}


class BepalingGraaf(FakeGraph):
    def __init__(self, faal: bool = False) -> None:
        super().__init__(results=self._antwoord)
        self.faal = faal

    def _antwoord(self, q: str) -> str:
        if "bwb:opschrift" in q:
            return _tsv(["r", "citeertitel", "opschrift"], [[f"urn:bwb:{IWB}", "Invorderingswet 1990", ""]])
        if "definieertBegrip:" in q:
            return _tsv(["node", "begrip", "label", "tekst", "jci", "bwbId", "citeertitel"],
                        [[ART2K, "belastingaanslag", "", "belastingaanslag: aanslag als bedoeld in ...", "", IWB, ""]])
        if "VALUES ?bepaling" in q:
            return _tsv(["bepaling", "deel", "soort", "label"], [[L1, H2, "Hoofdstuk", "Hoofdstuk II – Invordering"]])
        if self.faal:
            raise RuntimeError("graaf hapert")
        return next(t for soort, t in TREFFERS.items() if f"?node a bwb:{soort} ." in q)


DOSSIER = {"analysevraag": "Wanneer is een aanslag invorderbaar?",
           "praktijkvoorbeeld": "Een aanslagbiljet met dagtekening 1 maart."}


def _opties(graaf=None, **kw):
    from agent.werkgebied_context import uitsluitstammen

    args = {"regelingen": [IWB], "deelvraag": "Wanneer is een belastingaanslag invorderbaar?", "dossier": DOSSIER,
            "buiten": uitsluitstammen("de kosten van vervolging")} | kw
    return bronnen_vinden.bepaling_opties(graaf or BepalingGraaf(), **args)


def test_bepalingen_bij_een_deelvraag_op_lid_niveau_en_in_vaste_volgorde():
    uit = _opties()
    # Volgorde: deelvraagtermen, dan dossiertermen, dan kop, dan documentvolgorde. Een andere regeling valt
    # weg; een artikel met een geraakt lid ook; een onderdeel telt voor zijn lid.
    assert [o["bron_iri"] for o in uit] == [L1, ART10, L9_2, f"{IW}:artikel:2:lid:1", f"{IW}:artikel:8:lid:1", ART12_1]
    eerste = uit[0]
    assert eerste["label"] == "Artikel 9, lid 1 – Invorderingswet 1990" and not eerste["buiten"]
    assert eerste["omschrijving"].startswith("Een belastingaanslag is invorderbaar zes weken")
    assert eerste["omschrijving"].endswith("raakt: belastingaanslag, invorderbaar, aanslag, aanslagbiljet, dagtekening")
    # Hetzelfde gesprek, dezelfde opties.
    assert _opties() == uit


def test_wat_buiten_de_afbakening_raakt_valt_niet_stil_weg():
    """Het invorderingsgeval: 'de kosten van vervolging' valt erbuiten. Een lid dat daar meer over gaat dan
    over de deelvraag staat onderaan, gemarkeerd, en telt niet mee voor het maximum."""
    uit = _opties(limit=2)
    assert [o["bron_iri"] for o in uit] == [L1, ART10, ART12_1]
    assert uit[-1]["buiten"] and uit[-1]["omschrijving"] == bronnen_vinden.BUITEN_TEKST
    # Zonder uitsluiting is hetzelfde lid gewoon een optie.
    assert not [o for o in _opties(buiten=[]) if o["buiten"]]


def test_zonder_deelvraag_zoekt_lex_op_de_analysevraag_en_een_storing_is_leeg():
    assert _opties(deelvraag=None)[0]["bron_iri"] in (L1, ART10)
    assert _opties(BepalingGraaf(faal=True)) == []
    assert _opties(deelvraag="Wat?", dossier={}) == []


def test_de_deelvragen_agent_zoekt_per_deelvraag_met_dezelfde_functie():
    dv = [{"id": "d1", "vraag": "Wanneer is een belastingaanslag invorderbaar?"}, {"id": "d2", "vraag": "Wat?"}]
    invoer = {**INVOER, "deelvragen": dv, "dossier": {"afbakening": "Regelingen: Invorderingswet 1990.\n"
                                                                      "Buiten de afbakening: kosten van vervolging."}}
    assert bronnen_vinden.standaard_voor(invoer)[-1] == "deelvraag"
    assert bronnen_vinden.standaard_voor({**invoer, "kern": []}) == ("overzicht", "deelvraag")
    uit = vind(BepalingGraaf(), invoer, methoden=("deelvraag",))
    k = _per_iri(uit)
    # Met een kern: aanverwant, binnen de regeling van de kern; wat al in de selectie valt, valt weg.
    assert L1 not in k and L9_2 not in k and k[ART10]["rol"] == "aanverwant"
    assert k[ART10]["bewijs"][0]["detail"] == {"deelvraag_id": "d1", "vraag": dv[0]["vraag"],
                                               "raakt": ["belastingaanslag", "invorderbaar"]}
    assert k[ART12_1]["bewijs"][0]["detail"]["buiten"] is True
    assert uit["meting"]["deelvraag"]["aantal"] == len(k)
    # Zonder kern: kern.
    uit = vind(BepalingGraaf(), {**invoer, "kern": []}, methoden=("deelvraag",))
    assert {x["rol"] for x in uit["kandidaten"]} == {"kern"}
    assert bronnen_vinden.buiten_uit_afbakening(invoer["dossier"]["afbakening"]) == "kosten van vervolging."


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

def test_het_request_model():
    # Geen tekstpatroon meer: zoeken is een taak van de deelvragen-agent, of een klik op de suggestie.
    r = ChatRequest(question="Zoek bepalingen", actie="bronnen_zoeken", werkgebied_id="wg1")
    assert r.actie == "bronnen_zoeken" and r.modus == "auto"
    with pytest.raises(ValueError):
        ChatRequest(question="x", modus="bronnen", werkgebied_id="wg1")
    with pytest.raises(ValueError):
        ChatRequest(question="x", actie="bronnen_zoeken")


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


def _kern(deelvraag_id: str = ""):
    async def draai():
        api = bronnen_run.WetsanalyseApi(_settings(), "jurist")
        try:
            ctx = agent_ctx(api, settings=_settings(), run_id="b1", graph=Graaf())
            return await bronnen_run.bronnen_kern(ctx, "wg1", deelvraag_id), ctx.meldingen
        finally:
            await api.aclose()
    return asyncio.run(draai())


def test_de_taak_geeft_een_bronnenartefact(nep):
    nep()
    uit, meldingen = _kern()
    assert uit.status == "ok" and uit.artefact == {"soort": "bronnen", "titel": "Invorderbaarheid",
                                                   "ref": {"werkgebied_id": "wg1", "run_id": "r1"}}
    assert "bepalingen voor in werkgebied" in uit.tekst and uit.meting["model"] is False
    assert any("Verwijzingen vanuit de kern" in m for m in meldingen)


def test_zonder_vertrekpunt_een_antwoord_zonder_artefact(nep):
    nep(weiger=(409, {"fout": "geen_vertrekpunt", "melding": "…"}))
    uit, _ = _kern()
    assert uit.status == "geweigerd" and "analysevraag" in uit.reden and uit.artefact is None


def test_bij_een_deelvraag_noemt_lex_wat_daarbij_hoort():
    wg = {"deelvragen": [{"id": "d1", "vraag": "Wanneer is de aanslag invorderbaar?"}]}
    ks = [{"id": "k1", "label": "art. 8 Iw", "status": "voorgesteld",
           "bewijs": [{"methode": "deelvraag", "detail": {"deelvraag_id": "d1"}}]},
          {"id": "k2", "label": "art. 10 Iw", "status": "voorgesteld", "bewijs": [{"methode": "opbouw"}]}]
    assert bronnen_run.bij_deelvraag(wg, ks, "d1") == ("Bij de deelvraag “Wanneer is de aanslag invorderbaar?” stel "
                                                        "ik 1 voor: art. 8 Iw.")
    assert "geen nieuwe" in bronnen_run.bij_deelvraag(wg, ks[1:], "d1")
    assert "ken ik niet" in bronnen_run.bij_deelvraag(wg, ks, "d9")


def test_chat_weigert_een_actie():
    from fastapi.testclient import TestClient

    import api.main as main
    c = TestClient(main.app)
    assert c.post("/v1/chat", json={"question": "x", "actie": "bronnen_zoeken", "werkgebied_id": "wg1"}).status_code == 422
