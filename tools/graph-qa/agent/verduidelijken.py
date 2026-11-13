"""Doorvragen in plaats van gokken (R3): een vervolgvraag die een open keuzevraag van Lex niet beantwoordt.

Op acceptatie (7 nov 2026) vroeg Lex "Bedoel je artikel 3:1, 3:2, of een ander artikel?". Op "En het tweede lid?" koos hij
daarna zelf 3:1, "want dat was het onderwerp van de vorige beurt", wat niet klopte. Staat er zo'n keuzevraag open, en
verwijst de nieuwe vraag terug (een lid, "daarvan") zonder zelf een artikel te noemen, dan beslist de code: Lex vraagt
opnieuw welk artikel, zonder model en zonder te gokken. Noemt de vraag wel een artikel, dan is de keuze gemaakt.
"""
from __future__ import annotations

import re

from bronmodel.taal import RANGTELWOORDEN

from .aanwijzing import lees_aanwijzing

_KEUZE = re.compile(r"\b(?:bedoel\s+je|welk(?:e)?\s+(?:artikel|regeling|wet|lid|bepaling|onderdeel))\b", re.IGNORECASE)
_ZIN = re.compile(r"[^.!?\n]*\?")
_TERUG = re.compile(rf"\b(?:lid|leden|onderdeel|onderdelen|daarvan|daarin|dat\s+artikel|die\s+bepaling|hetzelfde)\b"
                    rf"|\b(?:{'|'.join(RANGTELWOORDEN[:20])})\s+lid\b", re.IGNORECASE)


def _slotvragen(antwoord: str) -> list[str]:
    """De vragen waarmee het antwoord eindigt: de aaneengesloten reeks vraagzinnen aan het eind, in volgorde. Een vraag
    midden in het antwoord, met een gewone zin erna, hoort er niet bij."""
    tekst = (antwoord or "").rstrip().rstrip("*_` ")
    uit: list[str] = []
    eind = len(tekst)
    for m in reversed(list(_ZIN.finditer(tekst))):
        if tekst[m.end():eind].strip(" \n*_`"):
            break
        uit.append(m.group(0).strip(" \n*_`"))
        eind = m.start()
    return uit[::-1]


def open_keuzevraag(antwoord: str) -> str:
    """De keuzevraag waarmee het antwoord eindigt ("Bedoel je …?"), anders leeg.

    Meestal is dat de laatste zin. Soms zet het model de mogelijkheden in een losse slotvraag erachter ("Bedoel je een
    specifiek artikel? Bijvoorbeeld artikel 3:1, 3:2 of een ander artikel?"): dan is de laatste zin geen keuzevraag meer,
    en ging een vervolg ("En het tweede lid?") naar het model, dat er zelf een artikel bij koos (ronde 2 van de meting
    van ADR-016, 12 nov 2026). Daarom telt de hele reeks vragen aan het eind, vanaf de eerste die een keuze voorlegt."""
    vragen = _slotvragen(antwoord)
    eerste = next((i for i, v in enumerate(vragen) if _KEUZE.search(v)), None)
    return " ".join(vragen[eerste:]) if eerste is not None else ""


def doorvraag(vraag: str, vorig_antwoord: str) -> str:
    """De tekst waarmee Lex opnieuw vraagt, of leeg als de vraag de keuze maakt of er niet naar verwijst."""
    keuze = open_keuzevraag(vorig_antwoord)
    if not keuze or lees_aanwijzing(vraag).artikelen or not _TERUG.search(vraag or ""):
        return ""
    # De eigen keuzevraag alleen als die opties noemt ("3:1, 3:2 …"); anders stond het verzoek er twee keer.
    opties = f" {keuze}" if re.search(r"\d", keuze) else ""
    return (f"Ik weet nog niet welk artikel je bedoelt, dus ik kies er niet zelf een.{opties} "
            "Noem het artikel, dan zoek ik het lid erbij op.")
