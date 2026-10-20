"""De agents onder de supervisor (F3c, ADR-005): routering, de node `agent_taak`, de deelvragen-agent.

Bewaakt:
1. de supervisor kiest `deelvragen`/`begrippen` met een `TAAK:` uit een vaste lijst, en een `actie` zonder model;
2. de node maakt van de uitkomst events (status, token, artefact, bevestiging), en de beurt-driver legt ze vast;
3. elke taak zonder model draait zonder één modelaanroep (`FakeLLM([])` faalt bij de eerste);
4. de modelstap van `verbeteren` valideert in code: nooit een half voorstel.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent.agent import answer_stream
from agent.agents import Uitkomst, deelvragen as dva, register
from agent.beurt import BeurtSchrijver
from agent.deelvragen import TOOL_VERBETER, valideer_verbetering
from agent.models import ACTIE_TAAK
from agent.supervisor import parse_supervisor, parse_taak
from fakes import FakeGraph, FakeLLM, agent_ctx, make_settings, response, text_block, tool_block

WG = {"id": "wg1", "naam": "Invorderbaarheid", "analysevraag": "Wanneer is een aanslag invorderbaar?",
      "bronnen": [{"id": "s1", "label": "art. 9 Iw", "rol": "analyseren"}, {"id": "s2", "label": "art. 2 AWR", "rol": "context"}],
      "deelvragen": [{"id": "d1", "vraag": "Wanneer vervalt de betalingstermijn?", "status": "actief", "bronnen": ["s1"]},
                     {"id": "d2", "vraag": "Wie is belastingschuldige en wanneer moet hij betalen?", "status": "actief",
                      "bronnen": []},
                     {"id": "d3", "vraag": "Een voorstel?", "status": "voorgesteld", "bronnen": []}]}
DEKKING = {"deelvragen": [{"id": "d1", "vraag": "Wanneer vervalt de betalingstermijn?", "stand": "geen_begrip",
                           "bronnen": [{"id": "s1", "label": "art. 9 Iw"}], "begrippen": []},
                          {"id": "d2", "vraag": "Wie is belastingschuldige en wanneer moet hij betalen?",
                           "stand": "geen_bron", "bronnen": [], "begrippen": []}],
           "telling": {"gedekt": 0, "geen_begrip": 1, "geen_bron": 1}, "totaal": 2}
KANDIDATEN = {"kandidaten": [{"id": "k1", "label": "art. 10 Iw", "status": "voorgesteld",
                              "bewijs": [{"methode": "deelvraag", "detail": {"deelvraag_id": "d2"}}]}]}


class NepApi:
    def __init__(self):
        self.voorgesteld: list[list[str]] = []
        self.gesloten = False

    async def haal_werkgebied(self, wid):
        return WG

    async def haal_deelvragen_dekking(self, wid):
        return DEKKING

    async def haal_kandidaten(self, wid):
        return KANDIDATEN

    async def stel_deelvragen_voor(self, wid, vragen, model=""):
        self.voorgesteld.append(vragen)
        return {"nieuw": [f"n{i}" for i in range(len(vragen))], "overgeslagen": []}

    async def aclose(self):
        self.gesloten = True


def _api_settings(**kw):
    return make_settings(wetsanalyse_api_url="http://api.test", wetsanalyse_api_token="t", qa_api_token="q", **kw)


# --- 1. de supervisor ------------------------------------------------------------------------------

def test_de_taak_staat_op_een_eigen_regel_en_de_agents_ketenen_met_niets():
    tekst = "WORKERS: deelvragen, antwoord\nSPECIALIST: algemeen\nTAAK: Dekking.\nPLAN: de dekking"
    assert parse_taak(tekst) == "dekking"
    assert parse_supervisor(tekst)[0] == ["deelvragen"]
    assert parse_supervisor("WORKERS: begrippen\nPLAN: x")[0] == ["begrippen"]
    assert parse_taak("WORKERS: antwoord\nPLAN: x") == ""


def test_elke_actie_hoort_bij_een_bestaande_taak():
    for actie, (agent, taak) in ACTIE_TAAK.items():
        assert register.is_taak(agent, taak), actie
    # En elke taak is met een actie te kiezen: F3d hoeft alleen suggesties te maken.
    gekozen = set(ACTIE_TAAK.values())
    for agent in register.AGENTS:
        assert {(agent, t) for t in register.taken(agent)} <= gekozen, agent


def test_parameters_komen_uit_wat_er_ligt():
    o = {"soort": "deelvraag", "werkgebied_id": "wg1", "id": "d2"}
    assert register.parameters("deelvragen", "verbeteren", onderwerp=o, actie="deelvraag_splitsen") == {
        "werkgebied_id": "wg1", "deelvraag_id": "d2", "soort": "splits"}
    assert register.parameters("deelvragen", "dekking", vraag="is deelvraag 2 gedekt?", werkgebied_id="wg1") == {
        "werkgebied_id": "wg1", "deelvraag_nr": 2}
    assert register.parameters("begrippen", "voorbeelden", vraag="geef voorbeelden van termijn",
                               onderwerp={"soort": "begrip", "werkgebied_id": "wg1", "id": "b1"}) == {
        "werkgebied_id": "wg1", "begrip_id": "b1", "termen": ["termijn"]}
    assert register.parameters("begrippen", "meedenken", werkgebied_id="wg1", bevestigd=3) == {
        "werkgebied_id": "wg1", "bevestigd": 3}


def _beurt(vraag: str, llm, *, api=None, **kw) -> list[dict[str, Any]]:
    settings = _api_settings(enable_decomposition=False)

    async def verzamel():
        return [e async for e in answer_stream(vraag, None, settings=settings, llm=llm, graph=FakeGraph(),
                                               user_id="jurist", run_id="r1", werkgebied_id="wg1",
                                               agent_api=lambda s, u: api or NepApi(), **kw)]
    return asyncio.run(verzamel())


def test_een_actie_kiest_agent_en_taak_zonder_model():
    llm = FakeLLM([])
    events = _beurt("Hoe staat de dekking ervoor?", llm, actie="dekking")
    assert llm.calls == []
    assert any(e.get("message", "").startswith("Supervisor · kiest de deelvragen-agent · taak dekking (suggestie)")
               for e in events)
    token = "".join(e["content"] for e in events if e["type"] == "token")
    assert "0 van 2 deelvragen gedekt" in token and "alleen context" not in token
    assert "1 kandidaat van Lex open" in token and "nog geen bron" in token
    [artefact] = [e["artefact"] for e in events if e["type"] == "artefact"]
    assert artefact == {"soort": "werkgebied", "titel": "Invorderbaarheid", "ref": {"werkgebied_id": "wg1"}}


def test_een_getypte_vraag_kiest_de_agent_met_het_model():
    llm = FakeLLM([response([text_block("WORKERS: deelvragen\nSPECIALIST: algemeen\nTAAK: dekking\nPLAN: d")],
                            "end_turn")])
    events = _beurt("Is deelvraag 2 gedekt?", llm)
    assert len(llm.calls) == 1                                   # alleen de supervisor
    token = "".join(e["content"] for e in events if e["type"] == "token")
    assert token.startswith("Dekking in werkgebied *Invorderbaarheid*") and "“Wie is belastingschuldige" in token
    assert "Wanneer vervalt" not in token                       # alleen de aangewezen deelvraag


def test_een_onbekende_taak_is_een_vraag_van_lex_geen_stille_beurt():
    llm = FakeLLM([response([text_block("WORKERS: begrippen\nSPECIALIST: algemeen\nTAAK: toveren\nPLAN: x")],
                            "end_turn")])
    events = _beurt("Doe iets met de begrippen", llm)
    token = "".join(e["content"] for e in events if e["type"] == "token")
    assert "Wat wil je dat ik doe?" in token and "uitwerken" in token
    assert not any(e["type"] == "artefact" for e in events)


def test_het_hele_werkgebied_annoteren_is_een_taak_van_de_annotatie_agent():
    class Werkvoorraad(NepApi):
        async def haal_annotatie_werkvoorraad(self, wid):
            return {"naam": "Inv", "te_annoteren": ["urn:bwb:X:artikel:1"], "eenheden": [], "schatting": None,
                    "budget": {}}

    llm = FakeLLM([response([text_block("WORKERS: annotatie\nSPECIALIST: algemeen\nTAAK: werkgebied\nPLAN: x")],
                            "end_turn")])
    events = _beurt("Annoteer wat nog niet geannoteerd is", llm, api=Werkvoorraad())
    [bevestiging] = [e["bevestiging"] for e in events if e["type"] == "bevestiging"]
    assert bevestiging["soort"] == "werkgebied_annoteren" and bevestiging["aantal"] == 1
    assert not any(e["type"] in ("doel", "element") for e in events)    # niets geannoteerd zonder bevestiging


def test_een_storing_van_de_api_is_een_zin_in_het_gesprek():
    class Kapot(NepApi):
        async def haal_werkgebied(self, wid):
            raise RuntimeError("weg")

    api = Kapot()
    events = _beurt("x", FakeLLM([]), api=api, actie="dekking")
    token = "".join(e["content"] for e in events if e["type"] == "token")
    assert "haperde" in token and api.gesloten


def test_zonder_api_zegt_lex_dat_hij_niets_kan_bewaren():
    async def verzamel():
        return [e async for e in answer_stream("x", None, settings=make_settings(), llm=FakeLLM([]), graph=FakeGraph(),
                                               werkgebied_id="wg1", actie="dekking")]
    token = "".join(e["content"] for e in asyncio.run(verzamel()) if e["type"] == "token")
    assert "Zonder koppeling met de wetsanalyse-api" in token


# --- 2. de beurt-driver ----------------------------------------------------------------------------

def test_de_beurt_driver_neemt_artefact_en_bevestiging_mee():
    s = BeurtSchrijver()
    for ev in ({"type": "token", "content": "Klaar."}, {"type": "artefact", "artefact": {"soort": "werkgebied"}},
               {"type": "bevestiging", "bevestiging": {"soort": "begrippen_verdiepen", "aantal": 2}}):
        s.verwerk(ev)
    assert s.tekst == "Klaar." and s.artefact == {"soort": "werkgebied"} and s.bevestiging["aantal"] == 2


# --- 3. de deelvragen-agent ------------------------------------------------------------------------

def _taak(taak: str, llm=None, api=None, **params):
    api = api or NepApi()
    invoer = register.invoer("deelvragen", taak, {"werkgebied_id": "wg1", **params})
    return asyncio.run(dva.voer_uit(invoer, agent_ctx(api, settings=_api_settings(), llm=llm or FakeLLM([])))), api


@pytest.mark.parametrize("taak", sorted(set(register.taken("deelvragen")) - {t.value for t in dva.MODEL_TAKEN}))
def test_een_taak_zonder_model_roept_geen_model_aan(taak, monkeypatch):
    async def bronnen(ctx, wid, did=""):
        return Uitkomst(taak="bronnen_zoeken", tekst="gezocht")
    monkeypatch.setattr(dva, "bronnen_kern", bronnen)
    llm = FakeLLM([])
    uit, _ = _taak(taak, llm)
    assert llm.calls == [] and uit.status == "ok" and uit.meting.get("model") is not True


def test_deelvraag_op_nummer_telt_alleen_actieve():
    uit, _ = _taak("dekking", deelvraag_nr=2)
    assert "Wie is belastingschuldige" in uit.tekst
    uit, _ = _taak("dekking", deelvraag_nr=3)
    assert uit.status == "geweigerd" and "heeft er 2" in uit.reden


def test_verbeteren_vraagt_een_deelvraag():
    uit, _ = _taak("verbeteren")
    assert uit.status == "geweigerd" and "Welke deelvraag" in uit.reden


def _verbeter(soort, vragen):
    return response([tool_block("t", TOOL_VERBETER, {"soort": soort, "vragen": vragen, "motivatie": "Twee dingen."})],
                    "tool_use")


def test_splitsen_wordt_twee_voorstellen_met_de_methode_in_de_prompt():
    llm = FakeLLM([_verbeter("splits", ["Wie is belastingschuldige?", "Wanneer moet de belastingschuldige betalen?"])])
    uit, api = _taak("verbeteren", llm, deelvraag_id="d2", soort="splits")
    assert api.voorgesteld == [["Wie is belastingschuldige?", "Wanneer moet de belastingschuldige betalen?"]]
    assert "te splitsen in 2 deelvragen" in uit.tekst and "trek de oude deelvraag in" in uit.tekst
    systeem = llm.calls[0]["system"]
    assert "WETSANALYSE" in systeem and "rol deelvragen" in systeem and "Dekking betekent" in systeem
    assert "Gevraagd: splits" in llm.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("item, soort", [
    ({"soort": "herformuleer", "vragen": ["Wanneer vervalt de betalingstermijn?"]}, "geen"),   # niets nieuws
    ({"soort": "herformuleer", "vragen": ["Wanneer?", "Wie is het?"]}, "geen"),                # te kort, te veel
    ({"soort": "splits", "vragen": ["Wie is belastingschuldige?"]}, "geen"),                 # één is geen splitsing
    ({"soort": "toveren", "vragen": ["Wie is belastingschuldige?"]}, "geen"),
    ({"soort": "herformuleer", "vragen": ["Op welke dag vervalt de betalingstermijn?"]}, "herformuleer"),
])
def test_de_verbetering_wordt_in_code_gevalideerd(item, soort):
    d = WG["deelvragen"][0]
    assert valideer_verbetering({**item, "motivatie": "m"}, d, [])[0] == soort


def test_geen_verbetering_is_een_antwoord_zonder_voorstel():
    llm = FakeLLM([_verbeter("geen", [])])
    uit, api = _taak("verbeteren", llm, deelvraag_id="d1")
    assert api.voorgesteld == [] and "geen betere formulering" in uit.tekst and uit.status == "ok"


def test_de_verbetering_past_in_het_api_contract():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))
    try:
        from app.werkgebied_contracts import DeelvraagVoorstellen
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    _, vragen, _ = valideer_verbetering({"soort": "splits", "vragen": [f"Vraag nummer {i}?" for i in range(9)]},
                                        WG["deelvragen"][1], [])
    assert vragen == []                                          # meer dan vier is geen splitsing
    _, vragen, _ = valideer_verbetering({"soort": "splits", "vragen": ["Vraag een?", "Vraag twee?"]},
                                        WG["deelvragen"][1], [])
    DeelvraagVoorstellen(vragen=vragen, model="m")
