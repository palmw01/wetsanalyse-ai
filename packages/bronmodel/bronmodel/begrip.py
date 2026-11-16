"""Wat api en graph-qa over de inhoud van een begrip gelijk moeten zien.

Bij het aanmaken krijgt een begrip als toelichting een vindplaatsregel ("Komt voor in …", `begrippen_run_store.context_uit`
in de api, `kaart._context` in graph-qa). Die zegt waar de term staat, niet wat er afgebakend wordt (S6): de accorderingspoort
telt haar niet als toelichting, en Lex stelt er bij het uitwerken gewoon een toelichting voor in de plaats van.
"""
from __future__ import annotations

import re

# Een punt binnen een vindplaats staat tegen het volgende teken ("Artikel 79.5a"); een punt met een spatie erachter is het
# eind van de zin, dus wie er een eigen tekst achter zet, valt hier niet onder.
_NIET_EINDE = r"(?:[^.]|\.(?=\S))+"
VINDPLAATSREGEL = re.compile(rf"Komt voor in {_NIET_EINDE}\.(?: Wettelijke definitie in {_NIET_EINDE}\.)?")


def eigen_toelichting(context: str | None) -> bool:
    """Staat er een toelichting? De gegenereerde vindplaatsregel is er geen."""
    tekst = (context or "").strip()
    return bool(tekst) and VINDPLAATSREGEL.fullmatch(tekst) is None
