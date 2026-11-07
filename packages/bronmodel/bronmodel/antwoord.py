"""Het antwoord van Lex als sjabloon: het contract tussen agent, api en werkplek (ADR-008).

Een sjabloon is een tool waarmee de agent een beurt afrondt. De code vult de blokken uit wat de graaf
teruggaf; het model levert alleen wat `door: "lex"` draagt. De blokken zijn een gesloten lijst: de
werkplek heeft per soort één component, en een soort zonder component compileert daar niet.

`tekst` op het bericht blijft bestaan. Die maakt `antwoord_tekst` uit de blokken, en voedt de controle,
de historie, de kopieerknop en de eval.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

VERSIE = 1

Sjabloon = Literal["begrip", "bepaling", "duiding", "annotaties"]


class Vindplaats(BaseModel):
    """Waar iets staat, altijd uit de tool-rijen: nooit overgetypt door het model."""

    iri: str
    label: str
    jci: str = ""
    regeling: str = ""


class Definitie(BaseModel):
    term: str
    tekst: str
    vindplaats: Vindplaats
    #: Waar de definitie geldt ("Deze wet", "Dit artikel"), als de aanhef dat zegt.
    bereik: str = ""


class VastgelegdBegrip(BaseModel):
    """Een analyse-uitkomst met een status, geen wettelijke definitie en dus geen vindplaats."""

    id: str
    naam: str
    status: str
    definitie: str = ""
    werkgebied: str = ""
    werkgebied_id: str = ""
    herbeoordelen: bool = False


class Bepaling(BaseModel):
    tekst: str
    vindplaats: Vindplaats
    #: De bepaling staat al in de regeling maar geldt nog niet (`bwb:status`, van de code).
    nog_niet_in_werking: bool = False


class Citaat(BaseModel):
    tekst: str
    vindplaats: Vindplaats
    #: Waarom deze passage het antwoord draagt; van Lex.
    waarom: str = ""


class Markering(BaseModel):
    id: str
    klasse: str
    tekst: str
    vindplaats: str = ""


class Definities(BaseModel):
    soort: Literal["definities"] = "definities"
    door: Literal["bron"] = "bron"
    items: list[Definitie]


class Begrippen(BaseModel):
    soort: Literal["begrippen"] = "begrippen"
    door: Literal["bron"] = "bron"
    items: list[VastgelegdBegrip]


class Wettekst(BaseModel):
    soort: Literal["wettekst"] = "wettekst"
    door: Literal["bron"] = "bron"
    items: list[Bepaling]


class Citaten(BaseModel):
    soort: Literal["citaten"] = "citaten"
    door: Literal["bron"] = "bron"
    items: list[Citaat]


class Verwijzingen(BaseModel):
    soort: Literal["verwijzingen"] = "verwijzingen"
    door: Literal["bron"] = "bron"
    items: list[Vindplaats]


class Annotaties(BaseModel):
    soort: Literal["annotaties"] = "annotaties"
    door: Literal["bron"] = "bron"
    items: list[Markering]
    totaal: int
    volledig: bool = True


class Toelichting(BaseModel):
    soort: Literal["toelichting"] = "toelichting"
    door: Literal["lex"] = "lex"
    kop: str = "Toelichting van Lex"
    tekst: str


class Twijfel(BaseModel):
    soort: Literal["twijfel"] = "twijfel"
    door: Literal["lex"] = "lex"
    punten: list[str]


class Leemte(BaseModel):
    """Wat het hoofddeel van een sjabloon niet kon vinden: gezegd, niet opgevuld. Altijd "in de graaf",
    nooit "bestaat niet"."""

    soort: Literal["leemte"] = "leemte"
    door: Literal["bron"] = "bron"
    tekst: str


Blok = Annotated[
    Definities | Begrippen | Wettekst | Citaten | Verwijzingen | Annotaties | Toelichting | Twijfel | Leemte,
    Field(discriminator="soort"),
]


class Antwoord(BaseModel):
    sjabloon: Sjabloon
    versie: int = VERSIE
    blokken: list[Blok]
    #: De bepalingen waar het antwoord over gaat, door de code afgeleid: de doelen van de graaf.
    doelen: list[Vindplaats] = []


#: Een onvolledig resultaat blijft ook in de tekst zichtbaar: die voedt de historie, *Kopieer* en de eval.
NOG_NIET_TEKST = " (nog niet in werking getreden)"
NIET_ALLES = "Dit zijn niet alle markeringen; ontbrekende treffers zijn niet uitgesloten."

#: Wat de brongetrouwheidscontrole niet leest. Annotaties en begrippen zijn afgeleide duiding die niet als bron telt, en
#: een leemte is tekst van de code: alle drie komen niet van het model, en hun BWB-id's of citaten staan niet in de bron.
NIET_GETOETST = frozenset({"annotaties", "begrippen", "leemte"})


def _vindplaats_regel(v: Vindplaats) -> str:
    return f"{v.label}, {v.regeling}" if v.regeling else v.label


def _blok_tekst(b: BaseModel) -> str:
    if isinstance(b, Definities):
        return "\n\n".join(
            f'> "{d.tekst}"\n\n**Vindplaats:** {_vindplaats_regel(d.vindplaats)}' + (f" (geldt voor: {d.bereik})" if d.bereik else "")
            for d in b.items)
    if isinstance(b, Begrippen):
        return "\n".join(
            f"- **{x.naam}** ({x.status}{', ' + x.werkgebied if x.werkgebied else ''})" + (f": {x.definitie}" if x.definitie else "")
            for x in b.items)
    if isinstance(b, Wettekst):
        return "\n\n".join(f"**{_vindplaats_regel(x.vindplaats)}**{NOG_NIET_TEKST if x.nog_niet_in_werking else ''}\n\n{x.tekst}"
                           for x in b.items)
    if isinstance(b, Citaten):
        return "\n\n".join(
            f'> "{c.tekst}"\n\n{_vindplaats_regel(c.vindplaats)}' + (f"\n\n{c.waarom}" if c.waarom else "")
            for c in b.items)
    if isinstance(b, Verwijzingen):
        return "\n".join(f"- {_vindplaats_regel(v)}" for v in b.items)
    if isinstance(b, Annotaties):
        rijen = "\n".join(f"- {m.klasse}: {m.tekst}" + (f" ({m.vindplaats})" if m.vindplaats else "") for m in b.items)
        return rijen if b.volledig else f"{rijen}\n\n{NIET_ALLES}"
    if isinstance(b, Toelichting):
        return b.tekst
    if isinstance(b, Twijfel):
        return "\n".join(f"- {p}" for p in b.punten)
    if isinstance(b, Leemte):
        return b.tekst
    return ""


KOPPEN = {"definities": "Wettelijke definitie", "begrippen": "Vastgelegd begrip", "wettekst": "Wettekst", "citaten": "Onderbouwing",
          "verwijzingen": "Verwijzingen", "annotaties": "Markeringen", "twijfel": "Twijfel en aannames"}


def antwoord_tekst(antwoord: Antwoord, zonder: frozenset[str] = frozenset()) -> str:
    """De vaste Markdown van een antwoord. Dezelfde blokken geven dezelfde tekst."""
    delen: list[str] = []
    for b in antwoord.blokken:
        tekst = "" if b.soort in zonder else _blok_tekst(b)
        if not tekst:
            continue
        kop = b.kop if isinstance(b, Toelichting) else KOPPEN.get(b.soort, "")
        delen.append(f"**{kop}**\n\n{tekst}" if kop else tekst)
    return "\n\n".join(delen)
