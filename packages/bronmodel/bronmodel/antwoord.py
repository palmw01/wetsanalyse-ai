"""Het antwoord van Lex als sjabloon: het contract tussen agent, api en werkplek (ADR-008).

Een sjabloon is een tool waarmee de agent een beurt afrondt. De code vult de blokken uit wat de graaf
teruggaf; het model levert alleen wat `door: "lex"` draagt. De blokken zijn een gesloten lijst: de
werkplek heeft per soort één component, en een soort zonder component compileert daar niet.

`tekst` op het bericht blijft bestaan. Die maakt `antwoord_tekst` uit de blokken, en voedt de controle,
de historie, de kopieerknop en de eval.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from .contenttoets import OORDEEL_LABEL, Oordeel, criterium_tekst, telling_tekst as _toets_telling
from .definities import geldt_voor

VERSIE = 1

Sjabloon = Literal["begrip", "bepaling", "duiding", "annotaties", "extern", "rapport", "regels", "contenttoets"]


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
    #: Waar de definitie geldt ("Deze wet", "Dit artikel"), als de aanhef dat zegt: de formule zelf.
    bereik: str = ""
    #: Dezelfde formule als soort (`definities.Geldigheid`): "regeling", "artikel", "artikel_n", "lid" of "structuur",
    #: met het artikelnummer of het woord als `bereik_waarde`. Daarmee zegt het antwoord het in woorden (`geldt_voor`).
    bereik_soort: str = ""
    bereik_waarde: str = ""
    #: De begrippen die deze definitie zelf gebruikt en die in dezelfde bepaling gedefinieerd zijn ("belastingaanslag" in
    #: de definitie van "belastingschuldige"): de jurist leest de definitie pas goed met die erbij.
    gebruikt: list["Definitie"] = Field(default_factory=list)


class VastgelegdBegrip(BaseModel):
    """Een analyse-uitkomst met een status, geen wettelijke definitie en dus geen vindplaats."""

    id: str
    naam: str
    status: str
    definitie: str = ""
    werkgebied: str = ""
    werkgebied_id: str = ""
    herbeoordelen: bool = False
    #: Een generiek begrip staat boven de werkgebieden (ADR-006): geen werkgebied, wel dit kenmerk.
    generiek: bool = False


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


class RegelVerwijzing(BaseModel):
    id: str
    naam: str = ""


class RegelDrager(BaseModel):
    """Waarop een regel rust: de rol, het geval, de passage van de markering en de bronnode met de weg naar de wettekst."""
    element_id: str = ""
    rol: str
    geval: str = ""
    beoordeling: str = ""
    passage: str = ""
    vindplaats: str = ""
    bron_iri: str = ""
    jci: str = ""


class VastgelegdeRegel(BaseModel):
    """Een afleidingsregel (ADR-018), uit de api: een analyse-uitkomst met een status, geen wettekst. `gelezen`: de regel
    zelf is gelezen (`get_regel`), dus de gevallen en dragers staan erbij; anders alleen de rij uit de zoektool."""
    id: str
    werkgebied_id: str = ""
    werkgebied: str = ""
    naam: str
    uitvoer: str = ""
    status: str
    soort: str = ""
    gevallen: list[dict[str, str]] = Field(default_factory=list)       # [{label, tekst}], de afgeleide regeltekst
    dragers: list[RegelDrager] = Field(default_factory=list)
    open_punten: int = 0
    vervangen_door: RegelVerwijzing | None = None
    vervangt: list[RegelVerwijzing] = Field(default_factory=list)
    gelezen: bool = False


class Definities(BaseModel):
    soort: Literal["definities"] = "definities"
    door: Literal["bron"] = "bron"
    items: list[Definitie]


class Begrippen(BaseModel):
    soort: Literal["begrippen"] = "begrippen"
    door: Literal["bron"] = "bron"
    items: list[VastgelegdBegrip]


class Regels(BaseModel):
    soort: Literal["regels"] = "regels"
    door: Literal["bron"] = "bron"
    items: list[VastgelegdeRegel]


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
    #: Wat Lex over dit stuk zegt, in eigen woorden (`antwoord_extern`, veld `kern` per aanwijzing; plan centrale agent na
    #: A6, PR A). Leeg bij een stuk dat alleen aangewezen is, en bij een ouder bericht. Zonder dit veld schreef het model
    #: de samenvatting per stuk naast het sjabloon, en die ging verloren (S01), of perste het vier stukken in het korte
    #: antwoord (P01).
    kern: str = ""
    passages: list[ExternePassage]
    #: De versie die Lex las (review ADR-013, punt 3): de hash van het gelezen document en de stand bij de bron
    #: (`dt.modified` bij KOOP). Leeg bij een ouder bericht. Zo blijft een passage herleidbaar, ook als de bron later
    #: een nieuwe versie publiceert.
    bron_hash: str = ""
    gewijzigd: str = ""
    #: Uit de metadata van het gelezen stuk (`ConnectorBeschrijving.metadata`): de datum van het stuk en zijn soort
    #: ("Motie"). Uit de bron, niet uit de tekst van het model; leeg bij een ouder bericht.
    datum: str = ""
    soort_stuk: SoortNaam = ""
    #: Bij welke tekst van de bepaling het stuk hoort, uit de zoekrij (zie `Stuk`); leeg als het stuk niet gezocht is.
    tekst_vanaf: str = ""
    tekst_tot: str = ""
    tekststand: str = ""
    op_peildatum: bool | None = None
    #: Wat de bron is tegenover de wet, uit de code (`ConnectorBeschrijving.status_regel`, met de datum van het stuk):
    #: "Beleid van de Belastingdienst, bindend voor de inspecteur; geen wet en geen rechtspraak. Stand op 12 november
    #: 2026." Leeg bij een bron zonder regel en bij een ouder bericht.
    status_regel: str = ""
    #: De stand van het stuk bij de bron (`METADATA_SLEUTELS["status"]`): bij een kennisgroepstandpunt "geldend",
    #: "ingetrokken" of "vervallen", met de standpunten die het introkken. De werkplek meldt een ingetrokken standpunt.
    status: str = ""
    vervangen_door: list[str] = []


#: Afkortingen in een soortnaam van de bron, voluit: "Nota n.a.v. het verslag" leest als zin.
_AFKORTINGEN = (("n.a.v.", "naar aanleiding van"), ("t.b.v.", "ten behoeve van"), ("i.v.m.", "in verband met"),
                ("m.b.t.", "met betrekking tot"))
#: Een opsomming van varianten tussen haakjes: "(nader/tweede nader/enz.)".
_VARIANTEN = re.compile(r"(?<!\s)\s*+\([^()/]*+/[^()]*+\)")


def soort_netjes(soort: str) -> str:
    """Een soortnaam zoals de bron hem geeft, leesbaar voor de jurist en voor elke connector gelijk: zonder de opsomming
    van varianten tussen haakjes, afkortingen voluit, en een naam in hoofdletters ("JAARVERSLAG") met één hoofdletter.
    Acceptatie 24 nov 2026: "Nota n.a.v. het (nader/tweede nader/enz.) verslag" stond zo in de lijst. Alleen de weergave:
    het filter van de zoektool krijgt de naam van de bron (`ConnectorBeschrijving.soorten`)."""
    s = _VARIANTEN.sub("", soort or "")
    for kort, voluit in _AFKORTINGEN:
        s = re.sub(rf"(?<!\w){re.escape(kort)}", voluit, s, flags=re.IGNORECASE)
    s = " ".join(s.split())
    if len(s) > 3 and s.isupper():
        s = s.capitalize()
    return s[:1].upper() + s[1:]


SoortNaam = Annotated[str, AfterValidator(soort_netjes)]


class Stuk(BaseModel):
    """Eén gevonden stuk in een lijst, met de metadata uit de zoektool van de connector (de sleutels van
    `bronmodel.connectors.METADATA_SLEUTELS`). Gevonden, niet gelezen: over de inhoud zegt de lijst niets."""

    id: str
    label: str
    link: str = ""
    soort: SoortNaam = ""
    titel: str = ""
    datum: str = ""
    gepubliceerd: str = ""
    jaar: str = ""
    orgaan: str = ""
    indieners: list[str] = []
    reeks: list[str] = []
    #: De dossiers die samen zijn behandeld (`METADATA_SLEUTELS["gezamenlijk"]`). Los van `reeks`, want dat is per connector
    #: iets anders: bij wetgeving buiten de kennisgraaf de plek in de regeling (wetgeving_live ronde 3, I13/I14).
    gezamenlijk: list[str] = []
    status: str = ""
    versie: str = ""
    #: Bij welke tekst van de bepaling het stuk hoort (een uitspraak bij een eerdere versie van het artikel), uit de bron:
    #: `tekststand` is "huidige tekst", "eerdere tekst" of "onbekend" tegenover de tekst in de graaf.
    tekst_vanaf: str = ""
    tekst_tot: str = ""
    tekststand: str = ""
    #: Of die tekst gold op de peildatum (alleen als er een peildatum is meegegeven).
    op_peildatum: bool | None = None
    leesbaar: bool = True
    #: Waarom er geen tekst is, bij `leesbaar: false`: de tekst van de connector (`ConnectorBeschrijving.zonder_tekst`).
    zonder_tekst: str = ""


class TelPost(BaseModel):
    """Eén post van een verdeling: een waarde ("Hoge Raad") en hoeveel stukken de bron daar telt."""

    waarde: str
    aantal: int


class Telling(BaseModel):
    """Het antwoord op een telvraag ("hoeveel …", "hoe verdelen … zich over de instanties"): het aantal dat de bron zelf
    telt, nooit een schatting van het model of een telling van één pagina. `dekking` zegt of de bron alles telt
    ("precies") of een ondergrens geeft ("ten minste", LiDO); `per` is de verdeling die de bron geeft, in haar volgorde.
    Vraagt de jurist een verdeling die de bron niet geeft, dan staat dat in `zonder_verdeling` en is `per` leeg.
    Kamerstukken ronde 4 (K26) en Rechtspraak ronde 3 (R22): het model duidde of schatte een telling."""

    aantal: int
    dekking: Literal["precies", "ten minste"] = "precies"
    #: De bron die telt, in woorden ("Kamerstukken").
    bron: str = ""
    per_wat: str = ""
    per: list[TelPost] = []
    zonder_verdeling: str = ""


def telling_tekst(t: Telling) -> str:
    """De vaste zin van een telling: "Kamerstukken telt 72 stukken bij deze zoekvraag." De frontend zegt hetzelfde
    (`tellingTekst` in `lib/antwoord.ts`)."""
    n = f"{'ten minste ' if t.dekking == 'ten minste' else ''}{getal(t.aantal)} {'stuk' if t.aantal == 1 else 'stukken'}"
    zin = f"{t.bron + ' telt' if t.bron else 'De bron telt'} {n} bij deze zoekvraag."
    if t.per:
        zin += f"\n\nPer {t.per_wat}:\n" + "\n".join(f"- {p.waarde}: {getal(p.aantal)}" for p in t.per)
    elif t.zonder_verdeling:
        zin += f" {t.zonder_verdeling}"
    return zin


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
    #: Bij een telvraag: het aantal uit de bron, vóór de lijst (`Telling`).
    telling: Telling | None = None


class ToetsBron(BaseModel):
    """Een letterlijke passage uit de bron bij een bevinding van de contenttoets: de code nam de tekst uit de rijen die de
    graaf in deze beurt teruggaf, het model wees alleen de bepaling en de eerste en laatste woorden aan."""

    tekst: str
    vindplaats: Vindplaats


class Toetsbevinding(BaseModel):
    """Eén bewering uit de getoetste content met het oordeel van Lex (`bronmodel.contenttoets`).

    `citaat` staat letterlijk in de content; `begin` en `eind` zijn de plek in de content in Unicode-codepoints, uit de
    code (het zijpaneel markeert er de tekst mee). Het oordeel, de toelichting, de twijfel en het voorstel zijn van Lex."""

    nr: int
    citaat: str
    begin: int
    eind: int
    oordeel: Oordeel
    #: J1–J7 of V1–V3 (`bronmodel.contenttoets.CRITERIA`); leeg bij een juiste bewering zonder bijzonderheid.
    criterium: str = ""
    bronnen: list[ToetsBron] = []
    toelichting: str = ""
    twijfel: str = ""
    #: Een betere zin, of bij "niet in de bron" een vraag aan de redacteur. Een voorstel, nooit een besluit.
    voorstel: str = ""


class ToetsOntbreekt(BaseModel):
    """Wat de bron wezenlijk zegt en de content nergens noemt."""

    tekst: str
    bronnen: list[ToetsBron] = []


class Contenttoets(BaseModel):
    """Het toetsrapport van de contenttoets (plan contenttoets, C1): de content met per toetsbare bewering een oordeel en
    de letterlijke bron. Twee lagen: `voor_redacteur` in gewone taal, en per bevinding de juridische kern. De content
    staat er één keer in; de bevindingen wijzen ernaar met hun plek."""

    soort: Literal["contenttoets"] = "contenttoets"
    door: Literal["lex"] = "lex"
    content: str
    #: Vandaag, of de publicatiedatum die de gebruiker meegaf (ISO).
    peildatum: str = ""
    #: De regelingen waartegen getoetst is, uit de vindplaatsen van de bronnen (code).
    getoetst_tegen: list[str] = []
    voor_redacteur: list[str] = []
    bevindingen: list[Toetsbevinding]
    ontbreekt: list[ToetsOntbreekt] = []
    niet_getoetst: list[str] = []


def toets_aantallen(b: Contenttoets) -> dict[str, int]:
    uit: dict[str, int] = {}
    for x in b.bevindingen:
        uit[x.oordeel] = uit.get(x.oordeel, 0) + 1
    return uit


def toets_telling(b: Contenttoets) -> str:
    return _toets_telling(toets_aantallen(b), len(b.ontbreekt))


def _toets_bron_tekst(bron: ToetsBron) -> str:
    return f'> "{bron.tekst}"\n\n{_vindplaats_regel(bron.vindplaats)}'


def _toets_tekst(b: Contenttoets) -> str:
    """Het rapport als lijsten, nooit als tabel: het moet heel blijven als de redacteur het kopieert. Het voorstel staat
    niet tussen aanhalingstekens: het is tekst van Lex, geen citaat."""
    kop = "Getoetst tegen " + (", ".join(b.getoetst_tegen) if b.getoetst_tegen else "de wet- en regelgeving in de graaf")
    delen = [kop + (f", geldend op {b.peildatum}" if b.peildatum else "") + ". " + toets_telling(b)]
    if b.voor_redacteur:
        delen.append("**Voor de redacteur**\n\n" + "\n".join(f"- {r}" for r in b.voor_redacteur))
    for x in b.bevindingen:
        regels = [f"**[{x.nr}] {OORDEEL_LABEL[x.oordeel]}**" + (f" · {criterium_tekst(x.criterium)}" if x.criterium else ""),
                  f'De tekst: "{x.citaat}"']
        regels += [f"De bron:\n\n{_toets_bron_tekst(br)}" for br in x.bronnen]
        regels += [f"{k}: {v}" for k, v in (("Toelichting", x.toelichting), ("Twijfel of aanname", x.twijfel),
                                             ("Voorstel", x.voorstel)) if v]
        delen.append("\n\n".join(regels))
    if b.ontbreekt:
        delen.append("**Ontbreekt**\n\n" + "\n\n".join(
            "\n\n".join([f"- {o.tekst}", *(_toets_bron_tekst(br) for br in o.bronnen)]) for o in b.ontbreekt))
    if b.niet_getoetst:
        delen.append("**Niet getoetst**\n\n" + "\n".join(f"- {n}" for n in b.niet_getoetst))
    return "\n\n".join(delen)


class Leemte(BaseModel):
    """Wat het hoofddeel van een sjabloon niet kon vinden: gezegd, niet opgevuld. Altijd "in de graaf",
    nooit "bestaat niet"."""

    soort: Literal["leemte"] = "leemte"
    door: Literal["bron"] = "bron"
    tekst: str


Blok = Annotated[
    Definities | Begrippen | Regels | Wettekst | Citaten | Verwijzingen | Annotaties | Toelichting | Twijfel | Extern
    | Stukken | Contenttoets | Leemte,
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
NIET_GETOETST = frozenset({"annotaties", "begrippen", "regels", "leemte", "stukken"})


def _vindplaats_regel(v: Vindplaats) -> str:
    return f"{v.label}, {v.regeling}" if v.regeling else v.label


def _bereik_tekst(d: Definitie) -> str:
    """Waar de definitie geldt, in woorden; een ouder antwoord droeg alleen de formule."""
    if d.bereik_soort:
        return f" ({geldt_voor(d.bereik_soort, d.bereik_waarde, d.vindplaats.regeling)})"
    return f" (geldt voor: {d.bereik})" if d.bereik else ""


def _definitie_tekst(d: Definitie) -> str:
    tekst = f'> "{d.tekst}"\n\n**Vindplaats:** {_vindplaats_regel(d.vindplaats)}' + _bereik_tekst(d)
    if d.gebruikt:
        tekst += "\n\n**Gebruikt begrip:**\n\n" + "\n\n".join(
            f'> "{g.tekst}"\n\n**Vindplaats:** {_vindplaats_regel(g.vindplaats)}' for g in d.gebruikt)
    return tekst


def _regel_tekst(r: VastgelegdeRegel) -> str:
    """Een regel als lijst, nooit als tabel: naam en status, de opvolging, de gevallen en waarop ze rust."""
    kop = f"- **{r.naam or r.uitvoer or r.id}** ({r.status}" + (f", werkgebied {r.werkgebied}" if r.werkgebied else "") + ")"
    regels = [kop]
    if r.vervangen_door:
        regels.append(f"  - vervangen door {r.vervangen_door.naam or r.vervangen_door.id}")
    if r.vervangt:
        regels.append("  - vervangt " + ", ".join(v.naam or v.id for v in r.vervangt))
    if r.open_punten:
        regels.append(f"  - {r.open_punten} open punt{'en' if r.open_punten != 1 else ''}")
    for g in r.gevallen:
        # De tekst van een geval kan een lijst voorwaarden dragen, regel voor regel: die springt in onder het geval.
        eerste, *rest = (g.get("tekst", "") or "").split("\n")
        regels.append(f"  - {g.get('label') + ': ' if g.get('label') else ''}{eerste}")
        regels += [f"    {x.strip()}" for x in rest if x.strip()]
        regels += [f"    - {d.rol}: {d.vindplaats}" for d in r.dragers if d.vindplaats and d.geval == g.get("label")]
    regels += [f"  - {d.rol}: {d.vindplaats}" for d in r.dragers if d.vindplaats and not d.geval]
    return "\n".join(regels)


def _blok_tekst(b: BaseModel) -> str:
    if isinstance(b, Definities):
        return "\n\n".join(
            _definitie_tekst(d) for d in b.items)
    if isinstance(b, Begrippen):
        return "\n".join(
            f"- **{x.naam}** ({x.status}{', generiek' if x.generiek else ', ' + x.werkgebied if x.werkgebied else ''})" + (f": {x.definitie}" if x.definitie else "")
            for x in b.items)
    if isinstance(b, Regels):
        return "\n\n".join(_regel_tekst(x) for x in b.items)
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
        # De statusregel en een ingetrokken standpunt staan vóór de passages: de lezer weet eerst wat de bron is.
        vooraf = [f"*{b.status_regel}*"] if b.status_regel else []
        if b.brontype == "standpunt" and b.status in ("ingetrokken", "vervallen"):
            door = ", ".join(x.upper() for x in b.vervangen_door)
            vooraf.append(f"**Dit standpunt is {b.status} en is geen geldend beleid" + (f"; ingetrokken door {door}" if door
                                                                                       else "") + ".**")
        # De kern staat onder een kop met het stuk, zodat de toetsen op een stuk (`gelezen.per_stuk`) weten waarover hij gaat.
        if b.kern:
            vooraf.append(f"**{b.label}**" + ("" if b.id in b.label else f" ({b.id})") + f"\n{b.kern}")
        return "\n\n".join([*vooraf, *(f'> "{p.tekst}"' + (f" ({p.plek})" if p.plek else "") for p in b.passages)]) \
            + f"\n\n{regel}"
    if isinstance(b, Stukken):
        def regel(x: Stuk) -> str:
            naam = f"[{x.label}]({x.link})" if x.link else x.label
            wat = " · ".join(v for v in (x.soort, x.datum) if v)
            geen = f" ({x.zonder_tekst or 'geen tekst bij de bron'})" if not x.leesbaar else ""
            return f"- {naam}{' · ' + wat if wat else ''}{': ' + x.titel if x.titel else ''}{geen}{gezamenlijk_tekst(x.gezamenlijk)}"
        # Het totaal staat er ook als alles getoond is: "hoeveel stukken zitten er in dossier 33755?" kreeg anders een
        # lijst zonder getal (ronde 1 Kamerstukken, 11 nov 2026, K25).
        aantal = ("" if not b.totaal else f"{len(b.items)} van de {getal(b.totaal)} stukken." if b.totaal > len(b.items)
                  else f"{getal(b.totaal)} {'stuk' if b.totaal == 1 else 'stukken'}.")
        voet = " ".join(v for v in (b.zoekvraag, aantal) if v)
        lijst = "\n".join(regel(x) for x in b.items) + (f"\n\n{voet}" if voet else "")
        return f"{telling_tekst(b.telling)}\n\n{lijst}" if b.telling else lijst
    if isinstance(b, Contenttoets):
        return _toets_tekst(b)
    if isinstance(b, Leemte):
        return b.tekst
    return ""


KOPPEN = {"definities": "Wettelijke definitie", "begrippen": "Vastgelegd begrip", "wettekst": "Wettekst", "citaten": "Onderbouwing",
          "verwijzingen": "Verwijzingen", "annotaties": "Markeringen", "twijfel": "Twijfel en aannames",
          "contenttoets": "Contenttoets"}


def gezamenlijk_tekst(reeks: list[str]) -> str:
    """Een stuk uit een gezamenlijke behandeling van dossiers: " (gezamenlijk behandeld: 33752–33755)". Zonder die zin
    stonden in de lijst van dossier 33755 tien stukken als "Kamerstukken 33752, nr. B" zonder uitleg (ronde 2
    Kamerstukken, 11 nov 2026: K04, K21, K25). De frontend zegt hetzelfde (`gezamenlijkTekst` in `lib/antwoord.ts`). Alleen het veld `gezamenlijk`, niet
    `reeks`: dat is bij wetgeving buiten de kennisgraaf de plek in de regeling."""
    if len(reeks) < 2:
        return ""
    return f" (gezamenlijk behandeld: {reeks[0]}–{reeks[-1]})" if len(reeks) > 2 else f" (gezamenlijk behandeld: {reeks[0]} en {reeks[1]})"


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
