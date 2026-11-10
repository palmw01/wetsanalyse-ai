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

Sjabloon = Literal["begrip", "bepaling", "duiding", "annotaties", "extern"]


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
    #: De bronnode waar de markering op staat, uit de rij van de api: daarmee opent de werkplek de bepaling naast het
    #: gesprek. Leeg bij een groep uit het overzicht (die staat op meer bepalingen).
    bron_iri: str = ""


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


class ExterneVerwijzing(BaseModel):
    """Een stuk waar een passage naar verwijst (de `extref` van een voetnoot), met de vindplaats uit `bronmodel.extern`."""

    id: str
    label: str
    link: str = ""


class ExternePassage(BaseModel):
    nr: int
    tekst: str
    #: De kop van het deel waarin de passage staat, zoals de bron hem noemt.
    kop: str = ""
    #: `alinea`, `voetnoot`, `tabel` (de titel, met de kolomkoppen als `cellen`) of `tabelrij` (met `cellen`). Zo tekent
    #: de werkplek een tabel als tabel; de tekst blijft wat er letterlijk staat.
    soort: str = "alinea"
    cellen: list[str] | None = None
    #: Bij een voetnoot: de stukken waar hij naar verwijst.
    verwijst_naar: list[ExterneVerwijzing] | None = None
    #: Waar de passage staat binnen haar kop, zoals de bron nummert ("r.o. 2.1"); leeg als de bron niet nummert.
    plek: str = ""


class Extern(BaseModel):
    """Een bron naast de wet (ADR-013): letterlijke passages uit één stuk, met zijn eigen vindplaats en brontype. Geen
    wettekst: het blok staat in een antwoord ná de wettekst en onderbouwt nooit wat de wet zegt. Alles komt uit de rijen
    van de leestool van de connector; het model wees alleen het stuk en de passages aan. Eén blok per stuk."""

    soort: Literal["extern"] = "extern"
    door: Literal["bron"] = "bron"
    brontype: str
    id: str
    label: str
    link: str = ""
    #: Uit de connectorbeschrijving (`kop_in_antwoord`).
    kop: str
    passages: list[ExternePassage]
    #: De versie die Lex las (review ADR-013, punt 3): de hash van het gelezen document en de stand bij de bron
    #: (`dt.modified` bij KOOP). Leeg bij een ouder bericht. Zo blijft een passage herleidbaar, ook als de bron later
    #: een nieuwe versie publiceert.
    bron_hash: str = ""
    gewijzigd: str = ""
    #: Uit de metadata van het gelezen stuk (`ConnectorBeschrijving.metadata`): de datum van het stuk en zijn soort
    #: ("Motie"). Uit de bron, niet uit de tekst van het model; leeg bij een ouder bericht.
    datum: str = ""
    soort_stuk: str = ""


class Stuk(BaseModel):
    """Eén gevonden stuk in een lijst, met de metadata uit de zoektool van de connector (de sleutels van
    `bronmodel.connectors.METADATA_SLEUTELS`). Gevonden, niet gelezen: over de inhoud zegt de lijst niets."""

    id: str
    label: str
    link: str = ""
    soort: str = ""
    titel: str = ""
    datum: str = ""
    gepubliceerd: str = ""
    jaar: str = ""
    orgaan: str = ""
    indieners: list[str] = []
    reeks: list[str] = []
    status: str = ""
    versie: str = ""
    leesbaar: bool = True
    #: Waarom er geen tekst is, bij `leesbaar: false`: de tekst van de connector (`ConnectorBeschrijving.zonder_tekst`).
    zonder_tekst: str = ""


class Stukken(BaseModel):
    """Een lijst stukken uit een bron naast de wet (ADR-013), zoals de zoektool ze teruggaf: "de tien nieuwste
    Kamerstukken", "de stukken van dossier 33755". Het model wees de stukken aan; alles hier komt uit de zoekrijen, ook
    de volgorde. `zoekvraag` zegt in woorden wat er gezocht is en `totaal` hoeveel er bij de bron aan voldoen, zodat een
    lijst nooit volledig lijkt als hij dat niet is."""

    soort: Literal["stukken"] = "stukken"
    door: Literal["bron"] = "bron"
    brontype: str
    kop: str
    items: list[Stuk]
    zoekvraag: str = ""
    totaal: int | None = None


class Leemte(BaseModel):
    """Wat het hoofddeel van een sjabloon niet kon vinden: gezegd, niet opgevuld. Altijd "in de graaf",
    nooit "bestaat niet"."""

    soort: Literal["leemte"] = "leemte"
    door: Literal["bron"] = "bron"
    tekst: str


Blok = Annotated[
    Definities | Begrippen | Wettekst | Citaten | Verwijzingen | Annotaties | Toelichting | Twijfel | Extern | Stukken
    | Leemte,
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
#: Een lijst stukken komt helemaal uit de zoekrijen; haar ids zijn gevonden, niet gelezen, en dat is geen signaal.
NIET_GETOETST = frozenset({"annotaties", "begrippen", "leemte", "stukken"})


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
    if isinstance(b, Extern):
        regel = (f"[{b.label}]({b.link})" if b.link else b.label) + (
            f" ({', '.join(x for x in (b.soort_stuk, b.datum) if x)})" if b.soort_stuk or b.datum else "")
        return "\n\n".join(f'> "{p.tekst}"' + (f" ({p.plek})" if p.plek else "") for p in b.passages) + f"\n\n{regel}"
    if isinstance(b, Stukken):
        def regel(x: Stuk) -> str:
            naam = f"[{x.label}]({x.link})" if x.link else x.label
            wat = " · ".join(v for v in (x.soort, x.datum) if v)
            geen = f" ({x.zonder_tekst or 'geen tekst bij de bron'})" if not x.leesbaar else ""
            return f"- {naam}{' · ' + wat if wat else ''}{': ' + x.titel if x.titel else ''}{geen}"
        voet = " ".join(v for v in (
            b.zoekvraag, f"{len(b.items)} van de {getal(b.totaal)} stukken." if b.totaal and b.totaal > len(b.items) else "")
            if v)
        return "\n".join(regel(x) for x in b.items) + (f"\n\n{voet}" if voet else "")
    if isinstance(b, Leemte):
        return b.tekst
    return ""


KOPPEN = {"definities": "Wettelijke definitie", "begrippen": "Vastgelegd begrip", "wettekst": "Wettekst", "citaten": "Onderbouwing",
          "verwijzingen": "Verwijzingen", "annotaties": "Markeringen", "twijfel": "Twijfel en aannames"}


def getal(n: int) -> str:
    """Een aantal met een punt voor de duizendtallen ("19.523"), zoals de statusregels het schrijven."""
    return f"{n:,}".replace(",", ".")


def antwoord_tekst(antwoord: Antwoord, zonder: frozenset[str] = frozenset()) -> str:
    """De vaste Markdown van een antwoord. Dezelfde blokken geven dezelfde tekst."""
    delen: list[str] = []
    for b in antwoord.blokken:
        tekst = "" if b.soort in zonder else _blok_tekst(b)
        if not tekst:
            continue
        kop = b.kop if isinstance(b, (Toelichting, Extern, Stukken)) else KOPPEN.get(b.soort, "")
        delen.append(f"**{kop}**\n\n{tekst}" if kop else tekst)
    return "\n\n".join(delen)
