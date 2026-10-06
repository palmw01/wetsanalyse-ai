"""De uitleg bij een voorstel: waarom deze klasse, en waarom de alternatieven er staan.

Deterministisch en alleen uit wat de keten al weet – geen modeltekst. Twee teksten:

- **toelichting** in twee lagen: het *criterium* (de eerste zin van de omschrijving van de klasse,
  `jas_klassen.py`) en *hier*: waarop dit fragment berust, met de leesbare namen van de bewijscodes
  (`verklaringen.yaml`) en wie besliste.
- **reden per alternatief**: het bewijs van de detectoren die déze klasse aandroegen
  (`DetectieBijdrage`), aangevuld met de verwarringsreden uit het profiel van de klasse. Een vaste
  zin als "ook mogelijk volgens de detectie" zei de jurist niets.

Een bijdrage met meerdere bewijsstukken is gezamenlijke ondersteuning, geen één-op-één koppeling
(zie `DetectieBijdrage`); de reden noemt daarom de bewijzen van de bijdragen die de klasse aanboden.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..jas_klassen import JAS_KLASSEN
from .kandidaten import Candidate, DetectieBijdrage, Evidence
from .profielen import laad as profielen
from .verklaringen import naam as verklaring

# Administratief bewijs: zegt iets over de afhandeling, niet over waarom een klasse past.
# (`TEMPORAL_KERNEL` wél: "kern van een langere tijdsaanduiding" is precies de reden.)
_ADMINISTRATIEF = {"PRIORITY_APPLIED"}
_OMSCHRIJVING = {k.naam: k.omschrijving for k in JAS_KLASSEN}
_MAX_DETAIL = 40


def _criterium(klasse: str) -> str:
    """De eerste zin van de omschrijving van de klasse."""
    tekst = _OMSCHRIJVING.get(klasse, "").strip()
    eerste = tekst.split(". ")[0].rstrip(".")
    return f"{eerste}." if eerste else ""


def _bewijs(evidence: Iterable[Evidence]) -> list[str]:
    """Leesbare bewijsregels, ontdubbeld, in vaste volgorde: 'Naam ("detail")'."""
    uit: list[str] = []
    for e in evidence:
        if e.code in _ADMINISTRATIEF:
            continue
        detail = (e.detail or "").strip()
        # JSON-details (functiedetector) en lange details zijn geen leesbaar kopwoord.
        regel = verklaring("detectie", e.code)
        if detail and not detail.startswith("{") and len(detail) <= _MAX_DETAIL:
            regel += f' ("{detail}")'
        if regel not in uit:
            uit.append(regel)
    return uit


def _bijdragen_voor(klasse: str, bijdragen: Iterable[DetectieBijdrage]) -> list[Evidence]:
    return [e for b in bijdragen if klasse in b.mogelijke_klassen for e in b.bewijs]


def _verwarring(klasse: str, gekozen: str) -> str:
    """De reden uit het profiel waarom twee klassen verwisselbaar zijn, van beide kanten bekeken."""
    for van, naar in ((klasse, gekozen), (gekozen, klasse)):
        if not van or not naar:
            continue
        try:
            paren = profielen()[van].confusable_classes
        except KeyError:
            continue
        reden = next((c["reden"] for c in paren if c["klasse"] == naar), "")
        if reden:
            return reden
    return ""


def reden_alternatief(klasse: str, gekozen: str, bijdragen: Iterable[DetectieBijdrage]) -> str:
    """Waarom `klasse` ook in aanmerking kwam naast `gekozen` (leeg bij een terugval)."""
    bijdragen = list(bijdragen)
    delen = []
    bewijs = _bewijs(_bijdragen_voor(klasse, bijdragen))
    if bewijs:
        delen.append("aangedragen door " + "; ".join(bewijs))
    verwarring = _verwarring(klasse, gekozen)
    if verwarring:
        delen.append(verwarring)
    return " – ".join(delen) or "ook mogelijk volgens de detectie"


def toelichting(k: Candidate, klasse: str, door: str, bijdragen: Iterable[DetectieBijdrage] = ()) -> str:
    """Criterium + toepassing op dit fragment. Bij een terugval: welke klassen open liggen."""
    bijdragen = list(bijdragen)
    if not klasse:
        return "Nog geen klasse gekozen; mogelijk: " + ", ".join(k.possible_classes) + "."
    bewijs = _bewijs(_bijdragen_voor(klasse, bijdragen)) or _bewijs(k.evidence)
    wie = {
        "regel": "herkend aan een vast patroon",
        "specificiteit": "volgt uit de JAS-voorrangsregel",
        "model": "gekozen door het model uit " + ", ".join(k.possible_classes),
    }.get(door, "")
    hier = f'Hier: "{k.span.tekst}"'
    if bewijs:
        hier += " – " + "; ".join(bewijs)
    if wie:
        hier += f"; {wie}"
    return f"{_criterium(klasse)} {hier}.".strip()
