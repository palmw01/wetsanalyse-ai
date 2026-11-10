"""Het register van connectormodules (ADR-013): per connector zijn tools, zijn bron en hoe een fout van die bron een
foutresultaat wordt. `tools/__init__.py` (de schema's, `dispatch`), de MCP-server en `tool_execution` lezen dit register;
er staat geen tak per connector meer naast. Een nieuwe connector is een beschrijving in `bronmodel.connectors`, een
module met zijn tools en een `ConnectorModule`, één regel in `MODULES` hieronder en een straatvlag.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectorModule:
    """Wat de toollaag van één connector weet. `dispatch(naam, args, bron, graph)` voert een tool uit; een `fout` van de
    bron (de adapter) wordt `fout_van(exc)`, met de reden uit de tabel `FOUTREDEN` van de module."""
    naam: str
    tools: list[dict[str, Any]]
    maak_bron: Callable[[Any], Any]
    dispatch: Callable[[str, dict[str, Any], Any, Any], str]
    fout: type[Exception]
    fout_van: Callable[[Exception], str]
    foutredenen: dict[str, str]
    _bron: Any = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def tool_namen(self) -> frozenset[str]:
        return frozenset(t["name"] for t in self.tools)

    def bron(self, settings: Any) -> Any:
        """Eén bron per proces, zodat de cache van de adapter gedeeld wordt (met Lex, het bronvenster en de MCP-server)."""
        with self._lock:
            if self._bron is None:
                self._bron = self.maak_bron(settings)
            return self._bron


def _kamerstukken() -> ConnectorModule:
    from ..adapters.sru_kamerstukken import KamerstukFout, SruKamerstukken
    from . import kamerstuk_tools as k

    return ConnectorModule(
        naam=k.CONNECTOR, tools=k.KAMERSTUK_TOOLS,
        maak_bron=lambda s: SruKamerstukken(sru_url=getattr(s, "kamerstukken_sru_url", "") or "https://repository.overheid.nl/sru"),
        dispatch=lambda n, a, bron, _graph: k.dispatch_kamerstuk(n, a, bron), fout=KamerstukFout, fout_van=k.fout_van,
        foutredenen=k.FOUTREDEN)


def _bekendmakingen() -> ConnectorModule:
    from ..adapters.sru_bekendmakingen import SruBekendmakingen
    from ..adapters.sru_koop import KoopFout
    from . import bekendmaking_tools as b

    return ConnectorModule(
        naam=b.CONNECTOR, tools=b.BEKENDMAKING_TOOLS,
        maak_bron=lambda s: SruBekendmakingen(sru_url=getattr(s, "kamerstukken_sru_url", "") or "https://repository.overheid.nl/sru"),
        dispatch=b.dispatch_bekendmaking, fout=KoopFout, fout_van=b.fout_van, foutredenen=b.FOUTREDEN)


def _rechtspraak() -> ConnectorModule:
    from ..adapters.lido_rechtspraak import LidoRechtspraak, RechtspraakFout
    from . import rechtspraak_tools as r

    return ConnectorModule(
        naam=r.CONNECTOR, tools=r.RECHTSPRAAK_TOOLS, maak_bron=lambda _s: LidoRechtspraak(),
        dispatch=r.dispatch_rechtspraak, fout=RechtspraakFout, fout_van=r.fout_van, foutredenen=r.FOUTREDEN)


#: Per connector (de naam uit `bronmodel.connectors`) zijn module.
MODULES: dict[str, ConnectorModule] = {m.naam: m for m in (_kamerstukken(), _bekendmakingen(), _rechtspraak())}


def module_van(tool: str) -> ConnectorModule | None:
    return next((m for m in MODULES.values() if tool in m.tool_namen), None)
