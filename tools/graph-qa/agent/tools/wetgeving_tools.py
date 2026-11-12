"""De bronconnector Wetgeving buiten de kennisgraaf (ADR-013, fase 1e): wettekst van het BWB, live bij overheid.nl.

Drie getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_regelingen`: regelingen in het Basiswettenbestand op naam (titel of afkorting), BWB-id, soort, ministerie of
  rechtsgebied, op een peildatum; elke rij zegt of de regeling in de kennisgraaf staat;
- `zoek_artikelen`: de opbouw van één toestand (de artikelen met hun koppen), of de artikelen waarin woorden staan;
- `get_wettekst` (de leestool): één artikel, lid, onderdeel, divisie of bijlage, per lid en onderdeel, met de status.

**De grens met de kennisgraaf ligt in code, niet in de prompt.** De graaf is de bron voor wat erin staat. Staat de
regeling in de graaf en valt de peildatum binnen de toestand die de graaf draagt, dan weigert deze connector (`in_graaf`)
en wijst hij de graaftool aan. Zo bestaan er nooit twee teksten van dezelfde toestand. Een peildatum buiten de graaf
(een eerdere of toekomstige tekst) en een regeling die niet in de graaf staat, leest hij wel. Kan de graaf niet zeggen of
de regeling erin staat, dan weigert hij ook: terugvallen op "staat er niet in" zou de graaftekst stil vervangen.

**Dezelfde lezer als de importer** (`bronmodel.bwb`, via `adapters/sru_bwb.py`), dus dezelfde tekst als na een import.
De rijen zijn de leden en onderdelen in documentvolgorde, met hun nummer en jci.

**Eigen vindplaats.** Een gelezen bepaling heet `bwbt:<bwb>:<toestand>:<staart van de graaf-IRI>`
(`bronmodel.extern`, brontype `wettekst_live`), geen `urn:bwb:`-IRI: die opent de werkplek uit de graaf. De resultaten
van deze tools tellen in `provenance.collect_sources` nooit als graafbron.
"""
from __future__ import annotations

import re
import threading
import time
import weakref
from collections.abc import Iterable
from datetime import date
from typing import Any, Protocol
from urllib.parse import quote

from bronmodel.bwb.boom import Plek, artikelen, divisies, divisies_met_plek, onderdelen
from bronmodel.bwb.models import Artikel, Bijlage, Divisie, Onderdeel
from bronmodel.connectors import WETGEVING_LIVE
from bronmodel.extern import bwbt_delen
from bronmodel.vindplaats import vindplaats

from ..adapters.sru_bwb import OPEN_EIND, BwbFout, Gelezen, Toestand, kies_toestand
from ..graph.results import parse_select
from ..resultaat import compact, fout, pagina, per_eenheid
from .stuk_tekst import INHOUD_ARG, inhoudpagina, tekstpagina

#: Uit de beschrijving (`bronmodel.connectors`); de poorttest toetst dat `WETGEVING_TOOLS` precies deze namen heeft.
WETGEVING_TOOL_NAMEN = WETGEVING_LIVE.tools
CONNECTOR = WETGEVING_LIVE.naam

_BWB_RE = re.compile(r"^BWB[RV]\d{7}$")
_DATUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMMER_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.:]{0,24}$")
_URN = "urn:bwb:"
#: Hoogstens zo veel records per zoekvraag aan de dienst; daarbinnen rangschikt de code.
MAX_RECORDS = 100
#: Zo veel rijen draagt één pagina van `zoek_regelingen` standaard, en hoogstens.
STANDAARD_AANTAL = 10
MAX_AANTAL = 25
#: Hoe lang de stand van de graaf (welke regelingen, welke toestand) geldt zonder nieuwe vraag.
GRAAF_VERS_S = 10 * 60
#: De volgorde van de soorten bij gelijke stand: wet eerst, zoals `overzicht.RANG`.
_SOORTRANG = {"wet": 0, "AMvB": 1, "KB": 2, "ministeriele-regeling": 3, "zbo": 4, "pbo": 4, "beleidsregel": 5,
              "circulaire": 6}
#: Een titel die zo begint, is een regeling óver een andere (een wijziging, de invoering, een tijdelijk experiment).
_AFGELEID_RE = re.compile(r"^(?:wijzigings|invoerings|aanpassings|reparatie|verzamel)|^tijdelijke?\b", re.IGNORECASE)
_VOLGORDE_CQL = {"nieuwste": " sortBy dcterms.modified/sort.descending",
                 "oudste": " sortBy dcterms.modified/sort.ascending"}

_CONTRACT = (
    "\nCONTRACT: status, volledig, aantal, resultaten; bij volledig=false staat de aanroep voor de rest in 'vervolg'."
)
_GRENS = ("\nGRENS: de huidige tekst van een regeling die in de kennisgraaf staat, komt altijd uit de graaf "
          "(get_artikel, get_lid, get_bepaling); deze tool weigert die dan (reden in_graaf). Verwijzingen, definities, "
          "annotaties en begrippen bestaan alleen in de graaf. Een bepaling hieruit kan geen bron in een werkgebied "
          "worden en niet geannoteerd worden zonder import.")
_PEILDATUM = {"type": "string", "description": "De datum (JJJJ-MM-DD) waarop de tekst gold; leeg = vandaag. Een "
                                               "peildatum uit het werkgebied of de vraag geef je mee."}
_BWB_ARG = {"type": "string", "description": "BWB-id, bijv. 'BWBR0015703' (de Participatiewet)."}

