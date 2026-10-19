"""Lex stelt met de analist een werkgebied samen (activiteit 1): herkenning, de stapmachine, de kaartjes,
de voorstellen uit graaf en model, het gesprek over meerdere beurten en het aanmaken door de driver."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from agent import werkgebied_intake as wi
from agent.models import ChatRequest
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block
from test_contract_drift import _bericht_velden

IB = "BWBR0011353"
H2 = f"urn:bwb:{IB}:hoofdstuk:2"
AFD = f"urn:bwb:{IB}:hoofdstuk:5:afdeling:5.1"


def _voorstel(naam=(), vraag=(), onderwerp=""):
    blok = SimpleNamespace(type="tool_use", id="v1", name=wi.TOOL,
                           input={"naam": list(naam), "analysevraag": list(vraag), "onderwerp": onderwerp})
    return response([blok], "tool_use")


OPTIES = [{"label": "Wet inkomstenbelasting 2001", "waarde": IB, "bron": {"bwb_id": IB}},
          {"label": "Algemene wet inzake rijksbelastingen", "waarde": "BWBR0002320", "bron": {"bwb_id": "BWBR0002320"}}]
DELEN = {IB: [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht"}, {"iri": AFD, "kop": "Afdeling 5.1 – Box 3"}]}


@pytest.fixture
def graaf(monkeypatch):
    """De regelingvoorstellen zonder graaf: wat `regeling_opties` krijgt, en wat het teruggeeft."""
    gezocht: list[tuple[str, str]] = []

    def opties(graph, zoek, *, genoemd_in=""):
        gezocht.append((zoek, genoemd_in))
        if zoek == "niets":
            return [], {}, []
        return list(OPTIES), dict(DELEN), []

    monkeypatch.setattr(wi, "regeling_opties", opties)
    return gezocht


# --- Herkenning ------------------------------------------------------------------------------------

@pytest.mark.parametrize("vraag", [
    "Kunnen we een werkgebied samenstellen?", "Ik wil een wetsanalyse uitvoeren", "maak een nieuw werkgebied",
    "Help me een werkgebied te bepalen over box 3", "Laten we beginnen met een wetsanalyse",
    "Start een wetsanalyse", "Ik wil graag een werkgebied aanmaken voor de invordering",
])
def test_startzinnen_worden_herkend(vraag):
    assert wi.is_werkgebiedvraag(vraag)


@pytest.mark.parametrize("vraag", [
    "Annoteer het werkgebied", "Welke bepalingen horen bij het werkgebied?", "Wat is een wetsanalyse?",
    "Wat betekent artikel 3.1 Wet IB 2001?", "Stel begrippen voor in dit werkgebied", "Wat ontbreekt er nog?",
])
def test_andere_vragen_zijn_geen_startzin(vraag):
    assert not wi.is_werkgebiedvraag(vraag)


def test_alleen_een_wetsanalysevraag_krijgt_uitleg():
    assert wi.is_wetsanalysevraag("ik wil een wetsanalyse uitvoeren")
    assert not wi.is_wetsanalysevraag("kunnen we een werkgebied samenstellen?")


def test_inhoud_van_de_startzin():
    assert wi.inhoud("Kunnen we een werkgebied samenstellen?") == []
    assert "box" in wi.inhoud("Ik wil een werkgebied over de box 3-heffing per 2026")


def test_een_startzin_binnen_een_werkgebied_gaat_niet_een_harde_route_in():
    for vraag in ("Kunnen we een werkgebied samenstellen?", "Ik wil een wetsanalyse uitvoeren"):
        r = ChatRequest(question=vraag, werkgebied_id="wg1")
        assert not (r.is_werkgebied_annotatie or r.is_begrippen_verdieping or r.is_bronnenbeurt
                    or r.is_kaartbeurt or r.is_begrippenbeurt), vraag


# --- De stapmachine --------------------------------------------------------------------------------

def _klik(intake, stap, **kw):
    return {"intake_id": intake["id"], "stap": stap, "actie": kw.pop("actie", "antwoord"), **kw}


def test_de_volgorde_ligt_vast_en_de_samenvatting_volgt():
    i = wi.nieuwe_intake("kunnen we een werkgebied samenstellen?")
    assert i["stap"] == "naam"
    i, u = wi.verwerk(i, _klik(i, "naam", tekst="Box 3"))
    assert (u, i["stap"]) == ("verder", "analysevraag")
    i, _ = wi.verwerk(i, _klik(i, "analysevraag", tekst="Wie is belastingplichtig voor box 3?"))
    i = {**i, "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[IB]))
    assert i["stap"] == "onderdelen" and i["antwoorden"]["regelingen"] == [{"bwb_id": IB, "label": OPTIES[0]["label"]}]
    i = {**i, "voorstellen": {**i["voorstellen"], "onderdelen": wi.onderdeel_opties(i["antwoorden"]["regelingen"], DELEN)}}
    i, _ = wi.verwerk(i, _klik(i, "onderdelen", keuzes=[AFD, wi.HELE + IB]))
    i, _ = wi.verwerk(i, _klik(i, "buiten", tekst="geen overgangsrecht"))
    assert i["stap"] == "samenvatting"
    verzoek = wi.aanmaakverzoek(i)
    assert verzoek["werkgebied"] == {
        "naam": "Box 3", "analysevraag": "Wie is belastingplichtig voor box 3?", "intake_id": i["id"],
        "afbakening": ("Regelingen: Wet inkomstenbelasting 2001.\n"
                       "Onderdelen: Afdeling 5.1 – Box 3 en De hele Wet inkomstenbelasting 2001.\n"
                       "Buiten de afbakening: geen overgangsrecht.")}
    # De hele regeling staat in de tekst, maar wordt geen bronselectie.
    assert verzoek["bronnen"] == [{"bron_iri": AFD, "label": "Afdeling 5.1 – Box 3"}]


def test_weet_ik_niet_slaat_de_onderdelen_over_en_maakt_geen_bron():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"},
         "voorstellen": {"regelingen": OPTIES}}
    i, _ = wi.verwerk(i, _klik(i, "regelingen", keuzes=[wi.ONBEKEND]))
    assert i["stap"] == "buiten"
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: nog te bepalen."
    assert wi.bronnen(i["antwoorden"]) == []
    kaart = wi.kaart({**i, "stap": "regelingen", "voorstellen": {"regelingen": OPTIES}})
    assert kaart["opties"][-1] == {"label": "Weet ik (nog) niet", "waarde": wi.ONBEKEND, "bron": {}}


def test_ook_bij_onderdelen_kan_weet_ik_niet():
    i = {**wi.nieuwe_intake("x"), "stap": "onderdelen",
         "antwoorden": {"naam": "Box 3", "regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}]}}
    assert wi.kaart(i)["opties"][-1]["waarde"] == wi.ONBEKEND
    i, _ = wi.verwerk(i, _klik(i, "onderdelen", keuzes=[wi.ONBEKEND]))
    assert wi.afbakening(i["antwoorden"]) == "Regelingen: Wet IB 2001.\nOnderdelen: nog te bepalen."


def test_artikelen_in_eigen_tekst_worden_bronnen_bij_een_regeling():
    a = {"regelingen": [{"bwb_id": IB, "label": "Wet IB 2001"}], "onderdelen": [],
         "onderdelen_tekst": "artikel 5.2 en 5.3"}
    assert wi.bronnen(a) == [{"bwb_id": IB, "artikel": "5.2", "label": "Wet IB 2001 – art. 5.2"},
                             {"bwb_id": IB, "artikel": "5.3", "label": "Wet IB 2001 – art. 5.3"}]
    # Bij twee regelingen is niet te zeggen waar de artikelen staan: alleen tekst.
    assert wi.bronnen({**a, "regelingen": a["regelingen"] * 2}) == []


def test_naam_is_verplicht():
    i = wi.nieuwe_intake("x")
    assert wi.verwerk(i, _klik(i, "naam", actie="overslaan"))[1] == "naam_nodig"
    assert wi.verwerk(i, _klik(i, "naam", tekst="   "))[1] == "naam_nodig"
    assert not wi.kaart(i)["overslaanbaar"] and wi.kaart({**i, "stap": "buiten"})["overslaanbaar"]


def test_een_oud_kaartje_verandert_niets():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"}}
    assert wi.verwerk(i, _klik(i, "naam", tekst="Anders")) == (i, "verouderd")
    assert wi.verwerk(i, _klik(i, "samenvatting", actie="aanmaken"))[1] == "verouderd"


def test_eigen_tekst_bij_de_regelingen_is_een_zoekopdracht():
    i = {**wi.nieuwe_intake("x"), "stap": "regelingen", "antwoorden": {"naam": "Box 3"}}
    i, u = wi.verwerk(i, _klik(i, "regelingen", tekst="Awir"))
    assert (u, i["stap"], i["zoekterm"]) == ("zoek", "regelingen", "Awir")


def test_vanaf_de_samenvatting_aanpassen_aanmaken_en_afbreken():
    i = {**wi.nieuwe_intake("x"), "stap": "samenvatting", "antwoorden": {"naam": "Box 3"}}
    assert wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "wijzig", "naar": "buiten"})[0]["stap"] == "buiten"
    klaar, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})
    assert (u, klaar["stap"]) == ("aanmaken", "klaar")
    # Nog eens aanmaken mag (de api is idempotent op de intake-id); na afbreken niet.
    assert wi.verwerk(klaar, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})[1] == "aanmaken"
    weg, u = wi.verwerk(i, {"intake_id": i["id"], "stap": "samenvatting", "actie": "afbreken"})
    assert u == "afgebroken" and not wi.is_open(weg)
    assert wi.verwerk(weg, {"intake_id": i["id"], "stap": "samenvatting", "actie": "aanmaken"})[1] == "verouderd"


def test_het_kaartje_volgt_het_api_contract():
    """De vraagkaart gaat het bericht in; de api weigert stil niets, maar valideert wel."""
    import importlib.util
    import sys
    from pathlib import Path

    pad = Path(__file__).parents[3] / "api" / "app" / "gesprek_contracts.py"
    spec = importlib.util.spec_from_file_location("gesprek_contracts_intake", pad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    i = {**wi.nieuwe_intake("x"), "voorstellen": {"regelingen": OPTIES}}
    for stap in (*wi.STAPPEN, "samenvatting"):
        mod.Vraagkaart.model_validate(wi.kaart({**i, "stap": stap, "antwoorden": {"naam": "Box 3"}}))
    assert "vraagkaart" in _bericht_velden()


# --- Voorstellen ------------------------------------------------------------------------------------

def test_het_model_stelt_alleen_voor_en_een_storing_is_geen_fout():
    llm = FakeLLM([_voorstel(naam=["Box 3", "Box 3"], vraag=["Wie betaalt box 3?", "zonder vraagteken"],
                             onderwerp="box 3")])
    vs = wi.stel_voor(llm, "router", wi.nieuwe_intake("werkgebied over box 3"))
    assert vs == {"naam": ["Box 3"], "analysevraag": ["Wie betaalt box 3?"], "onderwerp": "box 3"}

    class Kapot:
        def create(self, **_):
            raise RuntimeError("provider weg")
    assert wi.stel_voor(Kapot(), "router", wi.nieuwe_intake("x")) == {"naam": [], "analysevraag": [], "onderwerp": ""}


def test_regelingen_komen_uit_het_overzicht_en_genoemde_staan_voorop(monkeypatch):
    from agent import overzicht as ov

    monkeypatch.setattr(ov, "regelingen_in_vraag", lambda g, v: ["BWBR0002320"] if "awr" in v.lower() else [])
    monkeypatch.setattr(ov, "_regelingen", lambda g: [{"bwb_id": "BWBR0002320", "namen": ["Algemene wet inzake rijksbelastingen", "AWR"]}])
    monkeypatch.setattr(ov, "bouw_overzicht", lambda g, v, onderwerp=None, scope=None: {"regelingen": [
        {"bwb_id": IB, "citeertitel": "Wet inkomstenbelasting 2001",
         "delen": [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht"}, {"iri": "", "kop": "zonder iri"}]}]})
    opties, delen, voorop = wi.regeling_opties(FakeGraph(), "belastingplicht", genoemd_in="volgens de AWR")
    assert [o["waarde"] for o in opties] == ["BWBR0002320", IB]
    assert voorop == ["BWBR0002320"] and delen == {IB: [{"iri": H2, "kop": "Hoofdstuk 2 – Belastingplicht"}]}


# --- Het gesprek ------------------------------------------------------------------------------------

def _beurt(settings, llm, vraag, actie=None, cid="g1"):
    from agent.agent import answer_stream
    from agent.models import IntakeActie

    async def run():
        return [e async for e in answer_stream(vraag, cid, settings=settings, llm=llm, graph=FakeGraph(),
                                               intake_actie=IntakeActie(**actie) if actie else None)]
    return asyncio.run(run())


def _kaart(events) -> dict[str, Any]:
    kaarten = [e["vraagkaart"] for e in events if e["type"] == "vraagkaart"]
    assert len(kaarten) == 1, events
    return kaarten[0]


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


def test_een_heel_gesprek_tot_aanmaken(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(vraag=["Wie is belastingplichtig voor box 3?"]),
                   _voorstel(onderwerp="box 3"),
                   response([text_block("WORKERS: antwoord\nSPECIALIST: algemeen\nPLAN: uitleg")], "end_turn"),
                   response([text_block("Box 3 is het inkomen uit sparen en beleggen.")], "end_turn")])

    k = _kaart(e := _beurt(settings, llm, "Ik wil een wetsanalyse uitvoeren"))
    assert wi.UITLEG in _tekst(e) and (k["stap"], k["opties"], k["overslaanbaar"]) == ("naam", [], False)
    assert llm.index == 0, "een startzin zonder inhoud kost geen modelaanroep"

    k = _kaart(_beurt(settings, llm, "Box 3", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "Box 3"}))
    assert k["stap"] == "analysevraag" and k["opties"][0]["waarde"] == "Wie is belastingplichtig voor box 3?"

    k = _kaart(_beurt(settings, llm, "Wie?", {"intake_id": k["intake_id"], "stap": "analysevraag",
                                              "keuzes": ["Wie is belastingplichtig voor box 3?"]}))
    assert k["stap"] == "regelingen" and k["meerkeuze"] and graaf[-1][0] == "box 3"
    assert [o["waarde"] for o in k["opties"]] == [IB, "BWBR0002320", wi.ONBEKEND]

    # Een tussenvraag: gewoon antwoord, het kaartje blijft open.
    tussen = _beurt(settings, llm, "Wat is box 3 eigenlijk?")
    assert not [x for x in tussen if x["type"] == "vraagkaart"]
    assert "box 3" in llm.calls[2]["system"].lower() and "OPEN KAARTJE" in llm.calls[2]["system"]

    k = _kaart(_beurt(settings, llm, "Wet IB", {"intake_id": k["intake_id"], "stap": "regelingen", "keuzes": [IB]}))
    assert k["stap"] == "onderdelen" and [o["waarde"] for o in k["opties"]] == [H2, AFD, wi.HELE + IB, wi.ONBEKEND]
    k = _kaart(_beurt(settings, llm, "Box 3", {"intake_id": k["intake_id"], "stap": "onderdelen", "keuzes": [AFD]}))
    k = _kaart(_beurt(settings, llm, "-", {"intake_id": k["intake_id"], "stap": "buiten", "actie": "overslaan"}))
    assert k["soort"] == "samenvatting" and k["samenvatting"]["bronnen"] == ["Afdeling 5.1 – Box 3"]

    e = _beurt(settings, llm, "Maak aan", {"intake_id": k["intake_id"], "stap": "samenvatting", "actie": "aanmaken"})
    [aan] = [x for x in e if x["type"] == "werkgebied_aanmaken"]
    assert aan["werkgebied"]["naam"] == "Box 3" and aan["bronnen"] == [{"bron_iri": AFD, "label": "Afdeling 5.1 – Box 3"}]
    assert llm.index == 4, "geen modelaanroep voor de klikken zelf"


def test_een_getypt_antwoord_op_het_open_kaartje(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([response([text_block("WORKERS: werkgebied\nPLAN: antwoord op het kaartje")], "end_turn"),
                   _voorstel()])
    _beurt(settings, llm, "Kunnen we een werkgebied samenstellen?")
    k = _kaart(_beurt(settings, llm, "Invordering van de erfbelasting"))
    assert k["stap"] == "analysevraag"


def test_een_kaartje_van_een_oude_intake(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([])
    _beurt(settings, llm, "Kunnen we een werkgebied samenstellen?")
    e = _beurt(settings, llm, "Box 3", {"intake_id": "oud", "stap": "naam", "tekst": "Box 3"})
    assert "niet meer loopt" in _tekst(e) and not [x for x in e if x["type"] == "vraagkaart"]


def test_vooringevuld_uit_de_eerste_zin(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(naam=["Box 3-heffing"], vraag=["Hoe wordt box 3 per 2026 berekend?"], onderwerp="box 3")])
    k = _kaart(_beurt(settings, llm, "Ik wil een werkgebied maken over de box 3-heffing per 2026"))
    assert k["vooringevuld"] == ["Box 3-heffing"] and k["opties"][0]["waarde"] == "Box 3-heffing"
    k = _kaart(_beurt(settings, llm, "ok", {"intake_id": k["intake_id"], "stap": "naam", "keuzes": ["Box 3-heffing"]}))
    assert k["opties"][0]["waarde"] == "Hoe wordt box 3 per 2026 berekend?" and llm.index == 1


def test_niets_gevonden_bij_eigen_zoekterm(tmp_path, graaf):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm = FakeLLM([_voorstel(), _voorstel()])
    k = _kaart(_beurt(settings, llm, "Kunnen we een werkgebied samenstellen?"))
    k = _kaart(_beurt(settings, llm, "X", {"intake_id": k["intake_id"], "stap": "naam", "tekst": "X"}))
    k = _kaart(_beurt(settings, llm, "-", {"intake_id": k["intake_id"], "stap": "analysevraag", "actie": "overslaan"}))
    k = _kaart(e := _beurt(settings, llm, "niets", {"intake_id": k["intake_id"], "stap": "regelingen", "tekst": "niets"}))
    assert k["stap"] == "regelingen" and [o["waarde"] for o in k["opties"]] == [wi.ONBEKEND]
    assert "Ik vond geen regeling bij ‘niets’." in k["toelichting"] and "Weet ik (nog) niet" in _tekst(e)


# --- Aanmaken door de driver -------------------------------------------------------------------------

class NepApi:
    def __init__(self, weiger: set[str] = frozenset(), faal: bool = False):
        self.werkgebieden: dict[str, dict[str, Any]] = {}
        self.bronnen: list[dict[str, Any]] = []
        self.berichten: list[dict[str, Any]] = []
        self.weiger, self.faal = weiger, faal

    async def maak_werkgebied(self, invoer):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if self.faal:
            raise WetsanalyseApiFout("POST → 503", 503)
        wg = self.werkgebieden.setdefault(invoer["intake_id"], {"id": f"wg-{len(self.werkgebieden) + 1}",
                                                                 "revisie": 1, **invoer})
        return dict(wg)

    async def voeg_bron_toe(self, wid, bron):
        from agent.wetsanalyse_api import WetsanalyseApiFout
        if bron.get("bron_iri") in self.weiger:
            raise WetsanalyseApiFout("POST → 422", 422)
        self.bronnen.append(bron)
        wg = next(w for w in self.werkgebieden.values() if w["id"] == wid)
        wg["revisie"] += 1
        return {"werkgebied": dict(wg)}

    async def voeg_bericht_toe(self, gid, bericht):
        self.berichten.append(bericht)
        return {}

    async def aclose(self):
        pass


def _driver(monkeypatch, nep, events):
    from agent import beurt
    from agent.runs import Run

    monkeypatch.setattr(beurt, "WetsanalyseApi", lambda settings, user: nep)
    settings = make_settings(wetsanalyse_api_url="http://api", wetsanalyse_api_token="t")

    async def stroom():
        for e in events:
            yield e

    async def run():
        return [e async for e in beurt.voer_beurt_uit(stroom(), settings=settings, run=Run(run_id="r1", conversation_id="g1", user_id="u"),
                                                      gesprek_id="g1", user_id="u")]
    return asyncio.run(run())


VERZOEK = {"type": "werkgebied_aanmaken", "intake_id": "ik1",
           "werkgebied": {"naam": "Box 3", "analysevraag": "Wie?", "afbakening": "", "intake_id": "ik1"},
           "bronnen": [{"bron_iri": AFD, "label": "Afdeling 5.1"}, {"bron_iri": H2, "label": "Hoofdstuk 2"}]}


def test_de_driver_maakt_het_werkgebied_met_bronnen(monkeypatch):
    nep = NepApi(weiger={H2})
    uit = _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert [b["bron_iri"] for b in nep.bronnen] == [AFD]
    assert nep.bronnen[0] | {} == {"bron_iri": AFD, "verwachte_revisie": 1, "rol": "analyseren",
                                   "bereik": "onderliggend", "reden": wi.REDEN}
    [bericht] = nep.berichten
    assert bericht["artefact"] == {"soort": "werkgebied", "titel": "Box 3", "ref": {"werkgebied_id": "wg-1"}}
    assert "met 1 bron" in bericht["tekst"] and "Hoofdstuk 2" in bericht["tekst"] and "deelvragen" in bericht["tekst"]
    [opgeslagen] = [e for e in uit if e["type"] == "opgeslagen"]
    assert opgeslagen["artefact"] == bericht["artefact"] and uit[-1]["type"] == "done"
    # Nog eens: hetzelfde werkgebied, niets dubbel.
    _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert len(nep.werkgebieden) == 1


def test_mislukt_aanmaken_dan_een_fout_en_geen_bericht(monkeypatch):
    nep = NepApi(faal=True)
    uit = _driver(monkeypatch, nep, [dict(VERZOEK), {"type": "done"}])
    assert [e.get("foutcode") for e in uit if e["type"] == "error"] == ["werkgebied_niet_aangemaakt"]
    assert not nep.berichten and uit[-1]["type"] == "done"


def test_het_kaartje_gaat_mee_in_het_bericht(monkeypatch):
    nep = NepApi()
    kaart = wi.kaart(wi.nieuwe_intake("x"))
    _driver(monkeypatch, nep, [{"type": "token", "content": "Hoe noemen we het?"},
                               {"type": "vraagkaart", "vraagkaart": kaart}, {"type": "done"}])
    assert nep.berichten[0]["vraagkaart"] == kaart and json.dumps(nep.berichten[0])


def test_een_klik_gaat_nooit_een_harde_route_in():
    r = ChatRequest(question="Stel begrippen voor", werkgebied_id="wg1",
                    intake_actie={"intake_id": "ik1", "stap": "naam", "tekst": "Stel begrippen voor"})
    assert r.intake_actie is not None
    with pytest.raises(Exception):
        ChatRequest(question="x", intake_actie={"intake_id": "ik 1", "stap": "naam"})


def test_de_supervisor_kent_de_werkgebied_worker_en_ketent_hem_niet():
    from agent.supervisor import parse_supervisor

    assert parse_supervisor("WORKERS: werkgebied, antwoord\nPLAN: samenstellen") == (["werkgebied"], "samenstellen", False)
    assert parse_supervisor("WORKERS: antwoord\nSPECIALIST: duiding\nPLAN: x")[0] == ["duiding"]


def test_artikelnummers_in_eigen_tekst():
    assert wi.artikelen_in("artikel 5.2 en 5.3, art. 7a") == ["5.2", "5.3", "7a"]
    assert wi.artikelen_in("hoofdstuk 5") == []
