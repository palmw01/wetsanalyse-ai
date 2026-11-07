"""Het rapport van een werkgebied: één gestructureerd document waaruit PDF en Markdown komen (ADR-009).

`werkgebied_export.bouw_rapport` vult het uit de stand; `rapport_regels` maakt er (stijl, tekst)-regels van. Het document
draagt codes en ISO-datums, zodat het als JSON bruikbaar is. Alle woorden, labels en de volgorde staan hier, dus de
uitvoervormen kunnen inhoudelijk niet uit elkaar lopen.

`door` zegt van wie de inhoud komt: `bron` (letterlijk uit de wettekst), `lex` (een voorstel) of `analist`.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from bronmodel.antwoord import Vindplaats
from pydantic import BaseModel, ConfigDict

from .pdf_opmaak import BLOK_BEGIN, BLOK_EIND, PAGINA

VERSIE = 1
SCHEMA = "werkgebied-rapport-v1"

Regel = tuple[str, str]
Door = Literal["bron", "lex", "analist"]


class _Deel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Stand(_Deel):
    op: str
    door: str


class Bronstand(_Deel):
    """Welke toestand van een regeling in het dossier staat."""

    bwb_id: str
    citeertitel: str
    geldig_vanaf: str | None = None
    geldig_tot: str | None = None


class Signaal(_Deel):
    """Wat een lezer moet weten voor hij het rapport gebruikt. Dezelfde punten staan ook op hun plek."""

    soort: Literal["niet_in_dossier", "bron_veranderd", "toestand_onvolledig", "na_peildatum", "markeringen_veranderd",
                   "passages_veranderd", "opnieuw_bekijken", "zoeken_onvolledig"]
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
    regelingen: list[Bronstand] = []
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
    label: str
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
    label: str
    overal: bool = False
    nrs: list[int] = []
    besloten_door: str = ""
    reden: str = ""
    door: Door = "analist"


class Bronvoorstel(_Deel):
    label: str
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


_DOSSIER = {"aanleiding": "Aanleiding", "context": "Context", "doel": "Doel", "analysevraag": "Analysevraag",
            "praktijkvoorbeeld": "Praktijkvoorbeeld", "afbakening": "Afbakening", "gebeurtenis": "Gebeurtenis"}
DOSSIERVELDEN = tuple(_DOSSIER)
_WERKGEBIED_STATUS = {"in_voorbereiding": "In voorbereiding", "actief": "Actief", "afgerond": "Afgerond"}
_VOORTGANG = {"niet_gestart": "Nog niet gestart", "in_behandeling": "In behandeling",
              "voorlopig_afgerond": "Voorlopig afgerond", "beoordeeld": "Beoordeeld"}
_BRONROL = {"analyseren": "analyseren", "context": "context"}
_KANDIDAATROL = {"kern": "kernbepaling", "afhankelijkheid": "afhankelijkheid", "aanverwant": "aanverwant"}
_ZONE = ZoneInfo("Europe/Amsterdam")
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")

BLOK: tuple[Regel, ...] = ((BLOK_BEGIN, ""),)
BLOK_UIT: tuple[Regel, ...] = ((BLOK_EIND, ""),)


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
    return "Het zoeken naar bronnen is onvolledig of verouderd; zie deel 2."


def voorblad_regels(v: Voorblad, stand: Stand) -> list[Regel]:
    uit: list[Regel] = [("Title", v.naam), ("Subtitle", "Wetsanalyse: dossier van het werkgebied")]
    if v.analysevraag:
        uit.append(("BodyText", "Analysevraag: " + v.analysevraag))
    uit.append(("BodyText", f"Status: {_WERKGEBIED_STATUS.get(v.status, v.status)} · revisie {v.revisie}"))
    if v.thema:
        uit.append(("BodyText", "Thema: " + v.thema))
    uit.append(("BodyText", "Peildatum: " + (datum(v.peildatum) or "niet vastgelegd") + (" (de aanmaakdag)" if v.peildatum_standaard else "")))
    uit.append(("BodyText", f"Stand van {datum(stand.op)}, geëxporteerd door {stand.door}."))
    if v.regelingen:
        uit.append(("Heading4", "Bronstand per regeling"))
        for r in v.regelingen:
            # De graaf zet een regeling zonder einde op 9999-12-31.
            tot = f" tot {datum(r.geldig_tot)}" if r.geldig_tot and r.geldig_tot < "9999" else ""
            vanaf = f"geldt vanaf {datum(r.geldig_vanaf)}{tot}" if r.geldig_vanaf else "geldigheid onbekend"
            uit.append(("Meta", f"{r.citeertitel} ({r.bwb_id}): {vanaf}"))
    if v.signalen:
        uit.append(("Heading4", "Let op"))
        uit += [("Waarschuwing", _signaal(s)) for s in v.signalen]
    uit += [("Heading4", "Zo lees je dit dossier"),
            ("Meta", "Dit is een analyse-uitkomst, geen wettelijke definitie en geen juridisch oordeel. De wettekst is "
                     "letterlijk overgenomen uit de kennisgraaf, die gevuld is uit de officiële publicatie. Bij elke "
                     "bepaling staat de vindplaats en de bronreferentie (jci)."),
            ("Meta", "Lex stelt voor, de jurist beslist. Beoordeeld of geaccordeerd betekent dat een jurist het bevestigde. "
                     "Voorstel en concept zijn nog niet bevestigd; afgewezen en uitgesloten zijn bewust niet meegenomen.")]
    return uit


def dossier_regels(d: Dossier) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "1. Dossier")]
    for v in d.velden:
        uit.append(("Heading4", _DOSSIER[v.veld]))
        uit += alinea(v.tekst) or [("Meta", "Niet ingevuld.")]
    if d.zoekbereik:
        uit.append(("Heading4", "Zoekbereik"))
        uit += [("BodyText", f"{r.label or r.bwb_id} ({r.bwb_id})") for r in d.zoekbereik]
    return uit


def deelvragen_regels(d: Deelvragen) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "2. Deelvragen en bronnen")]
    for v in d.deelvragen:
        uit += [*BLOK, ("Heading2", "Analysevraag" if d.modus == "analysevraag" else f"Deelvraag {v.nr}"), ("BodyText", v.vraag)]
        stand = "Opnieuw bekijken" if v.opnieuw_bekijken else _VOORTGANG.get(v.status, v.status)
        uit.append(("Meta", f"Stand: {stand} · {meervoud(len(v.bronnen), 'bron', 'bronnen')}"))
        if v.opnieuw_bekijken:
            uit.append(("Waarschuwing", "De scope veranderde na het afronden; deze deelvraag moet opnieuw bekeken worden."))
        uit += [("Waarschuwing", "Open punt: " + p) for p in v.open_punten]
        uit += [("BodyText", f"{b.label} · {_BRONROL.get(b.rol, b.rol)}" + (f": {b.reden}" if b.reden else "")) for b in v.bronnen]
        if v.niet_gekozen:
            uit.append(("Meta", meervoud(v.niet_gekozen, "voorstel van Lex is niet gekozen.", "voorstellen van Lex zijn niet gekozen.")))
        uit += BLOK_UIT

    uit.append(("Heading2", "Uitgesloten bronnen"))
    if not d.uitgesloten:
        uit.append(("Meta", "Er zijn geen bronnen uitgesloten."))
    for k in d.uitgesloten:
        waar = "alle deelvragen" if k.overal else "deelvraag " + ", ".join(map(str, k.nrs))
        uit.append(("BodyText", f"{k.label} · uitgesloten voor {waar}" + (f" door {k.besloten_door}" if k.besloten_door else "")
                    + f". Reden: {k.reden or 'niet vastgelegd'}"))

    uit.append(("Heading2", "Open voorstellen van Lex"))
    if not d.open_vragen and not d.open_bronnen:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    uit += [("Voorstel", "Voorstel voor een deelvraag: " + v) for v in d.open_vragen]
    for k in d.open_bronnen:
        waar = f" · deelvraag {', '.join(map(str, k.nrs))}" if k.nrs else " · bij geen deelvraag"
        uit.append(("Voorstel", f"Voorstel voor een bron: {k.label} · {_KANDIDAATROL.get(k.rol, k.rol)}{waar}"))

    if d.zoekdekking:
        uit.append(("Heading2", "Zoekdekking"))
        uit.append(("BodyText", "Lex heeft gezocht"
                    + (", maar niet alles kon worden doorzocht: " + ", ".join(d.zoekdekking.onvolledig) + "." if d.zoekdekking.onvolledig else ".")))
        if d.zoekdekking.verouderd:
            uit.append(("Waarschuwing", "Het werkgebied veranderde na het zoeken."))
        if d.zoekdekking.reden:
            uit.append(("Meta", d.zoekdekking.reden))
    return uit
