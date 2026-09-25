"""Anker- en tekstbasis voor annotaties: positie, hash, letterlijkheid en de ontdubbelsleutel.

Wat hier staat, gebruiken de annotatieketen (`jas_pipeline.keten`: het corpusanker), de grounding
van het antwoordpad (`komt_letterlijk_voor`), de beurt-driver (`sleutel_van`) en de statusregels
(`aanduiding_in_woorden`). De generatieve annotatieroute die hier ook woonde (parsen van model-JSON,
de Critic-patcher, lokaliseren van vrije fragmenten) is weggehaald met ADR-001 PR 18: de grens van
een markering komt sindsdien uit een detector, niet uit tekst die een model teruggeeft.
"""
from __future__ import annotations

import re

from .models import Anker

_WS = re.compile(r"\s+")

# De offsets slaan op de *originele* brontekst (vóór normalisatie), zodat de UI exact het juiste
# teken kan markeren. De hash is FNV-1a 32-bit – identiek aan `bronHash()` in
# `frontend/lib/selectie.ts`, zodat de UI kan detecteren of de brontekst verschoven is na een
# herimport.
_CONTEXT_LENGTE = 48   # tekens context vóór/na het fragment – gelijk aan frontend CONTEXT_LENGTE
_FNV_PRIME = 0x01000193
_FNV_OFFSET = 0x811C9DC5

def _fnv1a_32(tekst: str) -> str:
    """FNV-1a 32-bit hash als hex-string. Identiek aan bronHash() in selectie.ts."""
    h = _FNV_OFFSET
    for ch in tekst:
        for byte in ch.encode("utf-8"):
            h ^= byte
            h = (h * _FNV_PRIME) & 0xFFFFFFFF
    return format(h, "08x")


def _maak_anker(corpus: str, start: int, eind: int, lid: str = "") -> Anker:
    """Bouw het Anker voor een fragment op positie [start, eind) in `corpus`.

    De offsets zijn op de originele (niet-genormaliseerde) brontekst. De context
    (voor/na) bewaart 48 tekens zodat de UI het juiste voorkomen van een herhaald
    fragment kan kiezen als de offsets na een herimport zijn verschoven.
    """
    return Anker(
        lid=lid,
        start=start,
        eind=eind,
        voor=corpus[max(0, start - _CONTEXT_LENGTE): start],
        na=corpus[eind: eind + _CONTEXT_LENGTE],
        bron_hash=_fnv1a_32(corpus),
    )


def _normaliseer(s: str) -> str:
    """Collapse witruimte, zodat een fragment ondanks layout-verschillen matcht."""
    return _WS.sub(" ", s or "").strip()


def komt_letterlijk_voor(corpus: str, fragment: str) -> bool:
    """Staat dit fragment letterlijk in de opgehaalde tekst?

    Witruimte-ongevoelig, met dezelfde normalisatie als `sleutel_van`. De eval gebruikt deze eis om
    te toetsen dat elke markering in de opgehaalde bepaling staat.
    """
    norm = _normaliseer(fragment)
    return bool(norm) and _normaliseer(corpus).find(norm) >= 0


def sleutel_van(tekst: str, lid: str) -> tuple[str, str]:
    """Identiteit van een markering los van zijn id: fragment + lid.

    Twee elementen met dezelfde sleutel zijn dezelfde markering, ook al dragen ze een ander id. Dat
    gebeurt als een herziening een bestaand fragment opnieuw voorstelt zonder het id mee te sturen —
    en dan krijgt de jurist twee identieke kaartjes te reviewen.

    **Bewust ZONDER klasse**, gelijk aan de terugval in de api-merge (`routers/annotatie.py:_sleutel`)
    en aan `mergeVoorstellen` in de werkplek: een herziening mág juist de klasse veranderen en moet
    dan hetzelfde element treffen. Stond de klasse er wél in, dan werd een herclassificatie zonder
    id een tweede element – en zag de jurist dezelfde tekstspan twee keer met tegenstrijdige
    klassen. Dit is de canonieke regel; wie hem elders nabouwt, bouwt hem hiernaar.
    """
    return (_normaliseer(tekst).lower(), (lid or "").strip())


def aanduiding_in_woorden(aanduiding: str, lid: str = "", soort: str = "") -> str:
    """"art. 9 lid 1" of "bepaling 25.1" – hoe je deze vindplaats in proza noemt.

    Een `Divisie` van een beleidsregel is geen artikel en heeft geen leden: "art. 25.1 lid 2" is een
    vindplaats die niet bestaat. De Leidraad labelt haar top-divisies zelf wél "Artikel 25", maar de
    subdivisies eronder niet, en "bepaling" dekt beide zonder iets te beweren wat niet klopt. Het is
    ook de term die de code al gebruikt (`get_bepaling`, `_bepaling_fallback`, `OngeldigeVindplaats`).

    Onbekend soort valt terug op "art.": dat is wat er stond, en bij de zes wet-achtige regelingen –
    veruit het meeste verkeer – is het gewoon juist.
    """
    nummer = str(aanduiding).strip()
    scope = str(lid or "").strip()
    if soort == "Divisie":
        return f"bepaling {nummer}" + (f", {scope}" if scope else "")
    return f"art. {nummer}" + (f" lid {scope}" if scope else "")

