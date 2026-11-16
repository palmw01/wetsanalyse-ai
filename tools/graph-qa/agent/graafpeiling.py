"""Heeft de graaf regelingen? De peiling van de ketenrooktest (`GET /health?keten=1`, plan Lex Bench §20.5 stap 5).

Een revisie die draait, zegt niet dat Lex iets kan: na een herstart van GraphDB is de repository `inning` er niet, en
dan antwoordt Lex op elke vraag met een melding. De rooktest na een uitrol vraagt het daarom aan graph-qa, en een straat
met een lege of onbereikbare graaf komt niet meer groen door de uitrol. Eén query met `LIMIT 1`, zonder model.
"""
from __future__ import annotations

from typing import Any

from .graph import queries
from .graph.results import parse_select


def graafpeiling(graaf: Any) -> str:
    """`ok` als de graaf minstens één regeling heeft, `leeg` als hij antwoordt zonder, en `onbereikbaar` bij een fout.
    Een ontbrekende repository geeft een fout of een lege uitkomst; beide zijn niet `ok`."""
    try:
        rijen = parse_select(graaf.sparql(queries.list_regelingen(limit=1)))
    except Exception:  # noqa: BLE001 - de peiling zegt alleen of het werkt, de oorzaak staat in het log van de graaf
        return "onbereikbaar"
    return "ok" if any((r.get("regeling") or "").startswith(queries.NS) for r in rijen) else "leeg"
