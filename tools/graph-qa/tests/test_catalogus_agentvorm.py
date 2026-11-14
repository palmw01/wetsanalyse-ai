"""De werkwijze toont de centrale agent en de subagents zoals ze werken (ADR-016), afgeleid uit de registers.

Een overdracht, een doelnode van de overdrachten of een profiel zonder plek in de werkwijze maakt deze tests rood; de
werkwijze houdt geen eigen lijst bij (`agent/catalogus.py`, §*de agentvorm*).
"""
from __future__ import annotations

import pytest
from bronmodel.agentprofiel import Agentprofiel

from agent import catalogus as cat
from agent import profielen
from agent import subagent as sub
from agent.overdracht import CENTRAAL, CENTRAAL_BREED, OVERDRACHT, REGIE_PLAN, SUBAGENT, doelen, voor

ALLE = {o.id: o for o in cat.catalogus()}


@pytest.mark.parametrize("naam", sorted(OVERDRACHT))
def test_elke_overdracht_leidt_naar_een_onderdeel(naam: str):
    """Een nieuwe overdracht zonder doel in de werkwijze geeft hier een KeyError of een lege lijst."""
    uit = cat.overdracht_doelen(naam)
    assert uit, f"{naam} leidt nergens heen"
    for d in uit:
        assert d in ALLE, f"{naam} leidt naar {d}, dat niet in de catalogus staat"
        assert naam in ALLE[d].ingang, f"{d} noemt de overdracht {naam} niet als ingang"


def test_elke_doelnode_van_de_overdrachten_heeft_een_onderdeel():
    for node in doelen():
        if node != "agent":
            assert cat._node_onderdeel(node), node


def test_elk_profiel_heeft_een_plek_in_de_werkwijze():
    for naam in profielen.PROFIELEN:
        plek = cat.profielplek(naam)
        assert plek in cat.PROFIELPLEK and plek != "onbekend", f"profiel {naam} heeft geen plek in de werkwijze"
        assert set(cat.PROFIELPLEK[plek]["stand"]) == set(cat.standen()), plek


def test_een_nieuw_profiel_zonder_plek_valt_op(monkeypatch):
    nep = Agentprofiel(naam="nep", beschrijving="Een nep-profiel.", instructie="nep", tools=("get_artikel",),
                       methoderol="algemeen", kiesbaar=False)
    monkeypatch.setitem(profielen.PROFIELEN, "nep", nep)
    assert cat.profielplek("nep") is None
    rij = next(p for p in cat.agentvorm("aan")["profielen"] if p["id"] == "agentprofiel/nep")
    assert rij["plek"] is None and rij["label"] == cat.PROFIELPLEK["onbekend"]["label"]


@pytest.mark.parametrize("stand", ["uit", "meten", "aan"])
def test_de_ingang_volgt_de_stand_van_de_vlag(stand: str):
    v = cat.agentvorm(stand)
    assert set(v["standen"]) == set(cat.standen()) == {"uit", "meten", "aan"}
    assert v["ingang"] == ("agentprofiel/centraal" if stand == "aan" else "rol/supervisor")
    assert v["ingang"] in ALLE
    for p in v["profielen"]:
        assert p["nu"], p
    for sleutel in ("centrale_agent", "subagents", "regie"):
        assert v[sleutel] in ALLE


def test_een_onbekende_stand_is_een_fout():
    with pytest.raises(ValueError):
        cat.agentvorm("half")


def test_de_centrale_agent_noemt_zijn_overdrachten_en_de_kernset():
    for naam in (CENTRAAL, CENTRAAL_BREED):
        i = ALLE[f"agentprofiel/{naam}"].inhoud
        assert [o["naam"] for o in i["overdrachten"]] == list(voor(naam))
        assert set(i["kernset"]) | set(i["alleen_breed"]) == set(ALLE["agentprofiel/centraal_breed"].tools)
        assert set(i["kernset"]) == set(ALLE["agentprofiel/centraal"].tools)
        assert all(m in ALLE for m in i["skills"]["methodes"])


def test_subagents_als_begrip():
    o = ALLE["workflow/subagent"]
    assert SUBAGENT in o.ingang and o.straat == cat.VLAG
    i = o.inhoud
    assert i["profielen"] == [f"agentprofiel/{n}" for n in profielen.KIESBAAR]
    limieten = {x["naam"]: x["waarde"] for x in i["limieten"]}
    assert limieten["MAX_SUBAGENTS"] == sub.MAX_SUBAGENTS
    assert {"MAX_RONDES_SUBAGENT", "MAX_TOKENS_SUBAGENT", "DELEGATIE_AANDEEL", "REGIE_PARALLEL"} <= set(limieten)
    assert any(c["naam"] == "per stuk" for c in i["controles"])
    assert "sjabloon/rapport" in o.hangt_af_van


def test_de_regie_als_tool_naast_de_vaste_route():
    o = ALLE["workflow/regie"]
    assert REGIE_PLAN in o.ingang and "regie_bronnen" in o.ingang
    assert o.inhoud["als_tool"]["opdrachten"] == OVERDRACHT[REGIE_PLAN].invoer["opdracht"]["enum"]
    assert len(o.inhoud["fasen"]) == 3


@pytest.mark.parametrize("stand", ["uit", "meten", "aan"])
def test_het_endpoint_geeft_de_agentvorm_van_deze_straat(monkeypatch, stand: str):
    from fastapi.testclient import TestClient

    import api.main as main

    monkeypatch.setattr(main.settings, "qa_api_token", "", raising=False)
    monkeypatch.setattr(main.settings, "centrale_agent", stand, raising=False)
    lijst = TestClient(main.app).get("/v1/catalogus").json()
    assert lijst["agentvorm"]["stand"] == stand
    per_id = {o["id"]: o for o in lijst["onderdelen"]}
    assert per_id["agentprofiel/centraal"]["aan"] is (stand != "uit")
    assert per_id["workflow/subagent"]["aan"] is (stand != "uit")
