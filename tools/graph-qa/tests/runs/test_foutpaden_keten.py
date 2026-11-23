"""De foutpaden K1, K2, K3 en K5 als scenario's: een verstoring midden in een beurt, gezien zoals de werkplek hem ziet.

Testplan keten-e2e §2.1 en §5 punt 5 (Lex Bench §20.5 stap 5, keten 5). Elk scenario start een beurt over de echte
run-endpoints (`POST /v1/runs`), spuit een verstoring in en leest de beurt terug met een SSE-kijker die doet wat de
werkplek doet: frames lezen tot `done`, met `\\r\\n` als scheiding. Getoetst wordt wat de jurist ziet en wat er níet mag
gebeuren, niet een exacte tekst:

- **K1, de graaf is leeg.** De annotatieroute leest de bron in code, buiten `dispatch` om. Zonder de tak in
  `agent.agent._foutmelding` kreeg de jurist "Er ging iets mis", en niet dat de wettekst tijdelijk weg is.
- **K2, een beurt die halverwege afbreekt.** Wat al getoond is blijft, er komt een fout en precies één `done`, de
  afbraak wordt vastgelegd (zodat de vraag na herladen niet onbeantwoord blijft), en het gesprek is direct vrij.
  Een deploy van graph-qa (de replica verdwijnt) toetst de gedeelde store: `test_runstore_postgres.py`, de wezen.
- **K3, een 429 of een 400 van het model.** Een eigen melding, geen tekst van de provider.
- **K5, het budget is op.** Bij de start een 429 met de reden, en er loopt geen run. Halverwege een reeks: dat stopt de
  reeks met de reden `budget_op` (`test_reeks.py`); een lopende beurt wordt nooit afgekapt.

K4, K6–K10 vragen de straat of een browser: die staan als scenario in `docs/acceptatie/foutpaden.md`.
"""
from __future__ import annotations

import functools
import json

import bron_fakes
import pytest
from fakes import FakeGraph, FakeLLM, KetenLLM, response, text_block, tool_block
from fastapi.testclient import TestClient

from agent.runstore.geheugen import GeheugenStore
from api import main

pytestmark = [pytest.mark.risico("R01"), pytest.mark.risico("R04"), pytest.mark.risico("R05"),
              pytest.mark.risico("R08")]

VRAAG = "Wat is de hoofdregel van artikel 9 van de Invorderingswet 1990?"
ALGEMEEN = "Er ging iets mis"


@pytest.fixture
def keten(monkeypatch):
    """De run-endpoints met de echte beurt-driver en run-store; `zet(llm, graph)` kiest de nepdiensten."""
    monkeypatch.setattr(main.settings, "graphdb_token", "test", raising=False)
    monkeypatch.setattr(main.settings, "graphdb_mcp_url", "https://graaf.test/mcp", raising=False)
    afbraken: list[tuple[str, str]] = []

    async def bij_afbraak(run, melding):
        afbraken.append((run.conversation_id, melding))

    monkeypatch.setattr(main, "runs", GeheugenStore(bij_afbraak=bij_afbraak))

    def zet(*, llm=None, graph=None, stroom=None):
        nep = stroom or functools.partial(bron_fakes.answer_stream, llm=llm, graph=graph)
        monkeypatch.setattr(main, "answer_stream", nep)

    with TestClient(main.app) as client:
        client.zet, client.afbraken = zet, afbraken
        yield client


def kijk(client, run_id: str) -> list[dict]:
    """Lees de beurt zoals de werkplek: SSE-frames tot de stroom sluit, `\\r\\n` als scheiding."""
    events, buffer = [], ""
    with client.stream("GET", f"/v1/runs/{run_id}/events?vanaf=0") as stroom:
        for stuk in stroom.iter_text():
            buffer += stuk.replace("\r\n", "\n")
            *frames, buffer = buffer.split("\n\n")
            for frame in frames:
                data = "".join(r[5:].strip() for r in frame.split("\n") if r.startswith("data:"))
                if data:
                    events.append(json.loads(data))
    return events


def beurt(client, vraag: str, gesprek: str = "g1") -> list[dict]:
    start = client.post("/v1/runs", json={"question": vraag, "conversation_id": gesprek})
    assert start.status_code == 201, start.text
    return kijk(client, start.json()["run_id"])


def wat_de_jurist_ziet(events: list[dict]) -> str:
    return "".join(str(e.get("content") or "") if e["type"] == "token" else
                   f"\n{e.get('message', '')}" if e["type"] == "error" else "" for e in events)


def eindigt_eenmaal_mislukt(events: list[dict]) -> None:
    dones = [e for e in events if e["type"] == "done"]
    assert len(dones) == 1 and events[-1] is dones[0], "precies één done, als laatste event"
    assert dones[0].get("uitkomst") == "mislukt"


def status_van(client, gesprek: str = "g1") -> str:
    return (client.get(f"/v1/conversations/{gesprek}/run").json() or {}).get("status", "")


# --- K1: de graaf is leeg midden in een reis ---------------------------------------------------------------------

def _graaf_weg(_query: str) -> str:
    raise ValueError("Repository inning doesn't exist")


