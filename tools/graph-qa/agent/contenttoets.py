"""De route van de contenttoets (plan docs/architectuur/plan-contenttoets.md, C2): herkennen en de invoer lezen, in code.

`/contenttoets <tekst>` (of de actie `contenttoets` van de werkplek) gaat zonder model naar het profiel `contenttoets`,
dat met de skill van die naam toetst en afrondt met het sjabloon `antwoord_contenttoets`. De content staat dan in het
bronspoor (`sjablonen.contenttoets.CONTENT_TOOL`): daar leest het sjabloon hem, en de controle toetst de citaten uit de
content ertegen.

Een proefvlag (`Settings.contenttoets`, env `CONTENTTOETS`) zet de route aan; alleen acceptatie, tot de meting (C5).
Staat hij uit, dan zegt Lex dat in een vaste zin, zonder model.
"""
from __future__ import annotations

import re
from datetime import date

COMMANDO = "/contenttoets"
#: Zoveel tekens content toetst Lex in één beurt; een langere tekst toets je in delen.
MAX_TEKENS = 15_000
#: Korter is geen content om te toetsen.
MIN_TEKENS = 20

_PEILDATUM = re.compile(r"^\s*peildatum\s*[=:]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2}-\d{4})\s*", re.I)

UIT = ("De contenttoets staat in deze omgeving nog niet aan. Hij is in proef op acceptatie; zodra hij hier beschikbaar "
       "is, toets je een tekst met /contenttoets en de tekst erachter.")
LEEG = ("Plak de tekst die ik moet toetsen achter /contenttoets. Wil je toetsen tegen een andere datum dan vandaag, zet "
        "dan vooraan peildatum=2026-03-01.")
TE_LANG = ("Deze tekst is langer dan {max} tekens. Toets hem in delen, bijvoorbeeld per kop, zodat elk rapport "
           "overzichtelijk blijft.")


def is_contenttoets(vraag: str) -> bool:
    """Begint de vraag met het commando? Hoofdletters tellen niet; "/contenttoetsen" is iets anders."""
    v = (vraag or "").lstrip().lower()
    return v.startswith(COMMANDO) and (len(v) == len(COMMANDO) or not v[len(COMMANDO)].isalnum())


def _iso(datum: str) -> str:
    if "-" in datum and len(datum.split("-")[0]) == 4:
        jaar, maand, dag = (int(x) for x in datum.split("-"))
    else:
        dag, maand, jaar = (int(x) for x in datum.split("-"))
    return date(jaar, maand, dag).isoformat()


def ontleed(vraag: str, *, vandaag: date | None = None) -> tuple[str, str]:
    """(de content, de peildatum als ISO-datum). Het commando gaat eraf; een peildatum vooraan ook. Zonder peildatum, of
    met een datum die niet bestaat, geldt vandaag."""
    tekst = (vraag or "").lstrip()
    if is_contenttoets(tekst):
        tekst = tekst[len(COMMANDO):]
    peildatum = (vandaag or date.today()).isoformat()
    if m := _PEILDATUM.match(tekst):
        try:
            peildatum = _iso(m.group(1))
            tekst = tekst[m.end():]
        except ValueError:
            pass
    return tekst.strip(), peildatum


def melding(content: str) -> str:
    """De vaste zin als de content niet te toetsen is, of leeg als hij dat wel is."""
    if len(content) < MIN_TEKENS:
        return LEEG
    if len(content) > MAX_TEKENS:
        return TE_LANG.format(max=f"{MAX_TEKENS:,}".replace(",", "."))
    return ""