WETGEVING_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_regelingen",
        "description": (
            "Zoek een regeling in het Basiswettenbestand (overheid.nl) op naam, afkorting of BWB-id – ook een "
            "regeling die niet in de kennisgraaf staat. Gebruik dit als list_regelingen de regeling niet kent, of om "
            "het BWB-id van een wet bij naam te vinden.\n"
            "GEEFT TERUG: per regeling bwb_id, titel, soort, ministerie, rechtsgebied, de geldigheid van de toestand "
            "op de peildatum en 'in_graaf'. Staat in_graaf op true, lees de tekst dan met de graaftools "
            "(get_artikel); anders met zoek_artikelen en get_wettekst.\n"
            "Een afkorting die bij meer regelingen past ('Pw'), noemt de toelichting: vraag dan welke regeling "
            "bedoeld is en kies niet zelf." + _CONTRACT),
        "input_schema": {"type": "object", "properties": {
            "naam": {"type": "string", "description": "De citeertitel of afkorting, of woorden uit de titel: "
                                                      "'Participatiewet', 'Wlz', 'Wet IB 2001'."},
            "bwb_id": _BWB_ARG,
            "soort": {"type": "string", "enum": ["wet", "AMvB", "KB", "ministeriele-regeling", "beleidsregel",
                                                  "circulaire"], "description": "Het soort regeling."},
            "orgaan": {"type": "string", "description": "Het verantwoordelijke ministerie, bijv. 'Financiën'."},
            "rechtsgebied": {"type": "string", "description": "Een rechtsgebied volgens de BWB, bijv. 'Belastingrecht'."},
            "peildatum": _PEILDATUM,
            "volgorde": {"type": "string", "enum": list(WETGEVING_LIVE.volgordes),
                         "description": "relevantie (standaard bij een naam: de exacte titel of afkorting eerst), "
                                        "nieuwste of oudste (op de laatste wijziging)."},
            "aantal": {"type": "integer", "description": f"Hoeveel regelingen per pagina (1–{MAX_AANTAL})."},
            "offset": {"type": "integer", "description": "Vanaf welke rij (voor het vervolg)."},
        }, "required": []},
    },
    {
        "name": "zoek_artikelen",
        "description": (
            "De opbouw van een regeling uit het Basiswettenbestand, live: de artikelen (of divisies en bijlagen) in "
            "documentvolgorde met de koppen erboven (reeks: hoofdstuk, paragraaf) en hun status. Met 'woorden' alleen de "
            "artikelen waarin die woorden staan. Geen lopende tekst: lees een artikel met get_wettekst (het 'id' "
            "van de rij); 'reeks' zijn de koppen erboven." + _GRENS + _CONTRACT),
        "input_schema": {"type": "object", "properties": {
            "bwb_id": _BWB_ARG,
            "peildatum": _PEILDATUM,
            "woorden": {"type": "string", "description": "Woorden die in de tekst van het artikel moeten staan, bijv. "
                                                         "'kostendelende medebewoner'; een zinsdeel tussen "
                                                         "aanhalingstekens moet letterlijk staan."},
            "offset": {"type": "integer", "description": "Vanaf welke rij (voor het vervolg)."},
        }, "required": ["bwb_id"]},
    },
    {
        "name": "get_wettekst",
        "description": (
            "De letterlijke tekst van één artikel (of divisie of bijlage) uit een toestand van het Basiswettenbestand, "
            "live bij overheid.nl: per lid en onderdeel, met nummer en jci, en de status (vervallen, nog niet in "
            "werking). Geef het 'id' uit zoek_artikelen (bwbt:…), of bwb_id + artikel (en eventueel lid), met een "
            "peildatum voor een eerdere of toekomstige tekst.\n"
            "Noem in het antwoord welke tekst het is (geldig van … tot …) en dat hij niet in de kennisgraaf staat; een "
            "bepaling die nog niet in werking is, presenteer je niet als geldend recht." + _GRENS + _CONTRACT),
        "input_schema": {"type": "object", "properties": {
            "id": {"type": "string", "description": "Het id van een bepaling, bijv. "
                                                    "'bwbt:BWBR0015703:2026-07-01_0:artikel:31'."},
            "bwb_id": _BWB_ARG,
            "artikel": {"type": "string", "description": "Het artikelnummer, bijv. '31' of '7a'."},
            "lid": {"type": "string", "description": "Alleen dit lid, bijv. '2'."},
            "onderdeel": {"type": "string", "description": "Alleen dit onderdeel (met 'lid' van dat lid), bijv. 'c'."},
            "peildatum": _PEILDATUM,
            "offset": {"type": "integer", "description": "Vanaf welke rij (voor het vervolg)."},
            "inhoud": INHOUD_ARG,
        }, "required": []},
    },
]
for _t in WETGEVING_TOOLS:
    _t["input_schema"]["additionalProperties"] = False


class WetgevingBron(Protocol):
    def zoek(self, cql: str, *, start: int = 1, maximum: int = 50) -> tuple[int, list[Toestand]]: ...
    def toestanden(self, bwb_id: str) -> list[Toestand]: ...
    def toestand_op(self, bwb_id: str, peildatum: str | None = None) -> Toestand: ...
    def lees(self, toestand: Toestand) -> Gelezen: ...


# --- de grens met de kennisgraaf --------------------------------------------------------------------------------------

class GraafOnbekend(RuntimeError):
    """De graaf kon niet zeggen welke regelingen erin staan."""


_Q_IN_GRAAF = """PREFIX bwb: <urn:bwb-ns:>
SELECT ?r ?van ?tot WHERE {{
  VALUES ?r {{ {waarden} }}
  ?r a bwb:Regeling .
  OPTIONAL {{ ?r bwb:geldigVanaf ?van }}
  OPTIONAL {{ ?r bwb:geldigTot ?tot }}
}}"""

def q_in_graaf(bwb_ids: list[str]) -> str:
    """De toestand van deze regelingen in de kennisgraaf (één rij per regeling die erin staat)."""
    return _Q_IN_GRAAF.format(waarden=" ".join(f"<{_URN}{b}>" for b in bwb_ids))


_graaf_lock = threading.Lock()
#: Per graafverbinding de stand per BWB-id, met het moment van vragen. Aan de verbinding gekoppeld (zwak), zodat een andere
#: graaf (een test, een herstart) nooit de stand van een vorige erft.
_graaf_stand: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def graaftoestanden(graph: Any, bwb_ids: Iterable[str]) -> dict[str, tuple[str, str] | None]:
    """Per BWB-id de periode van de toestand in de graaf (van, tot), of None als de regeling er niet in staat. Een
    graaf die niet antwoordt is `GraafOnbekend`, nooit "staat er niet in"."""
    ids = sorted({b for b in bwb_ids if _BWB_RE.match(b)})
    if graph is None:
        raise GraafOnbekend("geen kennisgraaf in deze aanroep")
    nu = time.monotonic()
    with _graaf_lock:
        try:
            stand = _graaf_stand.setdefault(graph, {})
        except TypeError:  # een graaf zonder zwakke verwijzing: dan zonder cache
            stand = {}
        bekend = {b: p[1] for b in ids if (p := stand.get(b)) and nu - p[0] < GRAAF_VERS_S}
    open_ = [b for b in ids if b not in bekend]
    if open_:
        try:
            ruw = graph.sparql(q_in_graaf(open_))
        except Exception as exc:  # noqa: BLE001 – elke storing betekent: onbekend
            raise GraafOnbekend(str(exc)[:200]) from exc
        if "?r" not in str(ruw or ""):
            # Geen SELECT-kop: een onleesbaar antwoord, geen bewijs dat de regeling er niet in staat.
            raise GraafOnbekend("onleesbaar antwoord van de graaf")
        rijen = parse_select(ruw)
        gevonden = {r.get("r", "").strip("<>").removeprefix(_URN): (str(r.get("van") or "")[:10],
                                                                     str(r.get("tot") or "")[:10] or OPEN_EIND)
                    for r in rijen}
        with _graaf_lock:
            for b in open_:
                stand[b] = (nu, gevonden.get(b))
                bekend[b] = gevonden.get(b)
    return bekend


