"""De bronconnector Rechtspraak (ADR-013, fase 1c): uitspraken die een wetsartikel noemen, en hun tekst.

Twee getypeerde tools, met het resultaatcontract van de graaftools:

- `zoek_uitspraken`: de uitspraken en conclusies die Linked Data Overheid (KOOP) aan een artikel koppelt, over alle
  versies van dat artikel, met instantie, datum en zaaknummer;
- `get_uitspraak`: de tekst van één Nederlandse uitspraak uit de open data van de Rechtspraak, per alinea.

**Een vermelding is geen uitleg.** LiDO koppelt een uitspraak aan een artikel als haar tekst het noemt; in de spike
(10 nov 2026) was dat in 30 van de 30 paren juist, maar in 4 noemde de uitspraak het artikel alleen terloops. De tool zegt
daarom "noemt", ordent naar instantie en datum en draagt `dekking: "ten minste"`: LiDO loopt achter op de wetgeving
en kan versies missen. **Een uitspraak is een bron, geen wettekst**: de vindplaats is de ECLI (`bronmodel.extern`),
de grounding toetst een citaat letterlijk, en wat de wet zegt onderbouwt ze niet. De rijen dragen hun tekst daarom
onder `id`, nooit onder `iri`/`uri`.

Het artikel zoekt de tool zelf op in de graaf (jci en label-id), zodat het model alleen regeling en artikel noemt.
"""
from __future__ import annotations

import calendar
import logging
import datetime as dt
import re
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Any, Protocol

from bronmodel.connectors import INSTANTIE_MEERVOUD, INSTANTIES, RECHTSPRAAK
from bronmodel.extern import externe_vindplaats

from ..adapters.lido_rechtspraak import RechtspraakFout, begindatum
from ..graph import queries
from ..graph.results import parse_select
from ..resultaat import compact, fout, pagina, per_eenheid
from .zoekfilters import datum as _datum
from .stuk_tekst import INHOUD_ARG, inhoudpagina, tekstpagina

logger = logging.getLogger(__name__)

RECHTSPRAAK_TOOL_NAMEN = RECHTSPRAAK.tools
CONNECTOR = RECHTSPRAAK.naam

LIMIT = 25
STANDAARD = 10
#: Een alinea groter dan dit wordt op zinsgrenzen in delen geknipt (elk deel een eigen rij), zodat één rij binnen de
#: begroting blijft. Een deel draagt `deel` ("2/3").
MAX_ALINEA = 3000
#: De titel zoals LiDO hem overneemt ("ECLI:… - Hoge Raad, 21-01-2022 / 21/00733") en zoals de zoekfeed van de
#: Rechtspraak hem geeft ("ECLI:…, Hoge Raad, 02-10-2026, 26/01026").
_TITEL_RE = re.compile(r"^\s*(ECLI:[^\s,]+)\s*[-,]\s*(?P<orgaan>.+?),\s*(?P<d>\d{2})-(?P<m>\d{2})-(?P<j>\d{4})"
                       r"(?:\s*[/,]\s*(?P<zaak>.+?))?\s*$")
_R = "{http://www.rechtspraak.nl/schema/rechtspraak-1.0}"
_RANG = {n: i for i, n in enumerate(INSTANTIES)}


class RechtspraakBron(Protocol):
    def koppelingen(self, bwb_id: str, artikel: str, jci: str = "") -> Any: ...
    def document(self, ecli: str) -> Any: ...
    def metadata(self, ecli: str) -> bytes: ...
    def titel(self, bwb_id: str) -> str: ...
    def zoek(self, *, instanties: tuple[str, ...] = (), rechtsgebieden: tuple[str, ...] = (), soort: str = "",
             vanaf: str = "", tot: str = "", maximum: int = 1000) -> Any: ...
    def instanties(self) -> Any: ...
    def rechtsgebieden(self) -> Any: ...


_CONTRACT = (
    "\nResultaatcontract: {status, volledig, aantal, totaal?, vervolg?, resultaten}. Is `volledig` false, roep "
    "dan `vervolg` aan voor de rest."
)
_UITLEG = (
    " Een uitspraak is rechtspraak, geen wettekst: noem haar met haar ECLI, zeg wat de wet zelf zegt alleen op grond "
    "van de opgehaalde bepaling, en zeg 'noemt het artikel', niet 'legt het uit', tot je de uitspraak hebt gelezen."
)
#: De regel over de versie van het artikel (review ADR-013, 10 nov 2026): LiDO koppelt een uitspraak aan de tekst die
#: gold op haar datum, en een artikel verandert.
_VERSIE = (
    " Een uitspraak bij een 'eerdere tekst' presenteer je niet als uitleg van de huidige norm zonder dat te zeggen, met "
    "de periode erbij ('over de tekst die gold van … tot …'). Ook bij 'huidige tekst' koppelt LiDO alleen naar de datum "
    "van de uitspraak: welke tekst de rechter toepaste (een eerder belastingjaar, overgangsrecht) staat pas in de "
    "uitspraak. Geef 'peildatum' mee als het werkgebied een peildatum heeft of de vraag een datum noemt."
)
#: De standen van de tekst waarbij een uitspraak hoort, en het filter erop.
HUIDIG, EERDER, ONBEKEND = "huidige tekst", "eerdere tekst", "onbekend"
TEKSTSTANDEN = (HUIDIG, EERDER, "op peildatum")
#: Hoogstens zoveel versies in `tekstversies` (de begroting van een pagina is klein; de nieuwste eerst).
MAX_TEKSTVERSIES = 8

