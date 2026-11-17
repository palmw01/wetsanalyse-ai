"""Contextisolatie (ADR-014 §7): een agent krijgt alleen zijn eigen skills en tools, en de catalogus zegt welke.

Zoals bij een subagent in Claude Code. De bron is het declaratieve register (`Specialist.tools`, `Specialist.sjablonen`,
de rol in `agentrollen.json`); de runtime en de catalogus lezen het allebei. Deze test vergelijkt wat de antwoordlus per
specialist werkelijk meestuurt met wat de catalogus zegt, met alle connectors aan (de ruimste stand). Komt er een tool,
sjabloon of methodesectie bij buiten de catalogus om, of valt er een weg, dan wordt dit rood.
"""
from __future__ import annotations

import pytest
from bronmodel import catalogus as bc
from bronmodel.connectors import CONNECTORS

from agent import catalogus as cat
from agent import specialists
from agent.profielen import PROFIELEN
from agent.llm_stap import Rol
from agent.methode import vingerafdruk
from agent.methodepakket import PAKKET
from agent.sjablonen import EXTERN, sjabloon_schemas
from agent.tools import anthropic_schemas, toegestane_tools


class _AllesAan:
    def __getattr__(self, naam: str):
        if naam.startswith("connector_"):
            return True
        raise AttributeError(naam)


NAMEN = sorted(specialists.SPECIALISTS)


def _onderdeel(naam: str) -> bc.Onderdeel:
    o = cat.onderdeel(bc.oid("agentprofiel", naam))
    assert o is not None
    return o


@pytest.mark.parametrize("naam", NAMEN)
def test_de_tools_van_een_specialist_zijn_die_van_de_catalogus(naam: str):
    spec = specialists.SPECIALISTS[naam]
    runtime = {t["name"] for t in anthropic_schemas(only=toegestane_tools(spec.tools, _AllesAan()))}
    o = _onderdeel(naam)
    assert runtime == set(o.tools), f"{naam}: buiten de catalogus {sorted(runtime ^ set(o.tools))}"
    assert {bc.oid("tool", t) for t in runtime} <= set(o.hangt_af_van)


@pytest.mark.parametrize("naam", NAMEN)
def test_de_sjablonen_van_een_specialist_zijn_die_van_de_catalogus(naam: str):
    spec = specialists.SPECIALISTS[naam]
    bediend = bool(PROFIELEN[naam].connectors)
    namen = spec.sjablonen | {EXTERN} if spec.sjablonen and bediend else spec.sjablonen
    runtime = {s["name"] for s in sjabloon_schemas(namen, extern=tuple(CONNECTORS) if bediend else False)}
    in_catalogus = {d.split("/", 1)[1] for d in _onderdeel(naam).hangt_af_van if d.startswith("sjabloon/")}
    assert runtime == in_catalogus


@pytest.mark.parametrize("naam", NAMEN)
def test_een_specialist_draagt_precies_de_secties_van_zijn_rol(naam: str):
    """De methodetekst in de systeemprompt is die van zijn rol, niet meer en niet minder; de vingerafdruk is de versie
    van de rol in de catalogus (dezelfde waarde als `methode_sha` in `model_aanroep`)."""
    rol = specialists.methoderol(naam)
    assert bc.oid("rol", rol) in _onderdeel(naam).hangt_af_van
    assert cat.onderdeel(bc.oid("rol", rol)).versie == vingerafdruk(rol)
    system = specialists.get(naam).system
    eigen = set(PAKKET["rollen"][rol])
    for sectie, s in PAKKET["secties"].items():
        assert (f"[{sectie}]\n" in system) == (sectie in eigen), f"{naam}: sectie {sectie}"


def test_elke_methoderol_van_een_modelaanroep_staat_in_de_catalogus():
    for r in Rol:
        if r.methoderol:
            assert cat.onderdeel(bc.oid("rol", r.methoderol)) is not None, r.naam