def _vandaag() -> str:
    return date.today().isoformat()


def _graafbesluit(graph: Any, bwb_id: str, peil: str, *, artikel: str = "", lid: str = "") -> str | None:
    """Een foutresultaat als deze toestand uit de graaf moet komen, anders None."""
    try:
        periode = graaftoestanden(graph, [bwb_id]).get(bwb_id)
    except GraafOnbekend:
        return fout("graaf_onbereikbaar", (
            f"Of {bwb_id} in de kennisgraaf staat, kon ik niet nagaan: de graaf antwoordde niet. Lees deze tekst daarom "
            "niet live (anders kan hij afwijken van de graaf); zeg dat de graaf niet bereikbaar is."))
    if periode is None:
        return None
    van, tot = periode
    if van and van <= peil <= tot:
        graaftool = ({"tool": "get_lid", "args": {"bwb_id": bwb_id, "artikel": artikel, "lid": lid}} if lid else
                     {"tool": "get_artikel", "args": {"bwb_id": bwb_id, "artikel": artikel}} if artikel else
                     {"tool": "inhoudsopgave", "args": {"bwb_id": bwb_id}})
        return fout("in_graaf", (
            f"{bwb_id} staat in de kennisgraaf, met de tekst die geldt van {van} tot {_tot_tekst(tot)}; op {peil} geldt "
            f"die tekst. Lees hem uit de graaf met {graaftool['tool']}. Deze bron leest alleen een regeling die niet in "
            f"de graaf staat, of een andere tekst: een peildatum vóór {van}"
            + (f" of na {tot}" if tot != OPEN_EIND else "") + "."), graaftool=graaftool, graaf_van=van,
            graaf_tot=_tot_tekst(tot))
    return None


def _tot_tekst(tot: str) -> str:
    return "nu" if not tot or tot == OPEN_EIND else tot


def tekststand(t: Toestand, vandaag: str) -> str:
    """De tekst tegenover vandaag: huidige, eerdere of toekomstige tekst."""
    if t.geldig_vanaf > vandaag:
        return "toekomstige tekst"
    if (t.geldig_tot or OPEN_EIND) < vandaag:
        return "eerdere tekst"
    return "huidige tekst"


def tekst_periode(t: Toestand, vandaag: str) -> str:
    """Welke tekst het is, voor het label: "tekst geldig vanaf 2026-07-01" bij de huidige, en bij een andere ook dat het
    die is, met het einde: "eerdere tekst, geldig van 2020-01-01 tot en met 2020-05-31". Dat stond alleen in de metadata,
    niet in het antwoord dat de jurist kopieert (meting ronde 2, I15 en I16)."""
    stand = tekststand(t, vandaag)
    if stand == "huidige tekst":
        return f"tekst geldig vanaf {t.geldig_vanaf}"
    tot = "" if (t.geldig_tot or OPEN_EIND) == OPEN_EIND else t.geldig_tot
    return f"{stand}, geldig " + (f"van {t.geldig_vanaf} tot en met {tot}" if tot else f"vanaf {t.geldig_vanaf}")


# --- invoer -----------------------------------------------------------------------------------------------------------

def _peildatum(a: dict[str, Any]) -> str | None:
    waarde = str(a.get("peildatum") or "").strip()
    if not waarde:
        return None
    if not _DATUM_RE.match(waarde):
        raise ValueError(f"peildatum '{waarde}' is geen datum; geef JJJJ-MM-DD, bijvoorbeeld '2020-01-01'")
    return waarde


def _schoon(waarde: Any, maximum: int = 120) -> str:
    """Tekst voor in de CQL: zonder aanhalingstekens en backslashes, witruimte samengevoegd."""
    return " ".join(re.sub(r'["\\]', " ", str(waarde or "")).split())[:maximum]


def _geheel(waarde: Any, standaard: int, laag: int, hoog: int) -> int:
    try:
        return min(max(int(waarde), laag), hoog)
    except (TypeError, ValueError):
        return standaard


# --- zoeken -----------------------------------------------------------------------------------------------------------

def _filters_cql(a: dict[str, Any], peil: str) -> str:
    delen = [f"overheidbwb.geldigheidsdatum={peil}"]
    if soort := _schoon(a.get("soort"), 40):
        delen.append(f'dcterms.type="{soort}"')
    if orgaan := _schoon(a.get("orgaan"), 80):
        delen.append(f'overheid.authority="{re.sub(r"^ministerie van ", "", orgaan, flags=re.IGNORECASE)}"')
    if gebied := _schoon(a.get("rechtsgebied"), 80):
        delen.append(f'overheidbwb.rechtsgebied="{gebied}"')
    return " and ".join(delen)


def _per_regeling(toestanden: Iterable[Toestand], peil: str, vandaag: str) -> list[Toestand]:
    """Eén toestand per regeling: die op de peildatum, met dezelfde keuze als de adapter (`kies_toestand`)."""
    per: dict[str, list[Toestand]] = {}
    for t in toestanden:
        per.setdefault(t.bwb_id, []).append(t)
    uit = []
    for rijen in per.values():
        if (gekozen := kies_toestand(rijen, peil, vandaag)) is not None:
            uit.append(gekozen)
    return uit


def _rang(t: Toestand, naam: str, afkorting: set[str]) -> tuple:
    titel = t.titel.casefold()
    n = naam.casefold()
    return (0 if titel == n else 1, 0 if t.bwb_id in afkorting else 1, 0 if titel.startswith(n) else 1,
            1 if _AFGELEID_RE.search(t.titel) else 0, _SOORTRANG.get(t.soort, 9), len(t.titel), t.bwb_id)


def _zoekvraag_tekst(a: dict[str, Any], peil: str) -> str:
    delen = []
    if a.get("naam"):
        delen.append(f"„{_schoon(a['naam'])}”")
    if a.get("bwb_id"):
        delen.append(str(a["bwb_id"]))
    if a.get("soort"):
        delen.append(f"soort {a['soort']}")
    if a.get("orgaan"):
        delen.append(f"ministerie {a['orgaan']}")
    if a.get("rechtsgebied"):
        delen.append(f"rechtsgebied {a['rechtsgebied']}")
    return "regelingen " + ", ".join(delen) + f", geldig op {peil}"


