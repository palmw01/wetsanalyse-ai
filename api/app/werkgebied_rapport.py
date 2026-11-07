"""Het rapport van een werkgebied: één gestructureerd document waaruit PDF en Markdown komen (ADR-009).

`werkgebied_export.bouw_rapport` vult het uit de stand; `rapport_regels` maakt er (stijl, tekst)-regels van. Het document
draagt codes en ISO-datums, zodat het als JSON bruikbaar is. Alle woorden, labels en de volgorde staan hier, dus de
uitvoervormen kunnen inhoudelijk niet uit elkaar lopen.

`door` zegt van wie de inhoud komt: `bron` (letterlijk uit de wettekst), `lex` (een voorstel) of `analist`.
"""
from __future__ import annotations

import re
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from bronmodel.antwoord import Vindplaats
from pydantic import BaseModel, ConfigDict

from .bepaling_graaf_contract import RegelingInfo, Structuurdeel, Verwijzing
from .jas_klassen import JAS_KLASSEN_VOLGORDE
from .pdf_opmaak import BEGRIP, BLOK_BEGIN, BLOK_EIND, INHOUD, MARKERING, PAGINA, PLAATS, SPANS, TITELBLAD, TOELICHTING

VERSIE = 2
SCHEMA = "werkgebied-rapport-v2"

Regel = tuple[str, str]
Door = Literal["bron", "lex", "analist"]


class _Deel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stand(_Deel):
    op: str
    door: str


class Document(_Deel):
    """Wat het rapport als document identificeert: titelblad en colofon."""

    titel: str
    kenmerk: str                                     # "WG-<eerste 8 tekens van het id>-r<revisie>": welk werkgebied, welke revisie
    werkgebied_id: str
    concept: bool                                    # zolang het werkgebied niet afgerond is
    inhoud_hash: str = ""                            # "sha256:<hex>" over de inhoud (`inhoud_hash`): welke analyseversie precies


class Telling(_Deel):
    code: str
    aantal: int


class Kerncijfers(_Deel):
    """De samenvatting: codes en getallen, de zinnen maakt de tekstlaag."""

    deelvragen: list[Telling] = []                   # voortgang → aantal
    bronnen: list[Telling] = []                      # rol → aantal
    markeringen: list[Telling] = []                  # beoordeeld | voorstel | afgewezen → aantal
    begrippen: list[Telling] = []                    # status → aantal


class Bronstand(_Deel):
    """Welke toestand van een regeling in het dossier staat."""

    bwb_id: str
    citeertitel: str
    geldig_vanaf: str | None = None
    geldig_tot: str | None = None


class Signaal(_Deel):
    """Wat een lezer moet weten voor hij het rapport gebruikt. Dezelfde punten staan ook op hun plek."""

    soort: Literal["niet_in_dossier", "bron_veranderd", "toestand_onvolledig", "na_peildatum", "markeringen_veranderd",
                   "passages_veranderd", "opnieuw_bekijken", "zoeken_onvolledig", "graaf_onvolledig"]
    label: str = ""
    reden: str = ""
    datum: str | None = None
    aantal: int = 0
    nrs: list[int] = []


class Voorblad(_Deel):
    naam: str
    analysevraag: str = ""
    status: str
    revisie: int
    thema: str = ""
    peildatum: str | None = None
    peildatum_standaard: bool = False
    regelingen: list[RegelingInfo] = []
    signalen: list[Signaal] = []


class DossierVeld(_Deel):
    veld: Literal["aanleiding", "context", "doel", "analysevraag", "praktijkvoorbeeld", "afbakening", "gebeurtenis"]
    tekst: str = ""
    door: Door = "analist"


class Zoekregeling(_Deel):
    bwb_id: str
    label: str = ""


class Dossier(_Deel):
    velden: list[DossierVeld]
    zoekbereik: list[Zoekregeling] = []


class DeelvraagBron(_Deel):
    vindplaats: Vindplaats
    rol: str
    reden: str = ""


class Deelvraag(_Deel):
    nr: int
    vraag: str
    status: str
    opnieuw_bekijken: bool = False
    open_punten: list[str] = []
    bronnen: list[DeelvraagBron] = []
    niet_gekozen: int = 0
    door: Door = "analist"


class UitgeslotenBron(_Deel):
    vindplaats: Vindplaats
    overal: bool = False
    nrs: list[int] = []
    besloten_door: str = ""
    reden: str = ""
    door: Door = "analist"


class Bronvoorstel(_Deel):
    vindplaats: Vindplaats
    rol: str
    nrs: list[int] = []
    door: Door = "lex"


class Zoekdekking(_Deel):
    onvolledig: list[str] = []
    verouderd: bool = False
    reden: str = ""


class Deelvragen(_Deel):
    modus: str
    deelvragen: list[Deelvraag] = []
    uitgesloten: list[UitgeslotenBron] = []
    open_vragen: list[str] = []
    open_bronnen: list[Bronvoorstel] = []
    zoekdekking: Zoekdekking | None = None


class KlasseTelling(_Deel):
    klasse: str = ""                                 # leeg: een markering die nog geen klasse heeft
    aantal: int


class Herkomst(_Deel):
    """Wie stelde voor en wat deed de jurist. Het volledige spoor staat in de annotatie-export."""

    herkomst: str = ""
    besloten_door: str = ""
    terugval: bool = False
    twijfel: list[str] = []
    gedegradeerd: bool = False
    jurist: str = ""


class Afwijking(_Deel):
    """Een ankerfragment dat niet meer op zijn offsets staat."""

    plek: str
    toen: str
    nu: str


class Span(_Deel):
    """Een markering in de wettekst van haar bepaling: offsets in Unicode-codepoints, uit het opgeslagen anker."""

    start: int
    eind: int
    nr: int                                          # het nummer van de markering in de lijst onder de bepaling
    klasse: str = ""


class Markering(_Deel):
    id: str
    nr: int = 0                                      # het nummer binnen de bepaling; 0 buiten de wettekst
    klasse: str = ""
    alternatieven: list[str] = []
    subtype: str = ""
    lifecycle: str
    tekst: str
    vindplaatsen: list[Vindplaats] = []
    toelichting: str = ""
    herkomst: Herkomst
    afwijkingen: list[Afwijking] = []
    reden_afwijzing: str = ""
    verouderd: bool = False
    deels_buiten: bool = False
    door: Door = "lex"


class Bepaling(_Deel):
    vindplaats: Vindplaats
    rol: str
    bron_gewijzigd: bool = False
    tekst: str = ""
    markeringen: list[Markering] = []
    spans: list[Span] = []                           # alleen ankers die nog op hun offsets staan; een afwijking staat bij de markering
    verwijzingen: list[Verwijzing] = []
    door: Door = "bron"


