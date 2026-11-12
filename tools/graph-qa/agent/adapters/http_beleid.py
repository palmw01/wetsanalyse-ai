"""Welke HTTP-status een bron als tijdelijk geeft, wat er dan gebeurt en welke foutcode volgt: één beleid voor elke adapter.

Elke adapter had een eigen lus en een eigen indeling. Rechtspraak ronde 4 (12 nov 2026, R08): LiDO gaf drie keer een 400,
een hik die bij LiDO een tel later lukt, en de beurt heette "de zoekdienst weigerde het verzoek", alsof de vraag fout was.
De KOOP-adapter noemde juist elke 4xx "niet bereikbaar", en herhaalde niets.

De regel:

- een netwerkfout, een time-out, een 5xx en een 429 zijn altijd tijdelijk;
- een adapter **declareert** per host welke andere statussen bij die bron tijdelijk zijn (`Statusbeleid.tijdelijk`): bij
  LiDO de 400;
- een tijdelijke status gaat opnieuw, tot `POGINGEN` keer met een groeiende wachttijd (een 429 volgt `Retry-After`);
- blijft hij, dan is de code `onbereikbaar` (of `bezet` bij een 429); `verzoek_geweigerd` alleen bij een status die de
  adapter niet als tijdelijk kent, en `niet_gevonden` bij een 404.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

#: Hoe vaak een verzoek gaat bij een tijdelijke status of een netwerkfout.
POGINGEN = 3
#: De eerste wachttijd; daarna groeit hij (1 s, 2 s).
HERHAAL_S = 1.0
#: Hoogstens zo lang wacht een 429 op `Retry-After`.
MAX_WACHT_S = 5.0

#: De codes die over de bron zeggen, niet over de vraag of het stuk.
TIJDELIJKE_CODES = frozenset({"onbereikbaar", "bezet"})


@dataclass(frozen=True)
class Statusbeleid:
    """Wat een bron bij een HTTP-status bedoelt. `tijdelijk`: de statussen onder de 500 die bij deze bron een hik zijn."""

    tijdelijk: frozenset[int] = frozenset()

    def is_tijdelijk(self, status: int) -> bool:
        return status >= 500 or status == 429 or status in self.tijdelijk

    def foutcode(self, status: int) -> str:
        """De code bij een status van 400 of hoger, na de herhalingen."""
        if status == 404:
            return "niet_gevonden"
        if status == 429:
            return "bezet"
        if self.is_tijdelijk(status):
            return "onbereikbaar"
        return "verzoek_geweigerd"


#: Het beleid zonder eigen tijdelijke statussen.
STANDAARD = Statusbeleid()


def wachttijd(r: httpx.Response | None, poging: int, wacht_s: float | None = None) -> float:
    """De wachttijd vóór de volgende poging: `Retry-After` bij een 429 (tussen `wacht_s` en `MAX_WACHT_S`), anders
    groeiend met de poging. Zonder `wacht_s` geldt `HERHAAL_S` op het moment van aanroepen (een test zet die op nul)."""
    wacht_s = HERHAAL_S if wacht_s is None else wacht_s
    if r is not None and r.status_code == 429:
        try:
            return min(max(float(r.headers.get("Retry-After", wacht_s)), wacht_s), MAX_WACHT_S)
        except ValueError:
            return wacht_s
    return wacht_s * (poging + 1)


def met_herhaling(doe: Callable[[], httpx.Response], *, beleid: Statusbeleid, host: str,
                  slaap: Callable[[float], None], logger: logging.Logger, gebeurtenis: str,
                  voor_poging: Callable[[], None] | None = None, pogingen: int = POGINGEN,
                  wacht_s: float | None = None) -> httpx.Response:
    """Doe het verzoek tot `pogingen` keer zolang het tijdelijk mislukt. Geeft het laatste antwoord terug (ook een fout:
    de adapter zet het om met `beleid.foutcode`); een netwerkfout bij de laatste poging gaat door als `httpx.HTTPError`.
    Elke mislukking logt `gebeurtenis` met host, status of fouttype en de poging."""
    for poging in range(pogingen):
        laatste = poging == pogingen - 1
        if voor_poging is not None:
            voor_poging()
        try:
            r = doe()
        except httpx.HTTPError as exc:
            logger.warning(gebeurtenis, extra={"host": host, "fout": type(exc).__name__, "poging": poging + 1})
            if laatste:
                raise
            slaap(wachttijd(None, poging, wacht_s))
            continue
        if r.status_code >= 400 and r.status_code != 404:
            logger.warning(gebeurtenis, extra={"host": host, "status": r.status_code, "poging": poging + 1})
        if beleid.is_tijdelijk(r.status_code) and not laatste:
            slaap(wachttijd(r, poging, wacht_s))
            continue
        return r
    raise AssertionError("onbereikbaar")  # pragma: no cover – de lus geeft altijd iets terug of gooit
