"""Lex annoteert het werkgebied (spoor D, fase B2): voorstel, bevestiging, de run en zijn grenzen."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from agent import werkgebied_annotatie as wa
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.models import ChatRequest
from agent.runs import Run
from agent.wetsanalyse_api import WetsanalyseApiFout
from fakes import FakeGraph, KetenLLM
from test_contract_drift import _bericht_velden
from test_reeks import ART8, L1, L2, ROWS, LeesApi, _settings, api  # noqa: F401

ONBEKEND = "urn:bwb:BWBR0004770:artikel:99"


def _eenheid(iri: str, label: str, status: str = "nieuw") -> dict[str, Any]:
    return {"bron_iri": iri, "label": label, "regeling": "Invorderingswet 1990", "bwb_id": "BWBR0004770",
            "stand": {"status": status, "voorstellen": 0, "te_beoordelen": 0}, "selecties": ["s1"]}


def _werkvoorraad(*iris: str, schatting=True, al: int = 0, context: int = 1) -> dict[str, Any]:
    eenheden = [_eenheid(i, f"Bepaling {n}") for n, i in enumerate(iris, 1)]
    eenheden += [_eenheid(f"urn:bwb:BWBR0004770:artikel:{100 + n}", "Klaar", "afgerond") for n in range(al)]
    return {"werkgebied_id": "wg1", "revisie": 3, "naam": "Invorderbaarheid", "eenheden": eenheden,
            "te_annoteren": list(iris), "context_niet_meegenomen": context, "volledig": True, "open_punten": [],
            "schatting": {"per_bepaling": 3000, "basis": 12, "totaal": 3000 * len(iris)} if schatting else None,
            "budget": {"resterend": 250_000, "budget": 500_000, "actief": True, "geblokkeerd": False}}


class WerkgebiedApi:
    """De api van de werkgebied-run: de werkvoorraad en het slotbericht."""

    def __init__(self, wv: dict[str, Any] | None = None, status: int = 0, *, onder: dict[str, Any] | None = None,
                 reden: str = "") -> None:
        # `onder`: de werkvoorraad bij bereik `deelvragen`; zonder geeft de api daar 409 geen_deelvragen.
        self.wv, self.status, self.onder, self.reden = wv, status, onder, reden
        self.berichten: list[dict[str, Any]] = []
        self.vragen: list[tuple[str, str]] = []

    async def haal_annotatie_werkvoorraad(self, werkgebied_id, bereik="werkgebied", deelvraag_id=""):
        self.vragen.append((bereik, deelvraag_id))
        if self.status:
            raise WetsanalyseApiFout("nee", self.status, self.reden)
        if bereik == "deelvragen":
            if self.onder is None:
                raise WetsanalyseApiFout("nee", 409, "geen_deelvragen")
            return self.onder
        return self.wv

    async def voeg_bericht_toe(self, gesprek_id, bericht):
        self.berichten.append(bericht)
        return {}

    async def aclose(self):
        pass


def _verzoek(bevestigd: int | None = None, **kw) -> ChatRequest:
    return ChatRequest(question="Annoteer het werkgebied", conversation_id="g1", werkgebied_id="wg1",
                       modus="werkgebied_annoteren", bevestigd=bevestigd, **kw)


async def _altijd() -> bool:
    return True


def _draai(request, wapi, *, budget=_altijd) -> list[dict[str, Any]]:
    async def verzamel():
        return [e async for e in wa.werkgebied_annotatie_beurt(
            request, Run(run_id="run-w", conversation_id="g1", vraag="v"), settings=_settings(),
            user_id="jurist", api=wapi, graph=FakeGraph(result=ROWS),
            llm=KetenLLM(kies=lambda t, f: GEEN_ANNOTATIE), annotaties=LeesApi(), budget_toegestaan=budget)]
    return asyncio.run(verzamel())


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token" and "onderdeel" not in e)


# --- herkenning en verzoek -------------------------------------------------------------------------

def test_verzoek_alleen_binnen_een_werkgebied_en_bevestigd_alleen_bij_die_modus():
    # Geen tekstpatroon meer: de modus of de actie (de knop), en getypt de supervisor.
    assert ChatRequest(question="x", werkgebied_id="wg1", modus="werkgebied_annoteren").is_werkgebied_annotatie
    assert not ChatRequest(question="Annoteer het werkgebied", werkgebied_id="wg1").is_werkgebied_annotatie
    with pytest.raises(ValidationError):
        ChatRequest(question="x", modus="werkgebied_annoteren")
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", bevestigd=2)
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", modus="werkgebied_annoteren", doel={"bron_iri": L1})


def test_getypt_levert_de_annotatie_agent_het_voorstel_met_een_knop():
    from agent.agents import annotatie, register
    from fakes import agent_ctx

    wapi = WerkgebiedApi(_werkvoorraad(L1, ART8, al=1))
    invoer = register.invoer("annotatie", "werkgebied", register.parameters("annotatie", "werkgebied", werkgebied_id="wg1"))
    uit = asyncio.run(annotatie.voer_uit(invoer, agent_ctx(wapi)))
    assert uit.status == "bevestiging" and "**2** bepalingen" in uit.tekst and uit.meting["model"] is False
    assert uit.bevestiging == {"soort": "werkgebied_annoteren", "werkgebied_id": "wg1", "aantal": 2, "schatting": 6000,
                              "bereik": "werkgebied", "deelvraag_id": ""}
    assert wapi.berichten == []                    # vastleggen doet de beurt-driver


# --- het voorstel ------------------------------------------------------------------------------------

def test_zonder_bevestiging_alleen_het_voorstel_met_een_knop(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, ART8, al=1))
    events = _draai(_verzoek(), wapi)
    assert not any(e["type"] in {"reeks", "onderdeel"} for e in events) and api.batches == []
    tekst = _tekst(events)
    assert "**2** bepalingen" in tekst and "~6.000 tokens" in tekst and "250.000" in tekst
    assert "1 bepaling met voorstellen" in tekst and "1 contextbron" in tekst
    bericht = wapi.berichten[-1]
    assert bericht["bevestiging"] == {"soort": "werkgebied_annoteren", "werkgebied_id": "wg1", "aantal": 2,
                                      "schatting": 6000, "bereik": "werkgebied", "deelvraag_id": ""}
    assert set(bericht) <= _bericht_velden()                       # niets valt stil weg bij de api
    assert [e["type"] for e in events][-2:] == ["opgeslagen", "done"]


def test_zonder_geschiedenis_geen_verzonnen_schatting(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, schatting=False))
    tekst = _tekst(_draai(_verzoek(), wapi))
    assert "nog geen annotatiebeurten" in tekst and "tokens (mediaan" not in tekst
    assert wapi.berichten[-1]["bevestiging"]["schatting"] is None


def test_een_gewijzigde_werkvoorraad_wordt_geweigerd(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, ART8))
    events = _draai(_verzoek(bevestigd=3), wapi)
    assert api.batches == [] and not any(e["type"] == "reeks" for e in events)
    assert "veranderde: nu 2 bepalingen in plaats van 3" in _tekst(events)
    assert wapi.berichten[-1]["bevestiging"]["aantal"] == 2          # opnieuw te bevestigen


def test_niets_nieuws_geeft_geen_knop(api):
    wapi = WerkgebiedApi(_werkvoorraad(al=2))
    events = _draai(_verzoek(bevestigd=0), wapi)
    assert "niets nieuws te annoteren" in _tekst(events) and "bevestiging" not in wapi.berichten[-1]


def test_onbekend_werkgebied_is_een_antwoord(api):
    wapi = WerkgebiedApi(status=404)
    assert "bestaat niet" in _tekst(_draai(_verzoek(), wapi))


def test_een_andere_api_fout_is_een_fout(api):
    events = _draai(_verzoek(), WerkgebiedApi(status=503))
    assert any(e["type"] == "error" for e in events) and events[-1]["type"] == "done"


# --- de run ------------------------------------------------------------------------------------------

def test_bevestigd_annoteert_per_bepaling_over_artikelen_heen(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, ART8))
    events = _draai(_verzoek(bevestigd=2), wapi)
    assert not [e for e in events if e["type"] == "error"], events
    assert [e["type"] for e in events].count("done") == 1 and events[-1]["type"] == "done"
    start = next(e for e in events if e["type"] == "reeks")
    assert start["ouder"] == {"bron_iri": "urn:wa:werkgebied:wg1", "label": "werkgebied Invorderbaarheid"}
    assert [o["label"] for o in start["onderdelen"]] == ["Invorderingswet 1990, Bepaling 1",
                                                         "Invorderingswet 1990, Bepaling 2"]
    # Per bepaling een eigen batch en bericht met de reeksplek, zoals een reeks op de keuzekaart.
    assert [b["doel"]["bron_iri"] for b in api.batches] == [L1, ART8]
    assert [(b["run_id"], b["reeks"]) for b in api.berichten] == [
        ("run-w.1", {"run_id": "run-w", "index": 0, "totaal": 2, "ouder": "werkgebied Invorderbaarheid"}),
        ("run-w.2", {"run_id": "run-w", "index": 1, "totaal": 2, "ouder": "werkgebied Invorderbaarheid"})]
    # Daarna één samenvatting als gewoon bericht van de hele run.
    slot = wapi.berichten[-1]
    assert slot["run_id"] == "run-w" and slot["tekst"].startswith("2 bepalingen geannoteerd")


def test_budget_op_halverwege_stopt_en_noemt_de_rest(api):
    async def budget():
        return False
    wapi = WerkgebiedApi(_werkvoorraad(L1, L2, ART8))
    events = _draai(_verzoek(bevestigd=3), wapi, budget=budget)
    eind = [e for e in events if e["type"] == "reeks"][-1]
    assert eind["reden"] == "budget_op" and eind["overgeslagen"] == [L2, ART8]
    assert len(api.batches) == 1
    assert "2 niet aan bod gekomen – je tokenbudget is op" in wapi.berichten[-1]["tekst"]


def test_een_fout_in_een_bepaling_stopt_de_rest_niet(api, monkeypatch):
    echte = wa.beurt_fabriek

    def fabriek(*a, **kw):
        beurt = echte(*a, **kw)

        def misschien_stuk(doel, index):
            if doel["bron_iri"] == ONBEKEND:
                raise RuntimeError("stuk")
            return beurt(doel, index)
        return misschien_stuk
    monkeypatch.setattr(wa, "beurt_fabriek", fabriek)
    wapi = WerkgebiedApi(_werkvoorraad(ONBEKEND, L1))
    events = _draai(_verzoek(bevestigd=2), wapi)
    uitkomst = {e["bron_iri"]: e["uitkomst"] for e in events if e["type"] == "onderdeel" and e["fase"] == "eind"}
    assert uitkomst == {ONBEKEND: "fout", L1: "klaar"}
    assert "1 mislukt" in wapi.berichten[-1]["tekst"]


def test_het_plafond(api, monkeypatch):
    monkeypatch.setattr(wa, "PLAFOND", 1)
    wapi = WerkgebiedApi(_werkvoorraad(L1, ART8))
    events = _draai(_verzoek(bevestigd=2), wapi)
    assert next(e for e in events if e["type"] == "reeks")["totaal"] == 1
    assert [b["doel"]["bron_iri"] for b in api.batches] == [L1]
    assert "nog 1 bepaling buiten deze run" in wapi.berichten[-1]["tekst"]


# --- de endpoints ------------------------------------------------------------------------------------

def test_niet_via_chat(monkeypatch):
    from fastapi.testclient import TestClient
    import api.main as main
    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    with TestClient(main.app) as c:
        r = c.post("/v1/chat", json={"question": "x", "modus": "werkgebied_annoteren", "werkgebied_id": "wg1"})
    assert r.status_code == 422


def test_annoteer_het_werkgebied_via_runs_gaat_deze_route_in(monkeypatch):
    from fastapi.testclient import TestClient
    import api.main as main

    gestart: list[tuple[str, int | None]] = []

    async def nep_beurt(request, run, **_kw):
        gestart.append((request.werkgebied_id, request.bevestigd))
        yield {"type": "done"}

    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    monkeypatch.setattr(main, "werkgebied_annotatie_beurt", nep_beurt)
    monkeypatch.setattr(main, "runs", type(main.runs)())
    with TestClient(main.app) as c:
        monkeypatch.setattr(type(main.settings), "legt_zelf_vast", property(lambda _s: True))
        main.app.dependency_overrides[main._budget_check] = lambda: None
        try:
            r = c.post("/v1/runs", json={"question": "Annoteer het werkgebied", "conversation_id": "g1",
                                         "werkgebied_id": "wg1", "modus": "werkgebied_annoteren", "bevestigd": 4})
            assert r.status_code == 201, r.text
            for _ in range(50):
                if gestart:
                    break
                asyncio.run(asyncio.sleep(0.02))
            assert gestart == [("wg1", 4)]
        finally:
            main.app.dependency_overrides.clear()


# --- het bereik: alleen de bronnen onder de deelvragen ---------------------------------------------

def _onder(*iris: str, deelvragen=(("d1", "Wie?", 1), ("d2", "Wanneer?", 2)), buiten: int = 3,
           context: int = 0) -> dict[str, Any]:
    return {**_werkvoorraad(*iris, context=context), "bereik": "deelvragen", "buiten_bereik": buiten,
            "deelvragen": [{"id": i, "vraag": v, "selecties": n} for i, v, n in deelvragen]}


def test_alle_deelvragen_in_een_keer(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, L2, ART8), onder=_onder(L1, L2))
    events = _draai(_verzoek(bereik="deelvragen"), wapi)
    tekst = _tekst(events)
    assert wapi.vragen == [("deelvragen", "")]                    # geen tweede vraag naar het hele werkgebied
    assert "Onder de 2 deelvragen van werkgebied *Invorderbaarheid*" in tekst and "**2** bepalingen" in tekst
    assert "3 analysebronnen buiten de deelvragen" in tekst
    assert wapi.berichten[-1]["bevestiging"]["bereik"] == "deelvragen"
    assert wapi.berichten[-1]["bevestiging"]["deelvraag_id"] == ""

    wapi = WerkgebiedApi(_werkvoorraad(L1, L2, ART8), onder=_onder(L1, L2))
    events = _draai(_verzoek(bevestigd=2, bereik="deelvragen"), wapi)
    reeks = [e for e in events if e["type"] == "reeks" and e.get("fase") == "start"]
    assert reeks and reeks[0]["ouder"]["bron_iri"] == "urn:wa:werkgebied:wg1:deelvragen"
    assert [e["bron_iri"] for e in events if e["type"] == "onderdeel" and e.get("fase") == "start"] == [L1, L2]
    assert "onder de 2 deelvragen van werkgebied *Invorderbaarheid*" in wapi.berichten[-1]["tekst"]


def test_een_deelvraag_via_het_onderwerp(api):
    r = ChatRequest(question="Annoteer de bepalingen hierbij", conversation_id="g1", actie="deelvragen_annoteren",
                    onderwerp={"soort": "deelvraag", "werkgebied_id": "wg1", "id": "d2"})
    assert (r.modus, r.bereik, r.deelvraag_id, r.werkgebied_id) == ("werkgebied_annoteren", "deelvragen", "d2", "wg1")
    wapi = WerkgebiedApi(_werkvoorraad(L1, L2), onder=_onder(L2, deelvragen=(("d2", "Wanneer?", 1),), buiten=1))
    tekst = _tekst(_draai(r, wapi))
    assert wapi.vragen == [("deelvragen", "d2")]
    assert "Onder deelvraag *Wanneer?* is **1** bepaling" in tekst and "buiten deze deelvraag" in tekst
    assert wapi.berichten[-1]["bevestiging"]["deelvraag_id"] == "d2"


def test_een_deelvraag_zonder_bronnen_zegt_wat_er_eerst_moet():
    leeg = {**_onder(deelvragen=(("d1", "Wie?", 0),)), "eenheden": [], "deelvraag_id": "d1"}
    tekst, bevestiging = wa.voorstel("Inv", leeg)
    assert bevestiging is None and "nog geen analysebronnen" in tekst and "*Zoek bepalingen hierbij*" in tekst


def test_het_hele_werkgebied_noemt_de_kortere_weg(api):
    wapi = WerkgebiedApi(_werkvoorraad(L1, L2, ART8), onder=_onder(L1))
    tekst = _tekst(_draai(_verzoek(), wapi))
    assert wapi.vragen == [("werkgebied", ""), ("deelvragen", "")]
    assert "Dat is er 1: vraag *Annoteer de bepalingen van de deelvragen*" in tekst
    # Zonder deelvragen (409 bij de api) geen zin, en geen storing.
    wapi = WerkgebiedApi(_werkvoorraad(L1, L2))
    tekst = _tekst(_draai(_verzoek(), wapi))
    assert "deelvragen" not in tekst and wapi.berichten[-1]["bevestiging"]["aantal"] == 2


@pytest.mark.parametrize("status,reden,zin", [
    (409, "niet_actief", "niet (meer) actief"),
    (409, "geen_deelvragen", "nog geen deelvragen"),
    (404, "Deelvraag bestaat niet.", "Die deelvraag bestaat niet"),
])
def test_een_weigering_van_de_api_is_een_antwoord(api, status, reden, zin):
    wapi = WerkgebiedApi(status=status, reden=reden)
    events = _draai(_verzoek(bereik="deelvragen", deelvraag_id="d9"), wapi)
    assert zin in _tekst(events) and not any(e["type"] == "error" for e in events)


def test_getypt_deelvraag_n_via_de_annotatie_agent():
    from agent.agents import annotatie, register
    from fakes import agent_ctx

    class Api(WerkgebiedApi):
        async def haal_werkgebied(self, wid):
            return {"naam": "Inv", "deelvragen": [{"id": "d1", "status": "actief"}, {"id": "d2", "status": "actief"}]}

    wapi = Api(_werkvoorraad(L1, L2), onder=_onder(L2, deelvragen=(("d2", "Wanneer?", 1),)))
    p = register.parameters("annotatie", "deelvragen", vraag="annoteer deelvraag 2", werkgebied_id="wg1")
    assert p == {"werkgebied_id": "wg1", "deelvraag_nr": 2}
    uit = asyncio.run(annotatie.voer_uit(register.invoer("annotatie", "deelvragen", p), agent_ctx(wapi)))
    assert wapi.vragen == [("deelvragen", "d2")] and uit.bevestiging["deelvraag_id"] == "d2"
    p = register.parameters("annotatie", "deelvragen", vraag="annoteer deelvraag 7", werkgebied_id="wg1")
    uit = asyncio.run(annotatie.voer_uit(register.invoer("annotatie", "deelvragen", p), agent_ctx(wapi)))
    assert uit.status == "geweigerd" and "Deelvraag 7 ken ik niet" in uit.reden


def test_bereik_hoort_bij_het_annoteren():
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", bereik="deelvragen")
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", modus="werkgebied_annoteren", deelvraag_id="d1")


def test_het_verschil_tussen_bronnen_en_bepalingen_wordt_uitgelegd():
    """18 bronnen, 60 bepalingen: zonder uitleg leest dat als een fout (acceptatie 22 okt 2026)."""
    wv = _onder(*[f"urn:bwb:BWBR0004770:artikel:28:lid:{i}" for i in range(1, 8)])
    wv["selecties"] = [
        {"id": "s1", "bron_iri": "a28", "label": "Artikel 28 – Invorderingswet 1990", "per_stand": {"nieuw": 4}},
        {"id": "s2", "bron_iri": "a30", "label": "Artikel 30 – Invorderingswet 1990", "per_stand": {"nieuw": 2}},
        {"id": "s3", "bron_iri": "a29", "label": "Artikel 29 – Invorderingswet 1990", "per_stand": {"nieuw": 1}},
        {"id": "s4", "bron_iri": "weg", "label": "Weg", "per_stand": {}, "onbereikbaar": "niet te vinden"},
    ]
    tekst, _ = wa.voorstel("Inv", wv)
    assert "**7** bepalingen" in tekst and "Ze komen uit 3 bronnen" in tekst and "per lid" in tekst
    assert "Het meest: Artikel 28 – Invorderingswet 1990 (4), Artikel 30 – Invorderingswet 1990 (2)." in tekst
    # Is elke bron één bepaling, dan valt er niets uit te leggen.
    een = _onder(L1, L2)
    een["selecties"] = [{"id": "s1", "per_stand": {"nieuw": 1}}, {"id": "s2", "per_stand": {"nieuw": 1}}]
    assert "Ze komen uit" not in wa.voorstel("Inv", een)[0]