class Artikel(_Deel):
    kop: str
    bepalingen: list[Bepaling]
    plaats: list[Structuurdeel] = []                 # van buiten naar binnen, zonder de regeling
    inwerking: str | None = None
    gewijzigd_bij: str = ""                          # bwb:bron: de publicatie van de laatste wijziging, zoals "Stb.2023-499"


class Regeling(_Deel):
    bwb_id: str
    titel: str
    artikelen: list[Artikel] = []
    context: list[Artikel] = []                      # bepalingen met rol context en zonder markering: naslag, in een bijlage


class Onbereikbaar(_Deel):
    label: str
    reden: str


class Wettekst(_Deel):
    markeringen: int
    beoordeeld: int
    per_klasse: list[KlasseTelling] = []
    regelingen: list[Regeling] = []
    onbereikbaar: list[Onbereikbaar] = []
    buiten_tekst: list[Markering] = []
    afgewezen: list[Markering] = []
    verwijzingen: list[Verwijzing] = []              # alle verwijzingen uit het dossier, in de volgorde van de bronboom
    #: Onwaar als de graaf meer verwijzingen gaf dan de grens (`bepaling_graaf.MAX_VERWIJZINGSRIJEN`): dan is de lijst niet alles.
    verwijzingen_volledig: bool = True


class Voorbeeld(_Deel):
    oordeel: str
    tekst: str


class Fragment(_Deel):
    tekst: str
    vindplaats: Vindplaats
    door: Door = "bron"


class Passage(_Deel):
    tekst: str
    vindplaats: Vindplaats
    klasse: str = ""
    rol: str
    beoordeling: str
    annotatie_beoordeeld: bool = False
    motivatie: str = ""
    beoordeeld_door: str = ""
    beoordeeld_op: str | None = None
    actualiteit: str = "actueel"
    nu: str | None = None
    door: Door = "bron"


class Relatie(_Deel):
    van: str
    type: str
    naar: str
    toelichting: str = ""


class Begrip(_Deel):
    id: str
    naam: str
    status: Literal["geaccordeerd", "concept", "vervangen"]
    generiek: bool = False
    alternatieve_termen: list[str] = []
    definitie: str = ""
    definitie_herkomst: str = ""
    definitie_door: str = ""
    definitie_vindplaats: Vindplaats | None = None
    uitleg: str = ""
    toelichting: str = ""
    voorbeelden: list[Voorbeeld] = []
    onderbouwing_aangepast: bool = False
    fragmenten: list[Fragment] = []
    passages: list[Passage] = []
    relaties: list[Relatie] = []
    open_punten: list[str] = []
    geaccordeerd_door: str = ""
    geaccordeerd_op: str | None = None
    reden: str = ""
    vervangen: bool = False
    door: Door = "analist"


class OpenGroep(_Deel):
    naam: str
    definitie: str = ""
    leden: list[Fragment] = []
    door: Door = "lex"


class OpenRelatie(_Deel):
    van: str
    type: str
    naar: str
    door: Door = "lex"


class Begrippen(_Deel):
    begrippen: list[Begrip] = []
    open_groepen: list[OpenGroep] = []
    open_relaties: list[OpenRelatie] = []


class Handeling(_Deel):
    actie: str
    aantal: int


class Besluit(_Deel):
    """Een beslissende handeling uit de audit: wie besloot wat, en wanneer."""

    op: str
    door: str
    actie: str
    onderwerp: str = ""
    reden: str = ""


class Selectie(_Deel):
    rol: str
    vindplaats: Vindplaats
    toegevoegd_door: str = ""
    toegevoegd: str | None = None


class Verantwoording(_Deel):
    aangemaakt_door: str
    aangemaakt: str
    gewijzigd: str
    juristen: list[str] = []
    accordeurs: list[str] = []
    handelingen: list[Handeling] = []
    besluiten: list[Besluit] = []
    bronnen: list[Selectie] = []


class Rapport(_Deel):
    schema_naam: Literal["werkgebied-rapport-v2"] = SCHEMA
    versie: int = VERSIE
    stand: Stand
    document: Document
    voorblad: Voorblad
    samenvatting: Kerncijfers
    dossier: Dossier
    deelvragen: Deelvragen
    wettekst: Wettekst
    begrippen: Begrippen
    verantwoording: Verantwoording


def inhoud_hash(r: "Rapport") -> str:
    """De identiteit van de inhoud: SHA-256 over het document zonder `stand` (wanneer en door wie geëxporteerd) en zonder de hash
    zelf, als JSON met gesorteerde sleutels. Gelijke inhoud geeft dezelfde hash, op elk moment en voor elke exporteur; een
    andere annotatie, beoordeling, begrip of graafgegeven geeft een andere. De werkgebiedrevisie (`kenmerk`) ziet dat niet.
    Narekenen: zet `document.inhoud_hash` op "" en laat `stand` weg."""
    inhoud = r.model_dump(mode="json", exclude={"stand": True, "document": {"inhoud_hash"}})
    tekst = json.dumps(inhoud, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(tekst.encode()).hexdigest()


def kort(h: str) -> str:
    """De eerste twaalf tekens van de hash: genoeg om twee rapporten naast elkaar te herkennen."""
    return h.removeprefix("sha256:")[:12]


SCHEMA_PAD = Path(__file__).parent / "schemas" / f"{SCHEMA}.schema.json"


def json_schema() -> dict:
    """Het JSON-schema van het document; het bestand in `schemas/` is hieruit gemaakt en een test bewaakt dat."""
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"urn:wetsanalyse:schema:{SCHEMA}",
            **Rapport.model_json_schema()}


def schrijf_schema() -> None:
    SCHEMA_PAD.write_text(json.dumps(json_schema(), ensure_ascii=False, indent=2) + "\n")


_DOSSIER = {"aanleiding": "Aanleiding", "context": "Context", "doel": "Doel", "analysevraag": "Analysevraag",
            "praktijkvoorbeeld": "Praktijkvoorbeeld", "afbakening": "Afbakening", "gebeurtenis": "Gebeurtenis"}
DOSSIERVELDEN = tuple(_DOSSIER)
_WERKGEBIED_STATUS = {"in_voorbereiding": "In voorbereiding", "actief": "Actief", "afgerond": "Afgerond"}
_VOORTGANG = {"niet_gestart": "Nog niet gestart", "in_behandeling": "In behandeling",
              "voorlopig_afgerond": "Voorlopig afgerond", "beoordeeld": "Beoordeeld"}
_BRONROL = {"analyseren": "analyseren", "context": "context"}
_KANDIDAATROL = {"kern": "kernbepaling", "afhankelijkheid": "afhankelijkheid", "aanverwant": "aanverwant"}
_LIFECYCLE = {"voorgesteld": "voorstel, nog niet beoordeeld", "human_approved": "beoordeeld: akkoord",
              "edited": "beoordeeld: aangepast", "published": "beoordeeld: gepubliceerd",
              "rejected": "afgewezen", "reused": "hergebruikt, nog niet beoordeeld",
              "vervangen": "vervangen door een nieuwe ronde van Lex"}
