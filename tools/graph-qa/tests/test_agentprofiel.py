"""Het agentprofiel en zijn grenzen (ADR-016 §A2): de validator in `bronmodel.agentprofiel`.

Een profiel is configuratie die een Python-agent laadt. Hier staat de vorm (het bestand `<naam>.md`) en wat de
validator weigert; het register dat de profielen laadt komt in stap A1.
"""
from __future__ import annotations

import pytest
from bronmodel import agentprofiel as ap
from bronmodel.validatie import ValidatieFout

GRENZEN = ap.Grenzen(
    tools=frozenset({"get_artikel", "get_lid", "zoek_definitie", "subagent", "besluit_nemen"}),
    skills=frozenset({"wetsanalyse"}), connectors=frozenset({"kamerstukken"}),
    sjablonen=frozenset({"antwoord_bepaling"}), verboden_tools=frozenset({"besluit_nemen"}),
    max_rondes=12, budget=100_000)

BESTAND = """---
name: definitie
description: Zoekt de wettelijke definitie van een begrip.
tools: [zoek_definitie, get_artikel]
skills: [wetsanalyse]
connectors: [kamerstukken]
sjablonen: [antwoord_bepaling]
model: licht
maxTurns: 8
budget: 50000
kiesbaar: false
---

Je bent de DEFINITIE-specialist.

Begin bij zoek_definitie.
"""


def test_het_bestand_wordt_een_getypeerd_profiel():
    p = ap.uit_markdown("definitie", BESTAND)
    assert p == ap.Agentprofiel(
        naam="definitie", beschrijving="Zoekt de wettelijke definitie van een begrip.", kiesbaar=False,
        instructie="Je bent de DEFINITIE-specialist.\n\nBegin bij zoek_definitie.", skills=("wetsanalyse",),
        tools=("zoek_definitie", "get_artikel"), connectors=("kamerstukken",), sjablonen=("antwoord_bepaling",),
        modelklasse="licht", max_rondes=8, budget=50_000)
    assert ap.toets(p, GRENZEN) == [] and ap.valideer(p, GRENZEN) is p
    with pytest.raises(Exception):
        p.naam = "anders"  # type: ignore[misc]


def test_zonder_tools_krijgt_een_profiel_alle_tools_behalve_wat_nooit_mag():
    p = ap.uit_markdown("algemeen", "---\nname: algemeen\ndescription: Breed.\n---\nAntwoord uit de graaf.\n")
    assert p.tools is None and p.kiesbaar and p.modelklasse == "zwaar" and p.max_rondes is None
    assert ap.toets(p, GRENZEN) == []
    assert ap.toegestane_tools(p, GRENZEN) == {"get_artikel", "get_lid", "zoek_definitie"}
    smal = p.model_copy(update={"tools": ("get_lid",)})
    assert ap.toegestane_tools(smal, GRENZEN) == {"get_lid"}


@pytest.mark.parametrize(("oud", "nieuw"), [
    ("name: definitie", "name: Definitie"),
    ("name: definitie", "name: anders"),
    ("description: Zoekt de wettelijke definitie van een begrip.", "description: ''"),
    ("model: licht", "model: reusachtig"),
    ("maxTurns: 8", "maxTurns: 0"),
    ("maxTurns: 8", "maxTurns: acht"),
    ("kiesbaar: false", "kiesbaar: nee, liever niet"),
    ("tools: [zoek_definitie, get_artikel]", "tools: zoek_definitie"),
    ("budget: 50000", "budget: 50000\npermissionMode: bypassPermissions"),
    ("Je bent de DEFINITIE-specialist.\n\nBegin bij zoek_definitie.\n", ""),
    ("---\nname", "name"),
])
def test_een_bestand_met_de_verkeerde_vorm_wordt_geweigerd(oud, nieuw):
    assert oud in BESTAND
    with pytest.raises(ValidatieFout) as fout:
        ap.uit_markdown("definitie", BESTAND.replace(oud, nieuw))
    assert fout.value.bevindingen


@pytest.mark.parametrize(("veld", "waarde"), [
    ("tools", ("subagent",)),              # één laag: een subagent stelt geen subagents op
    ("tools", ("besluit_nemen",)),         # nooit een besluit van de jurist
    ("tools", ("bestaat_niet",)),
    ("tools", ("get_lid", "get_lid")),
    ("skills", ("onbekende-skill",)),
    ("connectors", ("uit",)),
    ("mcp", ("server",)),
    ("sjablonen", ("antwoord_vrij",)),
    ("max_rondes", 13),
    ("budget", 100_001),
])
def test_een_profiel_buiten_de_grenzen_wordt_geweigerd(veld, waarde):
    p = ap.uit_markdown("definitie", BESTAND).model_copy(update={veld: waarde})
    assert {b.code for b in ap.toets(p, GRENZEN)} == {veld}
    with pytest.raises(ValidatieFout):
        ap.valideer(p, GRENZEN)


def test_subagent_mag_nooit_ook_niet_als_de_aanroeper_hem_niet_verbiedt():
    ruim = ap.Grenzen(tools=frozenset({"subagent", "get_lid"}), skills=frozenset(), connectors=frozenset(),
                      sjablonen=frozenset())
    p = ap.Agentprofiel(naam="x", beschrijving="x", instructie="x", tools=("subagent",))
    assert {b.code for b in ap.toets(p, ruim)} == {"tools"}
    assert ap.toegestane_tools(p.model_copy(update={"tools": None}), ruim) == {"get_lid"}
