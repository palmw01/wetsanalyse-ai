"""Welke regeling noemt de vraag die niet in de kennisgraaf staat? (connector `wetgeving_live`, ADR-013 fase 1e)

De graaf kent zijn eigen regelingen bij naam en afkorting (`overzicht.regelingen_in_vraag`). Een andere wet ("artikel 31
van de Participatiewet", "art. 7:610 BW", "artikel 1 Pw") kende Lex niet: het model zocht in de graaf, vond niets, en
moest zelf bedenken of de wet bestaat. Deze module beslist dat in code, vóór het model, en alleen als de connector in deze
beurt aanstaat (anders gaat er geen verzoek naar overheid.nl):

1. **Kandidaten uit de vraag** met vaste vormen: een samenstelling op -wet of -wetboek ("Participatiewet", "Gemeentewet
   2026"), een titel die met "Wet" begint ("Wet langdurige zorg"), een artikel van een boek van het BW ("7:610 BW") en een
   afkorting direct na een artikel ("artikel 1 Pw"). Een kandidaat die de graaf bij naam kent, valt af.
2. **Opzoeken bij de zoekdienst van de BWB**: de afkorting exact, de titel als woordgroep. Een kandidaat telt alleen bij een
   exact gelijke titel, of bij één regeling met die afkorting. Meer regelingen met dezelfde afkorting is **dubbelzinnig**:
   dan kiest de code niet, maar vraagt Lex welke bedoeld is.
3. **Staat hij in de graaf?** (`wetgeving_tools.graaftoestanden`). Zo ja, dan doet de rest niets: de graaftools lezen hem.

Een storing (de zoekdienst, de graaf) kost alleen de herkenning: het model zoekt dan zelf, met de toolfout `niet_in_graaf`
en `zoek_regelingen` als vangnet. Herkennen is nooit raden: geen treffer is geen regeling.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

#: Hoogstens zo veel kandidaten zoekt de code op; meer is een overzichtsvraag, en die zoekt het model.
MAX_KANDIDATEN = 3

_SAMENSTELLING_RE = re.compile(r"(?<![\w-])(?P<naam>[A-Z][a-zà-ÿ]+(?:wet|wetboek)(?:\s+(?:19|20)\d{2})?)(?![\w-])")
#: Waar de titel van een wet ophoudt: een voegwoord, een werkwoord of een vindplaats. "op", "tot", "de" en "van" horen er
#: juist in ("Wet op de loonbelasting 1964", "Wet tot ...").
_STOP = (r"(?:en|of|in|over|bij|voor|met|is|zijn|wordt|worden|was|staat|staan|stond|zegt|zei|regelt|bepaalt|geldt|gold|"
         r"wat|die|dat|lid|artikel|art|opgebouwd|gewijzigd|geregeld|bedoeld|genoemd|ingevoerd)")
_WET_RE = re.compile(rf"(?<![\w-])(?P<naam>Wet\s+(?:(?!{_STOP}\b)[A-Za-zà-ÿ0-9][\w.-]*\s+){{0,7}}?"
                     rf"(?!{_STOP}\b)[A-Za-zà-ÿ0-9][\w.-]*)(?=\s*(?:[?!,;:()]|\.(?:\s|$)|$)|\s+{_STOP}\b)")
_BW_RE = re.compile(r"(?<![\w:])(?P<boek>[1-8]|10):(?P<artikel>\d+[a-z]*)(?:\s*,?\s*lid\s+\d+[a-z]*)?\s*"
                    r"(?:van\s+het\s+)?(?:BW|Burgerlijk\s+Wetboek)\b", re.IGNORECASE)
_AFK_RE = re.compile(r"\bart(?:ikel|\.)\s*(?P<artikel>\d+[a-z]*(?:\.\d+[a-z]*)*)(?:\s*,?\s*(?:lid|eerste|tweede)\s*\w*)?"
                     r"\s+(?:van\s+de\s+|van\s+het\s+)?(?P<naam>[A-Z][A-Za-z]{1,6}(?:\s(?:19|20)\d{2})?)(?![\w-])")
#: Een afkorting als lidwoord + korte naam ("de Wlz", "de Awb"), ook zonder artikel.
_LOS_AFK_RE = re.compile(r"\b(?:de|het)\s+(?P<naam>[A-Z][a-z]{0,2}[A-Za-z]{1,3}(?:\s(?:19|20)\d{2})?)(?![\w-])")
#: Korte woorden met een hoofdletter die geen afkorting van een regeling zijn.
_GEEN_AFK = frozenset({"hoge", "raad", "staat", "kamer", "rijk", "wet", "eu", "bv", "nv", "vof"})
_ARTIKEL_RE = re.compile(r"\bart(?:ikel|\.)\s*(?P<artikel>\d+[a-z]*(?:[.:]\d+[a-z]*)*)", re.IGNORECASE)
_LID_RE = re.compile(r"\blid\s+(?P<lid>\d+[a-z]*)\b", re.IGNORECASE)
#: Woorden die als kandidaat voorkomen maar geen regeling zijn.
_GEEN = frozenset({"wet", "de wet", "deze wet", "die wet", "wetboek"})


@dataclass(frozen=True)
class Genoemd:
    """Een regeling die de vraag noemt en die niet in de kennisgraaf staat (of: dubbelzinnig is)."""

    naam: str
    bwb_id: str = ""
    titel: str = ""
    #: Het artikel dat de vraag bij deze regeling noemt, als dat eenduidig is.
    artikel: str = ""
    lid: str = ""
    #: Bij een afkorting die bij meer regelingen past: (bwb_id, titel) van elk.
    kandidaten: tuple[tuple[str, str], ...] = field(default=())

    @property
    def dubbelzinnig(self) -> bool:
        return not self.bwb_id and len(self.kandidaten) > 1


def _kandidaten(vraag: str) -> list[tuple[str, str, str]]:
    """(naam, titel om op te zoeken, artikel) in de volgorde van de vraag, ontdubbeld."""
    uit: list[tuple[int, str, str, str]] = []
    for m in _BW_RE.finditer(vraag):
        uit.append((m.start(), f"{m.group('boek')}:{m.group('artikel')} BW", f"Burgerlijk Wetboek Boek {m.group('boek')}",
                    m.group("artikel")))
    for m in _AFK_RE.finditer(vraag):
        uit.append((m.start("naam"), m.group("naam"), m.group("naam"), m.group("artikel")))
    for m in _LOS_AFK_RE.finditer(vraag):
        if m.group("naam").casefold() not in _GEEN_AFK:
            uit.append((m.start("naam"), m.group("naam"), m.group("naam"), ""))
    for patroon in (_SAMENSTELLING_RE, _WET_RE):
        for m in patroon.finditer(vraag):
            # Een jaartal sluit de titel af: "Wet op de loonbelasting 1964 ook" → tot en met 1964.
            naam = re.sub(r"^(.*?\b(?:18|19|20)\d{2})\b.*$", r"\1", m.group("naam"))
            uit.append((m.start("naam"), naam, naam, ""))
    gezien: dict[str, tuple[str, str, str]] = {}
    bezet: list[tuple[int, int]] = []
    for start, naam, titel, artikel in sorted(uit, key=lambda x: (x[0], -len(x[1]))):
        sleutel = titel.casefold()
        if sleutel in _GEEN or sleutel in gezien or any(s <= start < e for s, e in bezet):
            continue
        bezet.append((start, start + len(naam)))
        gezien[sleutel] = (naam, titel, artikel)
    return list(gezien.values())


def _graafnamen(graph: Any) -> set[str]:
    from . import overzicht

    try:
        return {n.casefold() for r in overzicht._regelingen(graph) for n in r["namen"]}
    except Exception:  # noqa: BLE001 – zonder namenlijst telt niets als graafnaam; de graafcontrole volgt nog
        return set()


def _zoek(bron: Any, titel: str, peil: str) -> tuple[list[Any], list[Any]]:
    """(met deze afkorting, met deze titel als woordgroep), geldig op de peildatum."""
    schoon = " ".join(re.sub(r'["\\]', " ", titel).split())
    filt = f"overheidbwb.geldigheidsdatum={peil}"
    afk = [] if len(schoon) > 20 else bron.zoek(f'overheidbwb.afkorting="{schoon}" and {filt}', maximum=20)[1]
    tit = bron.zoek(f'overheidbwb.titel adj "{schoon}" and {filt}', maximum=50)[1]
    return afk, tit


def genoemd(vraag: str, graph: Any, bron: Any, *, vandaag: str) -> list[Genoemd]:
    """De regelingen die de vraag noemt en die niet in de kennisgraaf staan, plus de dubbelzinnige afkortingen. Leeg bij
    een storing: dan zoekt het model zelf."""
    from .tools.wetgeving_tools import GraafOnbekend, graaftoestanden

    kandidaten = _kandidaten(vraag or "")
    if not kandidaten:
        return []
    graafnamen = _graafnamen(graph)
    kandidaten = [k for k in kandidaten if k[0].casefold() not in graafnamen and k[1].casefold() not in graafnamen]
    artikelen = {m.group("artikel") for m in _ARTIKEL_RE.finditer(vraag)}
    leden = {m.group("lid") for m in _LID_RE.finditer(vraag)}
    uit: list[Genoemd] = []
    for naam, titel, artikel in kandidaten[:MAX_KANDIDATEN]:
        try:
            afk, tit = _zoek(bron, titel, vandaag)
        except Exception:  # noqa: BLE001 – een storing kost alleen de herkenning
            logger.warning("regeling buiten de graaf niet opgezocht", extra={"naam": naam}, exc_info=True)
            return []
        exact = [t for t in [*afk, *tit] if t.titel.casefold() == titel.casefold()]
        per_id = {t.bwb_id: t.titel for t in afk}
        if exact:
            gekozen = exact[0]
        elif len(per_id) == 1:
            gekozen = afk[0]
        elif len(per_id) > 1:
            uit.append(Genoemd(naam, kandidaten=tuple(sorted(per_id.items(), key=lambda p: p[1]))))
            continue
        else:
            continue
        uit.append(Genoemd(naam, gekozen.bwb_id, gekozen.titel))
    eenduidig = [g for g in uit if g.bwb_id]
    if eenduidig:
        try:
            in_graaf = graaftoestanden(graph, [g.bwb_id for g in eenduidig])
        except GraafOnbekend:
            return []
        uit = [g for g in uit if not g.bwb_id or in_graaf.get(g.bwb_id) is None]
    # Eén artikel bij één regeling: dat lezen we vooraf. Een artikel uit de vorm zelf ("7:610 BW") gaat voor.
    zonder_dubbel = [g for g in uit if g.bwb_id]
    if len(zonder_dubbel) == 1:
        g = zonder_dubbel[0]
        eigen = next((k[2] for k in kandidaten if k[0] == g.naam and k[2]), "")
        artikel = eigen or (next(iter(artikelen)) if len(artikelen) == 1 else "")
        uit = [Genoemd(g.naam, g.bwb_id, g.titel, artikel.split(":")[-1] if artikel else "",
                       next(iter(leden)) if len(leden) == 1 and artikel else "") if x is g else x for x in uit]
    return uit


def plan_regel(genoemde: list[Genoemd]) -> str:
    """Wat het model over deze regelingen weet, voor het plan van de specialist."""
    regels = [f"{g.titel} ({g.bwb_id})" for g in genoemde if g.bwb_id]
    if not regels:
        return ""
    return ("\nREGELINGEN BUITEN DE KENNISGRAAF: " + "; ".join(regels) + " staan niet in de kennisgraaf. Lees hun tekst "
            "met get_wettekst (of zoek_artikelen voor de opbouw), niet met de graaftools, en zeg in het antwoord dat de "
            "tekst live van overheid.nl komt en niet uit de kennisgraaf; voor een werkgebied of annotatie moet zo'n "
            "regeling eerst geïmporteerd worden.")


def keuzevraag(genoemde: list[Genoemd]) -> str:
    """De vraag terug bij een dubbelzinnige afkorting: welke regeling bedoel je? Leeg als er niets dubbelzinnig is."""
    dubbel = [g for g in genoemde if g.dubbelzinnig]
    if not dubbel:
        return ""
    zinnen = []
    for g in dubbel:
        namen = ", ".join(titel for _, titel in g.kandidaten)
        zinnen.append(f"Met „{g.naam}” kunnen meer regelingen bedoeld zijn: {namen}.")
    return " ".join(zinnen) + " Welke bedoel je? Noem de naam, dan lees ik de tekst."


def leesaanroepen(genoemde: list[Genoemd]) -> list[dict[str, Any]]:
    """De leestool vooraf voor een eenduidig genoemd artikel van een regeling buiten de graaf."""
    return [{"name": "get_wettekst", "input": {"bwb_id": g.bwb_id, "artikel": g.artikel, **({"lid": g.lid} if g.lid else {})}}
            for g in genoemde if g.bwb_id and g.artikel]


def zonder_zoekdienst(vraag: str, graph: Any) -> list[str]:
    """De regelingen die de vraag bij een artikel noemt en die de graaf niet kent, zonder de zoekdienst van de BWB: voor
    een beurt waarin de connector uit staat (dan gaat er geen verzoek naar overheid.nl). Geeft hun titel ("Participatiewet",
    "Burgerlijk Wetboek Boek 7").

    Zonder de zoekdienst is niet zeker dat zo'n regeling bestaat, dus de melding zegt alleen dat ze niet in de kennisgraaf
    staat. Wat voorzichtig: alleen bij een vraag met een artikel, die geen regeling uit de graaf noemt, en alleen een naam
    met "wet" erin of een vorm die het artikel zelf draagt ("7:610 BW", "artikel 1 Pw"). Een naam die het begin van een
    naam in de graaf is ("Invorderingswet" bij "Invorderingswet 1990"), telt als graafnaam. Een storing is leeg."""
    from . import overzicht

    if not _ARTIKEL_RE.search(vraag or "") and not _BW_RE.search(vraag or ""):
        return []
    try:
        if overzicht.regelingen_in_vraag(graph, vraag):
            return []
    except Exception:  # noqa: BLE001 – zonder graaf geen uitspraak over wat er niet in staat
        return []
    graafnamen = _graafnamen(graph)
    if not graafnamen:
        return []
    uit: list[str] = []
    for naam, titel, artikel in _kandidaten(vraag):
        if "wet" not in naam.casefold() and not artikel:
            continue
        n, t = naam.casefold(), titel.casefold()
        if any(g in (n, t) or g.startswith((n + " ", t + " ")) for g in graafnamen):
            continue
        uit.append(titel)
    return uit[:MAX_KANDIDATEN]


def melding_annoteren(titels: list[str], *, lezen_kan: bool) -> str:
    """Waarom een bepaling uit een regeling buiten de kennisgraaf niet te annoteren is: een annotatie hangt aan een bronnode
    in de graaf."""
    wat = " en ".join(titels)
    return (f"Ik kan deze bepaling niet annoteren: {wat} {'staat' if len(titels) == 1 else 'staan'} niet in de "
            "kennisgraaf, en annoteren kan pas na een import in de graaf."
            + (" Lezen kan wel, via de bron Wetgeving buiten de kennisgraaf." if lezen_kan else ""))


def melding_bron_uit(titels: list[str], uit_zin: str) -> str:
    """Een regeling buiten de kennisgraaf terwijl de connector uit staat: zeggen wat er is en wie de bron aanzet."""
    wat = " en ".join(titels)
    return (f"{wat} {'staat' if len(titels) == 1 else 'staan'} niet in de kennisgraaf. {uit_zin} Uit mijn eigen kennis "
            "vul ik niet in wat daar staat. Over de regelingen in de kennisgraaf kan ik je wel helpen.")


def melding_opnemen(titels: list[str], *, lezen_kan: bool) -> str:
    """Waarom een bepaling uit een regeling buiten de kennisgraaf niet in een bronselectie of werkgebied kan: een bron van
    een werkgebied is een bronnode in de graaf. Vóór het model, zodat het nooit "staat nu in de bronselectie" schrijft
    (controle 11 nov 2026, W15)."""
    wat = " en ".join(titels)
    return (f"Ik kan deze bepaling niet opnemen: {wat} {'staat' if len(titels) == 1 else 'staan'} niet in de kennisgraaf, en "
            "een bron van het werkgebied kan zo'n bepaling pas worden na een import in de graaf. Er is niets opgenomen."
            + (" Lezen kan wel, via de bron Wetgeving buiten de kennisgraaf." if lezen_kan else ""))