_BEGRIPSTATUS = {"geaccordeerd": "Geaccordeerd", "concept": "Concept, nog niet geaccordeerd", "vervangen": "Vervangen"}
_KOPPELROL = {"duiding": "duidt dit begrip aan", "definitie": "ondersteunt de definitie", "context": "context"}
_BEOORDELING = {"open": "nog niet beoordeeld", "akkoord": "akkoord", "afgewezen": "afgewezen"}
_ACTUALITEIT = {"gewijzigd": "de passage veranderde", "verworpen": "de annotatie is verworpen",
                "verdwenen": "de annotatie bestaat niet meer"}
_OORDEEL = {"wel": "valt eronder", "niet": "valt er niet onder", "onzeker": "twijfel"}
_RELATIE = {"kwalificatie": "kwalificeert", "inclusie": "omvat", "uitsluiting": "omvat niet", "hierarchie": "heeft als soort",
            "verwant": "is verwant met", "opvolging": "wordt opgevolgd door"}
_DEFINITIE = {"letterlijk": "brondefinitie, letterlijk uit de wettekst", "samengesteld": "analysebegrip, samengesteld uit de wettekst",
              "geformuleerd": "analysebegrip, geformuleerd"}
_DEFINITIE_DOOR = {"lex": "voorgesteld door Lex", "analist": "door de analist"}
_MARKERINGSTAND = {"beoordeeld": "beoordeeld door een jurist", "voorstel": "voorstel, nog niet beoordeeld", "afgewezen": "afgewezen"}
_BESLUIT = {"status-gewijzigd": "status van het werkgebied gewijzigd",
            "bron-toegevoegd": "bron opgenomen in het werkgebied", "bron-verwijderd": "bron verwijderd uit het werkgebied",
            "bronselectie-opgenomen": "bron opgenomen bij een deelvraag", "bronselectie-uitgesloten": "bron uitgesloten bij een deelvraag",
            "bronselectie-losgekoppeld": "bron losgemaakt van een deelvraag",
            "kandidaat-opgenomen": "voorgestelde bron opgenomen", "kandidaat-uitgesloten": "voorgestelde bron uitgesloten",
            "bronselectie-afronden": "bronselectie afgerond", "bronselectie-heropenen": "bronselectie heropend",
            "bronselectie-heropend": "bronselectie heropend",
            "begrip-geaccordeerd": "begrip geaccordeerd", "begrip-heropend": "accordering van een begrip ingetrokken",
            "begrip-generiek": "begrip generiek gemaakt", "begrip-vervangen": "begrip vervangen", "begrip-opgevolgd": "begrip opgevolgd",
            "begrip-gecombineerd": "begrippen gecombineerd", "begrip-verwijderd": "begrip verwijderd",
            "relatie-vastgelegd": "relatie vastgelegd", "relatie-bevestigd": "relatie bevestigd", "relatie-afgewezen": "relatie afgewezen",
            "koppeling-bevestigd": "passage bij een begrip bevestigd",
            "voorstel-overgenomen": "voorstel van Lex overgenomen", "voorstel-afgewezen": "voorstel van Lex afgewezen",
            "groep-overgenomen": "betekenisgroep overgenomen", "groep-akkoord": "betekenisgroep akkoord bevonden"}
BESLUITEN = frozenset(_BESLUIT)
"""De audit-acties die een besluit zijn: die staan met datum en naam in het besluitenlog, de rest alleen geteld."""
_LEEG = "Niet ingevuld."
_ZONE = ZoneInfo("Europe/Amsterdam")
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")

BLOK: tuple[Regel, ...] = ((BLOK_BEGIN, ""),)
BLOK_UIT: tuple[Regel, ...] = ((BLOK_EIND, ""),)


def datum_tijd(iso: str | None) -> str:
    """"7 november 2026, 14:03", in Nederlandse tijd."""
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    d = d.astimezone(_ZONE) if d.tzinfo else d
    return f"{datum(iso)}, {d:%H:%M}"