def _zoek(bron: WetgevingBron, graph: Any, a: dict[str, Any]) -> str:
    vandaag = _vandaag()
    peil = _peildatum(a) or vandaag
    naam, bwb_id = _schoon(a.get("naam")), str(a.get("bwb_id") or "").strip()
    if bwb_id and not _BWB_RE.match(bwb_id):
        return fout("ongeldig_id", f"'{bwb_id}' is geen BWB-id; geef bijvoorbeeld 'BWBR0015703'")
    if not (naam or bwb_id or a.get("rechtsgebied") or a.get("orgaan")):
        return fout("ongeldige_argumenten", "geef een naam, een BWB-id, een rechtsgebied of een ministerie, bijvoorbeeld "
                    "{\"naam\": \"Participatiewet\"}")
    volgorde = str(a.get("volgorde") or "").strip() or "relevantie"
    if volgorde not in WETGEVING_LIVE.volgordes:
        return fout("ongeldige_volgorde", f"volgorde '{volgorde}' bestaat niet; kies bijvoorbeeld 'relevantie'")
    aantal = _geheel(a.get("aantal"), STANDAARD_AANTAL, 1, MAX_AANTAL)
    offset = _geheel(a.get("offset"), 0, 0, 100_000)
    filters = _filters_cql(a, peil)
    sortering = _VOLGORDE_CQL.get(volgorde, "")
    afkorting: set[str] = set()
    toelichting = []
    if bwb_id or naam:
        # Op naam of BWB-id rangschikt de code: de wet zelf vóór wat erover gaat. De scope is dan de MAX_RECORDS best
        # passende per zoekvraag; past de naam bij meer, dan zegt de toelichting dat.
        if bwb_id:
            totaal, rijen = bron.zoek(f"dcterms.identifier={bwb_id} and {filters}", maximum=20)
        else:
            _, met_afk = bron.zoek(f'overheidbwb.afkorting="{naam}" and {filters}{sortering}', maximum=MAX_RECORDS)
            afkorting = {t.bwb_id for t in met_afk}
            totaal, met_titel = bron.zoek(f'overheidbwb.titel adj "{naam}" and {filters}{sortering}',
                                          maximum=MAX_RECORDS)
            rijen = met_afk + met_titel
            if not rijen:
                woorden = " ".join(naam.split()[:8])
                totaal, rijen = bron.zoek(f'overheidbwb.titel all "{woorden}" and {filters}{sortering}',
                                          maximum=MAX_RECORDS)
            if totaal > MAX_RECORDS:
                toelichting.append(f"De naam past bij {totaal} regelingen; dit zijn de {MAX_RECORDS} best passende. "
                                   "Maak de naam specifieker als de gezochte er niet bij staat.")
        regelingen = _per_regeling(rijen, peil, vandaag)
        if volgorde == "relevantie" and naam:
            regelingen.sort(key=lambda t: _rang(t, naam, afkorting))
        elif volgorde in _VOLGORDE_CQL:
            regelingen.sort(key=lambda t: t.gewijzigd, reverse=volgorde == "nieuwste")
        deel = regelingen[offset:offset + aantal + 1]
    else:
        # Op filters pagineert de dienst zelf (startRecord), in zijn eigen volgorde of op de laatste wijziging: alle
        # pagina's samen zijn dan precies de treffers.
        totaal, rijen = bron.zoek(f"{filters}{sortering}", start=offset + 1, maximum=aantal + 1)
        deel = _per_regeling(rijen, peil, vandaag)
        regelingen = deel
    try:
        in_graaf = graaftoestanden(graph, [t.bwb_id for t in deel])
    except GraafOnbekend:
        in_graaf = None
        toelichting.append("Of een regeling in de kennisgraaf staat, kon ik niet nagaan (de graaf antwoordde niet).")
    if len(afkorting) > 1 and naam.casefold() not in {t.titel.casefold() for t in regelingen}:
        namen = ", ".join(t.titel for t in regelingen if t.bwb_id in afkorting)
        toelichting.append(f"De afkorting „{naam}” past bij {len(afkorting)} regelingen ({namen}): vraag welke bedoeld "
                           "is en kies niet zelf.")
    if naam and offset == 0 and not any(t.titel.casefold() == naam.casefold() or t.bwb_id in afkorting
                                        for t in regelingen):
        toelichting.append(_buiten_de_peildatum(bron, naam, peil))
    if bwb_id and not regelingen and offset == 0:
        toelichting.append(_id_buiten_de_peildatum(bron, bwb_id, peil))
    elif not regelingen and offset == 0:
        toelichting.append(f"Geen regeling gevonden ({_zoekvraag_tekst(a, peil)}). Dat bewijst niet dat ze niet "
                           "bestaat: probeer een andere schrijfwijze of de afkorting.")
    toelichting.append("Staat in_graaf op true, lees de tekst dan met de graaftools (get_artikel); anders met "
                       "zoek_artikelen en get_wettekst, met 'nummer' als bwb_id.")
    args = {k: v for k, v in a.items() if k in {"naam", "bwb_id", "soort", "orgaan", "rechtsgebied", "peildatum",
                                                  "volgorde"} and v}
    args["aantal"] = aantal
    return pagina([_regelingrij(t, peil, vandaag, in_graaf) for t in deel], tool="zoek_regelingen", args=args,
                  limit=aantal, offset=offset,
                  extra={**zoekvraag_van(args, volgorde), "totaal": max(totaal, len(regelingen))},
                  toelichting=" ".join(toelichting))


def zoekvraag_van(args: dict[str, Any], volgorde: str = "", *, regeling: str = "") -> dict[str, Any]:
    """De zoekvraag onder een lijst in de vorm van de andere connectors: de filters als dict (`zoekvraag`, de code zet
    ze in zinnen met de labels uit de beschrijving) en wat daar geen filter voor heeft als `kanttekening`: het BWB-id en
    de regeling waarin gezocht is. Een zin als zoekvraag maakte het blok `stukken` leeg: geen zoekvraag en geen totaal
    (meting ronde 2: I01, I14, I30)."""
    zoekvraag = {k: v for k, v in args.items() if k in {"naam", "soort", "orgaan", "rechtsgebied", "peildatum"} and v}
    if args.get("woorden"):
        zoekvraag["tekst"] = args["woorden"]
    if volgorde:
        zoekvraag["volgorde"] = volgorde
    kant = (f"In {regeling}." if regeling and args.get("woorden") else
            f"De artikelen van {regeling}, in de volgorde van de regeling." if regeling else
            f"BWB-id {args['bwb_id']}." if args.get("bwb_id") else "")
    return {"zoekvraag": zoekvraag, **({"kanttekening": kant} if kant else {})}