RECHTSPRAAK_TOOLS: list[dict[str, Any]] = [
    {
        "name": "zoek_uitspraken",
        "description": (
            "Uitspraken en conclusies zoeken, langs twee wegen. MET 'bwb_id' en 'artikel': de uitspraken die dat "
            "wetsartikel noemen, volgens Linked Data Overheid (KOOP), over alle versies van het artikel; een lid kan "
            "niet, LiDO koppelt per artikel. MET alleen 'bwb_id': de uitspraken die de regeling als geheel noemen (ook een "
            "beleidsregel als de Leidraad Invordering 2008). ZONDER regeling: de zoekfeed van de Rechtspraak zelf, op 'instantie', "
            "'rechtsgebied' (bijvoorbeeld 'belastingrecht'), 'soort' en periode – zo vind je 'de nieuwste uitspraken van "
            "de Hoge Raad in het belastingrecht'. Zoeken op woorden in de tekst kan langs geen van beide. Filter op "
            "'instantie' (een soort gerecht als 'Hoge Raad' of 'rechtbank', of één gerecht als 'Rechtbank Gelderland' of "
            "'CRvB'), 'soort' (uitspraak of conclusie) en een periode ('vanaf', 'tot'). Volgorde 'nieuwste' (standaard) "
            "of 'oudste', op de datum van de uitspraak. Met artikel ook 'tekststand' (huidige tekst, eerdere tekst, op "
            "peildatum) en 'peildatum'." + _UITLEG + _VERSIE + "\n"
            "GEEFT TERUG per uitspraak: id (de ECLI), label, soort, titel, datum (van de uitspraak), orgaan (het "
            "gerecht), nummer (het zaaknummer), link, met artikel tekst_vanaf en tekst_tot (de tekst van het artikel "
            "waaraan LiDO de uitspraak koppelde), tekststand ('huidige tekst', 'eerdere tekst' of 'onbekend', tegenover "
            "de tekst in de graaf) en met een peildatum op_peildatum, en, zonder artikel, samenvatting (de ingekorte inhoudsindicatie); leesbaar: false als de tekst niet bij de Rechtspraak staat (een "
            "buitenlandse of Europese ECLI). Daarnaast 'bepaling', 'zoekvraag', 'totaal', 'per_instantie' (hoeveel "
            "uitspraken per soort gerecht), 'koppelingen' (hoeveel LiDO automatisch herkende en hoeveel een redactie "
            "legde), 'huidige_tekst' (sinds wanneer de tekst in de graaf geldt), 'per_tekststand', 'tekstversies' (per "
            "versie van het artikel vanaf, tot en hoeveel uitspraken) en 'dekking': "
            "altijd 'ten minste', met 'versies' (hoeveel versies van het artikel LiDO kende). 'totaal' telt wat aan alle "
            "filters voldoet; per_instantie, per_tekststand en tekstversies tellen binnen de andere filters (per_instantie "
            "negeert alleen 'instantie', per_tekststand alleen 'tekststand'), en 'bij_het_artikel' is het aantal zonder "
            # Ronde 2, R22: "past bij het civielrechtelijke karakter van het artikel" bij een telling per instantie.
            "filters. Een telling duid je niet: zeg wat ze telt, niet wat ze over het artikel of zijn karakter zegt. "
            "Noem bij een lijst het "
            "totaal en dat het om vermeldingen gaat. Lees een uitspraak met get_uitspraak voor je zegt wat ze inhoudt."
            + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bwb_id": {"type": "string", "description": "BWB-id van de regeling, bijvoorbeeld 'BWBR0004770'; "
                                                            "met 'artikel' de uitspraken bij dat artikel, zonder de "
                                                            "uitspraken die de regeling als geheel noemen; weg voor de "
                                                            "zoekfeed."},
                "artikel": {"type": "string", "description": "Het artikelnummer, bijvoorbeeld '36' of '8:57'."},
                "instantie": {"type": "string",
                              "description": ("Een soort gerecht (" + ", ".join(INSTANTIES[:7]) + ") of één gerecht "
                                              "met naam of afkorting, bijvoorbeeld 'Rechtbank Gelderland' of 'CRvB'.")},
                "rechtsgebied": {"type": "string", "description": "Alleen zonder artikel (met een artikel past de tool "
                                 "het niet toe en zegt hij dat): een rechtsgebied uit de "
                                 "waardelijst van de Rechtspraak, bijvoorbeeld 'belastingrecht' of 'bestuursrecht'."},
                "soort": {"type": "string", "enum": ["uitspraak", "conclusie"],
                          "description": "Een uitspraak of een conclusie van de advocaat-generaal."},
                "vanaf": {"type": "string", "description": "Vanaf deze datum van de uitspraak: JJJJ-MM-DD, JJJJ-MM of "
                                                           "JJJJ, bijvoorbeeld '2020'."},
                "tot": {"type": "string", "description": "Tot en met deze datum, in dezelfde vorm."},
                "tekststand": {"type": "string", "enum": list(TEKSTSTANDEN),
                               "description": "Alleen met artikel: de uitspraken bij de huidige tekst, bij een eerdere "
                                              "tekst, of bij de tekst die gold op de 'peildatum'."},
                "peildatum": {"type": "string", "description": "Alleen met artikel: de datum waarop de tekst moet "
                              "gelden (JJJJ-MM-DD), bijvoorbeeld de peildatum van het werkgebied; elke uitspraak zegt "
                              "dan of haar tekst toen gold (op_peildatum)."},
                "volgorde": {"type": "string", "enum": list(RECHTSPRAAK.volgordes),
                             "description": "nieuwste of oudste (op de datum van de uitspraak)."},
                "aantal": {"type": "integer", "description": f"Hoeveel per pagina, 1 tot {LIMIT}."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_uitspraak",
        "description": (
            "De tekst van één Nederlandse uitspraak of conclusie uit de open data van de Rechtspraak, per alinea in "
            "documentvolgorde, met de inhoudsindicatie eerst. Gebruik de ECLI uit zoek_uitspraken." + _UITLEG +
            " Citeer letterlijk uit 'tekst'.\n"
            "GEEFT TERUG: het stuk (id, label, soort, titel, datum, orgaan, nummer, procedure, rechtsgebied, "
            "gepubliceerd, link, bron_hash, gewijzigd) en per alinea nr, kop en tekst (de kop alleen waar hij verandert; "
            "hij geldt tot de volgende), met 'plek' als de alinea in een "
            "genummerde rechtsoverweging staat ('r.o. 2.1'; noem haar zo); een lange alinea staat in delen ('deel'). De "
            "eerste pagina van een stuk dat niet op één pagina past draagt 'inhoud': per kop de offset waar dat deel begint; ga met die offset naar het deel dat "
            "de vraag raakt. Voor een samenvatting ('wat staat er in') volstaan de inhoudsindicatie, de inhoud en het deel met de "
            "beslissing: blader niet alle pagina's door. Noem de datum en de instantie uit 'stuk', niet uit de tekst."
            + _CONTRACT
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "De ECLI, bijvoorbeeld 'ECLI:NL:HR:2022:50'."},
                "offset": {"type": "integer", "description": "Voor het vervolg; begin bij 0."},

                "inhoud": INHOUD_ARG,
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
]


# --- de metadata van een uitspraak --------------------------------------------------------------------------------

def instantie(ecli: str) -> str:
    """De soort gerecht uit de code in de ECLI (`INSTANTIES`)."""
    delen = ecli.upper().split(":")
    land, code = (delen[1], delen[2]) if len(delen) > 2 else ("", "")
    if land == "CE":
        return "Europees Hof voor de Rechten van de Mens"
    if land == "EU":
        return "Hof van Justitie van de EU"
    if land != "NL":
        return "overig"
    vast = {"HR": "Hoge Raad", "PHR": "Parket bij de Hoge Raad", "RVS": "Raad van State",
            "CRVB": "Centrale Raad van Beroep", "CBB": "College van Beroep voor het bedrijfsleven"}
    if code in vast:
        return vast[code]
    if code.startswith("GH"):
        return "gerechtshof"
    if code.startswith("RB"):
        return "rechtbank"
    return "overig"


def soort_van(ecli: str) -> str:
    return "Conclusie" if ecli.upper().split(":")[2:3] == ["PHR"] else "Uitspraak"


def koppeling_van(soorten: set[str]) -> str:
    return "redactioneel" if any("Redactionele" in k for k in soorten) else "automatisch herkend"


def rij_van(ecli: str, titel: str) -> dict[str, Any]:
    """Eén uitspraak in de vaste metadatasleutels (`METADATA_SLEUTELS`), uit de ECLI en de titel die LiDO van de
    Rechtspraak overneemt. De soort gerecht (voor het filter) leidt `instantie` af uit de ECLI; die staat niet in de rij."""
    vp = externe_vindplaats(ecli)
    ident = vp.id if vp is not None else ecli
    m = _TITEL_RE.match(titel or "")
    datum = f"{m['j']}-{m['m']}-{m['d']}" if m else ""
    return compact({
        "id": ident, "label": label_van(ident, {"creator": m["orgaan"].strip(), "date": f"{m['j']}-{m['m']}-{m['d']}"})
        if m else (vp.label if vp is not None else ident), "soort": soort_van(ident), "titel": titel,
        "datum": datum or (ident.split(":")[3] if ident.count(":") >= 3 else ""),
        "orgaan": (m["orgaan"].strip() if m else "") or instantie(ident),
        "nummer": (m["zaak"] or "").strip() if m else "",
        "link": vp.uri if vp is not None else "",
        **({"leesbaar": False} if not ident.upper().startswith("ECLI:NL:") else {})})


#: Hoeveel rijen zonder titel `_aangevuld` hoogstens aanvult vóór het sorteren; daarboven alleen de getoonde pagina.
MAX_AANVULLEN = 50


def _aangevuld(bron: RechtspraakBron, rij: dict[str, Any]) -> dict[str, Any]:
    """Een rij zonder titel (een koppeling die LiDO alleen in RDF gaf) met datum, gerecht, titel en zaaknummer uit de
    metadata van de Rechtspraak. Meting 11 nov 2026 (`rechtspraak-versies-2026-11-11`, vraag 3): de 14 uitspraken bij de
    tekst op peildatum 2015 droegen alleen het jaar en "rechtbank". Lukt het niet, dan blijft de rij zoals hij was: het
    jaar uit de ECLI is waar, alleen minder precies."""
    if rij.get("titel") or not str(rij.get("id", "")).upper().startswith("ECLI:NL:"):
        return rij
    try:
        meta, _ = lees(bron.metadata(rij["id"]))
    except (RechtspraakFout, ET.ParseError) as exc:
        logger.info("uitspraak zonder metadata", extra={"ecli": rij["id"], "reden": str(exc)[:200]})
        return rij
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta.get("date", "")):
        return rij
    return {**rij, **compact({"label": label_van(rij["id"], meta), "titel": meta.get("title", ""),
                              "datum": meta["date"], "orgaan": meta.get("creator", "") or rij.get("orgaan", ""),
                              "nummer": meta.get("zaaknummer", "")})}


# --- zoeken --------------------------------------------------------------------------------------------------------

def _q_artikel(bwb_id: str, artikel: str) -> str:
    """De jci, de label-id, het soort van de bepaling en de citeertitel van haar regeling, uit de graaf."""
    return queries.PREFIXES + f"""SELECT ?node ?jci ?labelId ?label ?soort ?citeertitel ?inwerking ?terugwerkendTot WHERE {{
  {queries.node_patroon(bwb_id, artikel)}
  ?node a ?soort . FILTER(?soort IN (bwb:Artikel, bwb:Divisie))
  OPTIONAL {{ ?node bwb:jci ?jci }}
  OPTIONAL {{ ?node bwb:inwerking ?inwerking }}
  OPTIONAL {{ ?node bwb:terugwerkendTot ?terugwerkendTot }}
  OPTIONAL {{ ?node bwb:labelId ?labelId }}
  OPTIONAL {{ ?node rdfs:label ?label }}
  OPTIONAL {{ ?reg a bwb:Regeling ; bwb:bwbId {queries._lit(bwb_id)} ; bwb:citeertitel ?citeertitel }}
}} LIMIT 2"""


@dataclass(frozen=True)
class Tekstversie:
    """Eén versie van het artikel in LiDO: sinds wanneer en tot wanneer die tekst gold, en of het de tekst in de graaf
    is (`huidig`: True, False, of None als dat niet vast te stellen is)."""
    versie: str
    vanaf: str
    tot: str
    huidig: bool | None


def _dag_ervoor(datum: str) -> str:
    try:
        return (dt.date.fromisoformat(datum) - dt.timedelta(days=1)).isoformat()
    except ValueError:
        return ""


def tekstversies(versies: tuple[str, ...] | list[str], huidig: tuple[str, ...] = ()) -> tuple[list[Tekstversie], bool]:
    """(de versies met hun periode, nieuwste eerst; of LiDO de huidige tekst nog niet kent).

    `huidig` zijn de datums waarop de tekst in de graaf ging gelden (`bwb:inwerking`, en `bwb:terugwerkendTot` als die er
    is). Een LiDO-versie begint op de inwerkingtreding van haar tekst (dump 10 nov 2026: elke wijziging een versie, geen
    versie zonder wijziging), dus de versie met die begindatum is de tekst in de graaf. Een versie die daarvóór begint
    is een eerdere tekst; een die daarna begint kent de graaf nog niet (onbekend). Begint de nieuwste versie vóór de
    tekst in de graaf, dan kent LiDO die tekst nog niet: alles is dan een eerdere tekst, en de nieuwste gold tot de dag
    vóór de huidige. Zonder `huidig` is de stand onbekend, maar de perioden staan er wel."""
    met = sorted({(b, v) for v in versies if (b := begindatum(v))}, reverse=True)
    uit: list[Tekstversie] = []
    huidig = tuple(sorted(d for d in huidig if d))
    loopt_achter = bool(huidig and met and met[0][0] < huidig[0])
    for i, (begin, v) in enumerate(met):
        tot = _dag_ervoor(met[i - 1][0]) if i else (_dag_ervoor(max(huidig)) if loopt_achter else "")
        if not huidig:
            stand = None
        elif begin in huidig:
            stand = True
        elif begin < huidig[0]:
            stand = False
        else:
            stand = None
        uit.append(Tekstversie(v, begin, tot, stand))
    return uit, loopt_achter


def _tekst_van(versies: list[Tekstversie], peildatum: str) -> dict[str, Any]:
    """De velden van een rij uit de versies waaraan LiDO de uitspraak koppelde: de vroegste vanaf, de laatste tot (leeg
    als een versie nog geldt), de stand (huidig als een versie de tekst in de graaf is) en met een peildatum of een van
    die teksten toen gold."""
    if not versies:
        return {}
    standen = {t.huidig for t in versies}
    uit: dict[str, Any] = {
        "tekst_vanaf": min(t.vanaf for t in versies),
        "tekst_tot": "" if any(not t.tot for t in versies) else max(t.tot for t in versies),
        "tekststand": HUIDIG if True in standen else EERDER if standen == {False} else ONBEKEND,
    }
    if peildatum:
        uit["op_peildatum"] = any(t.vanaf <= peildatum and (not t.tot or peildatum <= t.tot) for t in versies)
    return uit


def _voluit(datum: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", datum or "")
    return f"{int(m[3])} {_MAANDEN[int(m[2]) - 1]} {m[1]}" if m else datum


def _in_woorden(label: str, regeling: str) -> str:
    """"artikel 36 van de Invorderingswet 1990": de bepaling waarbij gezocht is, voor de zoekvraag in woorden."""
    label = label[:1].lower() + label[1:] if label[:1].isupper() and not label[1:2].isupper() else label
    return f"{label} van {regeling}" if regeling else label


@dataclass(frozen=True)
class _Keuze:
    """Een instantie zoals de jurist haar noemt: een soort gerecht ("rechtbank") of één gerecht ("Rechtbank
    Gelderland", "CRvB"). Voor LiDO de toets op de ECLI, voor de feed de URI's uit de waardelijst."""
    label: str
    soort: str = ""
    codes: frozenset[str] = frozenset()
    uris: tuple[str, ...] = ()

    def past(self, ecli: str) -> bool:
        if self.soort:
            return instantie(ecli) == self.soort
        return ecli.upper().split(":")[2:3] and ecli.upper().split(":")[2] in self.codes  # type: ignore[return-value]


#: De soort gerecht (`INSTANTIES`) naar het type in de waardelijst Instanties; de laatste drie kent de feed niet.
_TYPE_VAN = {"Hoge Raad": ("TypeHr",), "Parket bij de Hoge Raad": ("Parket",), "Raad van State": ("TypeRvS",),
             "Centrale Raad van Beroep": ("TypeCRvB",), "College van Beroep voor het bedrijfsleven": ("TypeCBb",),
             "gerechtshof": ("Gerechtshof",), "rechtbank": ("Rechtbank",)}
#: Afkortingen die een jurist gebruikt naast die van de waardelijst (daar heet de CRvB "CRVB").
_AFKORTINGEN = {"crvb": "CRVB", "cbb": "CBB", "rvs": "RVS", "abrvs": "RVS", "hr": "HR", "phr": "PHR"}


def _instantie_keuze(bron: RechtspraakBron, waarde: str) -> "_Keuze | str":
    """De instantie uit de woorden van de jurist; een foutresultaat met een voorbeeld als ze niet bestaat."""
    w = " ".join(waarde.split())
    w = INSTANTIE_MEERVOUD.get(w.lower(), w)
    soort = next((i for i in INSTANTIES if i.lower() == w.lower()), "")
    if soort:
        # Een soort gerecht: LiDO toetst de ECLI, de feed krijgt de gerechten van dat type (`_feed_uris`).
        return _Keuze(soort, soort=soort)
    code = _AFKORTINGEN.get(w.lower(), w.upper())
    # Eén gerecht: de waardelijst. Is die niet te lezen, dan is dat een storing (`RechtspraakFout`), geen onbekend gerecht.
    gevonden = [i for i in bron.instanties() if i.naam.lower() == w.lower() or i.afkorting.upper() == code]
    if not gevonden:
        return fout("ongeldige_argumenten", f"de instantie {waarde!r} ken ik niet; geef een soort gerecht ("
                    f"{', '.join(INSTANTIES[:7])}) of de naam van één gerecht uit de waardelijst van de Rechtspraak, "
                    "bijvoorbeeld 'Rechtbank Gelderland' of 'CRvB'")
    return _Keuze(gevonden[0].naam, codes=frozenset(i.afkorting.upper() for i in gevonden),
                  uris=tuple(i.uri for i in gevonden))


def _rechtsgebied_uris(bron: RechtspraakBron, waarde: str) -> "tuple[str, ...] | str":
    w = " ".join(waarde.split()).lower()
    gebieden = tuple(bron.rechtsgebieden())
    gevonden = [r for r in gebieden if r.naam.lower() == w] or [r for r in gebieden if r.naam.lower() == w + "recht"]
    if not gevonden:
        return fout("ongeldige_argumenten", f"het rechtsgebied {waarde!r} staat niet in de waardelijst van de "
                    "Rechtspraak; geef bijvoorbeeld 'belastingrecht', 'bestuursrecht' of 'strafrecht'")
    return tuple(r.uri for r in gevonden)


def _laatste_dag(datum: str) -> str:
    """'2026-02-31' (het einde van een maand uit `_datum`) als echte datum, voor de feed."""
    j, m, d = (int(x) for x in datum.split("-"))
    return dt.date(j, m, min(d, calendar.monthrange(j, m)[1])).isoformat()


#: Het venster van de feed begint zo breed en groeit (×4) of krimpt (÷2) tot het genoeg uitspraken bevat en op één
#: pagina past. De feed sorteert alleen op wijzigingsdatum, dus "nieuwste" op de datum van de uitspraak doet de code.
_START_DAGEN = 31
_MAX_STAPPEN = 12
BEGIN_FEED = "1913-01-01"


def _venster(bron: RechtspraakBron, filters: dict[str, Any], *, nieuwste: bool, nodig: int, vanaf: str, tot: str):
    """(treffers in het venster, het venster, of het venster het hele gevraagde bereik dekt). Eerst het hele bereik: past
    dat op één pagina, dan is dat het venster."""
    van, tm = dt.date.fromisoformat(vanaf), dt.date.fromisoformat(tot)
    alles = bron.zoek(**filters, vanaf=vanaf, tot=tot)
    if alles.totaal <= len(alles.treffers):
        return alles.treffers, (vanaf, tot), True, alles.totaal
    dagen = _START_DAGEN
    for _ in range(_MAX_STAPPEN):
        lo, hi = (max(van, tm - dt.timedelta(days=dagen)), tm) if nieuwste else (van, min(tm, van + dt.timedelta(days=dagen)))
        feed = bron.zoek(**filters, vanaf=lo.isoformat(), tot=hi.isoformat())
        heel = lo == van and hi == tm
        if feed.totaal > len(feed.treffers):
            if dagen <= 1:
                return feed.treffers, (lo.isoformat(), hi.isoformat()), False, alles.totaal
            dagen = max(1, dagen // 2)
        elif feed.totaal >= nodig or heel:
            return feed.treffers, (lo.isoformat(), hi.isoformat()), heel, alles.totaal
        else:
            dagen *= 4
    return feed.treffers, (lo.isoformat(), hi.isoformat()), False, alles.totaal


def _zoek_feed(bron: RechtspraakBron, a: dict[str, Any], keuze: "_Keuze | None", *, volgorde: str, vanaf: str, tot: str,
               aantal: int, offset: int) -> str:
    """Zonder artikel: de zoekfeed van de Rechtspraak (instantie, rechtsgebied, soort, periode)."""
    if keuze is not None and keuze.soort in _TYPE_VAN:
        keuze = _Keuze(keuze.label, soort=keuze.soort,
                       uris=tuple(i.uri for i in bron.instanties() if i.actief and i.type in _TYPE_VAN[keuze.soort]))
    if keuze is not None and not keuze.uris:
        return fout("ongeldige_argumenten", f"de zoekfeed van de Rechtspraak kent {keuze.label!r} niet als gerecht; "
                    "zoek die uitspraken bij een artikel, bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}")
    rechtsgebieden: tuple[str, ...] = ()
    if a.get("rechtsgebied"):
        r = _rechtsgebied_uris(bron, str(a["rechtsgebied"]))
        if isinstance(r, str):
            return r
        rechtsgebieden = r
    soort = {"uitspraak": "Uitspraak", "conclusie": "Conclusie"}.get(str(a.get("soort") or "").lower(), "")
    filters = {"instanties": keuze.uris if keuze else (), "rechtsgebieden": rechtsgebieden, "soort": soort}
    van = vanaf or BEGIN_FEED
    tm = _laatste_dag(tot) if tot else dt.date.today().isoformat()
    treffers, venster, heel, totaal = _venster(bron, filters, nieuwste=volgorde == "nieuwste", nodig=offset + aantal + 1,
                                               vanaf=_laatste_dag(van), tot=tm)
    lijst = [{**rij_van(t.ecli, t.titel), **({"samenvatting": t.samenvatting} if t.samenvatting else {})}
             for t in treffers]
    lijst = [r for r in lijst if keuze is None or not keuze.codes or keuze.past(r["id"])]
    lijst.sort(key=lambda r: (_RANG.get(instantie(r["id"]), 99), r["id"]))
    lijst.sort(key=lambda r: r["datum"], reverse=volgorde == "nieuwste")
    toelichting = ""
    if not heel and len(lijst) <= offset + aantal:
        toelichting = (f"Op één dag ({venster[0]}) staan meer uitspraken dan de feed in één keer geeft; de lijst "
                       "toont een deel daarvan. Verfijn met een instantie of rechtsgebied.")
    elif not lijst:
        toelichting = "De Rechtspraak heeft geen uitspraken met tekst die aan de filters voldoen."
    extra = compact({
        "totaal": totaal, "bron": "zoekfeed van de Rechtspraak",
        "zoekvraag": {**{x: v for x, v in a.items() if x not in {"offset"} and v not in ("", None)}, "volgorde": volgorde,
                      **({"instantie": keuze.label} if keuze else {})},
    })
    return pagina(lijst[offset:offset + aantal + 1], tool="zoek_uitspraken", args={**a, "aantal": aantal},
                  limit=aantal, offset=offset, toelichting=toelichting, extra=extra)


def _stand_zin(label: str, versies: list[Tekstversie], huidig: tuple[str, ...], loopt_achter: bool,
               per_tekststand: dict[str, int], totaal: int, buiten_graaf: bool = False) -> str:
    """Wat de lijst zegt over de tekst van het artikel, in één zin, uit de versies en de graaf. Nooit een zin die meer
    weet dan LiDO: een uitspraak bij de huidige tekst kan nog over een eerder belastingjaar gaan."""
    if not versies or not totaal:
        return ""
    lab = label[:1].lower() + label[1:] if label[:1].isupper() and not label[1:2].isupper() else label
    if buiten_graaf:
        return (f"De regeling van {lab} staat niet in de kennisgraaf; bij welke tekst van het artikel een uitspraak "
                "hoort, is daarom niet vast te stellen.")
    if not huidig:
        return (f"Sinds wanneer de huidige tekst van {lab} geldt, staat niet in de graaf; bij welke tekst een uitspraak "
                "hoort, is daarom niet vast te stellen.")
    if loopt_achter:
        return (f"LiDO kent de huidige tekst van {lab} (geldig vanaf {_voluit(min(huidig))}) nog niet: alle uitspraken "
                "hieronder noemen een eerdere tekst.")
    eerder = per_tekststand.get(EERDER, 0)
    if not eerder:
        return ""
    return (f"{eerder} van de {totaal} uitspraken noemen een eerdere tekst van {lab}, die gold vóór "
            f"{_voluit(min(huidig))}.")


def _regeling_buiten_graaf(graph: Any, bwb_id: str) -> bool:
    """Staat de regeling niet in de kennisgraaf? Alleen waar als de graaf dat zegt; een graaf die niet antwoordt is
    geen "staat er niet in"."""
    from .wetgeving_tools import GraafOnbekend, graaftoestanden

    try:
        return graaftoestanden(graph, [bwb_id]).get(bwb_id) is None
    except GraafOnbekend:
        return False


def _zoek(bron: RechtspraakBron, graph: Any, a: dict[str, Any]) -> str:
    bwb_id, artikel = (a.get("bwb_id") or "").strip(), (a.get("artikel") or "").strip()
    # Een regeling zonder artikel mag: de uitspraken die de regeling als geheel noemen ("Welke uitspraken noemen de
    # Leidraad Invordering 2008?", ronde 2, R26: de zoekfeed gaf willekeurige uitspraken in het belastingrecht).
    if (bwb_id or artikel) and not re.fullmatch(r"BWB[RV]\d{7}", bwb_id):
        return fout("ongeldige_argumenten", "geef de regeling (en eventueel het artikel), bijvoorbeeld "
                    "{\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}, of laat ze allebei weg om in de zoekfeed van "
                    "de Rechtspraak te zoeken, bijvoorbeeld {\"instantie\": \"Hoge Raad\"}")
    volgorde = a.get("volgorde") or "nieuwste"
    if volgorde not in RECHTSPRAAK.volgordes:
        return fout("ongeldige_volgorde", f"de volgorde is 'nieuwste' of 'oudste', bijvoorbeeld "
                    f"{{\"volgorde\": \"oudste\"}}, niet {volgorde!r}")
    keuze = None
    if a.get("instantie"):
        keuze = _instantie_keuze(bron, str(a["instantie"]))
        if isinstance(keuze, str):
            return keuze
    try:
        vanaf = _datum(a["vanaf"], eind=False) if a.get("vanaf") else ""
        tot = _datum(a["tot"], eind=True) if a.get("tot") else ""
    except ValueError as exc:
        return fout("ongeldige_datum", f"een datum is JJJJ-MM-DD, JJJJ-MM of JJJJ, bijvoorbeeld '2020', niet {exc}")
    try:
        aantal = int(a.get("aantal") or STANDAARD)
    except (TypeError, ValueError):
        aantal = 0
    if not 1 <= aantal <= LIMIT:
        return fout("ongeldig_aantal", f"het aantal is 1 tot {LIMIT}, bijvoorbeeld {{\"aantal\": 10}}")
    offset = max(int(a.get("offset") or 0), 0)
    stand = str(a.get("tekststand") or "").strip().lower()
    if stand and stand not in TEKSTSTANDEN:
        return fout("ongeldige_argumenten", "de tekststand is 'huidige tekst', 'eerdere tekst' of 'op peildatum', "
                    "bijvoorbeeld {\"tekststand\": \"huidige tekst\"}")
    try:
        peildatum = _datum(a["peildatum"], eind=False) if a.get("peildatum") else ""
    except ValueError as exc:
        return fout("ongeldige_datum", f"de peildatum is JJJJ-MM-DD, bijvoorbeeld '2015-01-01', niet {exc}")
    if stand == "op peildatum" and not peildatum:
        return fout("ongeldige_argumenten", "'op peildatum' vraagt een peildatum, bijvoorbeeld "
                    "{\"tekststand\": \"op peildatum\", \"peildatum\": \"2015-01-01\"}")
    if not bwb_id and (stand or peildatum):
        return fout("ongeldige_argumenten", "de tekststand en de peildatum gaan over de tekst van een artikel: geef "
                    "ook 'bwb_id' en 'artikel', bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\", "
                    "\"peildatum\": \"2015-01-01\"}")
    if not bwb_id:
        return _zoek_feed(bron, a, keuze, volgorde=volgorde, vanaf=vanaf, tot=tot, aantal=aantal, offset=offset)
    # LiDO kent geen rechtsgebied. Weigeren liet het model de vraag overnemen en het filter stil laten vallen (meting 11
    # nov 2026, R24: 93k tokens); nu zoekt de tool zonder en zegt hij het, ook tegen de jurist (`kanttekening`).
    genegeerd = str(a.get("rechtsgebied") or "").strip()
    a = {k: v for k, v in a.items() if k != "rechtsgebied"}

    # Uit de graaf: de jci (de terugvalroute van LiDO, nodig voor de Awb), het label en of het een artikel is. Zonder
    # graaf (een MCP-client, de contractharnas) zoekt LiDO het artikel op bwb-id en nummer.
    zonder_graaf = [{"label": f"artikel {artikel}", "soort": "Artikel"}]
    buiten_graaf = False
    if not artikel:
        # De regeling als geheel: LiDO koppelt een uitspraak die de regeling noemt zonder artikel aan de regeling zelf.
        titel = (getattr(bron, "titel", None) or (lambda _b: ""))(bwb_id)
        rijen = [{"label": titel or bwb_id, "soort": "Regeling"}]
    else:
        rijen = parse_select(graph.sparql(_q_artikel(bwb_id, artikel))) if graph is not None else zonder_graaf
    if not rijen:
        # Een regeling die niet in de kennisgraaf staat (de Wet IB 2001, de Wet OB 1968) kent LiDO wel: zoek dan op
        # bwb-id en nummer, zoals zonder graaf (meting 11 nov 2026, R09/R10: "staat niet in de graaf" bij een artikel
        # met honderden uitspraken). Staat de regeling er wel in, dan bestaat het artikel niet: een tikfout.
        if not _regeling_buiten_graaf(graph, bwb_id):
            return fout("niet_gevonden", f"artikel {artikel} van {bwb_id} staat niet in de graaf. Controleer het "
                        "nummer, bijvoorbeeld met get_artikel.")
        # De naam uit de BWB-zoekdienst, zodat de zoekvraag en de bronnenlijst de regeling noemen (ronde 2, R09/R10).
        titel = (getattr(bron, "titel", None) or (lambda _b: ""))(bwb_id)
        rijen, buiten_graaf = [{**zonder_graaf[0], **({"citeertitel": titel} if titel else {})}], True
    kop = rijen[0]
    label = kop.get("label") or f"artikel {artikel}"
    bepaling = compact({"bwb_id": bwb_id, "artikel": artikel, "label": label})
    if artikel and not str(kop.get("soort", "")).endswith("Artikel"):
        return pagina([], tool="zoek_uitspraken", args=a, limit=aantal, offset=offset,
                      toelichting=(f"{label} is een divisie van een beleidsregel. LiDO koppelt uitspraken alleen aan "
                                   "artikelen van wetten en regelingen; de divisies kent het niet."),
                      extra={"bepaling": bepaling, "dekking": "ten minste", "totaal": 0})
    k = bron.koppelingen(bwb_id, artikel, kop.get("jci") or "")

    # De versies van het artikel met hun periode, tegenover de tekst in de graaf (review ADR-013: een uitspraak over
    # een eerdere rechtsstand hoort niet ongemerkt bij de huidige norm).
    huidig = tuple(d for d in (str(kop.get("inwerking") or "")[:10], str(kop.get("terugwerkendTot") or "")[:10]) if d)
    versies, loopt_achter = tekstversies(k.versies, huidig)
    per_versie = {t.versie: t for t in versies}

    # Eén rij per uitspraak, verenigd over de versies; de koppelingen (automatisch, redactioneel) samen.
    per: dict[str, tuple[str, set[str], set[str]]] = {}
    for ln in k.links:
        titel, soorten, vs = per.get(ln.ecli, ("", set(), set()))
        per[ln.ecli] = (titel or ln.titel, soorten | {ln.soort_link}, vs | {ln.versie})
    alle = [{**rij_van(e, t), **_tekst_van([per_versie[v] for v in sorted(vs) if v in per_versie], peildatum)}
            for e, (t, _, vs) in per.items()]
    # De filters als losse toetsen, zodat elke telling binnen de andere filters telt (zoals een facet): "487 van de
    # gerechtshoven" naast tellingen over alle 623 uitspraken bij het artikel was tegenstrijdig (meting 11 nov 2026, R06).
    toetsen = {
        "instantie": lambda r: keuze is None or keuze.past(r["id"]),
        "soort": lambda r: not a.get("soort") or r["soort"].lower() == a["soort"],
        "periode": lambda r: (not vanaf or r["datum"] >= vanaf) and (not tot or r["datum"][:10] <= tot),
        "tekststand": lambda r: not stand or (r.get("op_peildatum") is True if stand == "op peildatum"
                                              else r.get("tekststand") == stand),
    }

    def binnen(r: dict[str, Any], behalve: str = "") -> bool:
        return all(t(r) for n, t in toetsen.items() if n != behalve)

    lijst = [r for r in alle if binnen(r)]
    per_instantie: dict[str, int] = {}
    for r in alle:
        if binnen(r, "instantie"):
            per_instantie[instantie(r["id"])] = per_instantie.get(instantie(r["id"]), 0) + 1
    koppelingen: dict[str, int] = {}
    for r in lijst:
        soort_k = koppeling_van(per[r["id"]][1])
        koppelingen[soort_k] = koppelingen.get(soort_k, 0) + 1
    zonder_stand = [r for r in alle if binnen(r, "tekststand")]
    per_tekststand: dict[str, int] = {}
    for r in zonder_stand:
        if r.get("tekststand"):
            per_tekststand[r["tekststand"]] = per_tekststand.get(r["tekststand"], 0) + 1
    # Rijen zonder titel krijgen hun datum uit de metadata, vóór het sorteren, zodat de volgorde op de dag klopt. Zijn
    # het er meer dan `MAX_AANVULLEN`, dan alleen de getoonde pagina (hieronder): de Rechtspraak vraagt rust.
    vooraf = sum(1 for r in lijst if not r.get("titel")) <= MAX_AANVULLEN
    if vooraf:
        lijst = [_aangevuld(bron, r) for r in lijst]
    # Op datum; bij dezelfde datum de hoogste instantie eerst, dan de ECLI (vast, dus dezelfde vraag dezelfde lijst).
    lijst.sort(key=lambda r: (_RANG.get(instantie(r["id"]), 99), r["id"]))
    lijst.sort(key=lambda r: r["datum"], reverse=volgorde == "nieuwste")
    toelichting = ""
    if k.onvolledig:
        toelichting = (f"Van {len(k.onvolledig)} van de {len(k.versies)} versies kwam niet alles binnen (plafond of een "
                       "afgebroken antwoord van LiDO); de lijst is daar korter dan wat LiDO kent.")
        # LiDO telt zelf hoeveel uitspraken een versie noemt (het facet van de eerste pagina): noem dat, zodat "ten
        # minste" een getal heeft.
        telling = sum(k.totaal_lido.get(v, 0) for v, _ in k.onvolledig)
        binnen_v = sum(1 for _, (_, _, vs) in per.items() if vs & {v for v, _ in k.onvolledig})
        if telling > binnen_v:
            toelichting += (f" LiDO telt bij die versie{'s' if len(k.onvolledig) > 1 else ''} {telling} uitspraken; "
                            f"hiervan kwamen er {binnen_v} binnen.")
    elif not k.versies:
        toelichting = (f"LiDO kent {label} van {bwb_id} niet; dat zegt niet dat er geen uitspraken over zijn. Zoek "
                       "eventueel via een andere bron.")
    elif not lijst:
        toelichting = "LiDO noemt bij dit artikel geen uitspraken die aan de filters voldoen."
    # Wat de jurist bij de lijst moet weten: waar deze zoekvraag minder kon dan ze vroeg (`kanttekening`, het blok
    # toont het). De toelichting zegt het ook, voor het model.
    kanttekening = " ".join(z for z in (
        toelichting if (k.onvolledig or not k.versies) else "",
        _stand_zin(label, versies, huidig, loopt_achter, per_tekststand, len(zonder_stand), buiten_graaf)
        if buiten_graaf else "",
        (f"LiDO kent geen rechtsgebied; het filter op „{genegeerd}” is niet toegepast." if genegeerd else ""),
        ("Dit zijn de uitspraken die de regeling als geheel noemen; een uitspraak die een artikel of onderdeel noemt, "
         "staat bij dat artikel." if not artikel else ""),
    ) if z)
    if (stand_zin := _stand_zin(label, versies, huidig, loopt_achter, per_tekststand, len(zonder_stand),
                                buiten_graaf)):
        toelichting = f"{toelichting} {stand_zin}".strip()
    if genegeerd:
        toelichting = f"{toelichting} LiDO kent geen rechtsgebied: het filter op {genegeerd!r} is niet toegepast; zeg dat.".strip()
    per_tv: dict[str, int] = {}
    for r in zonder_stand:
        for v in per[r["id"]][2]:
            per_tv[v] = per_tv.get(v, 0) + 1
    extra = compact({
        "bepaling": bepaling, "totaal": len(lijst), "dekking": "ten minste", "versies": len(k.versies),
        "kanttekening": kanttekening,
        "bij_het_artikel": len(alle) if len(alle) != len(lijst) else None,
        "huidige_tekst": {"vanaf": min(huidig)} if huidig else {},
        "per_tekststand": per_tekststand,
        "tekstversies": [compact({"vanaf": t.vanaf, "tot": t.tot, "uitspraken": per_tv.get(t.versie, 0)})
                         for t in versies[:MAX_TEKSTVERSIES]],
        "peildatum": peildatum,
        "per_instantie": dict(sorted(per_instantie.items(), key=lambda x: _RANG.get(x[0], 99))),
        "koppelingen": koppelingen,
        "zoekvraag": {**{x: v for x, v in a.items() if x not in {"offset"} and v not in ("", None)},
                      "volgorde": volgorde,
                      "bepaling": (_in_woorden(label, kop.get("citeertitel") or bwb_id) if artikel
                                   else f"{label} als geheel")},
    })
    getoond = lijst[offset:offset + aantal + 1]
    return pagina(getoond if vooraf else [_aangevuld(bron, r) for r in getoond], tool="zoek_uitspraken",
                  args={**a, "aantal": aantal}, limit=aantal, offset=offset, toelichting=toelichting, extra=extra)


# --- lezen ---------------------------------------------------------------------------------------------------------

def _tekst(e: ET.Element) -> str:
    return " ".join("".join(e.itertext()).split())


def _knip(tekst: str) -> list[str]:
    """Een lange alinea in delen op zinsgrenzen, elk hoogstens `MAX_ALINEA` tekens (een zin langer dan dat blijft heel
    en wordt op een spatie geknipt)."""
    if len(tekst) <= MAX_ALINEA:
        return [tekst]
    delen, huidig = [], ""
    for zin in re.split(r"(?<=[.;:])\s+", tekst):
        while len(zin) > MAX_ALINEA:
            knip = zin.rfind(" ", 0, MAX_ALINEA) or MAX_ALINEA
            delen.append((huidig + " " + zin[:knip]).strip() if huidig else zin[:knip])
            huidig, zin = "", zin[knip:].strip()
        if huidig and len(huidig) + 1 + len(zin) > MAX_ALINEA:
            delen.append(huidig)
            huidig = zin
        else:
            huidig = f"{huidig} {zin}".strip()
    if huidig:
        delen.append(huidig)
    return delen


def _titel(e: ET.Element) -> str:
    """De tekst van een `title`, met haar `nr` ervoor en een spatie ertussen ("2 Uitgangspunten in cassatie"; zonder die
    spatie plakte het nummer aan de kop)."""
    nr = next((_tekst(c) for c in e if c.tag.replace(_R, "") == "nr"), "")
    delen = [e.text or ""]
    for c in e:
        if c.tag.replace(_R, "") != "nr":
            delen.append(_tekst(c))
        delen.append(c.tail or "")
    rest = " ".join(" ".join(delen).split())
    return f"{nr} {rest}".strip() if nr else rest


#: De metadata die `lees` uit de RDF neemt; meer waarden van één veld (twee rechtsgebieden) worden "a; b".
_META = {"identifier", "date", "issued", "modified", "creator", "type", "zaaknummer", "title", "procedure", "subject"}


def lees(xml: bytes) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """(metadata, rijen) uit een document van de Rechtspraak. Rijen in documentvolgorde: de inhoudsindicatie, dan de
    uitspraak of conclusie. De kop is het deel en de titel van de sectie ("Uitspraak › 2 Uitgangspunten in cassatie");
    een rij in een genummerde rechtsoverweging (`paragroup` met `nr`) draagt dat nummer als `plek` ("r.o. 2.1"; één veld, want elke byte telt in de begroting van een pagina), zodat een
    citaat naar r.o. 2.1 herleidbaar is. Lege alinea's tellen niet."""
    # Een regelafbreking in de bron (`<?linebreak?>`) is een processing instruction die de parser weggooit, en dan plakken
    # de zinnen aan elkaar ("bankrekeningen.In bezwaar", meting 10 nov 2026). Een spatie houdt de tekst leesbaar.
    root = ET.fromstring(re.sub(rb"<\?linebreak\s*\?>", b" ", xml))
    meta: dict[str, str] = {}
    beschrijving = next((d for d in root.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description")), None)
    if beschrijving is not None:
        for c in beschrijving:
            naam = c.tag.rsplit("}", 1)[-1]
            waarde = " ".join((c.text or "").split())
            if naam not in _META or not waarde:
                continue
            if naam in {"procedure", "subject"} and naam in meta:
                if waarde not in meta[naam].split("; "):
                    meta[naam] = f"{meta[naam]}; {waarde}"
            elif naam not in meta:
                meta[naam] = waarde
    rijen: list[dict[str, Any]] = []

    def voeg(tekst: str, kop: str, ro: str) -> None:
        delen = _knip(tekst)
        for i, deel in enumerate(delen, 1):
            rijen.append(compact({"nr": len(rijen) + 1, "kop": kop, "plek": f"r.o. {ro}" if ro else "",
                                  "tekst": deel,
                                  "deel": f"{i}/{len(delen)}" if len(delen) > 1 else ""}))

    def loop(e: ET.Element, top: str, kop: str, ro: str) -> str:
        for c in e:
            naam = c.tag.replace(_R, "")
            if naam == "title":
                titel = _titel(c)
                kop = f"{top} › {titel}" if titel else kop
            elif naam == "para":
                if t := _tekst(c):
                    voeg(t, kop, ro)
            elif naam == "paragroup":
                nr = next((_tekst(x) for x in c if x.tag.replace(_R, "") == "nr"), "")
                kop = loop(c, top, kop, nr or ro)
            elif naam != "nr":
                kop = loop(c, top, kop, ro)
        return kop

    for deel in root:
        naam = deel.tag.replace(_R, "")
        if naam == "inhoudsindicatie":
            loop(deel, "Inhoudsindicatie", "Inhoudsindicatie", "")
        elif naam in {"uitspraak", "conclusie"}:
            top = "Conclusie" if naam == "conclusie" else "Uitspraak"
            loop(deel, top, top, "")
    return meta, rijen


_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")


def label_van(ecli: str, meta: dict[str, str]) -> str:
    """"Hoge Raad 21 januari 2022, ECLI:NL:HR:2022:50": het gerecht en de datum uit de metadata, zoals een jurist een
    uitspraak noemt; zonder metadata alleen de ECLI."""
    datum = meta.get("date", "")
    voluit = ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        j, m, d = datum.split("-")
        voluit = f"{int(d)} {_MAANDEN[int(m) - 1]} {j}"
    voor = " ".join(x for x in (meta.get("creator", ""), voluit) if x)
    return f"{voor}, {ecli}" if voor else ecli


def _get(bron: RechtspraakBron, a: dict[str, Any]) -> str:
    vp = externe_vindplaats((a.get("id") or "").strip())
    if vp is not None and vp.brontype == "uitspraak" and not vp.id.startswith(RECHTSPRAAK.id_prefixen):
        # Een buitenlandse of Europese ECLI is een stuk dat bestaat maar niet bij de Rechtspraak staat: het resultaat
        # noemt het, met `leesbaar: false`, zodat het antwoord het mag noemen (meting ronde 2, R15: "ongegrond" omdat
        # alleen het voorbeeld in de fout stond).
        return fout("buiten_bereik", f"{vp.id} is geen Nederlandse uitspraak: de open data van de Rechtspraak heeft er "
                    "geen tekst van. Zeg dat, en citeer er niet uit.",
                    stuk={"id": vp.id, "label": vp.label, "link": vp.uri, "soort": "Uitspraak", "leesbaar": False,
                          "zonder_tekst": RECHTSPRAAK.zonder_tekst})
    if vp is None or vp.brontype != "uitspraak":
        return fout("ongeldig_id", "geef de ECLI van een Nederlandse uitspraak, bijvoorbeeld 'ECLI:NL:HR:2022:50'")
    doc = bron.document(vp.id)
    try:
        meta, rijen = lees(doc.xml)
    except ET.ParseError as exc:
        return fout("onleesbaar_document", f"{vp.id} kon niet worden gelezen: {exc}")
    stuk = compact({
        "id": vp.id, "label": label_van(vp.id, meta), "soort": meta.get("type") or soort_van(vp.id),
        "titel": meta.get("title", ""), "datum": meta.get("date", ""), "orgaan": meta.get("creator", ""),
        "nummer": meta.get("zaaknummer", ""), "gepubliceerd": meta.get("issued", ""), "link": vp.uri,
        "procedure": meta.get("procedure", ""), "rechtsgebied": meta.get("subject", ""),
        "bron_hash": doc.hash, "gewijzigd": getattr(doc, "gewijzigd", "") or meta.get("modified", "")})
    if getattr(doc, "gevalideerd", True) is False:
        # De Rechtspraak was niet te bereiken: de bewaarde versie, en dat zegt het stuk (het bronvenster toont het).
        stuk["gevalideerd"] = False
    # De koppen met hun offset, zoals bij Kamerstukken: een lange uitspraak (de Raad van State, honderden alinea's)
    # leest Lex vanaf het deel dat de vraag raakt, en het bronvenster toont er de inhoudsopgave mee (`tekstpagina`).
    if a.get("inhoud"):
        return inhoudpagina(rijen, tool="get_uitspraak", args={"id": vp.id}, offset=max(int(a.get("offset") or 0), 0),
                            stuk=stuk)
    return tekstpagina(rijen, tool="get_uitspraak", args={"id": vp.id}, offset=max(int(a.get("offset") or 0), 0),
                       stuk=stuk, toelichting="" if rijen else "Deze uitspraak heeft geen tekst in de open data.")


#: De reden in het foutresultaat per code van de adapter (`RechtspraakFout.code`).
FOUTREDEN = {"onbereikbaar": "bron_onbereikbaar", "geweigerd": "onleesbaar_document", "niet_gevonden": "niet_gevonden"}


def fout_van(exc: Any) -> str:
    code = getattr(exc, "code", "onbereikbaar")
    if code == "niet_gevonden":
        return fout("niet_gevonden", f"{exc}. Controleer de ECLI, of zoek uitspraken bij een artikel met "
                    "zoek_uitspraken, bijvoorbeeld {\"bwb_id\": \"BWBR0004770\", \"artikel\": \"36\"}.")
    return fout(FOUTREDEN.get(code, "bron_onbereikbaar"), str(exc))


def dispatch_rechtspraak(name: str, args: dict[str, Any], bron: RechtspraakBron | None, graph: Any) -> str:
    if bron is None:
        return fout("connector_uit", "De bron Rechtspraak staat uit. Zeg dat, en antwoord niet uit eigen kennis.")
    if name == "zoek_uitspraken":
        return _zoek(bron, graph, args)
    if name == "get_uitspraak":
        return _get(bron, args)
    raise KeyError(name)
