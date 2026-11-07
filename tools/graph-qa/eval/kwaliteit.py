"""Deterministische kwaliteitsscorers op de antwoordtekst: volgorde, sjabloon en toon.

- `volgorde_ok`: de tekstfragmenten uit de case staan in die volgorde in het antwoord. Vangt bijvoorbeeld dat een
  slotzin van een lid vóór de onderdelen staat waar hij op slaat.
- `sjabloon_ok`: het antwoord-event gebruikte het verwachte sjabloon (`bepaling`, `begrip`, `duiding`, …).
- `toon`: de afspraken uit `docs/schrijfrichtlijn-lex.md` die in code te toetsen zijn – geen emoji, geen
  Markdown-koppen, geen u-vorm, geen interne termen of IRI's, en het aandeel zinnen boven de B1-grens. Een
  aparte maat, geen slaagcriterium: hij telt overtredingen, het oordeel blijft bij wie het rapport leest.

De toon gaat over de *lopende tekst*: wat Lex zelf schrijft. Een citaat of de wettekst in een bepalingsantwoord
is brontekst; die hoort niet op B1 of op de je-vorm getoetst te worden. Met een antwoord-event zijn dat de
blokken die van Lex zijn; zonder (een vrij antwoord) de tekst zonder citaatregels en aanhalingen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent.begrippen_pipeline.begrip_b1 import MAX_WOORDEN


def _norm(tekst: str) -> str:
    return " ".join((tekst or "").split()).lower()


def volgorde_ok(tekst: str, fragmenten: list[str] | None) -> bool:
    """Staan de fragmenten in deze volgorde in de tekst (hoofdletter- en witruimteongevoelig)?"""
    laag, plek = _norm(tekst), 0
    for f in fragmenten or []:
        i = laag.find(_norm(f), plek)
        if i < 0:
            return False
        plek = i + len(_norm(f))
    return True


def sjabloon_ok(antwoord: dict[str, Any] | None, verwacht: str | None) -> bool:
    return not verwacht or (antwoord or {}).get("sjabloon") == verwacht


# --- toon ------------------------------------------------------------------------------------------

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]|(?<!\\w)[:;]-?[()DPp](?!\\w)")
_KOP = re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE)
# "u" als onderdeelletter ("onderdeel u.") is geen aanspreekvorm.
_U_VORM = re.compile(r"(?<![\w-])(?:u|uw)(?![\w.)-])", re.IGNORECASE)
_INTERN = re.compile(
    r"urn:bwb:|\b(?:bron_iri|human_approved|lifecycle|laagstatus|in_review|subtree|worker)\b"
    r"|\b[a-z]+(?:_[a-z]+)+\(", re.IGNORECASE)
_CITAAT = re.compile(r"^\s*>.*$", re.MULTILINE)
_AANHALING = re.compile(r"\"[^\"\n]*\"|„[^”\n]*”|“[^”\n]*”")
_ZINSGRENS = re.compile(r"(?<=[.!?])\s+|\n+")
_WOORD = re.compile(r"[\wÀ-ÿ][\wÀ-ÿ'-]*")
_LIJSTTEKEN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")


def lopende_tekst(tekst: str, antwoord: dict[str, Any] | None = None) -> str:
    """Wat Lex zelf schreef: zonder wettekst, citaten en definities."""
    if antwoord:
        delen: list[str] = []
        for b in antwoord.get("blokken") or []:
            soort = b.get("soort")
            if soort in ("toelichting", "leemte"):
                delen.append(b.get("tekst") or "")
            elif soort == "twijfel":
                delen.extend(b.get("punten") or [])
            elif soort == "citaten":
                delen.extend(c.get("waarom") or "" for c in b.get("items") or [])
        return "\n\n".join(d for d in delen if d)
    return _AANHALING.sub("", _CITAAT.sub("", tekst or ""))


def zinnen(tekst: str) -> list[str]:
    """Een simpele zinsplitsing (geen parser): op zinseinde en regelovergang, zonder lijsttekens."""
    uit = (_LIJSTTEKEN.sub("", z).strip() for z in _ZINSGRENS.split(tekst or ""))
    return [z for z in uit if _WOORD.search(z)]


@dataclass
class Toon:
    overtredingen: list[str] = field(default_factory=list)
    lange_zinnen: float = 0.0          # aandeel zinnen met meer dan MAX_WOORDEN woorden

    @property
    def aantal(self) -> int:
        return len(self.overtredingen)


def toon(tekst: str, antwoord: dict[str, Any] | None = None) -> Toon:
    lopend = lopende_tekst(tekst, antwoord)
    uit: list[str] = []
    if m := _EMOJI.search(lopend):
        uit.append(f"emoji {m.group(0)!r}")
    if _KOP.search(lopend):
        uit.append("Markdown-kop")
    if m := _U_VORM.search(lopend):
        uit.append(f"u-vorm {m.group(0)!r}")
    uit.extend(f"intern {t!r}" for t in dict.fromkeys(m.group(0) for m in _INTERN.finditer(lopend)))
    zz = zinnen(lopend)
    lang = sum(len(_WOORD.findall(z)) > MAX_WOORDEN for z in zz)
    return Toon(uit, lang / len(zz) if zz else 0.0)
