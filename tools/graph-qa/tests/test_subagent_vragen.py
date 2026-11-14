"""Vragen naar boven en hervatten (ADR-016 §A4): een rapport met `status: vraag`, de delegatie op `wacht`, de centrale
agent die één keer hervat, de vraagkaart voor de jurist, de klik zonder model, en doorvragen in een deelgesprek."""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api.main as main
from agent import overdracht, subagent as sub
from agent.models import ChatRequest
from agent.nodes import subagent_vervolg as vervolg
from agent.nodes import supervisie
from agent.sjablonen import Onvulbaar, vul
from agent.wetsanalyse_api import WetsanalyseApiFout
from test_subagent import ARTIKEL, OPDRACHT, STATE, _kinderen, _rapport

VRAGEN = [{"tekst": "Over welk belastingjaar gaat het?", "opties": ["2024", "2025"]},
          {"tekst": "Gaat het om een naheffingsaanslag?", "opties": []}]


def _vraag(**extra) -> dict:
    return {**_rapport(), "status": "vraag", "bevindingen": "", "onderbouwing": [], "vragen": VRAGEN, **extra}


# -- het rapport met een vraag ----------------------------------------------------------------------------

def test_een_vraag_is_een_rapport_met_status_vraag_en_de_vragen_erin():
    a = vul("rapport", _vraag(), [])
    assert [b.kop for b in a.blokken] == ["Gedaan", "Vragen"]
    assert "Over welk belastingjaar gaat het? (opties: 2024; 2025)" in a.blokken[1].tekst
    # Wat hij al vond mag erbij, met de controle van een uitleg.
    a = vul("rapport", _vraag(bevindingen=_rapport()["bevindingen"], onderbouwing=_rapport()["onderbouwing"]), [ARTIKEL])
    assert [b.kop for b in a.blokken if b.soort == "toelichting"] == ["Gedaan", "Bevindingen", "Vragen"]


@pytest.mark.parametrize("invoer", [
    _vraag(vragen=[]),                                                     # vraag zonder vraag
    _vraag(vragen=[{"tekst": "Welk jaar " * 40 + "?", "opties": []}]),     # te lang
])
def test_de_code_toetst_de_vragen(invoer):
    with pytest.raises(Onvulbaar) as fout:
        vul("rapport", invoer, [ARTIKEL])
    assert fout.value.code == "rapport_vragen"


def test_een_vraag_in_de_verkeerde_vorm_weigert_het_rapport_niet():
    """Meting bundel 115, D01: het kind wilde vragen, het rapport werd geweigerd op `rapport_vragen`, en het eindigde
    `niet_gelukt` zonder bevindingen. De code herstelt de vorm."""
    from agent.sjablonen.rapport import MAX_OPTIES, MAX_VRAGEN, genormaliseerd, status_van, vragen_van

    # niet_gelukt met een vraag is een vraag: het kind kan niet verder zonder antwoord.
    niet = {**_vraag(), "status": "niet_gelukt"}
    assert status_van(niet) == "vraag" and vragen_van(niet)
    assert [b.kop for b in vul("rapport", niet, [ARTIKEL]).blokken if b.soort == "toelichting"][-1] == "Vragen"
    # klaar met vragen blijft klaar; de vragen staan onder Open.
    klaar = genormaliseerd({**_rapport(), "vragen": VRAGEN})
    assert klaar["status"] == "klaar" and not klaar["vragen"] and any(p.startswith("Open vraag: ") for p in klaar["open"])
    vul("rapport", {**_rapport(), "vragen": VRAGEN}, [ARTIKEL])
    # Een vraagteken erbij, opties en vragen begrensd, de rest onder Open.
    n = genormaliseerd(_vraag(vragen=[{"tekst": f"Welk jaar {i}.", "opties": list("abcde")} for i in range(5)]))
    assert len(n["vragen"]) == MAX_VRAGEN and all(v["tekst"].endswith("jaar 0?") or v["tekst"].endswith("?")
                                                   for v in n["vragen"])
    assert n["vragen"][0]["tekst"] == "Welk jaar 0?" and len(n["vragen"][0]["opties"]) == MAX_OPTIES
    assert sum(p.startswith("Open vraag: ") for p in n["open"]) == 2


# -- de afloop: wachten, en hervatten ---------------------------------------------------------------------