def datum(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    d = d.astimezone(_ZONE) if d.tzinfo else d
    return f"{d.day} {_MAANDEN[d.month - 1]} {d.year}"


def meervoud(n: int, een: str, meer: str) -> str:
    return f"{n} {een if n == 1 else meer}"


def alinea(tekst: str, stijl: str = "BodyText") -> list[Regel]:
    return [(stijl, a.strip()) for a in re.split(r"\n\s*\n", tekst) if a.strip()]


def _signaal(s: Signaal) -> str:
    if s.soort == "niet_in_dossier":
        return f"Niet in dit dossier: {s.label}. {s.reden}"
    if s.soort == "bron_veranderd":
        return f"De bron veranderde sinds de selectie: {s.label}."
    if s.soort == "toestand_onvolledig":
        return "De toestand per regeling kon niet worden gelezen: de vergelijking met de peildatum ontbreekt."
    if s.soort == "na_peildatum":
        return f"{s.label}: de tekst in dit dossier geldt pas sinds {datum(s.datum)}, na de peildatum. Hij kan afwijken van wat op de peildatum gold."
    if s.soort == "markeringen_veranderd":
        return meervoud(s.aantal, "markering staat op tekst die veranderde.", "markeringen staan op tekst die veranderde.")
    if s.soort == "passages_veranderd":
        return meervoud(s.aantal, "passage bij een begrip veranderde; toen en nu staan bij het begrip.",
                        "passages bij begrippen veranderden; toen en nu staan bij het begrip.")
    if s.soort == "opnieuw_bekijken":
        return "Opnieuw te bekijken na een wijziging van de scope: deelvraag " + ", ".join(map(str, s.nrs)) + "."
    if s.soort == "graaf_onvolledig":
        return ("De kennisgraaf gaf niet alle gegevens over de regelingen, hun opbouw of de verwijzingen; wat ontbreekt, staat niet in "
                "dit rapport. Een onvolledige lijst zegt dat bij de lijst zelf.")
    return "Het zoeken naar bronnen is onvolledig of verouderd; zie de bijlage Niet meegenomen."


def titelblad_regels(doc: Document, v: Voorblad, stand: Stand) -> list[Regel]:
    """Pagina 1: wat dit is, waarover, en in welke stand. De PDF tekent het als titelblad, Markdown als kop met een lijst."""
    status = _WERKGEBIED_STATUS.get(v.status, v.status) + (" · concept" if doc.concept else "")
    uit: list[Regel] = [(TITELBLAD + "titel", v.naam), (TITELBLAD + "soort", "Wetsanalyse · rapport van het werkgebied")]
    if v.analysevraag:
        uit.append((TITELBLAD + "vraag", v.analysevraag))
    uit += [(TITELBLAD + "rij", "Status: " + status), (TITELBLAD + "rij", f"Revisie: {v.revisie}"),
            (TITELBLAD + "rij", "Peildatum: " + (datum(v.peildatum) or "niet vastgelegd") + (" (de aanmaakdag)" if v.peildatum_standaard else "")),
            (TITELBLAD + "rij", "Stand van: " + datum_tijd(stand.op)), (TITELBLAD + "rij", "Kenmerk: " + doc.kenmerk)]
    if doc.inhoud_hash:
        uit.append((TITELBLAD + "rij", "Inhoudscode: " + kort(doc.inhoud_hash)))
    if v.thema:
        uit.append((TITELBLAD + "rij", "Thema: " + v.thema))
    if v.regelingen:
        uit.append((TITELBLAD + "regelingen", "Regelingen: " + " · ".join(r.citeertitel for r in v.regelingen)))
    uit.append((TITELBLAD + "voetnoot", "Een analyse-uitkomst volgens de methode Wetsanalyse, geen wettelijke definitie en geen "
                                        "juridisch oordeel. Lex stelt voor, de jurist beslist."))
    return uit


def bronstand_regels(v: Voorblad) -> list[Regel]:
    uit: list[Regel] = []
    if v.regelingen:
        uit.append(("Heading4", "Bronstand per regeling"))
        for r in v.regelingen:
            # De graaf zet een regeling zonder einde op 9999-12-31.
            tot = f" tot {datum(r.geldig_tot)}" if r.geldig_tot and r.geldig_tot < "9999" else ""
            vanaf = f"geldt vanaf {datum(r.geldig_vanaf)}{tot}" if r.geldig_vanaf else "geldigheid onbekend"
            wie = " · ".join(filter(None, [r.soort, r.verantwoordelijke and "verantwoordelijk: " + r.verantwoordelijke]))
            uit.append(("Meta", f"{r.citeertitel} ({r.bwb_id}{', ' + r.afkorting if r.afkorting else ''}): {vanaf}" + (f" · {wie}" if wie else "")))
    return uit


def signalen_regels(v: Voorblad) -> list[Regel]:
    if not v.signalen:
        return []
    return [("Heading4", "Let op"), *[("Waarschuwing", _signaal(s)) for s in v.signalen]]


def leeswijzer_regels() -> list[Regel]:
    """Hoe je het rapport leest: één keer de statussen, de herkomst en de klassen, zodat ze niet bij elk stuk terugkomen."""
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "2. Leeswijzer"),
                        ("BodyText", "Dit is een analyse-uitkomst volgens de methode Wetsanalyse, geen wettelijke definitie en geen "
                                     "juridisch oordeel. De wettekst is letterlijk overgenomen uit de kennisgraaf, die gevuld is uit "
                                     "de officiële publicatie. Bij elke bepaling staan de vindplaats en de bronreferentie (jci)."),
                        ("Heading4", "Wie stelde voor, wie besliste"),
                        ("BodyText", "Lex stelt voor, de jurist beslist. Beoordeeld of geaccordeerd betekent dat een jurist het "
                                     "bevestigde. Voorstel en concept zijn nog niet bevestigd. Afgewezen en uitgesloten zijn bewust "
                                     "niet meegenomen; ze staan in een bijlage, zodat niets stil verdwijnt."),
                        ("Heading4", "Opbouw"),
                        ("BodyText", "Hoofdstuk 3 tot en met 6 dragen de analyse: het werkgebied, de deelvragen met hun bronnen, de "
                                     "analyse per bepaling en de begrippen. De bijlagen zijn naslag: de volledige begripskaarten, het "
                                     "bronnenregister, de contextbepalingen, de samenhang (verwijzingen), wat niet is meegenomen "
                                     "en de verantwoording."),
                        ("Heading4", "De klassen van het Juridisch Analyseschema"),
                        ("Meta", "Een markering draagt de kleur van haar klasse, en altijd ook de naam: de kleur is nooit de enige drager.")]
    uit += [(MARKERING + k, k) for k in JAS_KLASSEN_VOLGORDE]
    return uit


def colofon_regels(doc: Document, v: Voorblad, stand: Stand, verantwoording: Verantwoording) -> list[Regel]:
    """Pagina 2: wat het document is, wie het opstelde en waar de tekst vandaan komt."""
    status = _WERKGEBIED_STATUS.get(v.status, v.status) + (" · concept" if doc.concept else "")
    uit: list[Regel] = [(PAGINA, ""), ("Heading4", "Colofon"),
                        ("Meta", "Titel: " + doc.titel),
                        ("Meta", "Kenmerk: " + doc.kenmerk),
                        ("Meta", "Inhoudscode: " + (doc.inhoud_hash or "niet berekend")
                         + " (SHA-256 over de inhoud, zonder het exportmoment: gelijke inhoud, gelijke code)"),
                        ("Meta", "Werkgebied: " + doc.werkgebied_id),
                        ("Meta", f"Status: {status} · revisie {v.revisie}"),
                        ("Meta", "Peildatum: " + (datum(v.peildatum) or "niet vastgelegd") + (" (de aanmaakdag)" if v.peildatum_standaard else "")),
                        *([("Meta", "Thema: " + v.thema)] if v.thema else []),
                        ("Meta", f"Stand van {datum_tijd(stand.op)}, geëxporteerd door {stand.door}."),
                        ("Meta", "Opgesteld door: " + verantwoording.aangemaakt_door)]
    if verantwoording.juristen:
        uit.append(("Meta", "Markeringen beoordeeld door: " + ", ".join(verantwoording.juristen)))
    if verantwoording.accordeurs:
        uit.append(("Meta", "Begrippen geaccordeerd door: " + ", ".join(verantwoording.accordeurs)))
    uit += [("Meta", "Opgesteld met Lex, het wetsanalyseplatform. Lex stelt voor, de jurist beslist."),
            ("Meta", "Wettekst: de BWB-kennisgraaf, gevuld uit de officiële publicatie op wetten.overheid.nl. "
                     "De toestand per regeling staat in het rapport."),
            ("Meta", "Dit rapport is een analyse-uitkomst volgens de methode Wetsanalyse, geen wettelijke definitie en geen "
                     "juridisch oordeel.")]
    return [*uit, *bronstand_regels(v)]


def _tellingen(t: list[Telling], labels: dict[str, str]) -> str:
    return ", ".join(f"{labels.get(x.code, x.code)}: {x.aantal}" for x in t) or "geen"


