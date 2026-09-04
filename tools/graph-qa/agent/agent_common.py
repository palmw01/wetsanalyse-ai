"""Kleine helpers gedeeld door de wrapper (agent.py) en de orkestrator."""
from __future__ import annotations

import asyncio


class BeurtGestopt(Exception):
    """De jurist heeft om stoppen gevraagd; de graaf hoort geen nieuwe node meer te betreden.

    Bewust een exception en géén `task.cancel()`. De nodes zijn synchroon en draaien in de
    default-executor: een `run_in_executor`-future is niet annuleerbaar, en de MCP-verbinding wordt
    in een `finally` gesloten – die onder een nog draaiende thread wegtrekken breekt hem. Dit stopt
    dus netjes op een nodegrens, met een consistente checkpointer-state.

    Gevolg voor de gebruiker: stoppen kost tijd, want de lopende stap (een LLM- of MCP-call) maakt
    zichzelf eerst af. Dat hoort de UI te tonen in plaats van te doen alsof het meteen klaar is.
    """


def truncate(text: str, max_chars: int = 8000) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + f"\n...[resultaat ingekort op {max_chars} tekens]"
    return text


def kap_toolresultaat(text: str, max_chars: int = 8000) -> str:
    """Kap een tool-resultaat af en zeg HOEVEEL er wegviel, plus hoe je de rest krijgt.

    `truncate` meldde wél dát er is ingekort maar niet hoeveel, en dat is precies het verschil
    tussen "je mist een regel" en "je ziet een derde van de bepaling". Het model kon daardoor niet
    beoordelen of het genoeg had — en concludeerde bij een afgekapt definitieartikel gerust dat de
    laatste definities niet bestaan. Dat is stille onvolledigheid, alleen dan aan de leeskant.

    De aanwijzing erbij is geen beleefdheid: er is nu een uitweg (afbakenen met `bwb_id`/`soort`,
    doorbladeren met `offset`), en zonder die zin weet het model niet dat hij bestaat.

    Blijft `truncate` voor alles wat géén tool-resultaat is – de corpus-inkorting en de
    argument-weergave in de narratie, waar zo'n staart alleen ruis zou zijn.
    """
    if len(text) <= max_chars:
        return text
    weg = len(text) - max_chars
    return (
        text[:max_chars]
        + f"\n...[ingekort: {weg} van {len(text)} tekens niet getoond. Bak je vraag scherper af "
        "(bv. get_lid i.p.v. get_artikel, of bwb_id/soort bij search_wetgeving) of vraag de "
        "volgende pagina op met offset. Ga er NIET van uit dat het weggevallen deel leeg is.]"
    )


async def run_sync(fn, *args):
    """Draai een blocking functie in de default executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)
