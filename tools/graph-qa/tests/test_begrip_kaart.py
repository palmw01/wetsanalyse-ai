"""Lex naast de kaart (spoor D, fase E): de vier acties, tegen een nep-graaf, een nep-model en een nep-api.

Bewaakt: de brondefinitie komt letterlijk uit de graaf en zonder model, de sterkste plaats eerst; het
model kiest fragmenten op id en wat niet klopt wordt geen voorstel; een cirkel wordt verworpen; budget
op start niets; het verbruik wordt geboekt; en elk voorstel heeft de vorm van het api-contract.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import begrip_kaart as bk
from agent.begrippen_pipeline import kaartacties as ka, toetsen
from agent.begrippen_pipeline.model import Bron, Formulering, Manifest
from agent.models import KaartRunVerzoek, Verbruiksmeter
from fakes import FakeGraph, make_settings, response, tool_block

API_CONTRACT = Path(__file__).resolve().parents[3] / "api" / "app" / "begrip_voorstel_contracts.py"

IW, AWR = "urn:bwb:BWBR0004770", "urn:bwb:BWBR0002320"
ART9, DEF_IW, DEF_AWR, ELDERS = (f"{IW}:artikel:9:lid:1", f"{IW}:artikel:2:lid:1:o:m", f"{AWR}:artikel:2:lid:3:o:d",
                                 "urn:bwb:BWBR0099999:artikel:1:o:a")
A = "De ontvanger verzendt de belastingaanslag binnen zes weken. Daarna volgt de betaling."
D = "belastingaanslag: de voorlopige aanslag en de aanslag;"
AANHEF = "Deze wet verstaat onder:"


def _h(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _f(eid, iri, tekst, deel, klasse="Rechtsobject"):
    s = tekst.index(deel)
    return Formulering(element_id=eid, bron_iri=iri, start=s, eind=s + len(deel), tekst=deel, jas_klasse=klasse)


MANIFEST = Manifest(
    bronnen=(Bron(bron_iri=ART9, tekst=A, bron_hash=_h(A), label="Artikel 9 · Lid 1 – IW", regeling="BWBR0004770"),
             Bron(bron_iri=DEF_IW, tekst=D, bron_hash=_h(D), label="Artikel 2 · Lid 1 · m – IW", aanhef=AANHEF,
                  regeling="BWBR0004770")),
    formuleringen=(_f("e1", ART9, A, "belastingaanslag"), _f("e2", ART9, A, "De ontvanger", "Rechtssubject")))


def _invoer(actie="scherper", **begrip) -> dict:
    inhoud = {"naam": "belastingaanslag", **begrip}
    return {"actie": actie, "begrip": {"id": "b1", "revisie": 1, "inhoud": inhoud}, "leden": ["e1"],
            "ander": None, "selecties": [{"bron_iri": f"{IW}:artikel:9", "rol": "analyseren"}],
            "manifest": MANIFEST.model_dump(mode="json"), "manifest_id": MANIFEST.id}


def _kant(**begrip) -> ka.Kant:
    return ka.kant_uit({"id": "b1", "inhoud": {"naam": "belastingaanslag", **begrip}, "leden": ["e1"]}, MANIFEST)


# --- brondefinitie (geen model) ------------------------------------------------------------------

def _tsv(kop, rijen) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


AWR_TEKST = "belastingaanslag: de voorlopige aanslag, de aanslag en de navorderingsaanslag;"
DEFS = _tsv(["node", "begrip", "tekst", "aanhef"], [
    [DEF_AWR, "belastingaanslag", AWR_TEKST, "De belastingwet verstaat onder:"],
    [DEF_IW, "belastingaanslag", D, AANHEF],
    [ELDERS, "belastingaanslag", "belastingaanslag: iets heel anders;", "In dit besluit wordt verstaan onder:"],
])


def _graaf() -> FakeGraph:
    def antwoord(q: str) -> str:
        if "LCASE(STR(?begrip))" in q:
            return DEFS
        if "?naar WHERE" in q:
            return _tsv(["naar"], [[f"{AWR}:artikel:1"]])
        return ""
    return FakeGraph(results=antwoord)


def test_brondefinities_letterlijk_en_de_sterkste_plaats_eerst():
    uit = bk.zoek_brondefinities(_graaf(), _invoer("brondefinitie"))
    assert [v["definitie"]["vindplaats_soort"] for v in uit.voorstellen] == ["regeling", "definitieverwijzing", "elders"]
    iw, awr, elders = uit.voorstellen
    assert (iw["definitie"]["definitie"], iw["definitie"]["herkomst"], iw["aandacht"]) == (
        "de voorlopige aanslag en de aanslag", "letterlijk", "groen")
    assert iw["definitie"]["definitie"] in D and awr["definitie"]["definitie"] in AWR_TEKST
    assert (awr["aandacht"], awr["aandachtspunten"]) == ("geel", ["DEFINITIE_VIA_VERWIJZING"])
    assert elders["aandachtspunten"] == ["DEFINITIE_ELDERS"]


def test_een_definitie_die_er_al_staat_wordt_niet_nog_eens_voorgesteld():
    uit = bk.zoek_brondefinities(_graaf(), _invoer("brondefinitie", definitie="de voorlopige aanslag en de aanslag"))
    assert "regeling" not in [v["definitie"]["vindplaats_soort"] for v in uit.voorstellen]


def test_geen_treffer_is_een_melding():
    uit = bk.zoek_brondefinities(FakeGraph(results=lambda q: ""), _invoer("brondefinitie"))
    assert uit.voorstellen == [] and uit.melding == "Geen wettelijke definitie gevonden voor “belastingaanslag”."


def test_alleen_een_uitbreiding_is_geen_definitie_en_dat_zegt_lex():
    mede = _tsv(["node", "begrip", "tekst", "aanhef"], [
        [f"{IW}:artikel:2:lid:2:o:d", "aanslagbiljet", "aanslagbiljet: de kennisgeving van de belastingaanslag;",
         "Deze wet verstaat mede onder:"]])
    uit = bk.zoek_brondefinities(FakeGraph(results=lambda q: mede if "LCASE" in q else ""),
                                 _invoer("brondefinitie", naam="aanslagbiljet"))
    assert uit.voorstellen == []
    assert uit.melding.startswith("De wet breidt “aanslagbiljet” alleen uit of sluit iets uit")


def test_de_zoekterm_volgt_naam_en_alternatieve_termen():
    q = bk.q_brondefinities(ka.termen({"naam": "Belasting Aanslag", "alternatieve_termen": ["aanslag", "aanslag"]}))
    assert 'IN ("belasting aanslag", "aanslag")' in q


# --- scherper -------------------------------------------------------------------------------------

def _frs():
    return ka.fragmenten_voor(MANIFEST, [_kant()])


def test_fragmenten_komen_uit_de_passages_en_de_begripsbepaling_zonder_de_kale_term():
    teksten = [f.tekst for f in _frs()]
    assert "de voorlopige aanslag en de aanslag" in teksten
    assert "belastingaanslag" not in teksten


def test_scherper_samengesteld_uit_fragmenten():
    frs = _frs()
    fr = next(f for f in frs if f.tekst == "de voorlopige aanslag en de aanslag")
    uit = ka.valideer_scherper(MANIFEST, _kant(), frs, {"herkomst": "samengesteld", "fragmenten": [fr.id],
                                                        "definitie": "", "motivatie": "Uit de wet."})
    [v] = uit.voorstellen
    assert (v["definitie"]["definitie"], v["definitie"]["herkomst"], v["aandacht"]) == (
        "de voorlopige aanslag en de aanslag", "samengesteld", "geel")
    assert v["definitie"]["fragmenten"][0]["id"] == fr.id


def test_scherper_weigert_een_onbekend_fragment_een_cirkel_en_hetzelfde():
    frs = _frs()
    assert ka.valideer_scherper(MANIFEST, _kant(), frs, {"herkomst": "samengesteld", "fragmenten": ["Fnep0000000"],
                                                         "definitie": "", "motivatie": ""}).voorstellen == []
    cirkel = ka.valideer_scherper(MANIFEST, _kant(), frs, {"herkomst": "geformuleerd", "fragmenten": [frs[0].id],
                                                           "definitie": "een belastingaanslag van de ontvanger",
                                                           "motivatie": ""})
    assert cirkel.voorstellen == [] and cirkel.melding == toetsen.TEKST["CIRCULAIR_VERWORPEN"]
    zelfde = ka.valideer_scherper(MANIFEST, _kant(definitie="een aanslag van de fiscus"), frs, {
        "herkomst": "geformuleerd", "fragmenten": [frs[0].id], "definitie": "een  aanslag van de fiscus", "motivatie": ""})
    assert zelfde.voorstellen == [] and zelfde.melding.startswith(ka.TEKST["GEEN_VERBETERING"])
    assert ka.valideer_scherper(MANIFEST, _kant(), frs, None).melding == ka.TEKST["MODEL_ONBRUIKBAAR"]


def test_een_geformuleerde_definitie_is_geel_met_haar_signalen():
    frs = _frs()
    [v] = ka.valideer_scherper(MANIFEST, _kant(), frs, {"herkomst": "geformuleerd", "fragmenten": [frs[0].id],
                                                        "definitie": "een beschikking die een te betalen bedrag vaststelt",
                                                        "motivatie": "Scherper."}).voorstellen
    assert v["aandacht"] == "geel" and "DOOR_LEX_GEFORMULEERD" in v["aandachtspunten"]


# --- betekenisverschil en voorbeelden -------------------------------------------------------------

def test_verschil_geeft_uitleg_en_bij_onbeslist_een_open_vraag():
    a = _kant()
    b = ka.kant_uit({"id": "b2", "inhoud": {"naam": "ontvanger"}, "leden": ["e2"]}, MANIFEST)
    frs = ka.fragmenten_voor(MANIFEST, [a, b])
    uit = ka.valideer_verschil(a, b, frs, {"vergelijking": "onbeslist", "uitleg": "De tekst zegt het niet.",
                                           "fragmenten": [frs[0].id], "open_vraag": ""})
    uitleg, vraag = uit.voorstellen
    assert uitleg["tekst"] == "Ten opzichte van “ontvanger”: De tekst zegt het niet."
    assert uitleg["vergelijking"] == "onbeslist" and vraag["veld"] == "open_vragen"
    assert vraag["tekst"] == "Duiden “belastingaanslag” en “ontvanger” hetzelfde begrip aan?"
    assert ka.valideer_verschil(a, b, frs, {"vergelijking": "verschil", "uitleg": "x", "fragmenten": ["Fnep"],
                                            "open_vraag": ""}).voorstellen == []


def test_voorbeelden_zonder_dubbelen_en_met_signalen():
    k = _kant(definitie="de voorlopige aanslag en de aanslag", voorbeelden=[{"tekst": "Een aanslag IB 2025", "oordeel": "wel"}])
    uit = ka.valideer_voorbeelden(k, {"voorbeelden": [
        {"tekst": "Een aanslag IB 2025", "oordeel": "wel", "toelichting": ""},          # staat er al
        {"tekst": "Een voorlopige aanslag IB", "oordeel": "wel", "toelichting": "voorlopig"},
        {"tekst": "Het is de voorlopige aanslag en de aanslag", "oordeel": "onzeker", "toelichting": ""},
        {"tekst": "", "oordeel": "wel", "toelichting": ""}]})
    assert [v["tekst"] for v in uit.voorstellen] == ["Een voorlopige aanslag IB", "Het is de voorlopige aanslag en de aanslag"]
    assert "GEEN_TEGENVOORBEELD" in uit.voorstellen[0]["aandachtspunten"]
    assert "HERHAALT_DEFINITIE" in uit.voorstellen[1]["aandachtspunten"]


def test_elke_code_heeft_een_tekst():
    bron = (Path(ka.__file__)).read_text()
    gebruikt = {n.value for n in ast.walk(ast.parse(bron)) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and n.value.isupper() and "_" in n.value and len(n.value) > 6}
    assert gebruikt <= set(ka.TEKST) | set(toetsen.TEKST)
    assert not set(ka.TEKST) & set(toetsen.TEKST)


# --- het api-contract -----------------------------------------------------------------------------

def _velden(klasse: str) -> set[str]:
    boom = ast.parse(API_CONTRACT.read_text())
    k = next(n for n in boom.body if isinstance(n, ast.ClassDef) and n.name == klasse)
    return {s.target.id for s in k.body if isinstance(s, ast.AnnAssign)}


def test_elk_voorstel_heeft_de_vorm_van_het_api_contract():
    frs = _frs()
    voorstellen = [*bk.zoek_brondefinities(_graaf(), _invoer("brondefinitie")).voorstellen,
                   *ka.valideer_scherper(MANIFEST, _kant(), frs, {"herkomst": "geformuleerd", "fragmenten": [frs[0].id],
                                                                  "definitie": "een vastgesteld bedrag", "motivatie": ""}).voorstellen,
                   *ka.valideer_voorbeelden(_kant(definitie="x"), {"voorbeelden": [
                       {"tekst": "y", "oordeel": "niet", "toelichting": ""}]}).voorstellen]
    for v in voorstellen:
        assert set(v) <= _velden("VoorstelInvoer"), set(v) - _velden("VoorstelInvoer")
        if "definitie" in v:
            assert set(v["definitie"]) <= _velden("DefinitieWaarde")


# --- de stroom ------------------------------------------------------------------------------------

class NepApi:
    def __init__(self, invoer):
        self.invoer = invoer
        self.uitkomst: dict | None = None
        self.mislukt: list[str] = []
        self.geboekt: list[str] = []

    async def haal_kaartrun(self, wg, b, rid):
        return {"id": rid, "invoer_id": "I1", "invoer": self.invoer}

    async def meld_kaart_loopt(self, wg, b, rid):
        return {}

    async def zet_kaart_uitkomst(self, wg, b, rid, u):
        self.uitkomst = u
        return {}

    async def meld_kaart_mislukt(self, wg, b, rid, reden):
        self.mislukt.append(reden)
        return {}

    async def boek_verbruik(self, verbruik, *, model, gesprek_id, run_id):
        self.geboekt.append(run_id)
        return {}

    async def aclose(self):
        pass


class NepModel:
    def __init__(self):
        self.meter = Verbruiksmeter()
        self.aanroepen = 0

    def create(self, **kw):
        self.aanroepen += 1
        tool = kw["tools"][0]
        frs = tool["input_schema"]["properties"]["fragmenten"]["items"]["enum"]
        resp = response([tool_block("t", tool["name"], {"herkomst": "geformuleerd", "fragmenten": [frs[0]],
                                                         "definitie": "een vastgesteld te betalen bedrag",
                                                         "motivatie": "Scherper."})], "tool_use")
        resp.usage = SimpleNamespace(input_tokens=300, output_tokens=40)
        self.meter.tel_response(resp)
        return resp


async def _verloop(invoer, **kw):
    api = NepApi(invoer)
    events = [ev async for ev in bk.kaart_stroom("w1", "b1", "k1", None, settings=make_settings(), user_id="jurist",
                                                 api=api, **kw)]
    return api, events


def test_scherper_boekt_het_verbruik_en_zet_de_voorstellen_terug():
    model = NepModel()
    api, events = asyncio.run(_verloop(_invoer(), maak_llm=lambda s: model, budget_toegestaan=_ja))
    assert model.aanroepen == 1 and api.geboekt == ["kaart-k1"]
    [v] = api.uitkomst["voorstellen"]
    assert v["definitie"]["herkomst"] == "geformuleerd"
    assert (api.uitkomst["tokens"], api.uitkomst["invoer_id"]) == (340, "I1")
    assert api.uitkomst["promptversie"] == ka.promptversie("scherper")
    assert [e["type"] for e in events][-2:] == ["opgeslagen", "done"]


async def _ja():
    return True


async def _nee():
    return False


def test_budget_op_start_geen_model():
    model = NepModel()
    api, events = asyncio.run(_verloop(_invoer(), maak_llm=lambda s: model, budget_toegestaan=_nee))
    assert model.aanroepen == 0 and api.uitkomst is None
    assert api.mislukt == ["Het tokenbudget is op."] and events[-1]["soort"] == "budget"


def test_brondefinitie_gebruikt_geen_model_en_geen_budget():
    def geen_model(s):
        raise AssertionError("de brondefinitie mag geen model gebruiken")
    api, _ = asyncio.run(_verloop(_invoer("brondefinitie"), graph=_graaf(), maak_llm=geen_model, budget_toegestaan=_nee))
    assert len(api.uitkomst["voorstellen"]) == 3 and api.uitkomst["model"] == ""


def test_een_falend_model_is_een_mislukte_run_met_boeking():
    class Faalt(NepModel):
        def create(self, **kw):
            raise RuntimeError("provider weg")
    api, events = asyncio.run(_verloop(_invoer("voorbeelden", definitie="x"), maak_llm=lambda s: Faalt(),
                                       budget_toegestaan=_ja))
    assert api.uitkomst is None and api.mislukt and events[-1]["soort"] == "model"


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    from api import main

    async def langzaam(*a, **kw):
        await asyncio.sleep(0.3)
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "kaart_stroom", langzaam)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        yield c, main


def test_een_kaartrun_per_begrip(client, monkeypatch):
    c, main = client
    body = {"werkgebied_id": "w1", "begrip_id": "b1", "run_id": "k1"}
    assert c.post("/v1/kaart-runs", json=body).status_code == 503              # zonder api
    monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
    eerste = c.post("/v1/kaart-runs", json=body)
    assert eerste.status_code == 201 and eerste.json()["conversation_id"] == "begrip:b1:kaart"
    assert c.post("/v1/kaart-runs", json={**body, "run_id": "k2"}).status_code == 409
    assert c.post("/v1/kaart-runs", json={**body, "begrip_id": "b2"}).status_code == 201
    assert c.post("/v1/kaart-runs", json={**body, "begrip_id": "b 1"}).status_code == 422