def samenvatting_regels(k: Kerncijfers, v: Voorblad, d: Deelvragen) -> list[Regel]:
    """De kern op één pagina: de vraag, de cijfers en wat een lezer eerst moet weten."""
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "1. Samenvatting")]
    if v.analysevraag:
        uit += [("Heading4", "Analysevraag"), *alinea(v.analysevraag)]
    uit += signalen_regels(v)
    uit += [("Heading4", "Kerncijfers"),
            ("BodyText", "Deelvragen – " + _tellingen(k.deelvragen, _VOORTGANG)),
            ("BodyText", "Bronnen – " + _tellingen(k.bronnen, {"analyseren": "te analyseren", "context": "context"})),
            ("BodyText", "Markeringen – " + _tellingen(k.markeringen, _MARKERINGSTAND)),
            ("BodyText", "Begrippen – " + _tellingen(k.begrippen, {s: t.split(",")[0].lower() for s, t in _BEGRIPSTATUS.items()}))]
    if d.deelvragen and d.modus != "analysevraag":
        uit.append(("Heading4", "Stand per deelvraag"))
        uit += [("BodyText", f"{x.nr}. {'Opnieuw bekijken' if x.opnieuw_bekijken else _VOORTGANG.get(x.status, x.status)} – {x.vraag}")
                for x in d.deelvragen]
    return uit


def dossier_regels(d: Dossier) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "3. Werkgebied")]
    for v in d.velden:
        uit.append(("Heading4", _DOSSIER[v.veld]))
        uit += alinea(v.tekst) or [("Meta", "Niet ingevuld.")]
    if d.zoekbereik:
        uit.append(("Heading4", "Zoekbereik"))
        uit += [("BodyText", f"{r.label or r.bwb_id} ({r.bwb_id})") for r in d.zoekbereik]
    return uit


def deelvragen_regels(d: Deelvragen) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "4. Deelvragen en bronnen")]
    for v in d.deelvragen:
        uit += [*BLOK, ("Heading2", "Analysevraag" if d.modus == "analysevraag" else f"Deelvraag {v.nr}"), ("BodyText", v.vraag)]
        stand = "Opnieuw bekijken" if v.opnieuw_bekijken else _VOORTGANG.get(v.status, v.status)
        uit.append(("Meta", f"Stand: {stand} · {meervoud(len(v.bronnen), 'bron', 'bronnen')}"))
        if v.opnieuw_bekijken:
            uit.append(("Waarschuwing", "De scope veranderde na het afronden; deze deelvraag moet opnieuw bekeken worden."))
        uit += [("Waarschuwing", "Open punt: " + p) for p in v.open_punten]
        for b in v.bronnen:
            uit += [("BodyText", f"{b.vindplaats.label} · {_BRONROL.get(b.rol, b.rol)}" + (f": {b.reden}" if b.reden else "")),
                    ("Meta", _verwijzing(b.vindplaats))]
        if v.niet_gekozen:
            uit.append(("Meta", meervoud(v.niet_gekozen, "voorstel van Lex is niet gekozen.", "voorstellen van Lex zijn niet gekozen.")))
        uit += BLOK_UIT

    return uit


def niet_meegenomen_regels(d: Deelvragen, w: Wettekst, b: Begrippen) -> list[Regel]:
    """Bijlage: wat bewust niet meedoet, en wat nog open staat. Het staat apart, zodat het de analyse niet vertroebelt."""
    uit: list[Regel] = []
    uit.append(("Heading2", "Uitgesloten bronnen"))
    if not d.uitgesloten:
        uit.append(("Meta", "Er zijn geen bronnen uitgesloten."))
    for k in d.uitgesloten:
        waar = "alle deelvragen" if k.overal else "deelvraag " + ", ".join(map(str, k.nrs))
        uit.append(("BodyText", f"{k.vindplaats.label} · uitgesloten voor {waar}" + (f" door {k.besloten_door}" if k.besloten_door else "")
                    + f". Reden: {k.reden or 'niet vastgelegd'}"))
        uit.append(("Meta", _verwijzing(k.vindplaats)))

    uit.append(("Heading2", "Open voorstellen van Lex voor deelvragen en bronnen"))
    if not d.open_vragen and not d.open_bronnen:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    uit += [("Voorstel", "Voorstel voor een deelvraag: " + v) for v in d.open_vragen]
    for k in d.open_bronnen:
        waar = f" · deelvraag {', '.join(map(str, k.nrs))}" if k.nrs else " · bij geen deelvraag"
        uit.append(("Voorstel", f"Voorstel voor een bron: {k.vindplaats.label} · {_KANDIDAATROL.get(k.rol, k.rol)}{waar}"))
        uit.append(("Meta", _verwijzing(k.vindplaats)))

    if d.zoekdekking:
        uit.append(("Heading2", "Zoekdekking"))
        uit.append(("BodyText", "Lex heeft gezocht"
                    + (", maar niet alles kon worden doorzocht: " + ", ".join(d.zoekdekking.onvolledig) + "." if d.zoekdekking.onvolledig else ".")))
        if d.zoekdekking.verouderd:
            uit.append(("Waarschuwing", "Het werkgebied veranderde na het zoeken."))
        if d.zoekdekking.reden:
            uit.append(("Meta", d.zoekdekking.reden))


    uit += [(PAGINA, ""), ("Heading2", "Afgewezen markeringen"),
            ("Meta", "Deze markeringen verwierp een jurist; ze horen niet tot de analyse." if w.afgewezen else "Er zijn geen markeringen afgewezen.")]
    for m in w.afgewezen:
        uit += _markering(m)
    uit += [(PAGINA, ""), *open_begrippen_regels(b)]
    return uit


def _verwijzing(v: Vindplaats) -> str:
    """De bronreferentie: de jci, met de bron-IRI als terugval."""
    return v.jci or v.iri


def _herkomst(h: Herkomst) -> str:
    if not h.besloten_door:
        delen = ["door een jurist zelf gemarkeerd" if h.herkomst == "mens" else "geen spoor bewaard"]
    elif h.terugval:
        delen = [f"{h.besloten_door} – de jurist kiest uit de mogelijke klassen"]
    else:
        delen = [f"voorgesteld door Lex ({h.besloten_door})"]
    if h.twijfel:
        delen.append("twijfel: " + ", ".join(h.twijfel))
    if h.gedegradeerd:
        delen.append("zonder zinsontleding beoordeeld")
    if h.jurist:
        delen.append(re.sub(r"\d{4}-\d{2}-\d{2}T\S+", lambda m: datum(m[0]), h.jurist))
    return "Herkomst: " + "; ".join(delen) + "."