def _buiten_de_peildatum(bron: WetgevingBron, naam: str, peil: str) -> str:
    """Wat de BWB heeft van een regeling met precies deze titel als die op de peildatum geen toestand heeft: de periode
    van haar toestanden, of dat er geen is. Zonder deze zin gokte Lex achttien rondes naar BWB-id's (meting 11 nov 2026,
    I20: de Wet op de inkomstenbelasting 1964 op 1 januari 1995)."""
    exact: list[Toestand] = []
    try:
        # Eerst vandaag (dan is het één record per regeling), dan zonder datum (elke toestand een record).
        for cql in (f'overheidbwb.titel adj "{naam}" and overheidbwb.geldigheidsdatum={_vandaag()}',
                    f'overheidbwb.titel adj "{naam}"'):
            exact = [t for t in bron.zoek(cql, maximum=MAX_RECORDS)[1] if t.titel.casefold() == naam.casefold()]
            if exact:
                break
        if exact:
            exact = bron.toestanden(exact[0].bwb_id) or exact
    except Exception:  # noqa: BLE001 – een storing kost alleen deze zin
        return ""
    if not exact:
        return (f"Het Basiswettenbestand kent geen regeling met precies de titel „{naam}”, ook niet op een andere datum. "
                "Een regeling die verviel voordat het Basiswettenbestand haar bijhield, staat er niet in. Raad geen "
                "BWB-id's: zeg dat de regeling niet gevonden is.")
    van = min(t.geldig_vanaf for t in exact)
    tot = max((t.geldig_tot or OPEN_EIND) for t in exact)
    if van <= peil <= tot:
        return (f"„{naam}” ({exact[0].bwb_id}) heeft op {peil} een tekst in het Basiswettenbestand, mogelijk onder een "
                f"andere titel: lees haar met bwb_id {exact[0].bwb_id} en deze peildatum.")
    return (f"„{naam}” ({exact[0].bwb_id}) staat in het Basiswettenbestand met teksten van {van} tot {_tot_tekst(tot)}, "
            f"niet op {peil}: kies een peildatum in die periode, of zeg dat er voor {peil} geen tekst is.")


def _id_buiten_de_peildatum(bron: WetgevingBron, bwb_id: str, peil: str) -> str:
    """Wat een BWB-id is als het op de peildatum niets oplevert: de titel en de periode van zijn toestanden, of dat het id
    niet bestaat. "Niets gevonden" liet een geraden id lijken op de gezochte wet (ronde 4, I20: BWBR0002471 bij de Wet op
    de inkomstenbelasting 1964 is de Wet op de loonbelasting 1964)."""
    try:
        alle = bron.toestanden(bwb_id)
    except BwbFout:
        return (f"Het Basiswettenbestand kent geen regeling met id {bwb_id}. Raad geen BWB-id's: zoek op de naam, of zeg "
                "dat de regeling niet gevonden is.")
    except Exception:  # noqa: BLE001 – een storing kost alleen deze zin
        return f"Op {peil} heeft {bwb_id} geen tekst in het Basiswettenbestand."
    van = alle[0].geldig_vanaf
    tot = max((t.geldig_tot or OPEN_EIND) for t in alle)
    return (f"{bwb_id} is „{alle[-1].titel}” ({alle[-1].soort}), met teksten van {van} tot {_tot_tekst(tot)}, en heeft "
            f"op {peil} geen tekst. Is dat niet de regeling die je zoekt, gebruik dit id dan niet: zoek op de naam, of zeg "
            "dat de regeling niet gevonden is.")


def _regelingrij(t: Toestand, peil: str, vandaag: str, in_graaf: dict[str, Any] | None) -> dict[str, Any]:
    """Eén regeling in de vaste metadatasleutels (`bronmodel.connectors.METADATA_SLEUTELS`)."""
    rij = compact({"id": f"bwbt:{t.bwb_id}:{t.versie}", "label": t.titel, "titel": t.titel, "nummer": t.bwb_id,
                   "link": t.link,
                   "soort": t.soort, "orgaan": t.ministerie, "rechtsgebied": "; ".join(t.rechtsgebieden),
                   "datum": t.geldig_vanaf, "tekst_vanaf": t.geldig_vanaf,
                   "tekst_tot": "" if t.geldig_tot == OPEN_EIND else t.geldig_tot, "gewijzigd": t.gewijzigd,
                   "versie": t.versie, "tekststand": tekststand(t, vandaag)})
    if in_graaf is not None:
        rij["in_graaf"] = in_graaf.get(t.bwb_id) is not None
    return rij


# --- een toestand lezen -----------------------------------------------------------------------------------------------

def _staart(jci: str | None, reserve: str) -> str:
    """De staart van de graaf-IRI (`:artikel:31`) uit de jci, zoals de importer hem schrijft; zonder jci de reserve."""
    vp = vindplaats(jci) if jci else None
    if vp is not None and vp.soort not in ("regeling", "node") and vp.bron_iri.startswith(_URN):
        return vp.bron_iri[len(_URN) + len(vp.bwb_id):]
    return reserve


def _id(t: Toestand, staart: str) -> str:
    return f"bwbt:{t.bwb_id}:{t.versie}{staart}"


Bepaling = Artikel | Divisie | Bijlage


def _bepalingen(g: Gelezen) -> list[tuple[str, Plek | None, Bepaling]]:
    """Elke kiesbare bepaling van de toestand met haar staart, in documentvolgorde: artikelen, divisies met eigen tekst
    en bijlagen."""
    uit: list[tuple[str, Plek | None, Bepaling]] = []
    for plek, a in artikelen(g.wet):
        uit.append((_staart(a.jci, f":artikel:{quote(a.nummer.strip().rstrip('.'), safe='')}"), plek, a))
    for plek, d in divisies_met_plek(g.wet):
        if (d.tekst or "").strip() or d.onderdelen:
            uit.append((_staart(d.jci, f":id:{quote(d.id, safe='')}"), plek, d))
    for b in g.wet.bijlagen:
        uit.append((_staart(b.jci, f":bijlage:{quote((b.nummer or b.id).strip(), safe='')}"), None, b))
    return uit


def _label(b: Bepaling) -> str:
    label = (b.label or "").strip()
    nummer = (b.nummer or "").strip().rstrip(".")
    return label if not nummer or nummer in label.split() else f"{label} {nummer}".strip()


def _werking(b: Bepaling) -> str:
    status = (getattr(b, "status", "") or "").strip()
    if status == "vervallen":
        return f"vervallen per {b.inwerking}" if getattr(b, "inwerking", None) else "vervallen"
    if status == "nogniet":
        return f"nog niet in werking; treedt in werking op {b.inwerking}" if b.inwerking else "nog niet in werking"
    return ""


def _volledige_tekst(b: Bepaling) -> str:
    delen = [b.tekst or ""]
    for lid in getattr(b, "leden", []) or []:
        delen.append(lid.tekst or "")
        delen += [o.tekst or "" for o in onderdelen(lid.onderdelen)]
    delen += [o.tekst or "" for o in onderdelen(getattr(b, "onderdelen", []) or [])]
    return " ".join(" ".join(delen).split())


