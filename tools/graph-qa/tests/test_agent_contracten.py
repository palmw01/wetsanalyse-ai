"""Drift tussen de uitkomst van de agents (F3c) en de api-contracten die ze raken.

Een artefact of bevestiging die de api niet kent, valt bij het bewaren van het bericht met een 422 om – of,
erger, een onbekend veld valt stil weg en de werkplek opent na herladen geen paneel. Daarom tegen de bron.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent.agents import Uitkomst, register
from agent.begrippen_beurt import begrippen_artefact
from agent.beurt import deelvraag_artefact, werkgebied_artefact
from agent.bronnen_run import bronnen_artefact
from agent.kaart_beurt import begrip_artefact
from agent.werkgebied_annotatie import voorstel

API = Path(__file__).resolve().parents[3] / "api"


@pytest.fixture(scope="module")
def contracten():
    sys.path.insert(0, str(API))
    try:
        from app import gesprek_contracts
    except ImportError:
        pytest.skip("api-pakket niet importeerbaar in deze omgeving")
    finally:
        sys.path.pop(0)
    return gesprek_contracts


def test_elk_artefact_van_een_agent_kent_de_api(contracten):
    for artefact in (werkgebied_artefact({"id": "wg1", "naam": "Inv"}), bronnen_artefact("wg1", "r1", "Inv"),
                     begrippen_artefact("wg1", "r1", "Inv"), begrip_artefact("wg1", "b1", "Termijn"),
                     begrip_artefact("wg1", "b1", "Termijn", "k1", "voorbeelden"),
                     deelvraag_artefact("wg1", {"id": "d1", "vraag": "Wie betaalt?"})):
        contracten.Artefact(**artefact)


def test_elke_bevestiging_van_een_agent_kent_de_api(contracten):
    from agent.begrippen_verdieping import voorstel_tekst
    _, b1 = voorstel("Inv", {"werkgebied_id": "wg1", "te_annoteren": ["x"], "schatting": None})
    _, b2 = voorstel_tekst("Inv", {"werkgebied_id": "wg1", "aantal": 2, "vragen": ["v"], "schatting": None})
    for b in (b1, b2):
        contracten.Bevestiging(**b)


def test_het_bericht_draagt_artefact_en_bevestiging(contracten):
    velden = set(contracten.BerichtInvoer.model_fields)
    assert {"artefact", "bevestiging", "tekst", "denk", "run_id"} <= velden


def test_de_uitkomst_heeft_een_vaste_vorm():
    assert set(Uitkomst.model_fields) == {"taak", "status", "reden", "voorstellen", "artefact", "bevestiging",
                                          "tekst", "meting"}
    # Elke agent heeft dezelfde vorm: een vaste lijst taken, een getypte invoer, en wat er een model kan raken.
    for agent, mod in register.AGENTS.items():
        assert {"taak", "werkgebied_id"} <= set(mod.Invoer.model_fields), agent
        assert set(mod.MODEL_TAKEN) <= set(mod.Taak), agent
        assert callable(mod.voer_uit)


def test_de_taken_in_de_supervisorprompt_zijn_de_taken_van_de_agents():
    """De supervisor kent de taken alleen uit zijn prompt; een taak die daar ontbreekt, wordt nooit gekozen."""
    from agent.supervisor import SUPERVISOR_SYSTEM
    for agent in ("deelvragen", "begrippen"):
        for taak in register.taken(agent):
            assert f"{taak} (" in SUPERVISOR_SYSTEM, (agent, taak)
    assert "TAAK: werkgebied" in SUPERVISOR_SYSTEM