def _markering(m: Markering, eigen_iri: str = "", in_tekst: bool = False) -> list[Regel]:
    """Eén markering. Staat ze gemarkeerd in de wettekst erboven (`in_tekst`), dan draagt ze haar nummer en komt het citaat niet nog
    eens: de tekst staat er al, met dezelfde kleur en hetzelfde nummer."""
    # Een terugval draagt geen klasse: zeg dat, en noem de keuze.
    kop = m.klasse or "Nog geen klasse (" + ", ".join(m.alternatieven) + ")"
    if m.subtype:
        kop += f", {m.subtype}"
    nummer = f"{m.nr} · " if m.nr else ""
    uit: list[Regel] = [*BLOK, (MARKERING + m.klasse, f"{nummer}{kop} · {_LIFECYCLE.get(m.lifecycle, m.lifecycle)}")]
    if not in_tekst:
        uit.append(("Citaat", f"“{m.tekst}”"))
    uit += [("Meta", f"Vindplaats: {v.label} · {_verwijzing(v)}") for v in m.vindplaatsen if v.iri != eigen_iri]
    if m.toelichting:
        uit.append((TOELICHTING, m.toelichting))
    uit.append(("Meta", _herkomst(m.herkomst)))
    if m.reden_afwijzing:
        uit.append(("Meta", "Reden van afwijzing: " + m.reden_afwijzing))
    uit += [("Waarschuwing", f"Brontekst gewijzigd bij {a.plek}. Toen: “{a.toen}” Nu: “{a.nu}”") for a in m.afwijkingen]
    if m.verouderd and not m.afwijkingen:
        uit.append(("Waarschuwing", "Verouderd: de bepaling veranderde na het annoteren."))
    if m.deels_buiten:
        uit.append(("Meta", "Deze markering valt deels buiten de bronselectie."))
    return [*uit, *BLOK_UIT]


def wettekst_regels(w: Wettekst) -> list[Regel]:
    """Per regeling, in de volgorde van de bronboom, elke bronnode één keer met haar markeringen eronder."""
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "5. Analyse per bepaling"),
                        ("BodyText", f"{meervoud(w.markeringen, 'markering', 'markeringen')}, waarvan {w.beoordeeld} "
                                     f"beoordeeld door een jurist; {len(w.afgewezen)} afgewezen.")]
    uit += [("Meta", f"{k.klasse or 'Nog geen klasse'}: {k.aantal}") for k in w.per_klasse]
    for r in w.regelingen:
        uit += [(PAGINA, ""), ("Heading2", r.titel)]
        plaats = None
        for a in r.artikelen:
            if a.plaats and a.plaats != plaats:
                uit.append((PLAATS, _plaats(a.plaats)))
            plaats = a.plaats
            uit.append(("Heading3", a.kop))
            uit += _artikelmeta(a)
            for b in a.bepalingen:
                uit += _bepaling(b)
    for o in w.onbereikbaar:
        uit += [("Heading3", o.label), ("Waarschuwing", f"De tekst ontbreekt: {o.reden}")]
    if w.buiten_tekst:
        uit += [(PAGINA, ""), ("Heading2", "Markeringen buiten de getoonde tekst")]
        for m in w.buiten_tekst:
            uit += _markering(m)
    if any(r.context for r in w.regelingen):
        uit.append(("Meta", "De contextbepalingen zonder markering staan in de bijlage Contextbepalingen."))
    return uit


_SOORT = {"Hoofdstuk": "Hoofdstuk", "Titeldeel": "Titel", "Afdeling": "Afdeling", "Paragraaf": "§", "Divisie": "", "Bijlage": "Bijlage",
          "Artikel": "Artikel"}


def _plaats(plaats: list[Structuurdeel]) -> str:
    """"Hoofdstuk 2 – Uitbetaling › § 3 – Rekening": de opbouw boven een artikel, uit de bronboom met de titels uit de graaf."""
    delen = []
    for d in plaats:
        naam = " ".join(filter(None, [_SOORT.get(d.soort, d.soort), d.nummer])) or d.soort
        delen.append(f"{naam} – {d.titel}" if d.titel else naam)
    return " › ".join(delen)


def _publicatie(bron: str) -> str:
    m = re.fullmatch(r"(Stb|Stcrt|Trb)\.\s*(\d{4})-(\d+)", bron)
    return f"{m[1]}. {m[2]}, {m[3]}" if m else bron


def _artikelmeta(a: Artikel) -> list[Regel]:
    delen = []
    if a.inwerking:
        delen.append(f"in werking sinds {datum(a.inwerking)}")
    if a.gewijzigd_bij:
        delen.append(f"laatst gewijzigd bij {_publicatie(a.gewijzigd_bij)}")
    tekst = " · ".join(delen)
    return [("Meta", tekst[:1].upper() + tekst[1:] + ".")] if delen else []


def _bepaling(b: Bepaling) -> list[Regel]:
    uit: list[Regel] = [("Meta", f"{b.vindplaats.label} · rol {_BRONROL.get(b.rol, b.rol)} · {_verwijzing(b.vindplaats)}")]
    if b.bron_gewijzigd:
        uit.append(("Waarschuwing", "Deze bron veranderde sinds de selectie."))
    if b.tekst:
        if b.spans:
            # De markeringen gaan als eigen regel vlak vóór het citaat mee; zo blijft elke regel (stijl, tekst).
            uit.append((SPANS, json.dumps([[x.start, x.eind, x.nr, x.klasse] for x in b.spans], ensure_ascii=False)))
        uit.append(("Citaat", b.tekst))
    in_tekst = {x.nr for x in b.spans}
    for m in b.markeringen:
        uit += _markering(m, b.vindplaats.iri, m.nr in in_tekst)
    uit += [("Meta", _verwijst(v)) for v in b.verwijzingen]
    return uit


def _verwijst(v: Verwijzing) -> str:
    return (f"Verwijst naar {v.naar.label}" + (f" (“{v.anker}”)" if v.anker else "")
            + (" · in dit dossier" if v.in_dossier else "") + ("" if v.in_graaf else " · niet in de kennisgraaf"))


def samenhang_regels(w: Wettekst) -> list[Regel]:
    """Bijlage: de verwijzingen uit het dossier, eerst die binnen het dossier blijven, dan die naar buiten wijzen."""
    uit: list[Regel] = [("Meta", "Uit de kennisgraaf: de verwijzingen die vertrekken uit een bepaling in dit dossier, met de verwijzende "
                                 "tekst letterlijk. Verwijzingen naar deze bepalingen vanuit andere regelingen staan er niet in.")]
    if not w.verwijzingen_volledig:
        uit.append(("Waarschuwing", "Deze lijst is onvolledig: de kennisgraaf gaf meer verwijzingen dan het rapport opneemt. "
                                    "De aantallen hieronder zijn dus een ondergrens."))
    for binnen, kop in ((True, "Binnen het dossier"), (False, "Naar buiten het dossier")):
        groep = [v for v in w.verwijzingen if v.in_dossier == binnen]
        uit.append(("Heading2", f"{kop} ({'' if w.verwijzingen_volledig else 'minstens '}{len(groep)})"))
        if not groep:
            uit.append(("Meta", "Geen."))
        for v in groep:
            uit += [*BLOK, ("BodyText", f"{v.van.label} → {v.naar.label}")]
            if v.anker:
                uit.append(("Citaat", f"“{v.anker}”"))
            uit += [("Meta", _verwijzing(v.naar)), *BLOK_UIT]
    return uit


