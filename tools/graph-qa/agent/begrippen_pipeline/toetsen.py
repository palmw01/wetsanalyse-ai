"""Deterministische toetsen op een concept-kaart (spoor D, fase C).

Twee soorten, en ze verschillen in gevolg:

- **Garanties** – een id dat niet in het manifest bestaat, een fragment dat niet letterlijk op zijn
  offsets staat, een "letterlijke" definitie die niet in haar bron staat. Dat is een fout van de
  keten, geen twijfel: `garanties()` levert de codes, en wie een kaart met een gebroken garantie
  zou opslaan, faalt (`kaart.vul` gooit de definitie weg; de api toetst opnieuw).
- **Signalen** – inhoudelijke aandachtspunten voor de jurist (circulair, rekenregel, gemengde
  klassen, waarschijnlijk geen begrip). Ze maken een kaart geel, ze houden niets tegen.

Elke code heeft een leesbare tekst in `TEKST`; `tests/test_begrippen_kaart.py` bewaakt dat.
"""
from __future__ import annotations

import re

from . import fragmenten
from .model import Herkomst, Kaart, Manifest

VERSIE = "1"

TEKST: dict[str, str] = {
    # garanties
    "FRAGMENT_ONBEKEND": "De definitie noemt een fragment dat niet in het manifest bestaat.",
    "FRAGMENT_NIET_LETTERLIJK": "Een fragment staat niet letterlijk op zijn plek in de bron.",
    "LETTERLIJK_NIET_IN_BRON": "De 'letterlijke' definitie staat niet zo in haar bron.",
    "SAMENGESTELD_NIET_UIT_FRAGMENTEN": "De samengestelde definitie is meer dan haar fragmenten.",
    # signalen
    "CIRCULAIR": "De definitie gebruikt de naam van het begrip zelf.",
    "REKENREGEL": "Dit leest als een rekenregel of hoeveelheid, niet als een definitie.",
    "GEMENGDE_KLASSEN": "De passages hebben verschillende JAS-klassen; controleer of het één begrip is.",
    "GEEN_BEGRIP": "De passages zijn tijdsaanduidingen, parameters of operatoren; dat is meestal geen begrip.",
    "GEEN_DEFINITIE": "Er is nog geen definitie voorgesteld.",
    "MODEL_GEEN_DEFINITIE": "Lex gaf voor deze groep geen bruikbare definitie.",
    "CIRCULAIR_VERWORPEN": "Lex formuleerde een definitie met de naam van het begrip zelf; die is niet overgenomen.",
    "DOOR_LEX_GEFORMULEERD": "De definitie is door Lex geformuleerd; toets haar aan de passages.",
}

GARANTIES = ("FRAGMENT_ONBEKEND", "FRAGMENT_NIET_LETTERLIJK", "LETTERLIJK_NIET_IN_BRON",
             "SAMENGESTELD_NIET_UIT_FRAGMENTEN")

_GEEN_BEGRIP = {"Tijdsaanduiding", "Parameter en parameterwaarde", "Operator"}
_REKEN = re.compile(r"\b(?:bedraagt|wordt berekend|berekend als|vermenigvuldigd|gedeeld door|vermeerderd met|"
                    r"verminderd met|percent|procent)\b|%|\d+\s*[x×*/+−-]\s*\d+", re.IGNORECASE)


def scheiding(fragment_teksten: list[str]) -> str:
    """Hoe een samengestelde definitie haar fragmenten verbindt; één plek, zodat de toets klopt."""
    return " … ".join(fragment_teksten)


def garanties(manifest: Manifest, kaart: Kaart) -> list[str]:
    fouten: list[str] = []
    alle = fragmenten.alle(manifest)
    for f in kaart.fragmenten:
        bekend = alle.get(f.id)
        if bekend is None:
            fouten.append("FRAGMENT_ONBEKEND")
        elif bekend.tekst != f.tekst or manifest.bron(f.bron_iri).tekst[f.start:f.eind] != f.tekst:
            fouten.append("FRAGMENT_NIET_LETTERLIJK")
    if kaart.herkomst is Herkomst.LETTERLIJK:
        iris = {b.bron_iri for b in manifest.bronnen}
        if kaart.definitie_bron_iri not in iris or kaart.definitie not in manifest.bron(kaart.definitie_bron_iri).tekst:
            fouten.append("LETTERLIJK_NIET_IN_BRON")
    if kaart.herkomst is Herkomst.SAMENGESTELD and kaart.definitie != scheiding([f.tekst for f in kaart.fragmenten]):
        fouten.append("SAMENGESTELD_NIET_UIT_FRAGMENTEN")
    return list(dict.fromkeys(fouten))


def signalen(kaart: Kaart, klassen: list[str]) -> list[str]:
    """Over wat Lex voorstelt, niet over de wet: een letterlijke definitie is wat de wet zegt, ook als
    die de naam herhaalt, en een term die de wet definieert is een begrip."""
    uit: list[str] = []
    wettelijk = kaart.herkomst is Herkomst.LETTERLIJK
    if kaart.definitie and not wettelijk:
        naam = re.escape(kaart.naam.strip().lower())
        if naam and re.search(rf"\b{naam}\b", kaart.definitie.lower()):
            uit.append("CIRCULAIR")
        if _REKEN.search(kaart.definitie):
            uit.append("REKENREGEL")
    elif not kaart.definitie:
        uit.append("GEEN_DEFINITIE")
    eigen = {k for k in klassen if k and k != "Brondefinitie"}
    if len(eigen) > 1:
        uit.append("GEMENGDE_KLASSEN")
    if eigen and eigen <= _GEEN_BEGRIP and not wettelijk:
        uit.append("GEEN_BEGRIP")
    if kaart.herkomst is Herkomst.GEFORMULEERD:
        uit.append("DOOR_LEX_GEFORMULEERD")
    return uit
