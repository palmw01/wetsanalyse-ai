"""Een verzoek om werk volgens een methode die Lex nog niet uitvoert (plan methodes scheiden, S1).

De annotatieketen, de annotatie-UI en de JAS-tools zijn van wetsanalyse (ADR-014 §5, ADR-016 deel B). Noemt een
verzoek om te annoteren, markeren of analyseren een andere methode, en is die methode aan geen rol gekoppeld, dan
antwoordt Lex met een vaste zin en start hij niets: geen annotatie volgens het JAS onder een andere naam, en geen
model dat er zelf iets van maakt. De regel staat in code, vóór het model, en geldt voor de supervisor én de centrale
agent (`supervisie._kies`).

- **Gekoppeld** leest de regel uit het methodepakket: een methode-skill is gekoppeld zodra één van haar secties bij
  een rol hoort (`agentrollen.json`, `"rollen"`). Krijgt wetsuitvoering een rol, dan vervalt de regel voor haar vanzelf.
- **De trefwoorden** per methode staan hier. `tests/test_methodekeuze.py` eist dat elke methode-skill in het pakket,
  behalve wetsanalyse, hier een rij heeft: een derde methode kan niet stil zonder deze regel bestaan.
- **Een vraag óver een methode** ("wat zegt het JRM over een rechtsfeit?") is geen verzoek om werk en loopt zoals
  altijd. De regel vraagt daarom een werkwoord dat om werk vraagt, en slaat een vraag die met een vraagwoord begint over.
"""
from __future__ import annotations

import re

from .methodepakket import PAKKET

#: De methode waar de annotatieketen, de annotatie-UI en de JAS-tools van zijn.
EIGEN = "wetsanalyse"

#: methode-skill → (naam in de melding, patronen die de methode in een verzoek aanwijzen).
TREFWOORDEN: dict[str, tuple[str, tuple[str, ...]]] = {
    "wetsuitvoering": ("het Juridisch Referentiemodel (JRM, de methode wetsuitvoering)", (
        r"\bjrm\b",
        r"\bjuridisch referentie ?model\b",
        r"\bwetsuitvoering\b",
        r"\bjuridische? scenario",
        r"\bscenario'?s? met (een |de )?aktes?\b",
        r"\b(als|in|met) (een |de |juridische )?aktes?\b",
    )),
}

# Een werkwoord dat om werk vraagt. Zelfstandige naamwoorden ("een analyse", "de annotatie") tellen niet: die staan ook
# in een vraag óver de methode.
_WERK = re.compile(
    r"\b(annoteer|annoteren|markeer|markeren|classificeer|classificeren|analyseer|analyseren|uitwerken|opstellen|maak)\b"
    r"|\bwerk\b.{0,80}\buit\b|\bstel\b.{0,80}\bop\b")
_VRAAGWOORD = re.compile(r"^\W*(wat|hoe|waarom|welke?|wanneer|waar)\b")


def gekoppeld() -> frozenset[str]:
    """De methode-skills waarvan een sectie bij een rol hoort."""
    in_rol = {sectie for secties in PAKKET["rollen"].values() for sectie in secties}
    return frozenset(s["skill"] for naam, s in PAKKET["secties"].items() if naam in in_rol)


def niet_gekoppeld(vraag: str) -> str:
    """De methode-skill die dit verzoek noemt en die Lex nog niet uitvoert, of "" als het verzoek gewoon doorloopt."""
    tekst = " ".join((vraag or "").lower().split())
    if not tekst or _VRAAGWOORD.search(tekst) or not _WERK.search(tekst):
        return ""
    klaar = gekoppeld()
    for skill, (_naam, patronen) in TREFWOORDEN.items():
        if skill != EIGEN and skill not in klaar and any(re.search(p, tekst) for p in patronen):
            return skill
    return ""


def melding(skill: str) -> str:
    """De vaste zin: wat niet kan, en wat wel."""
    naam = TREFWOORDEN[skill][0]
    return (f"Een annotatie of analyse volgens {naam} kan ik nog niet maken. Annoteren doe ik alleen volgens het JAS, "
            "en dat start ik hier niet vanzelf. Wil je dat wel, vraag het dan zonder die methode erbij, bijvoorbeeld: "
            "\"annoteer artikel 9 van de Invorderingswet 1990\". Ik kan de wettekst ook voor je opzoeken en uitleggen.")
