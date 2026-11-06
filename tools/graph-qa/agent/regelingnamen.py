"""De naam van een regeling bij haar BWB-id, voor de bronnenlijst.

Een bron "Artikel 1" zegt niets als het antwoord vier regelingen noemt; de verwijzing zelf draagt
alleen het BWB-id. Eén SPARQL-query per beurt haalt de citeertitels van alle regelingen in de lijst
op (terugval: het opschrift). Namen wisselen niet binnen een graafstand, dus ze blijven in het proces
bewaard. Een fout kost alleen de naam: de bron toont dan haar BWB-id, het antwoord gaat gewoon door.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from .graph.results import parse_select
from .models import Source
from .ports import GraphPort

logger = logging.getLogger(__name__)

_BWB = re.compile(r"^BWB[RV]\d+$")
_CACHE: dict[str, str] = {}
_AFKORTINGEN: dict[str, list[str]] = {}
_CACHE_MAX = 2048


def _query(bwbs: list[str], *, afkortingen: bool = False) -> str:
    waarden = " ".join(f"(<urn:bwb:{b}> <urn:bwb:graph:{b}>)" for b in bwbs)
    return (
        "PREFIX bwb: <urn:bwb-ns:>\n"
        "SELECT ?r (MIN(?c) AS ?citeertitel) (MIN(?o) AS ?opschrift)"
        + (' (GROUP_CONCAT(DISTINCT ?a; separator=" | ") AS ?afkortingen)' if afkortingen else "") + " WHERE {\n"
        f"  VALUES (?r ?g) {{ {waarden} }}\n"
        "  GRAPH ?g { OPTIONAL { ?r bwb:citeertitel ?c } OPTIONAL { ?r bwb:opschrift ?o }"
        + (" OPTIONAL { ?r bwb:afkorting ?a }" if afkortingen else "") + " }\n"
        "} GROUP BY ?r"
    )


def _haal(graph: GraphPort, bwbs: list[str], *, afkortingen: bool = False) -> None:
    """Zet de namen van deze id's in de cache. Mislukt het, dan ontbreken ze: dat kost alleen de naam."""
    try:
        rijen = parse_select(graph.sparql(_query(bwbs, afkortingen=afkortingen)))
    except Exception:  # noqa: BLE001 - een naam mag het antwoord nooit breken
        logger.warning("regelingnamen niet opgehaald", extra={"aantal": len(bwbs)}, exc_info=True)
        rijen = []
    if len(_CACHE) + len(rijen) > _CACHE_MAX:
        _CACHE.clear()
        _AFKORTINGEN.clear()
    for rij in rijen:
        bwb = rij.get("r", "").removeprefix("urn:bwb:")
        naam = (rij.get("citeertitel") or rij.get("opschrift") or "").strip()
        if _BWB.fullmatch(bwb) and naam:
            _CACHE[bwb] = naam
            if afkortingen:
                _AFKORTINGEN[bwb] = [a.strip() for a in (rij.get("afkortingen") or "").split(" | ") if a.strip()]


def _geldig(bwbs: Iterable[str]) -> list[str]:
    return sorted({b for b in bwbs if b and _BWB.fullmatch(b)})


def regelingnamen(graph: GraphPort, bwbs: Iterable[str]) -> dict[str, str]:
    """BWB-id → naam, voor de id's die de graaf kent. Onbekend of mislukt: niet in het resultaat.

    Zonder afkortingen: deze query staat in de opnames van de bronselectie-eval (`OpnameGraaf`), die op de
    exacte tekst sleutelen, en de meetbestanden zijn bewijs."""
    gevraagd = _geldig(bwbs)
    if nieuw := [b for b in gevraagd if b not in _CACHE]:
        _haal(graph, nieuw)
    return {b: _CACHE[b] for b in gevraagd if b in _CACHE}


def met_regelingnamen(graph: GraphPort, sources: list[Source]) -> list[Source]:
    """Vul `regeling` en `afkortingen` in; een regeling-bron krijgt haar naam ook als label.

    De werkplek leest de afkortingen om "artikel 9 Awb" alleen aan een bron uit de Awb te koppelen."""
    gevraagd = _geldig(s.bwb_id or "" for s in sources)
    if nieuw := [b for b in gevraagd if b not in _AFKORTINGEN]:
        _haal(graph, nieuw, afkortingen=True)
    for s in sources:
        if s.bwb_id and (naam := _CACHE.get(s.bwb_id)):
            s.regeling = naam
            s.afkortingen = _AFKORTINGEN.get(s.bwb_id) or None
            if s.soort == "regeling":
                s.label = naam
    return sources