def test_k1_annoteren_bij_een_lege_graaf_zegt_dat_de_wettekst_weg_is(keten):
    llm = KetenLLM([
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block("De bepaling is nu niet te lezen.")], "end_turn"),
    ])
    keten.zet(llm=llm, graph=FakeGraph(results=_graaf_weg))
    events = beurt(keten, "annoteer artikel 9 lid 2 van de Invorderingswet 1990")

    tekst = wat_de_jurist_ziet(events)
    assert "kennisgraaf" in tekst and "niet beschikbaar" in tekst, tekst
    assert ALGEMEEN not in tekst and "Repository" not in tekst, "geen algemene of kale melding"
    assert not [e for e in events if e["type"] in ("element", "doel")], "geen voorstel zonder bron"
    eindigt_eenmaal_mislukt(events)
    assert keten.afbraken and "kennisgraaf" in keten.afbraken[0][1], "de melding staat ook in het gesprek"


# --- K2: een beurt die halverwege afbreekt ------------------------------------------------------------------------

def test_k2_een_afgebroken_beurt_laat_een_vrij_gesprek_en_een_vastgelegde_afbraak(keten):
    async def breekt_af(*_a, **_k):
        yield {"type": "token", "content": "Artikel 9 regelt "}
        raise ConnectionResetError("de verbinding met de replica viel weg")

    keten.zet(stroom=breekt_af)
    events = beurt(keten, VRAAG)

    tekst = wat_de_jurist_ziet(events)
    assert tekst.startswith("Artikel 9 regelt "), "wat al getoond is, blijft staan"
    assert "replica" not in tekst, "geen interne fouttekst"
    eindigt_eenmaal_mislukt(events)
    assert status_van(keten) == "mislukt"
    assert [g for g, _ in keten.afbraken] == ["g1"], "de afbraak staat in het gesprek, zodat herladen hem toont"

    # Een nieuwe beurt kan meteen, op hetzelfde gesprek.
    keten.zet(llm=FakeLLM([response([text_block("Artikel 9 gaat over uitstel van betaling.")], "end_turn")]),
              graph=FakeGraph(result=""))
    assert keten.post("/v1/runs", json={"question": VRAAG, "conversation_id": "g1"}).status_code == 201


# --- K3: een model-400 of een 429 ---------------------------------------------------------------------------------

def _provider_fout(naam: str, soort: str) -> Exception:
    klasse = type(naam, (Exception,), {})
    fout = klasse(f"Error code: 4xx – {{'type': 'error', 'error': {{'type': '{soort}', 'message': 'sk-ant intern'}}}}")
    fout.body = {"type": "error", "error": {"type": soort, "message": "sk-ant intern detail"}}
    return fout


class FoutLLM(FakeLLM):
    """Een model dat op de eerste aanroep een fout van de provider geeft."""

    def __init__(self, fout: Exception) -> None:
        super().__init__([])
        self.fout = fout

    def create(self, **kwargs):
        self.calls.append(kwargs)
        raise self.fout

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        raise self.fout


@pytest.mark.parametrize(("naam", "soort", "verwacht"), [
    ("RateLimitError", "rate_limit_error", "overbelast"),
    ("BadRequestError", "invalid_request_error", "weigerde"),
])
def test_k3_een_fout_van_het_model_krijgt_een_eigen_melding(keten, naam, soort, verwacht):
    keten.zet(llm=FoutLLM(_provider_fout(naam, soort)), graph=FakeGraph(result=""))
    events = beurt(keten, VRAAG)

    tekst = wat_de_jurist_ziet(events)
    assert verwacht in tekst, tekst
    assert "sk-ant" not in tekst and "Error code" not in tekst, "geen tekst van de provider"
    eindigt_eenmaal_mislukt(events)
    assert keten.afbraken and keten.afbraken[0][1] in tekst, "dezelfde melding in het gesprek"


# --- K5: het budget is op -----------------------------------------------------------------------------------------

def test_k5_budget_op_bij_de_start_weigert_met_de_reden_en_start_niets(keten, monkeypatch):
    class Api:
        def __init__(self, *_a):
            pass

        async def budget_toegestaan(self):
            return False, {"reset_op": "2026-11-23T00:00:00+00:00"}

        async def aclose(self):
            pass

    monkeypatch.setattr(main.settings, "wetsanalyse_api_url", "https://api.test", raising=False)
    monkeypatch.setattr(main.settings, "wetsanalyse_api_token", "t", raising=False)
    monkeypatch.setattr(main, "WetsanalyseApi", Api)
    llm = FakeLLM([])
    keten.zet(llm=llm, graph=FakeGraph(result=""))

    start = keten.post("/v1/runs", json={"question": VRAAG, "conversation_id": "g1"}, headers={"X-User-Id": "u1"})
    assert start.status_code == 429
    detail = start.json()["detail"]
    assert detail["reden"] == "budget_op" and "budget" in detail["melding"] and detail["reset_op"]
    assert status_van(keten) == "" and not llm.calls, "er loopt geen run en het model is niet aangeroepen"
