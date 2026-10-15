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

    def __init__(self, wv: dict[str, Any] | None = None, status: int = 0) -> None:
        self.wv, self.status = wv, status
        self.berichten: list[dict[str, Any]] = []

    async def haal_annotatie_werkvoorraad(self, werkgebied_id):
        if self.status:
            raise WetsanalyseApiFout("nee", self.status, "")
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

@pytest.mark.parametrize("vraag, ja", [
    ("Annoteer het werkgebied", True),
    ("annoteer wat nog niet geannoteerd is", True),
    ("Annoteer alle nieuwe bepalingen", True),
    ("annoteer alles", True),
    ("annoteer alles over aansprakelijkheid van de bestuurder", False),   # de onderwerproute
    ("Annoteer artikel 9 lid 1", False),
    ("Welke bepalingen horen bij het werkgebied?", False),
])
def test_herkenning(vraag, ja):
    assert wa.is_werkgebied_annoteervraag(vraag) is ja


def test_verzoek_alleen_binnen_een_werkgebied_en_bevestigd_alleen_bij_die_modus():
    assert ChatRequest(question="Annoteer het werkgebied", werkgebied_id="wg1").is_werkgebied_annotatie
    assert not ChatRequest(question="Annoteer het werkgebied").is_werkgebied_annotatie
    with pytest.raises(ValidationError):
        ChatRequest(question="x", modus="werkgebied_annoteren")
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", bevestigd=2)
    with pytest.raises(ValidationError):
        ChatRequest(question="x", werkgebied_id="wg1", modus="werkgebied_annoteren", doel={"bron_iri": L1})


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
                                      "schatting": 6000}
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
