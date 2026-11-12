"""Welke bronconnectors een beurt aanbiedt: alleen die de vraag of het gesprek noemt (ronde 6, 12 nov 2026).

Elke aangezette connector kost per modelronde ~2k tokens aan toolschema's en een regel in BRONNEN IN DEZE BEURT, ook als
de vraag maar over één bron gaat (Staatsblad ronde 5: +7k per leesbeurt met alle vier aan). De keuze is in code, zonder
model, en generiek: alles komt uit de `ConnectorBeschrijving`.

- **Wat beperkt** (de vraag noemt de bron): een signaalwoord of een id van zijn soort (`ConnectorBeschrijving.noemt`;
  een *aanwijzing* als "wat bedoelde de wetgever" telt niet, K16), een van zijn `organen`, of een route die de supervisor
  in code koos (`van_route`: een genoemd stuk lezen, een lijstvraag). Dan krijgen alleen die bronnen hun tools.
- **Wat erbij komt maar niet beperkt**: een filterwaarde die de vraag draagt (`filters_in`: een dossier, een
  vergaderjaar, een waarde uit `MetadataVeld.waarden`), en een regeling die niet bij naam in de graaf staat
  (`buiten_graaf.noemt_regeling_buiten_graaf`). Zo'n waarde zegt wat er gezocht wordt, niet in welke bron: "Welke
  publicaties horen bij Kamerdossier 36602?" noemt het Staatsblad, maar het dossier is ook een filter van Kamerstukken
  (B18). Een artikel of een datum telt niet: daar gaat elke vraag aan Lex over.
- Noemt de vraag geen bron, dan houdt een vervolgvraag de keuze van het gesprek (`State.bronkeuze`); zonder keuze blijft
  alles aan wat aanstaat, zoals voorheen.
- Wat zo buiten de beurt valt, krijgt in de bronstand de reden `niet_nodig` ("niet nodig voor deze vraag"), niet "uit":
  de bron staat aan, de jurist neemt hem erbij door hem te noemen. Het event, het promptblok en een statusregel in het
  denkproces zeggen het.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from bronmodel.connectors import CONNECTORS, genoemde as _genoemde

#: De connector die een regeling buiten de kennisgraaf leest (geen signaalwoord: elke wetsnaam zou er een zijn).
BUITEN_GRAAF = "wetgeving_live"

#: De reden in de bronstand voor een bron die aanstaat maar deze beurt niet meedoet.
NIET_NODIG = "niet_nodig"


def _filtervormen() -> dict[str, re.Pattern[str]]:
    """Zoekargumenten met een vaste vorm in de vraag: een dossiernummer, een vergaderjaar. Dezelfde patronen als de
    lijstroute (`bron_lijst`), zodat wat de lijstroute als filter leest, hier ook als filter telt."""
    from .bron_lijst import _DOSSIER_RE, _VERGADERJAAR_RE

    return {"dossier": _DOSSIER_RE, "vergaderjaar": _VERGADERJAAR_RE}


_WOORD = re.compile(r"[\w-]+")


def _woorden(tekst: str) -> str:
    return " " + " ".join(_WOORD.findall((tekst or "").casefold())) + " "


def _organen(tekst: str) -> set[str]:
    """De connectors waarvan de tekst een orgaan noemt (`ConnectorBeschrijving.organen`: "de Eerste Kamer", "de Hoge
    Raad", "het Ministerie van Financiën"), als hele woordgroep."""
    woorden = _woorden(tekst)
    return {n for n, c in CONNECTORS.items() if any(_woorden(o) in woorden for o in c.organen if o.strip())}


def genoemd(teksten: Iterable[str]) -> set[str]:
    """De connectors die deze teksten zelf noemen: een signaal of id (`noemt`, geen aanwijzing), of een orgaan."""
    return {n for t in teksten if t for n in (*_genoemde(t), *_organen(t))}


def filters_in(teksten: Iterable[str]) -> set[str]:
    """De connectors waarvan een zoekfilter een waarde in de tekst vindt: een filter met een vaste vorm
    (`_filtervormen`) of een veld met `waarden` ("belastingrecht"). Alleen als aanvulling op wat genoemd is."""
    vormen = _filtervormen()
    uit: set[str] = set()
    for t in (t for t in teksten if t):
        for n, c in CONNECTORS.items():
            for v in c.metadata:
                if any(f in vormen and vormen[f].search(t) for f in v.filters) or any(
                        re.search(p, t, re.IGNORECASE) for _, p in v.waarden):
                    uit.add(n)
    return uit


def van_route(upd: dict[str, Any]) -> set[str]:
    """De connectors waarvan de route die de supervisor in code koos al een tool aanroept: een genoemd stuk lezen
    (`bron_lezen`) of een lijstvraag (`bron_lijst`). Die horen altijd bij de keuze; anders liep de aanroep van de code zelf
    tegen een vernauwde stand aan (meting ronde 6, B18: "Welke publicaties horen bij Kamerdossier 36602?" noemt het
    Staatsblad, de lijstroute koos `zoek_kamerstukken {dossier}`, en Lex zei dat Kamerstukken uit stond)."""
    tools = {str(a.get("name", "")) for a in upd.get("bron_lezen") or [] if isinstance(a, dict)}
    lijst = upd.get("bron_lijst") or {}
    uit = {n for n, c in CONNECTORS.items() if tools & set(c.tools)}
    if isinstance(lijst, dict) and lijst.get("connector") in CONNECTORS:
        uit.add(lijst["connector"])
    return uit


def kies(stand: dict[str, dict[str, Any]], genoemde: set[str], vorige: list[str] | None,
         erbij: set[str] = frozenset()) -> tuple[dict[str, dict[str, Any]], list[str] | None]:
    """(de bronstand van deze beurt, de keuze van het gesprek). `genoemde` beperkt, `erbij` komt alleen bij een keuze
    (een filter, een regeling buiten de graaf). De keuze is None als er niets te kiezen valt: dan blijft alles aan wat
    aanstaat. Een bron die uit stond, gaat hier nooit aan."""
    aan = [n for n, s in stand.items() if s.get("aan")]
    keuze = [n for n in aan if n in genoemde] or [n for n in aan if n in (vorige or [])]
    if not keuze:
        return stand, (vorige if not genoemde else None)
    keuze = [n for n in aan if n in keuze or n in erbij]
    if len(keuze) == len(aan):
        return stand, keuze
    return {n: ({**s, "aan": False, "reden": NIET_NODIG} if n in aan and n not in keuze else s)
            for n, s in stand.items()}, keuze


def actief(stand: dict[str, dict[str, Any]]) -> list[str]:
    return [n for n, s in stand.items() if s.get("aan")]
