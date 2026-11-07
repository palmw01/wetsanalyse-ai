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


def open_keuzevraag(antwoord: str) -> str:
    """De laatste vraag in het antwoord als Lex daarin een keuze voorlegt ("Bedoel je …?"), anders leeg."""
    vragen = _ZIN.findall(antwoord or "")
    laatste = vragen[-1].strip() if vragen else ""
    return laatste if _KEUZE.search(laatste) else ""


def doorvraag(vraag: str, vorig_antwoord: str) -> str:
    """De tekst waarmee Lex opnieuw vraagt, of leeg als de vraag de keuze maakt of er niet naar verwijst."""
    keuze = open_keuzevraag(vorig_antwoord)
    if not keuze or lees_aanwijzing(vraag).artikelen or not _TERUG.search(vraag or ""):
        return ""
    # De eigen keuzevraag alleen als die opties noemt ("3:1, 3:2 …"); anders stond het verzoek er twee keer.
    opties = f" {keuze}" if re.search(r"\d", keuze) else ""
    return (f"Ik weet nog niet welk artikel je bedoelt, dus ik kies er niet zelf een.{opties} "
            "Noem het artikel, dan zoek ik het lid erbij op.")