def context_regels(w: Wettekst) -> list[Regel]:
    """Bijlage: de tekst van de bepalingen die alleen context geven. Ze dragen geen markering, dus ze horen niet in de analyse."""
    uit: list[Regel] = [("Meta", "Bepalingen die als context zijn opgenomen en geen markering dragen, letterlijk uit de bron.")]
    regelingen = [r for r in w.regelingen if r.context]
    if not regelingen:
        uit.append(("Meta", "Er zijn geen contextbepalingen zonder markering."))
    for r in regelingen:
        uit.append(("Heading2", r.titel))
        for a in r.context:
            if a.plaats:
                uit.append((PLAATS, _plaats(a.plaats)))
            uit.append(("Heading3", a.kop))
            uit += _artikelmeta(a)
            for b in a.bepalingen:
                uit += _bepaling(b)
    return uit


def _passage(p: Passage) -> list[Regel]:
    uit: list[Regel] = [("Citaat", f"“{p.tekst}”"),
                        ("Meta", " · ".join(filter(None, [p.vindplaats.label, _verwijzing(p.vindplaats), p.klasse, _KOPPELROL.get(p.rol, p.rol),
                                                          "passage " + _BEOORDELING.get(p.beoordeling, p.beoordeling),
                                                          None if p.annotatie_beoordeeld else "annotatie nog niet beoordeeld"])))]
    if p.motivatie:
        uit.append(("Meta", "Motivatie: " + p.motivatie))
    if p.beoordeeld_door:
        uit.append(("Meta", f"Beoordeeld door {p.beoordeeld_door} op {datum(p.beoordeeld_op)}."))
    if p.actualiteit != "actueel":
        uit.append(("Waarschuwing", f"Na bevestiging: {_ACTUALITEIT.get(p.actualiteit, p.actualiteit)}. Toen: “{p.tekst}”"
                    + (f" Nu: “{p.nu}”" if p.nu is not None else "")))
    return uit


def _begrip(b: Begrip) -> list[Regel]:
    """Eén begrip op een eigen pagina: elke pagina heeft dezelfde kopjes in dezelfde volgorde, ook als er niets staat."""
    meta = [_BEGRIPSTATUS.get(b.status, b.status)]
    if b.generiek:
        meta.append("generiek begrip, gebruikt in dit werkgebied")
    uit: list[Regel] = [(BEGRIP, b.naam), ("Meta", " · ".join(meta))]
    if b.alternatieve_termen:
        uit.append(("BodyText", "Ook genoemd: " + ", ".join(b.alternatieve_termen)))

    uit.append(("Heading4", "Definitie"))
    if b.definitie.strip():
        aard = [_DEFINITIE.get(b.definitie_herkomst, "definitie"), _DEFINITIE_DOOR.get(b.definitie_door, "")]
        uit += [("Citaat" if b.definitie_herkomst == "letterlijk" else "BodyText", b.definitie), ("Meta", ", ".join(filter(None, aard)) + ".")]
        if b.definitie_vindplaats:
            uit.append(("Meta", f"Vindplaats: {b.definitie_vindplaats.label} · {_verwijzing(b.definitie_vindplaats)}"))
    else:
        uit.append(("Meta", _LEEG))
    uit += [("Heading4", "Uitleg"), *(alinea(b.uitleg) or [("Meta", _LEEG)])]
    uit += [("Heading4", "Toelichting"), *(alinea(b.toelichting) or [("Meta", _LEEG)])]
    uit.append(("Heading4", "Voorbeelden"))
    uit += [("BodyText", f"{_OORDEEL.get(v.oordeel, v.oordeel).capitalize()}: {v.tekst}") for v in b.voorbeelden] or [("Meta", _LEEG)]

    uit.append(("Heading4", "Waarop de definitie rust"))
    if b.fragmenten:
        if b.onderbouwing_aangepast:
            uit.append(("Meta", "De analist paste de definitie aan; deze fragmenten waren het vertrekpunt."))
        for f in b.fragmenten:
            uit += [("Citaat", f"“{f.tekst}”"), ("Meta", f"{f.vindplaats.label} · {_verwijzing(f.vindplaats)}")]
    else:
        uit.append(("Meta", "Geen fragmenten vastgelegd."))

    uit.append(("Heading4", "Passages"))
    if b.passages:
        uit.append(("Meta", meervoud(len(b.passages), "passage", "passages")))
        for p in b.passages:
            uit += _passage(p)
    else:
        uit.append(("Meta", "Geen passages gekoppeld."))

    uit.append(("Heading4", "Relaties"))
    uit += [("BodyText", f"{r.van} {_RELATIE.get(r.type, r.type)} {r.naar}" + (f": {r.toelichting}" if r.toelichting else ""))
            for r in b.relaties] or [("Meta", "Geen relaties vastgelegd.")]

    uit.append(("Heading4", "Nog open"))
    uit += [("Waarschuwing", p) for p in b.open_punten] or [("Meta", "Geen open punten.")]

    uit.append(("Heading4", "Beoordeling"))
    if b.status == "geaccordeerd":
        uit.append(("Meta", f"Geaccordeerd door {b.geaccordeerd_door} op {datum(b.geaccordeerd_op)}" + (f". Reden: {b.reden}" if b.reden else ".")))
    elif b.vervangen:
        uit.append(("Meta", "Vervangen door een opvolger; dit begrip is alleen nog te lezen."))
    else:
        uit.append(("Meta", "Nog niet geaccordeerd."))
    return uit


def begrippenlijst_regels(d: Begrippen) -> list[Regel]:
    """Hoofdstuk 6: de geaccordeerde begrippen met hun definitie. De volledige kaarten staan in de bijlage."""
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "6. Begrippen"),
                        ("Meta", "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities.")]
    akkoord = [b for b in d.begrippen if b.status == "geaccordeerd"]
    if not akkoord:
        uit.append(("Meta", "Er zijn nog geen geaccordeerde begrippen."))
    for b in akkoord:
        uit += [*BLOK, ("Heading4", b.naam)]
        if b.definitie.strip():
            uit.append(("Citaat" if b.definitie_herkomst == "letterlijk" else "BodyText", b.definitie))
            if b.definitie_vindplaats:
                uit.append(("Meta", f"Vindplaats: {b.definitie_vindplaats.label} · {_verwijzing(b.definitie_vindplaats)}"))
        else:
            uit.append(("Meta", "Nog geen definitie."))
        uit += BLOK_UIT
    rest = len(d.begrippen) - len(akkoord)
    if rest:
        uit.append(("Meta", meervoud(rest, "begrip is", "begrippen zijn") + " nog niet geaccordeerd of vervangen; "
                    "ze staan met de volledige kaarten in de bijlage Begripskaarten."))
    elif akkoord:
        uit.append(("Meta", "De volledige kaarten staan in de bijlage Begripskaarten."))
    return uit


