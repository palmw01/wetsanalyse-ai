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

from .pdf_opmaak import BEGRIP, BLOK_BEGIN, BLOK_EIND, INHOUD, MARKERING, PAGINA

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


class Markering(_Deel):
    id: str
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
    door: Door = "bron"


class Artikel(_Deel):
    kop: str
    bepalingen: list[Bepaling]


class Regeling(_Deel):
    bwb_id: str
    titel: str
    artikelen: list[Artikel] = []


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
    bronnen: list[Selectie] = []


class Rapport(_Deel):
    schema_naam: Literal["werkgebied-rapport-v1"] = SCHEMA
    versie: int = VERSIE
    stand: Stand
    voorblad: Voorblad
    dossier: Dossier
    deelvragen: Deelvragen
    wettekst: Wettekst
    begrippen: Begrippen
    verantwoording: Verantwoording


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
              "rejected": "afgewezen", "reused": "hergebruikt, nog niet beoordeeld"}
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
_LEEG = "Niet ingevuld."
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
        for b in v.bronnen:
            uit += [("BodyText", f"{b.vindplaats.label} · {_BRONROL.get(b.rol, b.rol)}" + (f": {b.reden}" if b.reden else "")),
                    ("Meta", _verwijzing(b.vindplaats))]
        if v.niet_gekozen:
            uit.append(("Meta", meervoud(v.niet_gekozen, "voorstel van Lex is niet gekozen.", "voorstellen van Lex zijn niet gekozen.")))
        uit += BLOK_UIT

    uit.append(("Heading2", "Uitgesloten bronnen"))
    if not d.uitgesloten:
        uit.append(("Meta", "Er zijn geen bronnen uitgesloten."))
    for k in d.uitgesloten:
        waar = "alle deelvragen" if k.overal else "deelvraag " + ", ".join(map(str, k.nrs))
        uit.append(("BodyText", f"{k.vindplaats.label} · uitgesloten voor {waar}" + (f" door {k.besloten_door}" if k.besloten_door else "")
                    + f". Reden: {k.reden or 'niet vastgelegd'}"))
        uit.append(("Meta", _verwijzing(k.vindplaats)))

    uit.append(("Heading2", "Open voorstellen van Lex"))
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


def _markering(m: Markering, eigen_iri: str = "") -> list[Regel]:
    # Een terugval draagt geen klasse: zeg dat, en noem de keuze.
    kop = m.klasse or "Nog geen klasse (" + ", ".join(m.alternatieven) + ")"
    if m.subtype:
        kop += f", {m.subtype}"
    uit: list[Regel] = [*BLOK, (MARKERING + m.klasse, f"{kop} · {_LIFECYCLE.get(m.lifecycle, m.lifecycle)}"), ("Citaat", f"“{m.tekst}”")]
    uit += [("Meta", f"Vindplaats: {v.label} · {_verwijzing(v)}") for v in m.vindplaatsen if v.iri != eigen_iri]
    if m.toelichting:
        uit.append(("BodyText", m.toelichting))
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
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "3. Wettekst en annotaties"),
                        ("BodyText", f"{meervoud(w.markeringen, 'markering', 'markeringen')}, waarvan {w.beoordeeld} "
                                     f"beoordeeld door een jurist; {len(w.afgewezen)} afgewezen.")]
    uit += [("Meta", f"{k.klasse or 'Nog geen klasse'}: {k.aantal}") for k in w.per_klasse]
    for r in w.regelingen:
        uit += [(PAGINA, ""), ("Heading2", r.titel)]
        for a in r.artikelen:
            uit.append(("Heading3", a.kop))
            for b in a.bepalingen:
                uit.append(("Meta", f"{b.vindplaats.label} · rol {_BRONROL.get(b.rol, b.rol)} · {_verwijzing(b.vindplaats)}"))
                if b.bron_gewijzigd:
                    uit.append(("Waarschuwing", "Deze bron veranderde sinds de selectie."))
                if b.tekst:
                    uit.append(("Citaat", b.tekst))
                for m in b.markeringen:
                    uit += _markering(m, b.vindplaats.iri)
    for o in w.onbereikbaar:
        uit += [("Heading3", o.label), ("Waarschuwing", f"De tekst ontbreekt: {o.reden}")]
    if w.buiten_tekst:
        uit += [(PAGINA, ""), ("Heading2", "Markeringen buiten de getoonde tekst")]
        for m in w.buiten_tekst:
            uit += _markering(m)
    uit += [(PAGINA, ""), ("Heading2", "Afgewezen markeringen"),
            ("Meta", "Deze markeringen verwierp een jurist; ze horen niet tot de analyse." if w.afgewezen else "Er zijn geen markeringen afgewezen.")]
    for m in w.afgewezen:
        uit += _markering(m)
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


