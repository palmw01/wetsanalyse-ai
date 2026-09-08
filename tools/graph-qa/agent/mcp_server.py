"""Stdio-MCP-server over de getypeerde toollaag van graph-qa.

**Waarom dit bestaat.** Lex schrijft geen SPARQL: hij kiest uit `agent/tools/` en onze code bouwt de
query deterministisch (zie de invariant *"Geen vrije SPARQL voor het model"* in CLAUDE.md). Een
externe agent — een MCP-client zoals Claude Code, of de nl-sbb-begrip-workflow — had die keuze niet
en kreeg alleen de kale GraphDB-MCP met `sparql_query`. Dat betekent zelf SPARQL schrijven, en dus
zelf alle valkuilen opnieuw tegenkomen die hier al zijn opgelost: artikelnummers met een dubbele punt
(`4:89` → `artikel:4%3A89`), `bwb:heeftOnderdeel` in plaats van het niet-bestaande `bwb:bevat`,
bepalingen zonder eigen `bwb:tekst`, superklassen die rijen verdubbelen. nl-sbb-begrip liep er
allemaal in, plus een handgeschreven BWBR-tabel die naar de verkeerde wet wees.

**Deze server dupliceert daarom niets.** Hij is een doorgeefluik:

    tools/list  → anthropic_schemas()   (exact de tools die Lex krijgt, met hun schema's)
    tools/call  → dispatch(...)         (exact de uitvoering die Lex krijgt)

Elke verbetering aan `graph/queries.py` komt hier vanzelf mee, en de retrieval-smoke bewaakt ze al.

**Alleen lezen.** De toollaag kent geen schrijfbewerkingen en `mcp_client._reject_updates` weigert
SPARQL die op een update lijkt. `raw_sparql` blijft de afgeschermde ontsnapping die hij ook voor de
agent is.

Draaien (vraagt de `mcp`-extra, die bewust niet in het productie-image zit):

    GRAPHDB_MCP_URL=… GRAPHDB_TOKEN=… uv run --extra mcp graph-qa-mcp

Registreren hoort **machine-lokaal** (`claude mcp add`), niet in deze repo: die is publiek.
Logs gaan naar stderr; stdout is exclusief voor het MCP-protocol.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from agent import tools
from agent.adapters.graphdb_graph import make_graph
from agent.config import Settings
from agent.ports import GraphPort

logger = logging.getLogger("graph_qa.mcp_server")


def _bouw_server() -> tuple[Any, Settings, GraphPort]:
    """Bouw de MCP-server met de toollaag erachter.

    De graafverbinding wordt één keer opgezet en hergebruikt: de client houdt een MCP-sessie aan en
    een persistente httpx-client, dus per aanroep opnieuw verbinden zou elke tool-call een handshake
    plus TCP+TLS kosten.
    """
    from mcp.server.lowlevel import Server
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

    settings = Settings.from_env()
    settings.require_graph()          # fail-fast: zonder graaf heeft deze server geen bestaansrecht
    graph = make_graph(settings)

    async def lijst(_ctx: Any, _params: Any) -> Any:
        return ListToolsResult(
            tools=[
                Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
                for t in tools.anthropic_schemas()
            ]
        )

    async def roep_aan(_ctx: Any, params: Any) -> Any:
        # `dispatch` is synchroon (de graafclient is dat ook) en mag de event loop niet blokkeren.
        resultaat = await asyncio.to_thread(
            tools.dispatch, params.name, graph, params.arguments or {}, settings
        )
        # `dispatch` werpt niet: een toolfout komt terug als tekst, met uitleg voor het model. Die
        # afspraak houden we hier vast — een MCP-fout zou de client dwingen te raden of het aan de
        # vraag lag of aan de graaf, terwijl de tekst dat gewoon zegt.
        return CallToolResult(content=[TextContent(type="text", text=resultaat)])

    # De low-level server neemt de handlers als constructor-argumenten. Bewust niet de high-level
    # MCPServer: die leidt het JSON-schema af uit een Python-functiesignatuur, terwijl onze schema's
    # al bestaan in `anthropic_schemas()`. Ze daarheen vertalen zou precies de duplicatie zijn die
    # deze server moet voorkomen.
    server = Server(
        "wetsanalyse-graaf",
        instructions=(
            "De BWB-kennisgraaf via de getypeerde toollaag van graph-qa. Schrijf geen SPARQL; "
            "gebruik deze tools. Begin bij list_regelingen om een wet of afkorting naar een BWB-id "
            "te herleiden — raad een BWB-id nooit."
        ),
        on_list_tools=lijst,
        on_call_tool=roep_aan,
    )
    return server, settings, graph


async def _draai() -> None:
    from mcp.server.stdio import stdio_server

    server, _settings, graph = _bouw_server()
    logger.info("graaf-MCP gestart met %d tools", len(tools.anthropic_schemas()))
    try:
        async with stdio_server() as (lezen, schrijven):
            await server.run(lezen, schrijven, server.create_initialization_options())
    finally:
        graph.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(_draai())
    except ImportError as exc:
        # De `mcp`-extra ontbreekt. Zeggen wát er moet gebeuren, niet alleen dát het misging.
        print(f"MCP-SDK ontbreekt ({exc}). Installeer de extra: uv sync --extra mcp", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
