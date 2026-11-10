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
import json

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

    # Zonder CONNECTOR_*: de graaftools, zonder de bronconnectors (ADR-013).
    verwacht = [t for t in tools.anthropic_schemas() if t["name"] not in tools.CONNECTOR_TOOLS]
    assert [t.name for t in resultaat.tools] == [t["name"] for t in verwacht]
    assert [t.input_schema for t in resultaat.tools] == [t["input_schema"] for t in verwacht]
    assert [t.description for t in resultaat.tools] == [t["description"] for t in verwacht]


def test_call_tool_voert_de_echte_dispatch_uit(server_met_fake):
    """De uitvoering loopt via `dispatch`, dus dezelfde query-bouwers als de agent."""
    from mcp.types import CallToolRequestParams

    server, graaf = server_met_fake
    params = CallToolRequestParams(name="list_regelingen", arguments={})
    resultaat = asyncio.run(_handler(server, "tools/call")(None, params))

    # Exact de uitvoer van dispatch: het resultaatcontract over de rijen van de graaf.
    assert json.loads(resultaat.content[0].text)["resultaten"] == [{"x": "rij"}]
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


# ── Het contract naar buiten: annotaties, outputSchema, structuredContent (review ADR-013) ───────────────────────


def test_elke_tool_meldt_zijn_gedrag_en_de_contracttools_hun_schema(server_met_fake):
    from agent.mcp_server import CONTRACT_TOOLS

    server, _ = server_met_fake
    for t in asyncio.run(_handler(server, "tools/list")(None, None)).tools:
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False
        assert t.annotations.open_world_hint is (t.name in tools.CONNECTOR_TOOLS)
        assert (t.output_schema is not None) is (t.name in CONTRACT_TOOLS), t.name


def test_het_schema_is_geldig_en_vangt_een_onvolledig_resultaat_zonder_vervolg():
    jsonschema = pytest.importorskip("jsonschema")
    from agent.resultaat import CONTRACT_SCHEMA

    jsonschema.Draft202012Validator.check_schema(CONTRACT_SCHEMA)
    v = jsonschema.Draft202012Validator(CONTRACT_SCHEMA)
    assert v.is_valid({"status": "ok", "volledig": True, "aantal": 0, "resultaten": []})
    assert not v.is_valid({"status": "ok", "volledig": False, "aantal": 0, "resultaten": []}), "onvolledig zonder vervolg"
    assert not v.is_valid({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [],
                           "vervolg": {"tool": "x", "args": {}}}), "volledig met vervolg"
    assert v.is_valid({"status": "error", "reden": "bron_onbereikbaar", "melding": "weg"})


def _harnas():
    """Elke contracttool met zijn worst-case argumenten uit de contractharnas, alle pagina's."""
    from test_resultaatcontract import ARGS, CONNECTOR_ARGS, NEPBRONNEN, WorstCaseGraaf, _aanroep, _connector

    for naam, args in ARGS.items():
        yield naam, lambda n, a, g=WorstCaseGraaf(): _aanroep(n, a, g), args
    for naam, lijst in CONNECTOR_ARGS.items():
        c = _connector(naam)
        for args, _ in lijst:
            bron = NEPBRONNEN[c](1001, alineas=300)
            inst = make_settings(**{f"connector_{c}": True})
            yield naam, lambda n, a, b=bron, i=inst, c=c: tools.dispatch(n, None, a, i, **{c: b}), args


def test_structured_content_voldoet_aan_het_schema_voor_elke_contracttool():
    """Wat de server als outputSchema belooft, levert hij: elke pagina van elke contracttool, ook een fout."""
    jsonschema = pytest.importorskip("jsonschema")
    from agent.mcp_server import CONTRACT_TOOLS, resultaat_inhoud
    from agent.resultaat import CONTRACT_SCHEMA

    v = jsonschema.Draft202012Validator(CONTRACT_SCHEMA)
    gezien = set()
    for naam, roep, args in _harnas():
        assert naam in CONTRACT_TOOLS
        gezien.add(naam)
        for _ in range(60):
            tekst = roep(naam, args)
            structuur = resultaat_inhoud(naam, tekst)["structuur"]
            assert structuur is not None, f"{naam}: geen structuredContent"
            fouten = [e.message for e in v.iter_errors(structuur)]
            assert not fouten, f"{naam}: {fouten[:3]}"
            if structuur.get("volledig", True):
                break
            naam, args = structuur["vervolg"]["tool"], structuur["vervolg"]["args"]
    assert gezien == set(CONTRACT_TOOLS), f"zonder harnas: {set(CONTRACT_TOOLS) - gezien}"
    fout = tools.dispatch("zoek_kamerstukken", None, {}, make_settings(connector_kamerstukken=True))
    assert v.is_valid(resultaat_inhoud("zoek_kamerstukken", fout)["structuur"])


def test_een_gelezen_kamerstuk_is_een_resource_link_met_zijn_versie(monkeypatch):
    from mcp.types import CallToolRequestParams

    from agent import mcp_server
    from agent.adapters.sru_kamerstukken import Document
    from test_kamerstuk_tools import DOSSIER, XML, NepBron

    class Versie(NepBron):
        def document(self, ident):
            return Document(ident, self.xml, "h1", gewijzigd="2026-02-01", documentstatus="Opgemaakt")

    instellingen = make_settings(graphdb_mcp_url="http://x/mcp", graphdb_token="t", connector_kamerstukken=True)
    monkeypatch.setattr(mcp_server.Settings, "from_env", classmethod(lambda cls: instellingen))
    monkeypatch.setattr(mcp_server, "make_graph", lambda s: FakeGraph(result=""))
    monkeypatch.setattr(tools.CONNECTORMODULES["kamerstukken"], "_bron", Versie(DOSSIER, XML))
    server, _, _ = mcp_server._bouw_server()
    uit = asyncio.run(_handler(server, "tools/call")(None, CallToolRequestParams(name="get_kamerstuk",
                                                                                 arguments={"id": "kst-99001-3"})))
    link = next(c for c in uit.content if c.type == "resource_link")
    assert link.uri.endswith("kst-99001-3") and link.name == "kst-99001-3"
    assert link.annotations.last_modified == "2026-02-01"
    assert uit.structured_content["stuk"]["bron_hash"] == "h1" and uit.is_error is False
