"""Door het model van één toestand lopen: de artikelen met hun plek, en elke node die tekst draagt.

De importer (`collect`) en de connector `wetgeving_live` lezen dezelfde boom. `tekstdragers` volgt precies de nodes
waarvoor `collect` een `tekst` schrijft (artikel, lid, onderdeel, divisie, bijlage), zodat `model_tekens` gelijk is
aan wat de importer als `bwb:tekst` in de graaf zet; `tools/bwb-import/tests/test_boom.py` bewaakt dat.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .models import Artikel, Bijlage, Divisie, Lid, Onderdeel, Structuurdeel, Wet

Tekstdrager = Artikel | Lid | Onderdeel | Divisie | Bijlage


@dataclass(frozen=True)
class Plek:
    """Waar een artikel staat: de structuurdelen erboven (hoofdstuk › afdeling › …), of de divisie of bijlage."""

    structuur: tuple[Structuurdeel, ...] = ()
    divisie: Divisie | None = None
    bijlage: Bijlage | None = None

    def koppen(self) -> tuple[str, ...]:
        """De koppen boven het artikel, van boven naar beneden: "Hoofdstuk 3 – Algemene bijstand"."""
        uit = []
        if self.bijlage is not None:
            uit.append(_kop(_met_nummer(self.bijlage.label, self.bijlage.nummer), self.bijlage.titel))
        uit.extend(_kop(_met_nummer(s.label, s.nummer), s.titel) for s in self.structuur)
        if self.divisie is not None:
            uit.append(_kop(_met_nummer(self.divisie.label, self.divisie.nummer), self.divisie.titel))
        return tuple(k for k in uit if k)


def _met_nummer(label: str | None, nummer: str | None) -> str:
    """"Hoofdstuk" + "1" → "Hoofdstuk 1"; een label dat het nummer al draagt ("Artikel 9.4") blijft."""
    label, nummer = (label or "").strip(), (nummer or "").strip().rstrip(".")
    if not nummer or nummer in label.split():
        return label
    return f"{label} {nummer}".strip()


def _kop(label: str | None, titel: str | None) -> str:
    label, titel = (label or "").strip(), (titel or "").strip()
    return f"{label} – {titel}" if label and titel and titel != label else (label or titel)


def _in_structuur(delen: list[Structuurdeel], pad: tuple[Structuurdeel, ...], bijlage: Bijlage | None,
                  ) -> Iterator[tuple[Plek, Artikel]]:
    for deel in delen:
        hier = (*pad, deel)
        for artikel in deel.artikelen:
            yield Plek(hier, bijlage=bijlage), artikel
        yield from _in_structuur(deel.subdelen, hier, bijlage)


def _in_divisie(divisie: Divisie) -> Iterator[tuple[Plek, Artikel]]:
    for artikel in divisie.artikelen:
        yield Plek(divisie=divisie), artikel
    for sub in divisie.subdivisies:
        yield from _in_divisie(sub)


def artikelen(wet: Wet) -> Iterator[tuple[Plek, Artikel]]:
    """Elk artikel van de toestand, in documentvolgorde, met zijn plek. Bijlagen komen na de wettekst."""
    yield from _in_structuur(wet.structuurdelen, (), None)
    for artikel in wet.losse_artikelen:
        yield Plek(), artikel
    for divisie in wet.divisies:
        yield from _in_divisie(divisie)
    for bijlage in wet.bijlagen:
        for artikel in bijlage.artikelen:
            yield Plek(bijlage=bijlage), artikel
        yield from _in_structuur(bijlage.structuurdelen, (), bijlage)


def divisies(wet: Wet) -> Iterator[Divisie]:
    """Elke divisie (beleidsregels, circulaires), ook de geneste, in documentvolgorde."""
    def loop(d: Divisie) -> Iterator[Divisie]:
        yield d
        for sub in d.subdivisies:
            yield from loop(sub)
    for d in wet.divisies:
        yield from loop(d)


def onderdelen(lijst: list[Onderdeel]) -> Iterator[Onderdeel]:
    """De onderdelen met hun subonderdelen, in documentvolgorde."""
    for o in lijst:
        yield o
        yield from onderdelen(o.subonderdelen)


def _van_artikel(artikel: Artikel) -> Iterator[Tekstdrager]:
    yield artikel
    for lid in artikel.leden:
        yield lid
        yield from onderdelen(lid.onderdelen)
    yield from onderdelen(artikel.onderdelen)


def tekstdragers(wet: Wet) -> Iterator[Tekstdrager]:
    """Elke node waarvoor de importer een `tekst` schrijft. Lege tekst telt mee als drager, niet als tekens."""
    for _, artikel in artikelen(wet):
        yield from _van_artikel(artikel)
    for divisie in divisies(wet):
        yield divisie
        yield from onderdelen(divisie.onderdelen)
    for bijlage in wet.bijlagen:
        yield bijlage
        yield from onderdelen(bijlage.onderdelen)


def model_tekens(wet: Wet) -> int:
    """De tekens die de importer van deze toestand als `bwb:tekst` zou schrijven: de graafkant van de dekking."""
    return sum(len(d.tekst or "") for d in tekstdragers(wet))


def model_tekens_van(artikel: Artikel) -> int:
    """De modeltekens van één artikel met zijn leden en onderdelen: de graafkant van de dekking per artikel."""
    return sum(len(d.tekst or "") for d in _van_artikel(artikel))
