"""De route in code naar een subagent: "vat per uitspraak samen …" met een bron naast de wet aan (ADR-016 §A5)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import subagent as sub
from agent.nodes import subagent_route as route
from agent.nodes import supervisie
from test_subagent import ARTIKEL, STATE, Api, _kinderen

AAN = {"rechtspraak": {"naam": "rechtspraak", "label": "Rechtspraak", "aan": True, "reden": "aan"}}
EVAL = Path(__file__).resolve().parents[1] / "eval"


@pytest.mark.parametrize("vraag", [
    "Zoek de rechtspraak bij artikel 36 van de Invorderingswet 1990 en vat per uitspraak samen wat de rechter zegt over "
    "de melding van betalingsonmacht.",                                          # S01
    "Zoek de rechtspraak over de melding van betalingsonmacht bij artikel 36 van de Invorderingswet 1990 uit de periode "
    "van mijn dossier, en vat per uitspraak samen wat de rechter over de melding zegt.",  # D01
    "Geef per Kamerstuk de kern van wat de minister zegt over artikel 25 van de Invorderingswet 1990.",
    "Vat per uitspraak samen wat de rechter over de aansprakelijkheid van bestuurders zegt.",   # geen artikel
])
def test_per_uitspraak_samenvatten_gaat_naar_een_subagent(vraag):
    assert route.past(vraag, AAN)


@pytest.mark.parametrize("vraag, stand", [
    ("Vat per uitspraak samen wat de rechter zegt.", {}),                       # geen bron naast de wet aan
    ("Vat per uitspraak samen wat de rechter zegt.", {"rechtspraak": {"aan": False}}),
    ("Geef de 5 nieuwste uitspraken over artikel 36 van de Invorderingswet 1990.", AAN),   # een lijst: de lijstroute
    ("Wat zegt de uitspraak over de melding?", AAN),
    ("Zoek de rechtspraak over artikel 30 en vat per uitspraak samen wat de rechter over de rente zegt.", AAN),  # V01
])
def test_wat_niet_naar_de_route_gaat(vraag, stand):
    assert not route.past(vraag, stand)


def _vragen() -> list[tuple[str, str]]:
    uit = []
    for naam in ("golden_routering.jsonl", "golden_gesprek.jsonl", "golden_centrale_agent.jsonl"):
        for regel in (EVAL / naam).read_text().splitlines():
            if regel.strip().startswith("{"):
                rij = json.loads(regel)
                for v in [rij.get("vraag", ""), rij.get("opdracht", ""), *(b.get("vraag", "") for b in rij.get("beurten", []))]:
                    if v:
                        uit.append((rij.get("id", naam), v))
    return uit


def test_in_de_vragensets_pakt_de_route_alleen_wat_een_subagent_verwacht():
    """Geen vraag uit de routerings-, gespreks- en agentset valt erin, behalve S01 (een subagent verwacht)."""
    verwacht = {"S01"}
    gevangen = {i for i, v in _vragen() if route.past(v, AAN)}
    assert gevangen <= verwacht, gevangen - verwacht
    assert "S01" in gevangen


def test_de_supervisor_stuurt_de_vraag_zonder_model_naar_de_route(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    state = {**STATE, "question": "Vat per uitspraak samen wat de rechter over artikel 36 van de Invorderingswet 1990 zegt.", "modus": "auto",
             "agentvorm": "centraal", "bronstand": AAN}
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan"), graph=None)
    upd = supervisie._kies(b, state)
    assert upd["specialist"] == "subagent_route" and supervisie._entry_node(b, upd) == "subagent_route"


def _bouw(kinderen):
    return SimpleNamespace(kinderen=kinderen, settings=SimpleNamespace(legt_zelf_vast=True), loop=None, stop_check=None,
                           graph=None)


def test_de_route_start_de_subagent_met_de_vraag_en_geeft_het_rapport_aan_de_centrale_agent(monkeypatch):
    monkeypatch.setattr(route, "get_stream_writer", lambda: (lambda _e: None))
    monkeypatch.setattr(sub, "WetsanalyseApi", lambda *_a: Api())
    kinderen, gestart, _ = _kinderen({"rapport": {"status": "klaar"}, "answer": "Per uitspraak: …",
                                      "source_trace": [ARTIKEL]})
    vraag = "Vat per uitspraak samen wat de rechter over artikel 36 van de Invorderingswet 1990 zegt."
    upd = route.subagent_route_node(_bouw(kinderen), {**STATE, "question": vraag, "source_trace": []})
    [(verzoek, _, _)] = gestart
    assert verzoek.profiel == route.PROFIEL and verzoek.opdracht.doel == vraag
    assert upd["specialist"] == "centraal" and ARTIKEL in upd["source_trace"]
    assert upd["rapporten"].startswith("RAPPORT VAN EEN SUBAGENT") and "Per uitspraak: …" in upd["rapporten"]
    # Kan hij niet starten, dan beantwoordt de centrale agent de vraag zelf.
    assert route.subagent_route_node(_bouw(None), {**STATE, "question": vraag}) == {"specialist": "centraal"}