class Api:
    """De api van een subagent met een delegatie die wacht."""

    def __init__(self, status: str = "wacht", conflict: bool = False):
        self.aanroepen: list[tuple[str, object]] = []
        self.delegatie = {"id": "d1", "soort": "subagent", "status": status, "werkgebied_id": "",
                          "plan": {"taken": [{"profiel": "duiding", "opdracht": OPDRACHT.model_dump()}]},
                          "uitkomst": {"kinderen": [{"profiel": "duiding", "gesprek_id": "kind-1", "uitkomst": "vraag",
                                                     "vragen": VRAGEN}]}}
        self.conflict = conflict

    def __getattribute__(self, naam):
        if not naam.startswith("_") and naam not in ("aanroepen", "conflict", "delegatie"):
            assert naam in sub.API_AANROEPEN, f"de subagent roept {naam} aan"
        return object.__getattribute__(self, naam)

    async def start_delegatie(self, invoer):
        self.aanroepen.append(("start_delegatie", invoer))
        return {"id": "d1"}

    async def haal_delegatie(self, did):
        self.aanroepen.append(("haal_delegatie", did))
        return self.delegatie

    async def voeg_bericht_toe(self, gesprek_id, bericht):
        # Apart van `aanroepen`: de tests hieronder tellen de aanroepen op de delegatie.
        object.__getattribute__(self, "__dict__").setdefault("berichten", []).append((gesprek_id, bericht))
        return {}

    async def wijzig_delegatie(self, did, wijziging):
        if self.conflict and wijziging.get("status") == "loopt":
            raise WetsanalyseApiFout("bezet", 409, "delegatie_loopt_al")
        self.aanroepen.append(("wijzig_delegatie", wijziging))
        if wijziging.get("status"):
            self.delegatie = {**self.delegatie, "status": wijziging["status"],
                              **({"uitkomst": wijziging["uitkomst"]} if "uitkomst" in wijziging else {})}
        return self.delegatie

    async def maak_gesprek(self, invoer):
        self.aanroepen.append(("maak_gesprek", invoer))
        return {"id": "kind-1"}

    async def aclose(self):
        pass


VRAAG_KIND = {"rapport": {"status": "vraag", "vragen": VRAGEN}, "answer": "Gedaan: gezocht.\nVragen: …",
              "source_trace": [ARTIKEL]}


def test_een_subagent_met_een_vraag_wacht_bij_de_api():
    api, events = Api(), []
    kinderen, _, _ = _kinderen(VRAAG_KIND)
    afloop, _, weigering = asyncio.run(sub.voer_uit(STATE, "duiding", OPDRACHT, events.append, settings=None,
                                                    kinderen=kinderen, gestopt=lambda: False, api=api))
    assert not weigering and (afloop.uitkomst, afloop.vragen, afloop.delegatie_id) == ("vraag", VRAGEN, "d1")
    eind = api.aanroepen[-1][1]
    assert eind == {"status": "wacht", "uitkomst": {"kinderen": [afloop.als_dict()]}}
    assert events[-1]["uitkomst"] == "wacht" and events[-1]["wacht"] == 1


def test_hervatten_is_een_nieuwe_beurt_in_hetzelfde_deelgesprek():
    api, events = Api(), []
    kinderen, gestart, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Bevindingen: 2024.",
                                      "source_trace": [ARTIKEL]})
    afloop, kind, weigering = asyncio.run(sub.hervat(STATE, "d1", ["2024", "nee"], events.append, settings=None,
                                                     kinderen=kinderen, gestopt=lambda: False, van="van de gebruiker",
                                                     api=api))
    assert not weigering and afloop.hervat and afloop.uitkomst == "klaar" and kind["answer"] == "Bevindingen: 2024."
    assert [n for n, _ in api.aanroepen] == ["haal_delegatie", "wijzig_delegatie", "wijzig_delegatie"]
    assert api.delegatie["uitkomst"]["kinderen"][0]["uitkomst"] == "klaar"
    assert api.aanroepen[1][1] == {"status": "loopt"} and api.aanroepen[2][1]["status"] == "klaar"
    [(verzoek, _, _)] = gestart
    assert verzoek.conversation_id == "kind-1", "hetzelfde deelgesprek, geen nieuw"
    assert (verzoek.profiel, verzoek.opdracht, verzoek.delegatie_id) == ("duiding", OPDRACHT, "d1")
    assert verzoek.question.splitlines() == [
        "ANTWOORD OP JE VRAGEN (van de gebruiker)", "- Over welk belastingjaar gaat het?", "  Antwoord: 2024",
        "- Gaat het om een naheffingsaanslag?", "  Antwoord: nee",
        sub.antwoord_tekst([], [], van="").splitlines()[-1]]
    assert "eerste keer al kon stellen" in verzoek.question, "vragen in één keer (meting bundel 116, D01)"
    assert events[0]["hervat"] is True
    # De antwoorden staan als bericht in het deelgesprek (analyse centrale agent, gat 6).
    assert api.__dict__["berichten"] == [("kind-1", {"rol": "user", "tekst": verzoek.question})]


