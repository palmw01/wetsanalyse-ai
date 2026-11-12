"""Het register van de categorieën waarin een modelverzoek uiteenvalt (plan contextweergave, ADR-015).

Eén register, in vaste volgorde. Elk deel van een verzoek valt in precies één categorie; `verzoekopbouw` deelt in, de
meter rekent ermee en de werkplek tekent ze (`frontend/lib/contextdelen.ts` draagt label en kleur bij deze id's, met een
drifttest ertussen). De indeling volgt wat `/context` in Claude Code toont, vertaald naar hoe Lex een verzoek opbouwt.

Een categorie is `voorvoegsel` als ze vóór het cachepunt op de systeemprompt staat (tools → system): dat deel blijft een
uur in de cache (ADR-015) en is exact te meten zodra een verzoek het schrijft (`contextopbouw.verdeel`).

Tools worden ingedeeld via hun eigen register, niet via een lijst hier: een nieuwe connector of een nieuw sjabloon valt
vanzelf in de goede categorie.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categorie:
    id: str
    omschrijving: str
    voorvoegsel: bool = False


SYSTEEM = "systeem"
METHODE = "methode"
GRAAFTOOLS = "graaftools"
CONNECTORTOOLS = "connectortools"
AGENTTOOLS = "agenttools"
SJABLONEN = "sjablonen"
BEURTCONTEXT = "beurtcontext"
OPDRACHT = "opdracht"
HISTORIE = "historie"
BEURT = "beurt"
TOOLRESULTATEN = "toolresultaten"
OVERIG = "overig"

CATEGORIEEN: tuple[Categorie, ...] = (
    Categorie(SYSTEEM, "de identiteit van Lex (SYSTEM_PROMPT)", voorvoegsel=True),
    Categorie(METHODE, "de specialist- of rolprompt met de methodetekst", voorvoegsel=True),
    Categorie(GRAAFTOOLS, "de schema's van de tools uit het toolregister", voorvoegsel=True),
    Categorie(CONNECTORTOOLS, "de tools van aangezette bronconnectors (ADR-013)", voorvoegsel=True),
    Categorie(AGENTTOOLS, "de eigen tools van de agent: de overdracht aan een route of een profiel (ADR-016)",
              voorvoegsel=True),
    Categorie(SJABLONEN, "de sjabloontools (ADR-008)", voorvoegsel=True),
    Categorie(BEURTCONTEXT, "plan, gesprekscontext, werkgebied of dossier, bronstand, afrondregel"),
    Categorie(OPDRACHT, "bij een subagent: de opdracht van de centrale agent (ADR-016)"),
    Categorie(HISTORIE, "eerdere beurten"),
    Categorie(BEURT, "de vraag van deze beurt en wat het model zelf schreef: tekst en toolaanroepen"),
    Categorie(TOOLRESULTATEN, "wat tools en subagents in deze beurt teruggaven"),
    Categorie(OVERIG, "wat niet te herkennen is"),
)

#: De id's in de volgorde van het register: zo staan de delen in de contextopbouw en in de legenda.
IDS: tuple[str, ...] = tuple(c.id for c in CATEGORIEEN)
VOORVOEGSEL: frozenset[str] = frozenset(c.id for c in CATEGORIEEN if c.voorvoegsel)


def tool_categorie(naam: str) -> str:
    """De categorie van een toolschema, uit het register waar de tool in staat. Onbekend (de ene strict tool van een
    losse stap, een tool die geen register kent) is `overig`.

    De registers worden hier pas geladen: `verzoekopbouw` hangt onder de gedeelde modelstap, en de toollaag is zwaar."""
    from .sjablonen import SJABLONEN as sjabloonregister
    from .tools import _BY_NAME, CONNECTOR_TOOLS

    from .overdracht import OVERDRACHT

    if naam in OVERDRACHT:
        return AGENTTOOLS
    if naam in CONNECTOR_TOOLS:
        return CONNECTORTOOLS
    if naam in sjabloonregister:
        return SJABLONEN
    if naam in _BY_NAME:
        return GRAAFTOOLS
    return OVERIG
