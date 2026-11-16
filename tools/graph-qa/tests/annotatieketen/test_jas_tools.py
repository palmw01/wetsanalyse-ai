"""Fase 2B – unit-tests voor de JAS-kennistools."""
from __future__ import annotations

import json

from agent.tools.jas_tools import (
    JAS_TOOL_NAMEN,
    JAS_TOOLS,
    _jas_klasse_opvragen,
)


class TestJasKlasseOpvragen:
    def test_bekende_klasse(self):
        result = json.loads(_jas_klasse_opvragen("Rechtssubject"))
        assert result["naam"] == "Rechtssubject"
        assert "omschrijving" in result
        assert "vraag" in result
        assert "uitdrukkingswijze" in result

    def test_onbekende_klasse_geeft_fout(self):
        result = json.loads(_jas_klasse_opvragen("Fictieveklasse"))
        assert "fout" in result
        assert "Fictieveklasse" in result["fout"]

    def test_witruimte_wordt_gestript(self):
        result = json.loads(_jas_klasse_opvragen("  Voorwaarde  "))
        assert result["naam"] == "Voorwaarde"

    def test_alle_dertien_klassen_opvraagbaar(self):
        from agent.jas_klassen import JAS_KLASSEN_VOLGORDE
        for naam in JAS_KLASSEN_VOLGORDE:
            r = json.loads(_jas_klasse_opvragen(naam))
            assert r["naam"] == naam, f"Klasse {naam} niet gevonden"


class TestJasToolsRegistratie:
    def test_namen(self):
        assert JAS_TOOL_NAMEN == {"jas_klasse_opvragen"}

    def test_schema_structuur(self):
        for tool in JAS_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert "handler" in tool

    def test_handler_aanroepbaar(self):
        """Handlers zijn aanroepbaar via dispatch-interface (graph=None, args=dict)."""
        for tool in JAS_TOOLS:
            # Minimale args – onbekende klasse mag geen crash geven
            args = {k: "test" for k in tool["input_schema"]["required"]}
            result = tool["handler"](None, args)
            assert isinstance(result, str)

    def test_dispatch_integreert(self):
        from agent.tools import dispatch
        from fakes import FakeGraph
        result = dispatch("jas_klasse_opvragen", FakeGraph(result=""), {"naam": "Rechtsfeit"})
        data = json.loads(result)
        assert data["naam"] == "Rechtsfeit"

    def test_opvraagbaar_maar_niet_standaard_aangeboden(self):
        """Opt-in: wie erom vraagt krijgt ze, de QA-agent krijgt ze niet ongevraagd.

        Ze stonden alleen in `_BY_NAME`, dus `only=JAS_TOOL_NAMEN` – precies de aanroep die de
        module-docstring voorschrijft – gaf een lege lijst: uitvoerbaar, maar onaanroepbaar voor het
        model, want een tool die niet in de schema's staat bestaat voor hem niet.
        """
        from agent.tools import JAS_TOOL_NAMEN, anthropic_schemas

        gevraagd = {t["name"] for t in anthropic_schemas(only=JAS_TOOL_NAMEN)}
        assert gevraagd == set(JAS_TOOL_NAMEN)

        standaard = {t["name"] for t in anthropic_schemas()}
        assert not (standaard & set(JAS_TOOL_NAMEN))
