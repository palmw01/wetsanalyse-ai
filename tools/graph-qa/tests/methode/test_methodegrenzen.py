"""De grenzen tussen methodes (plan methodes scheiden, S3, tests 2 en 4).

De annotatieketen, de annotatie-UI en de JAS-tools zijn van wetsanalyse. Een andere methode krijgt er geen toegang toe:
niet via een rol (een rol draagt secties van één methode) en niet via een tool in een profiel.
"""
from __future__ import annotations

import pytest
from bronmodel import skill as sk
from bronmodel.agentprofiel import Agentprofiel, toegestane_tools, toets
from bronmodel.catalogus import NEUTRAAL

from agent import catalogus, profielen
from agent.methodepakket import PAKKET
from agent.tools import ANNOTATIE_TOOL_NAMEN, JAS_TOOL_NAMEN


def _skill(naam: str, rollen: dict[str, list[str]]) -> sk.Skill:
    secties = {s: {"bestand": "references/x.md", "bronnen": [], "tekst": "x", "sha256": "0", "skill": naam}
               for ids in rollen.values() for s in ids}
    return sk.Skill(naam=naam, versie="1", lex={}, rollen=rollen, secties=secties, bestanden=frozenset())


# --- test 2: een rol krijgt secties van één methode ------------------------------------------------------------------

def test_een_tweede_methode_hangt_zich_niet_aan_een_rol_van_wetsanalyse():
    basis = _skill("wetsanalyse", {"duiding": ["duiding"], "agent": ["duiding"]})
    tweede = _skill("wetsuitvoering", {"duiding": ["jrm-scenario"]})
    bevindingen = sk.toets_samen([basis, tweede])
    assert [b.code for b in bevindingen] == ["rol"] and "duiding" in bevindingen[0].melding


def test_de_centrale_agent_mag_secties_van_meer_methodes_dragen():
    basis = _skill("wetsanalyse", {"duiding": ["duiding"], "agent": ["duiding"]})
    tweede = _skill("wetsuitvoering", {"agent": ["jrm-scenario"]})
    assert sk.GEDEELDE_ROLLEN == {"agent"} and not sk.toets_samen([basis, tweede])


def test_een_skill_zonder_rollen_botst_niet():
    assert not sk.toets_samen([_skill("wetsanalyse", {"duiding": ["duiding"]}), _skill("wetsuitvoering", {})])


def test_in_het_pakket_draagt_elke_rol_behalve_de_centrale_agent_een_methode():
    per_rol = profielen.rol_methodes()
    assert set(per_rol) == set(PAKKET["rollen"])
    assert {rol: m for rol, m in per_rol.items() if len(m) != 1 and rol not in sk.GEDEELDE_ROLLEN} == {}


# --- test 4: een profiel van een andere methode noemt geen JAS-tool --------------------------------------------------

def _grenzen(**rol_methodes):
    g = profielen.grenzen()
    return type(g)(**{**g.__dict__, "methoderollen": g.methoderollen | set(rol_methodes),
                      "rol_methodes": {**g.rol_methodes, **{r: frozenset(m) for r, m in rol_methodes.items()}}})


def _profiel(**velden) -> Agentprofiel:
    return Agentprofiel(**{"naam": "scenario", "beschrijving": "Werkt een juridisch scenario uit.",
                           "instructie": "Werk het scenario uit.", "methoderol": "scenario", **velden})


@pytest.mark.parametrize("tool", sorted(profielen.TOOLS_VAN_WETSANALYSE))
def test_een_profiel_van_een_andere_methode_noemt_geen_tool_van_wetsanalyse(tool):
    g = _grenzen(scenario={"wetsuitvoering"})
    bevindingen = toets(_profiel(tools=("get_artikel", tool)), g)
    assert [b.code for b in bevindingen] == ["tools"] and tool in bevindingen[0].melding


def test_een_profiel_van_een_andere_methode_mag_de_neutrale_graaftools():
    g = _grenzen(scenario={"wetsuitvoering"})
    assert toets(_profiel(tools=("get_artikel", "search_wetgeving")), g) == []


def test_ook_een_profiel_met_alle_tools_krijgt_ze_niet():
    g = _grenzen(scenario={"wetsuitvoering"})
    krijgt = toegestane_tools(_profiel(tools=None), g)
    assert "get_artikel" in krijgt and not krijgt & profielen.TOOLS_VAN_WETSANALYSE


def test_een_rol_die_ook_wetsanalyse_draagt_mag_ze_wel():
    g = _grenzen(scenario={"wetsanalyse", "wetsuitvoering"})
    assert toets(_profiel(tools=("search_annotaties",)), g) == []


def test_de_bestaande_profielen_houden_hun_tools():
    """De grens verandert niets aan wat er nu draait: elk profiel is van wetsanalyse."""
    g = profielen.grenzen()
    assert all(toets(p, g) == [] for p in profielen.PROFIELEN.values())
    assert profielen.tools_van(profielen.PROFIELEN["annotaties_lezen"]) >= {"search_annotaties", "get_annotatie"}


def test_de_tools_van_wetsanalyse_zijn_die_van_de_catalogus():
    """Eén waarheid: wat de catalogus (S2) van wetsanalyse noemt, is wat een ander profiel niet krijgt."""
    in_catalogus = {o.naam for o in catalogus.catalogus() if o.soort == "tool" and o.methode != NEUTRAAL}
    assert in_catalogus == profielen.TOOLS_VAN_WETSANALYSE
    assert set(ANNOTATIE_TOOL_NAMEN) | set(JAS_TOOL_NAMEN) <= profielen.TOOLS_VAN_WETSANALYSE