def _bevat(tekst: str, woorden: str) -> bool:
    tekst = tekst.casefold()
    zinsdelen = re.findall(r'"([^"]+)"|„([^”]+)”', woorden)
    vast = [" ".join((a or b).split()).casefold() for a, b in zinsdelen]
    los = re.sub(r'"[^"]*"|„[^”]*”', " ", woorden).casefold().split()
    return all(z in tekst for z in vast) and all(w in tekst for w in los)


def _toestand(bron: WetgevingBron, bwb_id: str, versie: str, peil: str | None) -> Toestand:
    if versie:
        gekozen = next((t for t in bron.toestanden(bwb_id) if t.versie == versie), None)
        if gekozen is None:
            raise BwbFout(f"{bwb_id} heeft geen toestand {versie}", code="niet_gevonden")
        return gekozen
    return bron.toestand_op(bwb_id, peil)


def _regeling_kop(g: Gelezen, vandaag: str, peil: str | None) -> dict[str, Any]:
    t = g.toestand
    return compact({"bwb_id": t.bwb_id, "titel": g.wet.citeertitel or t.titel, "soort": t.soort,
                    "datum": t.geldig_vanaf, "tekst_vanaf": t.geldig_vanaf,
                    "tekst_tot": "" if t.geldig_tot == OPEN_EIND else t.geldig_tot,
                    "tekststand": tekststand(t, vandaag), "op_peildatum": True if peil else None,
                    "versie": t.versie, "gewijzigd": t.gewijzigd, "orgaan": t.ministerie,
                    "rechtsgebied": "; ".join(t.rechtsgebieden), "bron_hash": g.hash, "in_graaf": False})


def _opbouw(bron: WetgevingBron, graph: Any, a: dict[str, Any]) -> str:
    bwb_id = str(a.get("bwb_id") or "").strip()
    if not _BWB_RE.match(bwb_id):
        return fout("ongeldig_id", f"'{bwb_id}' is geen BWB-id; geef bijvoorbeeld {{\"bwb_id\": \"BWBR0015703\"}}")
    peil = _peildatum(a)
    vandaag = _vandaag()
    if (weigering := _graafbesluit(graph, bwb_id, peil or vandaag)) is not None:
        return weigering
    t = bron.toestand_op(bwb_id, peil)
    g = bron.lees(t)
    g.eis_volledig()
    woorden = " ".join(str(a.get("woorden") or "").split())[:200]
    rijen = []
    for staart, plek, b in _bepalingen(g):
        if woorden and not _bevat(_volledige_tekst(b), woorden):
            continue
        rijen.append(compact({"id": _id(t, staart), "label": _label(b), "titel": (b.titel or "").strip(),
                              "link": f"https://wetten.overheid.nl/{b.jci}" if getattr(b, "jci", None) else t.link,
                              "datum": getattr(b, "inwerking", "") or t.geldig_vanaf,
                              "reeks": list(plek.koppen()) if plek else [], "status": _werking(b)}))
    kop = _regeling_kop(g, vandaag, peil)
    toelichting = (f"De opbouw van {kop['titel']} (tekst geldig vanaf {t.geldig_vanaf}), live van overheid.nl, niet uit "
                   "de kennisgraaf. Lees een artikel met get_wettekst en het 'id' van de rij.")
    if woorden and not rijen:
        toelichting = (f"Geen artikel van {kop['titel']} bevat „{woorden}” (tekst geldig vanaf {t.geldig_vanaf}). Dat "
                       "zegt alleen iets over deze woorden: zoek eventueel met een ander woord.")
    args = {"bwb_id": bwb_id, **({"peildatum": peil} if peil else {}), **({"woorden": a["woorden"]} if woorden else {})}
    offset = _geheel(a.get("offset"), 0, 0, 10_000)
    extra: dict[str, Any] = {"regeling": kop, "totaal": len(rijen),
                             **zoekvraag_van(args, regeling=f"{kop['titel']} (tekst geldig vanaf {t.geldig_vanaf})")}
    if not woorden and offset == 0:
        # De opbouw en de telling in één keer: zonder deze velden bladerde het model door alle artikelen om de
        # hoofdstukken of de vervallen artikelen te tellen (meting 11 nov 2026, I13: 21 rondes en 1,0M tokens voor de
        # opbouw van de Wet IB 2001; I30: zes pagina's voor "hoeveel artikelen").
        extra |= {"opbouw": opbouw(rijen), "telling": telling(rijen)}
        toelichting += (" 'opbouw' geeft de delen op het hoogste niveau met hun artikelen, 'telling' het aantal per "
                        "status: blader alleen door als je de artikelen zelf nodig hebt.")
    return per_eenheid(rijen, tool="zoek_artikelen", args=args, offset=offset, extra=extra, toelichting=toelichting)