@pytest.mark.parametrize("api", [Api(status="klaar"), Api(conflict=True)])
def test_hervatten_weigert_als_de_vraag_niet_meer_openstaat_of_er_ander_werk_loopt(api):
    kinderen, gestart, _ = _kinderen({})
    _, _, weigering = asyncio.run(sub.hervat(STATE, "d1", ["2024"], lambda _e: None, settings=None, kinderen=kinderen,
                                             gestopt=lambda: False, van="x", api=api))
    assert weigering in (sub.AL_BEANTWOORD, sub.BEZET) and not gestart


# -- de centrale agent: de vraag gaat naar de jurist -----------------------------------------------------

def _bouw(kinderen):
    return SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                           graph=None)


def test_een_rapport_met_een_vraag_zegt_de_centrale_agent_wat_hij_kan():
    tekst = sub.als_toolresultaat("duiding", "vraag", "Vragen: …")
    # De vraag gaat naar de gebruiker; de centrale agent beantwoordt haar niet zelf (geen hervat_subagent in het voorvoegsel).
    assert "als kaart" in tekst and "niet zelf" in tekst and "hervat_subagent" not in tekst


def test_de_vraagkaart_volgt_het_contract_van_de_werkplek():
    k = sub.vraagkaart("0123456789abcdef", VRAGEN, 2)
    assert re.fullmatch(r"[A-Za-z0-9-]{1,64}", k["intake_id"]) and k["intake_id"] == "sa-0123456789abcdef"
    assert (k["modus"], k["stap"], k["nr"], k["totaal"], k["vraag"]) == (
        "subagent", "sa_vraag", 2, 2, "Gaat het om een naheffingsaanslag?")
    assert sub.vraagkaart("d1", VRAGEN, 1)["opties"] == [{"label": "2024", "waarde": "2024"},
                                                         {"label": "2025", "waarde": "2025"}]
    assert sub.open_vraag([{"uitkomst": "klaar"}, {"uitkomst": "vraag", "vragen": VRAGEN, "delegatie_id": "d1"}])
    assert sub.open_vraag([{"uitkomst": "klaar", "delegatie_id": "d1"}]) is None


def test_de_beurt_eindigt_met_de_vraagkaart_als_er_een_vraag_openstaat(monkeypatch):
    """`finalize_node` stuurt de kaart na het antwoord, uit code."""
    from agent.nodes import antwoord as antwoordnodes
    from fakes import FakeGraph, FakeLLM, make_settings

    events = []
    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: events.append)
    b = SimpleNamespace(settings=make_settings(), graph=FakeGraph(), llm=FakeLLM([]))
    state = {"answer": "De subagent vond nog niets en heeft een vraag.", "question": "x", "source_trace": [],
             "subagenten": [{"uitkomst": "vraag", "vragen": VRAGEN, "delegatie_id": "d1"}], "messages": []}
    antwoordnodes.finalize_node(b, state)
    kaarten = [e["vraagkaart"] for e in events if e.get("type") == "vraagkaart"]
    assert kaarten and kaarten[0]["intake_id"] == "sa-d1" and kaarten[0]["nr"] == 1


# -- de klik op de vraagkaart: zonder model --------------------------------------------------------------

def _klik(actie: str = "antwoord", **velden) -> dict:
    return {**STATE, "intake_actie": {"intake_id": "sa-d1", "stap": "sa_vraag", "actie": actie, **velden}}


def _vervolg_bouw(api, kinderen):
    return SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None,
                           stop_check=None, graph=None, agent_api=lambda *_a: api)


def _draai_vervolg(monkeypatch, api, kinderen, state):
    events = []
    monkeypatch.setattr(vervolg, "get_stream_writer", lambda: events.append)
    upd = vervolg.subagent_vervolg_node(_vervolg_bouw(api, kinderen), state)
    return upd, events


def test_een_klik_legt_het_antwoord_vast_en_toont_de_volgende_vraag(monkeypatch):
    api = Api()
    kinderen, gestart, _ = _kinderen({})
    upd, events = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=["2024"]))
    assert api.aanroepen[-1][1]["uitkomst"]["kinderen"][0]["antwoorden"] == ["2024"]
    assert api.delegatie["status"] == "wacht"
    [kaart] = [e["vraagkaart"] for e in events if e["type"] == "vraagkaart"]
    assert (kaart["nr"], kaart["totaal"]) == (2, 2) and not gestart
    assert vervolg.route_na_vervolg(None, {**_klik(), **upd}) == "einde"


