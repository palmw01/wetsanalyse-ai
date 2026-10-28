"""Deterministische toetsen op een concept-kaart (spoor D, fase C).

Twee soorten, en ze verschillen in gevolg:

- **Garanties** – een id dat niet in het manifest bestaat, een fragment dat niet letterlijk op zijn
  offsets staat, een "letterlijke" definitie die niet in haar bron staat. Dat is een fout van de
  keten, geen twijfel: `garanties()` levert de codes, en wie een kaart met een gebroken garantie
  zou opslaan, faalt (`kaart.vul` gooit de definitie weg; de api toetst opnieuw).
- **Signalen** – inhoudelijke aandachtspunten voor de jurist (circulair, rekenregel, gemengde
  klassen, waarschijnlijk geen begrip). Ze maken een kaart geel, ze houden niets tegen.

Elke code heeft een leesbare tekst in `TEKST`; `tests/test_begrippen_kaart.py` bewaakt dat.

**Met een betekenisdossier** (spoor M, `betekenis.py`) kijken de signalen ook naar de context: een
algemene naam met een definitie uit één variant van parallelle leden, een rechtsgevolg of afleiding in
de definitie, een onderbouwing uit één voorkomen terwijl de term vaker staat, een fragment dat de
definitie niet draagt, tegenbewijs in het onderzoek, en context die niet onderzocht is. Zonder dossier
zijn de signalen wat ze waren.
"""
from __future__ import annotations

import re

from . import fragmenten
from . import betekenis
from .betekenis import Dossier, inhoudswoorden
from .model import Herkomst, Kaart, Manifest, Onderzoek

VERSIE = "2"

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
    # signalen met het betekenisdossier (spoor M)
    "ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE": "De naam is algemeen, maar de definitie beschrijft één variant uit parallelle bepalingen; kies een specifiekere naam of een algemenere definitie.",
    "RECHTSGEVOLG_IN_DEFINITIE": "De definitie noemt een rechtsgevolg (wat er met het begrip gebeurt); dat hoort niet in de omschrijving.",
    "AFLEIDING_IN_DEFINITIE": "De definitie beschrijft een afleiding of verrekening; die is een eigen begrip ('bepalen …').",
    "ONDERBOUWING_EEN_VOORKOMEN": "De onderbouwing komt uit één bepaling, terwijl de term ook elders in de onderzochte context staat.",
    "FRAGMENT_ONDERSTEUNT_NIET": "Een gekozen fragment deelt geen inhoudswoord met de definitie; controleer of het haar draagt.",
    "TEGENBEWIJS_IN_ONDERZOEK": "Het onderzoek vond een andere definitie of kwalificatie die deze term raakt; vergelijk ze.",
    "CONTEXT_NIET_ONDERZOCHT": "Niet alle context is onderzocht; de definitie kan iets missen.",
    "ONVOLDOENDE_BEWIJS": "Lex vond onvoldoende bewijs voor een definitie; de motivatie zegt wat er ontbreekt.",
}

GARANTIES = ("FRAGMENT_ONBEKEND", "FRAGMENT_NIET_LETTERLIJK", "LETTERLIJK_NIET_IN_BRON",
             "SAMENGESTELD_NIET_UIT_FRAGMENTEN")

_GEEN_BEGRIP = {"Tijdsaanduiding", "Parameter en parameterwaarde", "Operator"}
_REKEN = re.compile(r"\b(?:bedraagt|wordt berekend|berekend als|vermenigvuldigd|gedeeld door|vermeerderd met|"
                    r"verminderd met|percent|procent)\b|%|\d+\s*[x×*/+−-]\s*\d+", re.IGNORECASE)


def scheiding(fragment_teksten: list[str]) -> str:
    """Hoe een samengestelde definitie haar fragmenten verbindt; één plek, zodat de toets klopt."""
    return " … ".join(fragment_teksten)


