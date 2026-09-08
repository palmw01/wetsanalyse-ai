"""De MCP-server is een doorgeefluik over de toollaag — en moet dat blijven.

De server bestaat omdat een externe agent anders zelf SPARQL schrijft. nl-sbb-begrip deed dat en
liep in de hele reeks valkuilen die `graph/queries.py` al had opgelost: artikelnummers met een
dubbele punt, `bwb:tekst` als harde eis, een handgeschreven BWBR-tabel die naar de verkeerde wet
wees. De winst zit er dus in dat hij **exact** aanbiedt wat Lex krijgt, niet een eigen selectie of
een eigen schema. Deze tests bewaken precies dat.

De `mcp`-extra zit niet in het productie-image en niet in de CI-installatie; ontbreekt hij, dan
slaan deze tests over in plaats van rood te worden — dezelfde lijn als `test_predicaat_dekking.py`.
"""
from __future__ import annotations

import asyncio

import pytest

from agent import tools
from fakes import FakeGraph, make_settings

pytest.importorskip("mcp", reason="de mcp-extra is niet geïnstalleerd (uv sync --extra mcp)")


@pytest.fixture
def server_met_fake(monkeypatch):
    """De server, met een FakeGraph in plaats van een echte graafverbinding."""
    from agent import mcp_server

    graaf = FakeGraph(result="?x\nrij")
    instellingen = make_settings(graphdb_mcp_url="http://x/mcp", graphdb_token="t")
    monkeypatch.setattr(mcp_server.Settings, "from_env", classmethod(lambda cls: instellingen))
    monkeypatch.setattr(mcp_server, "make_graph", lambda s: graaf)

    server, _settings, teruggegeven = mcp_server._bouw_server()
    assert teruggegeven is graaf
    return server, graaf


def _handler(server, naam: str):
    """De geregistreerde handler voor een MCP-methode.

    `get_request_handler` geeft een `HandlerEntry` (handler + params_type), niet de functie zelf.
    """
    return server.get_request_handler(naam).handler


def test_biedt_exact_de_tools_van_de_agent_aan(server_met_fake):
    """Geen eigen selectie en geen eigen schema's: één toollaag, twee consumenten."""
    server, _ = server_met_fake
    resultaat = asyncio.run(_handler(server, "tools/list")(None, None))

    verwacht = tools.anthropic_schemas()
    assert [t.name for t in resultaat.tools] == [t["name"] for t in verwacht]
    assert [t.input_schema for t in resultaat.tools] == [t["input_schema"] for t in verwacht]
    assert [t.description for t in resultaat.tools] == [t["description"] for t in verwacht]


def test_call_tool_voert_de_echte_dispatch_uit(server_met_fake):
    """De uitvoering loopt via `dispatch`, dus dezelfde query-bouwers als de agent."""
    from mcp.types import CallToolRequestParams

    server, graaf = server_met_fake
    params = CallToolRequestParams(name="list_regelingen", arguments={})
    resultaat = asyncio.run(_handler(server, "tools/call")(None, params))

    assert resultaat.content[0].text == "?x\nrij"
    assert graaf.queries, "de tool heeft de graaf niet bevraagd"
    assert "bwb:Regeling" in graaf.queries[0]


def test_een_toolfout_komt_terug_als_tekst_niet_als_protocolfout(server_met_fake):
    """`dispatch` werpt niet; die afspraak moet de MCP-laag niet omzeilen.

    Een MCP-fout zou de client laten raden of het aan de vraag lag of aan de graaf, terwijl de
    tekst van `dispatch` dat gewoon zegt.
    """
    from mcp.types import CallToolRequestParams

    server, _ = server_met_fake
    params = CallToolRequestParams(name="bestaat_niet", arguments={})
    resultaat = asyncio.run(_handler(server, "tools/call")(None, params))

    assert "Onbekende tool" in resultaat.content[0].text


def test_zonder_graafconfiguratie_start_hij_niet(monkeypatch):
    """Fail-fast: zonder graaf heeft deze server geen bestaansrecht."""
    from agent import mcp_server

    monkeypatch.setattr(
        mcp_server.Settings, "from_env", classmethod(lambda cls: make_settings(graphdb_mcp_url=""))
    )
    with pytest.raises(Exception):
        mcp_server._bouw_server()