def begrippen_regels(d: Begrippen) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "4. Begrippen"),
                        ("Meta", "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities.")]
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
    if d.begrippen:
        uit.append((PAGINA, ""))
    uit.append(("Heading2", "Open voorstellen van Lex"))
    if not d.open_groepen and not d.open_relaties:
        uit.append(("Meta", "Er staan geen voorstellen open."))
    else:
        uit.append(("Meta", "Hierover is nog geen besluit genomen; ze horen niet tot de analyse."))
    for g in d.open_groepen:
        uit.append(("Voorstel", f"Voorstel voor een begrip: {g.naam}" + (f". Definitie: {g.definitie}" if g.definitie else "")))
        uit += [("Meta", f"“{f.tekst}” · {f.vindplaats.label} · {_verwijzing(f.vindplaats)}") for f in g.leden]
    uit += [("Voorstel", f"Voorstel voor een relatie: {r.van} {_RELATIE.get(r.type, r.type)} {r.naar}") for r in d.open_relaties]
    return uit


def verantwoording_regels(v: Verantwoording) -> list[Regel]:
    uit: list[Regel] = [(PAGINA, ""), ("Heading1", "5. Verantwoording"), ("Heading2", "Wie deed wat"),
                        ("BodyText", f"Aangemaakt door {v.aangemaakt_door} op {datum(v.aangemaakt)}, laatst gewijzigd op {datum(v.gewijzigd)}.")]
    if v.juristen:
        uit.append(("BodyText", "Markeringen beoordeeld door: " + ", ".join(v.juristen) + "."))
    if v.accordeurs:
        uit.append(("BodyText", "Begrippen geaccordeerd door: " + ", ".join(v.accordeurs) + "."))
    uit += [("Heading2", "Handelingen in dit werkgebied"),
            ("Meta", meervoud(sum(h.aantal for h in v.handelingen), "handeling", "handelingen") + " in de audit, per soort:")]
    uit += [("Meta", f"{h.actie.replace('-', ' ')}: {h.aantal}") for h in v.handelingen]
    uit.append(("Heading2", "Bronnen"))
    for s in v.bronnen:
        uit += [("BodyText", s.vindplaats.label), ("Meta", f"Rol {_BRONROL.get(s.rol, s.rol)} · {_verwijzing(s.vindplaats)}")]
        if s.toegevoegd_door:
            uit.append(("Meta", f"Opgenomen door {s.toegevoegd_door} op {datum(s.toegevoegd)}."))
    return uit


def rapport_regels(r: Rapport) -> list[Regel]:
    """Het hele rapport als (stijl, tekst), de vorm die elke uitvoer leest."""
    return [*voorblad_regels(r.voorblad, r.stand), (PAGINA, ""), ("Heading4", "Inhoud"), (INHOUD, ""), *dossier_regels(r.dossier),
            *deelvragen_regels(r.deelvragen), *wettekst_regels(r.wettekst), *begrippen_regels(r.begrippen),
            *verantwoording_regels(r.verantwoording)]