def opbouw(rijen: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """De delen op het hoogste niveau (de eerste kop van `reeks`) in documentvolgorde: kop, aantal artikelen, eerste en
    laatste. Leeg voor een regeling zonder indeling."""
    delen: list[dict[str, Any]] = []
    for r in rijen:
        reeks = r.get("reeks") or []
        if not reeks:
            continue
        if not delen or delen[-1]["kop"] != reeks[0]:
            delen.append({"kop": reeks[0], "artikelen": 0, "van": r["label"], "tot": r["label"]})
        delen[-1]["artikelen"] += 1
        delen[-1]["tot"] = r["label"]
    return delen


def telling(rijen: list[dict[str, Any]]) -> dict[str, int]:
    """Het aantal bepalingen per status: geldend, vervallen, nog niet in werking."""
    uit = {"totaal": len(rijen), "geldend": 0, "vervallen": 0, "nog_niet_in_werking": 0}
    for r in rijen:
        status = str(r.get("status") or "")
        uit["vervallen" if status.startswith("vervallen") else "nog_niet_in_werking" if status.startswith("nog niet")
            else "geldend"] += 1
    return uit


_PUBLICATIE_RE = re.compile(r"^(Stb|Stcrt|Trb)\.?\s*(\d{4})[-,\s]+(\d+)$", re.IGNORECASE)


def publicatie(bron: str | None) -> str:
    """De bron van een artikel in de vorm van de BWB ("Stb.2025-312") als citeervorm ("Stb. 2025, 312"); een andere vorm
    blijft zoals hij is. Zo zegt de leestool zelf waarmee het artikel is ingevoegd of gewijzigd, en hoeft Lex daar niet naar
    te zoeken (meting 11 nov 2026, I06: zeven rondes en 185k voor "welk Staatsblad voerde artikel 24a in")."""
    waarde = (bron or "").strip()
    if not waarde:
        return ""
    m = _PUBLICATIE_RE.match(waarde)
    return f"{m.group(1).capitalize()}. {m.group(2)}, {m.group(3)}" if m else waarde


def onderdeel_plek(nummer: str) -> str:
    """Het nummer van een onderdeel als plek van zijn rij ("onderdeel b", "1°"): de tekst zelf draagt het niet, en een lid
    dat naar "onderdeel b" verwijst was anders niet te volgen (controle 11 nov 2026, W09). Leeg zonder nummer."""
    nr = (nummer or "").strip().rstrip(".").strip()
    if not nr:
        return ""
    return nr if "°" in nr else f"onderdeel {nr}"


def _rijen(b: Bepaling, lid_nr: str, o_nr: str, plek: Plek | None = None) -> list[dict[str, Any]]:
    """De rijen van een bepaling: haar eigen tekst, dan per lid de lidtekst en zijn onderdelen, dan de onderdelen
    direct onder de bepaling. Met `lid_nr` (en `o_nr`) alleen dat lid (dat onderdeel). De kop draagt de plek in de
    regeling ("Hoofdstuk 3 – Algemene bijstand › § 3.2 – Normen › Artikel 24a – …"), zoals een kop in een Kamerstuk."""
    naam = " › ".join([*(plek.koppen() if plek else ()),
                       _label(b) + (f" – {b.titel.strip()}" if (b.titel or "").strip() else "")])
    uit: list[dict[str, Any]] = []

    def rij(tekst: str, kop: str, nummer: str = "", jci: str | None = None, plek: str = "") -> None:
        if (tekst or "").strip():
            uit.append(compact({"nr": len(uit) + 1, "tekst": tekst.strip(), "kop": kop,
                                "nummer": nummer.strip(), "jci": jci or "", "plek": plek}))

    def onder(lijst: list[Onderdeel], kop: str) -> None:
        for o in onderdelen(lijst):
            if o_nr and o.nummer.strip().rstrip(".").casefold() != o_nr.casefold():
                continue
            rij(o.tekst, kop, o.nummer, o.jci, plek=onderdeel_plek(o.nummer))

    if not lid_nr:
        rij(b.tekst, naam, "", b.jci)
    for lid in getattr(b, "leden", []) or []:
        if lid_nr and lid.nummer.strip().rstrip(".") != lid_nr:
            continue
        kop = f"{naam} › lid {lid.nummer.strip().rstrip('.')}"
        # Met een onderdeel blijft de aanhef van het lid erbij ("Niet tot de middelen worden gerekend:"): zonder die
        # zin is het onderdeel niet te lezen.
        rij(lid.tekst, kop, lid.nummer, lid.jci)
        onder(lid.onderdelen, kop)
    if not lid_nr:
        onder(getattr(b, "onderdelen", []) or [], naam)
    return uit


def _deel_jci(b: Bepaling, lid: str, o_nr: str) -> str | None:
    """De jci van het gelezen lid (of onderdeel daarin), voor de link; None als de bepaling dat lid niet heeft."""
    for l in getattr(b, "leden", []) or []:
        if l.nummer.strip().rstrip(".") != lid:
            continue
        if o_nr:
            o = next((o for o in onderdelen(l.onderdelen) if o.nummer.strip().rstrip(".").casefold() == o_nr.casefold()),
                     None)
            return (o.jci if o is not None and o.jci else l.jci) or None
        return l.jci or None
    return None


def _deel_label(b: Bepaling, lid: str, o_nr: str) -> str:
    """"Artikel 9, lid 2" en "Artikel 31, lid 2, onderdeel c", zoals de graaf een deel van een artikel noemt."""
    return ", ".join(filter(None, [_label(b), f"lid {lid}" if lid else "", f"onderdeel {o_nr}" if o_nr else ""]))


def _get(bron: WetgevingBron, graph: Any, a: dict[str, Any]) -> str:
    ident = str(a.get("id") or "").strip()
    versie, paren = "", ()
    if ident:
        delen = bwbt_delen(ident)
        if delen is None:
            return fout("ongeldig_id", f"'{ident}' is geen id van deze bron; geef bijvoorbeeld "
                        f"{{\"id\": \"{WETGEVING_LIVE.voorbeeld_id}\"}} of {{\"bwb_id\": \"BWBR0015703\", \"artikel\": \"31\"}}")
        bwb_id, versie, paren = delen
    else:
        bwb_id = str(a.get("bwb_id") or "").strip()
    if not _BWB_RE.match(bwb_id):
        return fout("ongeldig_id", "geef een id of een BWB-id met een artikel, bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0015703\", \"artikel\": \"31\"}")
    gevraagd = dict(paren)
    artikel = str(a.get("artikel") or gevraagd.get("artikel") or "").strip().rstrip(".")
    lid = str(a.get("lid") or gevraagd.get("lid") or "").strip().rstrip(".")
    o_nr = str(a.get("onderdeel") or gevraagd.get("o", "")).strip().rstrip(".")
    if artikel and not _NUMMER_RE.match(artikel):
        return fout("ongeldig_nummer", f"'{artikel}' is geen artikelnummer; geef bijvoorbeeld '31' of '7a'")
    staart_gevraagd = "".join(f":{k}:{quote(v, safe='')}" for k, v in paren if k not in ("lid", "o"))
    if not (artikel or staart_gevraagd):
        return fout("ongeldige_argumenten", "welke bepaling? Geef een artikel, bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0015703\", \"artikel\": \"31\"}, of zoek haar met zoek_artikelen")
    peil = _peildatum(a)
    vandaag = _vandaag()
    # Eerst de graaf: staat de tekst daar, dan gaat er geen verzoek naar overheid.nl. Met een toestand in het id is de
    # peildatum het begin van die toestand.
    if not versie and (weigering := _graafbesluit(graph, bwb_id, peil or vandaag, artikel=artikel, lid=lid)):
        return weigering
    t = _toestand(bron, bwb_id, versie, peil)
    if versie and (weigering := _graafbesluit(graph, bwb_id, peil or t.geldig_vanaf, artikel=artikel, lid=lid)):
        return weigering
    g = bron.lees(t)
    kandidaten = _bepalingen(g)
    gezocht = staart_gevraagd if staart_gevraagd and not a.get("artikel") else f":artikel:{quote(artikel, safe='')}"
    treffer = next(((s, p, b) for s, p, b in kandidaten if s.casefold() == gezocht.casefold()), None)
    if treffer is None and ":" in artikel:
        # "7:610" bij Boek 7 van het BW: het nummer in de BWB is "610".
        kort = f":artikel:{quote(artikel.rsplit(':', 1)[1], safe='')}"
        treffer = next(((s, p, b) for s, p, b in kandidaten if s.casefold() == kort.casefold()), None)
    if treffer is None and artikel:
        # Een beleidsregel zonder artikelen nummert haar divisies ("§ 1", "26.5"): een nummer dat precies één divisie
        # draagt, is die divisie (iteratie wetgeving_live, I12: het BBBB kent geen "artikel 1", wel "§ 1").
        zelfde = [(s, p, b) for s, p, b in kandidaten if isinstance(b, Divisie)
                  and (b.nummer or "").strip().rstrip(".").casefold() == artikel.removeprefix("§").strip().casefold()]
        treffer = zelfde[0] if len(zelfde) == 1 else None
    if treffer is None:
        titel = g.wet.citeertitel or t.titel
        onbekend = (f" De bron heeft structuur die de lezer niet als eigen deel kent ({', '.join(g.wet.overgeslagen)}): "
                    f"staat de bepaling daarin, open dan {t.link}." if g.wet.overgeslagen else "")
        return fout("niet_gevonden", (
            f"{titel} ({bwb_id}, tekst geldig vanaf {t.geldig_vanaf}) heeft geen {artikel and 'artikel ' + artikel or ident}. "
            "Zoek de bepaling met zoek_artikelen, bijvoorbeeld "
            f"{{\"bwb_id\": \"{bwb_id}\"}}." + onbekend))
    staart, plek, b = treffer
    if not (g.artikel_volledig(b) if isinstance(b, Artikel) else g.volledig):
        raise BwbFout(f"de toestand {t.versie} van {bwb_id} is niet volledig te lezen (dekking {g.dekking:.1%}), en "
                      f"{_label(b)} ook niet", code="onvolledig")
    rijen = _rijen(b, lid, o_nr, plek)
    # Eén lid of onderdeel is een eigen stuk, zoals in de graaf: een eigen id, label en link. Met het id van het artikel
    # waren twee apart gelezen leden twee lezingen van één stuk, allebei vanaf nr 1, en kon het model lid 2 niet aanwijzen
    # (meting ronde 2, I28: artikel 2:9 BW, vijf sjabloonpogingen). Zonder rijen blijft het het artikel.
    deel_jci = _deel_jci(b, lid, o_nr) if rijen else None
    deel = (f":lid:{quote(lid, safe='')}" if lid and deel_jci else "") + (
        f":o:{quote(o_nr, safe='')}" if o_nr and deel_jci and any(r.get("plek") for r in rijen) else "")
    stuk_id = _id(t, staart + deel)
    titel = g.wet.citeertitel or t.titel
    werking = _werking(b)
    kop = _regeling_kop(g, vandaag, peil)
    stuk = compact({"id": stuk_id, "label": f"{titel}, {_deel_label(b, lid if deel else '', o_nr if ':o:' in deel else '')}"
                             f" ({tekst_periode(t, vandaag)})",
                    "link": f"https://wetten.overheid.nl/{deel_jci or b.jci}" if (deel_jci or b.jci) else t.link,
                    # De titel is die van de bepaling (haar opschrift), zoals in de rij van zoek_artikelen: het label
                    # noemt de regeling al, en een gelezen artikel stond in de lijst anders met de titel van de wet
                    # (ronde 3, I13: "Artikel 2.3 …: Wet inkomstenbelasting 2001" tussen "Artikel 2.4: Bepalingen …").
                    **{k: v for k, v in kop.items() if k != "bwb_id"}, "titel": (b.titel or "").strip() or titel,
                    "nummer": bwb_id,
                    "inwerking": getattr(b, "inwerking", "") or "", "status": werking,
                    "publicatie": publicatie(getattr(b, "bron", None)),
                    "reeks": list(plek.koppen()) if plek else [], "leesbaar": True})
    offset = _geheel(a.get("offset"), 0, 0, 10_000)
    args = {"id": stuk_id, **({"lid": lid} if lid else {}), **({"onderdeel": o_nr} if o_nr and a.get("onderdeel") else {})}
    if a.get("inhoud"):
        return inhoudpagina(rijen, tool="get_wettekst", args=args, offset=offset, stuk=stuk)
    zinnen = [f"Deze tekst komt van overheid.nl ({kop['tekststand']}, geldig van {t.geldig_vanaf} tot "
              f"{_tot_tekst(t.geldig_tot)}) en staat niet in de kennisgraaf. Citeer letterlijk met het id {stuk_id}; "
              "voor een werkgebied of een annotatie moet de regeling eerst in de graaf."]
    if werking.startswith("nog niet"):
        zinnen.append(f"{_label(b)} is {werking}: presenteer het niet als geldend recht.")
    elif werking.startswith("vervallen"):
        zinnen.append(f"{_label(b)} is {werking}: er geldt geen tekst meer.")
    if o_nr and not any(r.get("plek") for r in rijen):
        zinnen.append(f"{_label(b)} heeft in deze tekst geen onderdeel {o_nr}" + (f" in lid {lid}." if lid else "."))
    elif lid and not rijen:
        zinnen.append(f"{_label(b)} heeft in deze tekst geen lid {lid}.")
    if not g.volledig:
        zinnen.append(f"De toestand als geheel is niet volledig te lezen (dekking {g.dekking:.1%}); {_label(b)} wel: die "
                      "tekst is volledig en te citeren.")
    if not g.xsd_geldig:
        zinnen.append("De toestand valideert niet tegen de XSD van de BWB; de tekst is wel volledig gelezen.")
    return tekstpagina(rijen, tool="get_wettekst", args=args, offset=offset, stuk=stuk, toelichting=" ".join(zinnen))


# --- fouten en dispatch -----------------------------------------------------------------------------------------------

#: De reden in het foutresultaat per code van de adapter (`BwbFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "geweigerd": "zoekvraag_geweigerd", "niet_gevonden": "niet_gevonden",
             "onvolledig": "toestand_onvolledig", "te_groot": "resultaat_te_groot"}


def fout_van(exc: Any) -> str:
    """Het foutresultaat bij een `BwbFout`, met de reden en wat Lex ermee doet."""
    code = getattr(exc, "code", "onbereikbaar")
    if code == "onvolledig":
        return fout("toestand_onvolledig", f"{exc}. Citeer er niet uit; noem de link naar wetten.overheid.nl en zeg dat "
                    "de tekst niet volledig te lezen was.")
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}. Zeg dat; verzin geen tekst. Zoek eventueel met zoek_regelingen, "
                    "bijvoorbeeld {\"naam\": \"Participatiewet\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_wetgeving(name: str, args: dict[str, Any], bron: WetgevingBron | None, graph: Any) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Wetgeving buiten de kennisgraaf staat uit. Zeg dat, en antwoord niet uit "
                    "eigen kennis.")
    if name == "zoek_regelingen":
        return _zoek(bron, graph, args)
    if name == "zoek_artikelen":
        return _opbouw(bron, graph, args)
    if name == "get_wettekst":
        return _get(bron, graph, args)
    raise KeyError(name)