def garanties(manifest: Manifest, kaart: Kaart, onderzoek: Onderzoek | None = None) -> list[str]:
    """Over de fragmentruimte manifest + onderzoek: een letterlijke definitie uit een contextbron mag."""
    fouten: list[str] = []
    alle = fragmenten.alle(manifest, onderzoek)
    teksten = {b.bron_iri: b.tekst for b in (*manifest.bronnen, *(onderzoek.bronnen if onderzoek else ()))}
    for f in kaart.fragmenten:
        bekend = alle.get(f.id)
        if bekend is None:
            fouten.append("FRAGMENT_ONBEKEND")
        elif bekend.tekst != f.tekst or teksten[f.bron_iri][f.start:f.eind] != f.tekst:
            fouten.append("FRAGMENT_NIET_LETTERLIJK")
    if kaart.herkomst is Herkomst.LETTERLIJK:
        if kaart.definitie_bron_iri not in teksten or kaart.definitie not in teksten[kaart.definitie_bron_iri]:
            fouten.append("LETTERLIJK_NIET_IN_BRON")
    if kaart.herkomst is Herkomst.SAMENGESTELD and kaart.definitie != scheiding([f.tekst for f in kaart.fragmenten]):
        fouten.append("SAMENGESTELD_NIET_UIT_FRAGMENTEN")
    return list(dict.fromkeys(fouten))


_RECHTSGEVOLG = re.compile(r"\bgrondslag\s+(?:voor|van)\b|\bin\s+rekening\s+(?:wordt\s+|worden\s+)?gebracht\b|"
                          r"\b(?:wordt|worden)\s+vergoed\b|\bdient\s+als\b[^.]{0,60}\bberekening\b|"
                          r"\bvoor\s+de\s+berekening\s+van\b", re.IGNORECASE)
_AFLEIDING = re.compile(r"\bop\s+nihil\s+gesteld\b|\btot\s+geen\s+hoger\s+bedrag\b|\bna\s+(?:de\s+)?verrekening\b|"
                        r"\bna\s+aftrek\s+van\b|\bverminderd\s+met\b|\bvermeerderd\s+met\b|\bhet\s+verschil\s+tussen\b",
                        re.IGNORECASE)


def _norm(t: str) -> str:
    return " ".join((t or "").lower().split())


def met_dossier(kaart: Kaart, dossier: Dossier | None) -> list[str]:
    """De signalen die het betekenisdossier mogelijk maakt (spoor M). Alleen over wat Lex voorstelt:
    een letterlijke definitie uit de wet krijgt hier niets."""
    uit: list[str] = []
    if dossier is None or not kaart.definitie:
        return uit
    if kaart.herkomst is not Herkomst.LETTERLIJK:
        woorden = inhoudswoorden(kaart.definitie)
        for p in dossier.met(betekenis.PARALLEL):
            if _norm(kaart.naam) == p.term and woorden & set(p.specifiek):
                uit.append("ALGEMENE_NAAM_SPECIFIEKE_DEFINITIE")
        if _RECHTSGEVOLG.search(kaart.definitie):
            uit.append("RECHTSGEVOLG_IN_DEFINITIE")
        if _AFLEIDING.search(kaart.definitie):
            uit.append("AFLEIDING_IN_DEFINITIE")
        voorkomens = max((len(b.bron_iris) for b in dossier.met(betekenis.VOORKOMENS)), default=0)
        if kaart.fragmenten and len({f.bron_iri for f in kaart.fragmenten}) == 1 and voorkomens >= 2:
            uit.append("ONDERBOUWING_EEN_VOORKOMEN")
        if kaart.herkomst is Herkomst.GEFORMULEERD and any(not (inhoudswoorden(f.tekst) & woorden)
                                                          for f in kaart.fragmenten):
            uit.append("FRAGMENT_ONDERSTEUNT_NIET")
    eigen_bron = kaart.definitie_bron_iri if kaart.herkomst is Herkomst.LETTERLIJK else ""
    tegen = [b for b in (*dossier.met(betekenis.DEFINITIE), *dossier.met(betekenis.SAMENGESTELD))
             if eigen_bron not in b.bron_iris and not {f.bron_iri for f in kaart.fragmenten} & set(b.bron_iris)]
    if tegen or any("buiten dat bereik" in b.detail for b in dossier.met(betekenis.DEFINITIE)):
        uit.append("TEGENBEWIJS_IN_ONDERZOEK")
    if (dossier.ontbrekend or not dossier.onderzoek_id) and kaart.herkomst is not Herkomst.LETTERLIJK:
        uit.append("CONTEXT_NIET_ONDERZOCHT")
    return list(dict.fromkeys(uit))


def signalen(kaart: Kaart, klassen: list[str], dossier: Dossier | None = None) -> list[str]:
    """Over wat Lex voorstelt, niet over de wet: een letterlijke definitie is wat de wet zegt, ook als
    die de naam herhaalt, en een term die de wet definieert is een begrip. Met een dossier komen de
    signalen van de context erbij (`met_dossier`)."""
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
    uit += [c for c in met_dossier(kaart, dossier) if c not in uit]
    return uit