def begrippen_regels(d: Begrippen) -> list[Regel]:
    """Bijlage: elk begrip op een eigen pagina, op status."""
    uit: list[Regel] = [("Meta", "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities.")]
    if not d.begrippen:
        uit.append(("Meta", "Dit werkgebied heeft nog geen begrippen."))
    # Een groepskop staat boven zijn eerste begrip, dus de breuk komt vóór de kop en niet erna: een kop blijft nooit alleen.
    eerste_groep = True
    for status, kop in (("geaccordeerd", "Geaccordeerde begrippen"), ("concept", "Conceptbegrippen"), ("vervangen", "Vervangen begrippen")):
        groep = [b for b in d.begrippen if b.status == status]
        if not groep:
            continue
        if not eerste_groep:
            uit.append((PAGINA, ""))
        eerste_groep = False
        uit.append(("Heading2", f"{kop} ({len(groep)})"))
        if status == "concept":
            uit.append(("Meta", "Nog niet geaccordeerd: de inhoud kan veranderen."))
        for n, b in enumerate(groep):
            if n:
                uit.append((PAGINA, ""))
            uit += _begrip(b)
    return uit


def open_begrippen_regels(d: Begrippen) -> list[Regel]:
    uit: list[Regel] = [("Heading2", "Open voorstellen van Lex voor begrippen")]
    if not d.open_groepen and not d.open_relaties:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    for g in d.open_groepen:
        uit.append(("Voorstel", f"Voorstel voor een begrip: {g.naam}" + (f". Definitie: {g.definitie}" if g.definitie else "")))
        uit += [("Meta", f"“{f.tekst}” · {f.vindplaats.label} · {_verwijzing(f.vindplaats)}") for f in g.leden]
    uit += [("Voorstel", f"Voorstel voor een relatie: {r.van} {_RELATIE.get(r.type, r.type)} {r.naar}") for r in d.open_relaties]
    return uit


def register_regels(v: Voorblad, ver: Verantwoording) -> list[Regel]:
    """Bijlage: elke regeling met haar toestand, en elke bronselectie met haar volledige bronreferentie."""
    uit: list[Regel] = [("Heading2", "Regelingen")]
    if not v.regelingen:
        uit.append(("Meta", "Er zijn geen regelingen in dit werkgebied."))
    for r, regel in zip(v.regelingen, bronstand_regels(v)[1:]):
        uit += [*BLOK, ("BodyText", regel[1])]
        if r.url:
            uit.append(("Meta", "Op wetten.overheid.nl: " + r.url))
        if r.toestand_url:
            uit.append(("Meta", "Toestand in de graaf: " + r.toestand_url))
        if r.organisatie:
            uit.append(("Meta", "Organisatie (TOOI): " + r.organisatie))
        uit += BLOK_UIT
    uit.append(("Heading2", "Bronselecties"))
    if not ver.bronnen:
        uit.append(("Meta", "Er zijn geen bronnen geselecteerd."))
    for s in ver.bronnen:
        uit += [*BLOK, ("BodyText", s.vindplaats.label), ("Meta", f"Rol {_BRONROL.get(s.rol, s.rol)} · {_verwijzing(s.vindplaats)}")]
        if s.toegevoegd_door:
            uit.append(("Meta", f"Opgenomen door {s.toegevoegd_door} op {datum(s.toegevoegd)}."))
        uit += BLOK_UIT
    return uit


def verantwoording_regels(v: Verantwoording) -> list[Regel]:
    uit: list[Regel] = [("Heading2", "Wie deed wat"),
                        ("BodyText", f"Aangemaakt door {v.aangemaakt_door} op {datum(v.aangemaakt)}, laatst gewijzigd op {datum(v.gewijzigd)}.")]
    if v.juristen:
        uit.append(("BodyText", "Markeringen beoordeeld door: " + ", ".join(v.juristen) + "."))
    if v.accordeurs:
        uit.append(("BodyText", "Begrippen geaccordeerd door: " + ", ".join(v.accordeurs) + "."))
    uit += [("Heading2", "Handelingen in dit werkgebied"),
            ("Meta", meervoud(sum(h.aantal for h in v.handelingen), "handeling", "handelingen") + " in de audit, per soort:")]
    uit += [("Meta", f"{h.actie.replace('-', ' ')}: {h.aantal}") for h in v.handelingen]
    uit.append(("Heading2", "Besluitenlog"))
    if v.besluiten:
        uit.append(("Meta", "De beslissende handelingen, oudste eerst. Het werk van Lex zelf (zoeken, voorstellen) staat hierboven geteld."))
    else:
        uit.append(("Meta", "Er zijn nog geen besluiten vastgelegd."))
    for b in v.besluiten:
        uit.append(("BodyText", f"{datum_tijd(b.op)} · {b.door} · {_BESLUIT.get(b.actie, b.actie.replace('-', ' '))}"
                    + (f": {b.onderwerp}" if b.onderwerp else "")))
        if b.reden:
            uit.append(("Meta", "Reden: " + b.reden))
    return uit


BIJLAGEN = ("Begripskaarten", "Bronnenregister", "Contextbepalingen", "Samenhang", "Niet meegenomen", "Verantwoording")


def rapport_regels(r: Rapport) -> list[Regel]:
    """Het hele rapport als (stijl, tekst), de vorm die elke uitvoer leest. Vooraan de analyse, achteraan de naslag."""
    bijlagen = {"Begripskaarten": begrippen_regels(r.begrippen),
                "Bronnenregister": register_regels(r.voorblad, r.verantwoording),
                "Contextbepalingen": context_regels(r.wettekst),
                "Samenhang": samenhang_regels(r.wettekst),
                "Niet meegenomen": niet_meegenomen_regels(r.deelvragen, r.wettekst, r.begrippen),
                "Verantwoording": verantwoording_regels(r.verantwoording)}
    uit = [*titelblad_regels(r.document, r.voorblad, r.stand), *colofon_regels(r.document, r.voorblad, r.stand, r.verantwoording),
           (PAGINA, ""), ("Heading4", "Inhoud"), (INHOUD, ""), *samenvatting_regels(r.samenvatting, r.voorblad, r.deelvragen),
           *leeswijzer_regels(), *dossier_regels(r.dossier), *deelvragen_regels(r.deelvragen), *wettekst_regels(r.wettekst),
           *begrippenlijst_regels(r.begrippen)]
    for letter, naam in zip("ABCDEFGH", BIJLAGEN):
        uit += [(PAGINA, ""), ("Heading1", f"Bijlage {letter}. {naam}"), *bijlagen[naam]]
    return uit