def test_na_de_laatste_vraag_hervat_de_code_en_schrijft_de_centrale_agent_de_bundel(monkeypatch):
    api = Api()
    api.delegatie["uitkomst"]["kinderen"][0]["antwoorden"] = ["2024"]
    kinderen, gestart, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Bevindingen: gewone aanslag.",
                                      "source_trace": [ARTIKEL]})
    upd, events = _draai_vervolg(monkeypatch, api, kinderen, _klik(tekst="Nee, een gewone aanslag."))
    [(verzoek, _, _)] = gestart
    assert "Antwoord: 2024" in verzoek.question and "Antwoord: Nee, een gewone aanslag." in verzoek.question
    assert upd["rapporten"].startswith("RAPPORTEN VAN DE SUBAGENTS") and "Bevindingen: gewone aanslag." in upd["rapporten"]
    assert ARTIKEL in upd["source_trace"] and upd["specialist"] == "centraal"
    assert vervolg.route_na_vervolg(None, upd) == "agent"
    assert not any(e["type"] == "vraagkaart" for e in events)


def test_laat_maar_stopt_de_subagent_en_een_oude_klik_doet_niets(monkeypatch):
    api = Api()
    kinderen, gestart, _ = _kinderen({})
    upd, _ = _draai_vervolg(monkeypatch, api, kinderen, _klik("afbreken"))
    assert upd["answer"] == vervolg.GESTOPT and api.delegatie["status"] == "gestopt" and not gestart
    upd, events = _draai_vervolg(monkeypatch, api, kinderen, _klik(keuzes=["2024"]))
    assert upd["answer"] == sub.AL_BEANTWOORD and not any(e["type"] == "vraagkaart" for e in events)


def test_de_supervisor_stuurt_een_klik_zonder_model_naar_het_vervolg(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan"))
    upd = supervisie._kies(b, {**_klik(), "question": "2024"})
    assert upd["specialist"] == "subagent_vervolg" and supervisie._entry_node(b, upd) == "subagent_vervolg"
    # Zonder centrale agent bestaat de node niet: een vaste zin.
    upd = supervisie._kies(SimpleNamespace(settings=SimpleNamespace(centrale_agent="uit")), {**_klik(), "question": "x"})
    assert upd["afwijzen"] is True and upd["afwijs_melding"]


# -- doorvragen in een deelgesprek ------------------------------------------------------------------------

def test_doorvragen_in_een_deelgesprek_houdt_het_profiel_en_markeert_de_delegatie(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    api = Api()
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), loop=None,
                        agent_api=lambda *_a: api, graph=None)
    state = {**STATE, "question": "En geldt dat ook voor een naheffing?", "modus": "auto",
             "deelgesprek": {"delegatie_id": "d1", "profiel": "duiding"}}
    upd = supervisie._kies(b, state)
    assert (upd["specialist"], upd["worker_plan"]) == ("duiding", ["duiding"])
    assert api.aanroepen == [("wijzig_delegatie", {"later_gewijzigd": True})]


def test_de_delegatie_reist_alleen_met_een_opdracht_en_niet_via_http(monkeypatch):
    ChatRequest(question="x", profiel="algemeen", opdracht=OPDRACHT, delegatie_id="d1")
    with pytest.raises(ValueError):
        ChatRequest(question="x", delegatie_id="d1")
    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    with TestClient(main.app) as c:
        r = c.post("/v1/runs", headers={"X-User-Id": "a"}, json={
            "question": "x", "conversation_id": "g", "profiel": "algemeen", "opdracht": OPDRACHT.model_dump(),
            "delegatie_id": "d1"})
    assert r.status_code == 422 and r.json()["detail"]["reden"] == "subagent_intern"


def test_met_meer_kinderen_wacht_de_delegatie_zolang_er_een_een_vraag_heeft():
    vraag, klaar = {"uitkomst": "vraag", "vragen": VRAGEN}, {"uitkomst": "klaar"}
    assert sub.eindstand([klaar, vraag]) == "wacht" and sub.eerste_vraag([klaar, vraag]) == 1
    assert sub.eindstand([klaar, {"uitkomst": "niet_gelukt"}]) == "klaar"
    assert sub.eindstand([klaar, {"uitkomst": "mislukt"}]) == "klaar"
    assert sub.eindstand([{"uitkomst": "mislukt"}]) == "mislukt" and sub.eindstand([{"uitkomst": "gestopt"}]) == "gestopt"
    assert sub.eerste_vraag([klaar]) is None
