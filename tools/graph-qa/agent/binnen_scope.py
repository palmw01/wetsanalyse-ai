"""Wanneer een vraag niet af te wijzen is: één regel voor de supervisor en de centrale agent.

Een afwijzing is voor een vraag die niet over Nederlandse wet- en regelgeving gaat. Twee soorten vragen horen er altijd
bij, ook als het model er niets over vindt; de code beslist dat, niet de prompt:

- een vraag over een bron naast de wet (ADR-013, `bronmodel.connectors.herkende`);
- een vraag die een regeling noemt, ook een die niet in de kennisgraaf staat (ADR-016 ronde 4, K12: "wat is bekend over
  het milieu in de milieuwet?" wees de centrale agent af, de supervisor zocht en zei dat de graaf geen
  milieuregelgeving bevat, met de regelingen die er wel in staan). De vorm is die van `beweringen.regelingen_genoemd`,
  plus een samenstelling op -wet in kleine letters, zoals een jurist typt.
"""
from __future__ import annotations

import re

from bronmodel.connectors import herkende as bronnen_in_vraag

from .beweringen import regelingen_genoemd

#: "milieuwet", "omgevingswet", "burgerlijk wetboek": een samenstelling op -wet of -wetboek, ook zonder hoofdletter.
_WET_KLEIN = re.compile(r"(?i)(?<![\w-])(?P<naam>[a-zà-ÿ]{3,}(?:wet|wetboek))(?![\w-])")

ZIN_REGELING = ("Deze vraag noemt een regeling ({namen}) en valt binnen de wetgeving. Zoek haar in de kennisgraaf; staat "
                "ze er niet in, zeg dat dan en noem welke regelingen er wel in staan. Wijs de vraag niet af.")
ZIN_BRON = ("Deze vraag gaat over een bron naast de wet en valt binnen de wetgeving. Zoek in die bron, of zeg dat ze in "
            "deze beurt uit staat. Wijs de vraag niet af.")


def genoemde_regelingen(vraag: str) -> list[str]:
    """De namen in de vraag met de vorm van een regeling, in volgorde, elk één keer."""
    uit: list[str] = []
    for naam in [*regelingen_genoemd(vraag or ""), *(m.group("naam") for m in _WET_KLEIN.finditer(vraag or ""))]:
        # "Invorderingswet" is al genoemd als "Invorderingswet 1990".
        if not any(naam.casefold() in eerder.casefold() for eerder in uit):
            uit.append(naam)
    return uit


def niet_afwijzen(vraag: str) -> str:
    """Waarom deze vraag niet af te wijzen is, als zin voor het model; leeg als de afwijzing mag."""
    if bronnen_in_vraag(vraag or ""):
        return ZIN_BRON
    if namen := genoemde_regelingen(vraag):
        return ZIN_REGELING.format(namen=", ".join(namen))
    return ""
