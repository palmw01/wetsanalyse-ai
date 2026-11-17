"""De meting van de proef `model_kiest` (pilot LB3): welke sets ze meet en dat ze zonder commit niet start. Zonder model
en zonder graaf; de meting zelf draait alleen met akkoord, via `azure-infra` → `eval` → `bronselectie_model`."""
from __future__ import annotations

import pytest

from eval import bronselectie_model_meting as m


def test_de_sets_hebben_deelvragen_en_een_verwachting():
    sets = m.sets(m.lezer(True))
    assert [n for n, _ in sets] == [*m.SETS, *m.CASUSSEN]
    for naam, s in sets:
        assert s["deelvragen"], naam
        assert s["verwacht"], naam
        assert {v["deelvraag"] for v in s["verwacht"]} <= set(range(len(s["deelvragen"]))), naam


def test_zonder_commit_start_de_meting_niet(monkeypatch):
    monkeypatch.delenv("LEX_REVISIE", raising=False)
    with pytest.raises(SystemExit, match="LEX_REVISIE"):
        m.lezer(False)


def test_de_routes_bestaan():
    assert m.STANDAARD in m.ROUTES


def test_geen_eval_rekent_zelf_de_wortel_uit():
    """In het image staat een eval op `/app/eval/`: vier mappen omhoog bestaat daar niet en brak de meting bij het
    importeren (17 nov 2026, IndexError). De wortel komt uit één helper, `eval/wortel.py`."""
    from pathlib import Path

    evals = Path(__file__).resolve().parents[2] / "eval"
    fout = [p.name for p in evals.glob("*.py") if p.name != "wortel.py" and "parents[3]" in p.read_text(encoding="utf-8")]
    assert not fout, f"reken de wortel niet zelf uit, gebruik eval.wortel: {fout}"


def test_afval_per_bepaling(monkeypatch):
    """Per nodige bepaling waar ze afviel: niet gevonden, gevonden maar niet bij de 40, bij de 40 maar niet gekozen,
    gekozen. Een aanverwante bepaling telt niet."""
    import eval.bronselectie_eval as be

    monkeypatch.setattr(be, "_pool", lambda graaf, s, vraag, profiel=None: ["urn:bwb:X:artikel:2", "urn:bwb:X:artikel:3"])
    s = {"naam": "S", "deelvragen": ["v1"], "regelingen": ["X"],
         "verwacht": [{"deelvraag": 0, "bron_iri": f"urn:bwb:X:artikel:{n}", "rol": rol}
                      for n, rol in ((1, "kern"), (2, "kern"), (3, "afhankelijkheid"), (4, "kern"), (5, "aanverwant"))]}
    spoor = [{"set": "S", "vraag": "v1", "kandidaten": ["urn:bwb:X:artikel:3", "urn:bwb:X:artikel:4:lid:1"],
              "gekozen": ["urn:bwb:X:artikel:4:lid:1"], "terugval": False}]
    uit = m.afval(None, s, spoor)
    assert uit["telling"] == {"niet gevonden": 1, "gevonden, niet bij de 40": 1, "bij de 40, niet gekozen": 1,
                              "gekozen": 1}


def test_de_varianten_zijn_vlaggen_van_het_zoekprofiel():
    from agent.deelvraag_zoeken import Zoekprofiel
    velden = set(Zoekprofiel.__dataclass_fields__)
    assert all(set(v) <= velden for v in m.VARIANTEN.values())


def test_de_kandidatenroute_begrenst_en_kost_geen_model(monkeypatch):
    import eval.bronselectie_eval as be
    from agent import deelvraag_keuze

    gezien = {}

    def nep(graph, s, vraag, profiel, cache, limit=None):
        gezien["limit"] = limit
        return deelvraag_keuze.kandidaten([{"bron_iri": f"p{i}", "label": ""} for i in range(200)], [], maximaal=limit)

    monkeypatch.setattr(be, "kandidaten_voor", nep)
    uit = be.kandidaten_route(80)(None, {"naam": "S"}, "v")
    assert gezien["limit"] == 80 and len(uit) == 80 and not any(o["buiten"] for o in uit)
