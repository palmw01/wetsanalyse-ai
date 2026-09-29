"""Een reeks: meerdere leden van één artikel als één run, elk met een eigen laag en bericht."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from bronmodel import bouw_snapshot
from pydantic import ValidationError

from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.models import ChatRequest
from agent.reeks import reeks_run, reeks_stroom
from agent.runs import Run
from fakes import FakeGraph, KetenLLM, make_settings

BWB = "BWBR0004770"
REG = f"urn:bwb:{BWB}"
ART, ART8 = REG + ":artikel:9", REG + ":artikel:8"
L1, L2, L3 = ART + ":lid:1", ART + ":lid:2", ART + ":lid:3"
ROWS = [
    {"node": REG, "type": "Regeling", "nummer": "", "tekst": "", "citeertitel": "Invorderingswet 1990"},
    {"node": ART8, "parent": REG, "type": "Artikel", "nummer": "8", "tekst": "Artikel acht."},
    {"node": ART, "parent": REG, "type": "Artikel", "nummer": "9", "tekst": ""},
    {"node": L1, "parent": ART, "type": "Lid", "nummer": "1", "tekst": "Een aanslag is invorderbaar na zes weken."},
    {"node": L2, "parent": ART, "type": "Lid", "nummer": "2", "tekst": "De ontvanger kan uitstel verlenen."},
    {"node": L3, "parent": ART, "type": "Lid", "nummer": "3", "tekst": "Uitstel eindigt van rechtswege."},
]
SNAP = bouw_snapshot(ROWS, bron_iri=ART, bwb_id=BWB)


class LeesApi:
    def dekking(self, doel):
        return {"status": "ok", "snapshot_id": SNAP["snapshot_id"], "voltooid": False,
                "parent_context": False, "bereik": []}

    def weergave(self, doel):
        return {"schema_versie": 2, "snapshot_id": SNAP["snapshot_id"], "elementen": [], "lagen": []}

    def zoeken(self, filters):
        return {"status": "ok", "resultaten": [], "volledig": True}


class NepApi:
    def __init__(self) -> None:
        self.batches: list[dict[str, Any]] = []
        self.berichten: list[dict[str, Any]] = []

    async def zet_bronnode_batch(self, batch):
        self.batches.append(batch)
        return {"slug": batch["doel"]["bron_iri"]}

    async def voeg_bericht_toe(self, gesprek_id, bericht):
        self.berichten.append(bericht)
        return {}

    async def boek_verbruik(self, *a, **k):
        return {}

    async def aclose(self):
        pass


@pytest.fixture
def api(monkeypatch):
    nep = NepApi()
    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *_a, **_k: nep)
    return nep


def _settings():
    return make_settings(wetsanalyse_api_url="http://api:3000", wetsanalyse_api_token="t", qa_api_token="q")


def _verzoek(*iris):
    return ChatRequest(question="annoteer de gekozen leden", conversation_id="g1",
                       doelen=[{"bron_iri": i, "label": f"Lid {i[-1]}"} for i in iris])


def _draai(request, *, run=None, legt_vast=True, budget=None):
    async def verzamel():
        return [e async for e in reeks_run(
            request, run, settings=_settings(), user_id="jurist", legt_vast=legt_vast,
            graph=FakeGraph(result=ROWS), llm=KetenLLM(kies=lambda t, f: GEEN_ANNOTATIE),
            annotaties=LeesApi(), budget_toegestaan=budget)]
    return asyncio.run(verzamel())


def _run():
    return Run(run_id="run-1", conversation_id="g1", vraag="v")


def test_twee_leden_geven_twee_lagen_en_twee_berichten_in_een_run(api):
    events = _draai(_verzoek(L1, L2), run=_run())
    assert not [e for e in events if e["type"] == "error"], events
    assert [e["type"] for e in events].count("done") == 1 and events[-1]["type"] == "done"
    start, eind = events[0], [e for e in events if e["type"] == "reeks"][-1]
    assert start["fase"] == "start" and [o["bron_iri"] for o in start["onderdelen"]] == [L1, L2]
    assert start["ouder"]["bron_iri"] == ART
    assert eind == {"type": "reeks", "fase": "eind", "run_id": "run-1", "totaal": 2, "verwerkt": 2,
                    "overgeslagen": []}
    # Alles tussen onderdeel-start en -eind is van dat onderdeel.
    huidig = None
    for e in events:
        if e["type"] == "onderdeel":
            huidig = e["bron_iri"] if e["fase"] == "start" else None
        elif e["type"] not in {"reeks", "done"}:
            assert e["onderdeel"] == huidig, e
    # Per lid een eigen batch en bericht, met een eigen run-id: de api ontdubbelt daarop.
    assert [(b["batch_id"], b["doel"]["bron_iri"]) for b in api.batches] == [("run-1.1", L1), ("run-1.2", L2)]
    assert [(b["run_id"], b["reeks"]["index"], b["reeks"]["totaal"]) for b in api.berichten] == [
        ("run-1.1", 0, 2), ("run-1.2", 1, 2)]
    assert [e["uitkomst"] for e in events if e["type"] == "onderdeel" and e["fase"] == "eind"] == ["klaar", "klaar"]


def test_budget_op_halverwege_stopt_de_reeks_met_reden(api):
    toegestaan = iter([False])

    async def budget():
        return next(toegestaan)
    events = _draai(_verzoek(L1, L2, L3), run=_run(), budget=budget)
    eind = [e for e in events if e["type"] == "reeks"][-1]
    assert eind["reden"] == "budget_op" and eind["overgeslagen"] == [L2, L3] and eind["verwerkt"] == 1
    assert len(api.batches) == 1


def test_leden_van_verschillende_artikelen_worden_geweigerd(api):
    events = _draai(_verzoek(L1, ART8), run=_run())
    assert not any(e["type"] in {"reeks", "onderdeel", "element"} for e in events)
    assert "één artikel" in "".join(e.get("content", "") for e in events)
    assert api.batches == [] and api.berichten == []


def test_onbekend_onderdeel_wordt_geweigerd(api):
    events = _draai(_verzoek(L1, ART + ":lid:99"), run=_run())
    assert not any(e["type"] == "onderdeel" for e in events) and api.batches == []


def test_chatroute_legt_niets_vast_maar_heeft_dezelfde_indeling(api):
    events = _draai(_verzoek(L1, L2), legt_vast=False)
    assert [e["fase"] for e in events if e["type"] == "onderdeel"] == ["start", "eind", "start", "eind"]
    assert api.batches == [] and api.berichten == []


# --- de stroom zelf: stoppen en fouten ---------------------------------------------------------

def _stroom(doelen, beurt, **kw):
    async def verzamel():
        return [e async for e in reeks_stroom(doelen, run_id="r", beurt=beurt,
                                              ouder={"bron_iri": ART, "label": "Artikel 9"}, **kw)]
    return asyncio.run(verzamel())


def test_stop_na_het_eerste_lid_laat_de_rest_onaangeroerd():
    gestart, stop = [], {"nu": False}

    async def beurt(doel, index):
        gestart.append(doel["bron_iri"])
        stop["nu"] = True
        yield {"type": "token", "content": "x"}
        yield {"type": "done"}
    events = _stroom([{"bron_iri": L1}, {"bron_iri": L2}], beurt, stop_gevraagd=lambda: stop["nu"])
    assert gestart == [L1]
    eind = events[-2]
    assert eind["reden"] == "gestopt" and eind["overgeslagen"] == [L2]


def test_een_fout_in_een_lid_laat_het_volgende_lid_lopen():
    async def beurt(doel, index):
        if index == 0:
            raise RuntimeError("stuk")
        yield {"type": "element", "element": {}}
        yield {"type": "done"}
    events = _stroom([{"bron_iri": L1}, {"bron_iri": L2}], beurt)
    einden = [e for e in events if e["type"] == "onderdeel" and e["fase"] == "eind"]
    assert [(e["uitkomst"], e["voorstellen"]) for e in einden] == [("fout", 0), ("klaar", 1)]
    assert any(e["type"] == "error" and e["onderdeel"] == L1 for e in events)


# --- het contract -----------------------------------------------------------------------------

@pytest.mark.parametrize("velden", [
    {"doelen": [{"bron_iri": L1}]},                                           # één is geen reeks
    {"doelen": [{"bron_iri": L1}, {"bwbId": BWB, "artikel": "9", "lid": "2"}]},  # zonder bron_iri
    {"doelen": [{"bron_iri": L1}, {"bron_iri": L2}], "doel": {"bron_iri": L1}},
    {"doelen": [{"bron_iri": L1}, {"bron_iri": L2}], "modus": "advies", "context": {"bron_iri": L1}},
    {"doelen": [{"bron_iri": f"{ART}:lid:{n}"} for n in range(61)]},          # boven het plafond
])
def test_ongeldige_reeks_wordt_geweigerd(velden):
    with pytest.raises(ValidationError):
        ChatRequest(question="annoteer", **velden)
