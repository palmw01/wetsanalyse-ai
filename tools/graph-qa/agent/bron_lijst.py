"""Lijstvragen over een bron naast de wet (ADR-013, ADR-010 laag 2): "geef de 10 meest recente Kamerstukken", "wat is
het laatste stuk van dossier 32140", "de laatste vijf moties van de Eerste Kamer".

Op acceptatie (gesprek e906567a, 9 nov 2026) bladerde het model voor "wat is het laatste stuk" door een dossier van 405
stukken: elf rondes, 264k cache-tokens en twee foute antwoorden, want op nummer staan de letters na de cijfers. Wat er
gevraagd wordt, is een zoekvraag met een volgorde, en die leest de code uit de vraag: de volgorde, het aantal, het
dossier, het soort, een periode, de Kamer en een onderwerp. Lukt dat niet volledig (een woord dat de code niet plaatst
in de vraag naar de inhoud van een stuk), dan geen route: de agent heeft dezelfde tool met dezelfde argumenten.

De argumentnamen komen uit de beschrijving (`ConnectorBeschrijving.filters`, `soorten`, `organen`); er staat hier geen
connector met naam.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bronmodel.connectors import CONNECTORS, ConnectorBeschrijving

from .aanwijzing import _ARTIKEL, lees_aanwijzing

_TELWOORDEN = {"een": 1, "één": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6, "zeven": 7, "acht": 8,
               "negen": 9, "tien": 10, "twaalf": 12, "vijftien": 15, "twintig": 20, "vijfentwintig": 25}
_GETAL = r"\d{1,4}|" + "|".join(sorted(_TELWOORDEN, key=len, reverse=True))
_NIEUWSTE = r"meest\s+recente?|recentste|nieuwste|laatste|jongste"
_OUDSTE = r"oudste|eerste"
_VOLGORDE_RE = re.compile(rf"\b(?:(?P<nieuw>{_NIEUWSTE})|(?P<oud>{_OUDSTE}))\b", re.IGNORECASE)
_AANTAL_RE = re.compile(rf"\b(?:(?P<voor>{_GETAL})\s+(?:{_NIEUWSTE}|{_OUDSTE})|(?:{_NIEUWSTE}|{_OUDSTE})\s+(?P<na>{_GETAL}))\b",
                        re.IGNORECASE)
#: Eén stuk: "het laatste stuk", "wat is de nieuwste motie", "de meest recente brief".
_EEN_RE = re.compile(rf"\b(?:het|de)\s+(?:{_NIEUWSTE}|{_OUDSTE})\s+(?!\d)(?!(?:{_GETAL})\b)\w+", re.IGNORECASE)
#: Een vraag naar wat er in een stuk staat, is geen lijstvraag.
_INHOUD_RE = re.compile(r"\b(?:staat\s+er|zegt|zeggen|samenvat\w*|inhoud|uitleg|leg\s+uit|waarom|bedoel\w*|"
                        r"lees|citeer|wat\s+vind|betekent|betekenis|definitie|houdt\b.*\bin)\b", re.IGNORECASE)
#: Een vraag naar wat iets is ("Wat is een inwerkingtredingsbesluit?"): met alleen een soort stuk en verder niets is dat
#: een begripsvraag, geen lijst (meting Staatsblad en Staatscourant, 11 nov 2026). "Wat is het laatste …" en "Wat zijn de
#: moties van de Eerste Kamer?" hebben een volgorde of filter en blijven een lijst.
#: "Geef alle …": een volle pagina, niet de standaard tien (meting Rechtspraak ronde 2, R23: 10 van de 11).
_ALLE_RE = re.compile(r"\balle\b", re.IGNORECASE)
_BEGRIP_RE = re.compile(r"^\s*wat\s+(?:is|zijn|was|waren)\b", re.IGNORECASE)
_DOSSIER_RE = re.compile(r"\b(?:dossier(?:nummer)?|kamerstukdossier|kamerdossier)\s+(?P<d>\d{4,6}(?:[- ](?:[IVXLC]{1,6}|[A-Z]))?)\b",
                         re.IGNORECASE)
_JAAR = r"(?:19|20)\d{2}"
#: Een periode: "uit 2023 en 2024", "2023-2024", "tussen 2020 en 2022", "van 2020 tot en met 2022". Vóór de losse jaren,
#: anders werd "uit 2023 en 2024" alleen 2023 (analyse meting bekendmakingen, 10 nov 2026).
_PERIODE_RE = re.compile(rf"\b(?:(?:tussen|in|uit|van)\s+)?(?P<a>{_JAAR})\s*(?:-|–|/|\ben\b|\bt/m\b|\btot\s+en\s+met\b)\s*"
                         rf"(?P<b>{_JAAR})\b", re.IGNORECASE)
#: Eén jaar met een voorzetsel. "van 2018" is "in 2018": "de verbeterbladen in het Staatsblad van 2018" verloor het jaar
#: (meting bekendmakingen B11, 10 nov 2026).
_JAAR_RE = re.compile(rf"\b(?:(?P<sinds>sinds|vanaf|na)\s+(?P<j1>{_JAAR})|(?P<in>in|uit|van)\s+(?P<j2>{_JAAR})"
                      rf"|(?P<tot>tot|voor)\s+(?P<j3>{_JAAR}))\b", re.IGNORECASE)
_MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
            "november", "december")
#: Een maand met jaar: "in maart 2025", "sinds juni 2024", "voor januari 2026". Vóór de periode en de losse jaren, anders
#: bleef "maart" over en ging de vraag naar het model (meting Rechtspraak R04, 11 nov 2026).
_MAAND_RE = re.compile(rf"\b(?:(?P<sinds>sinds|vanaf|na)|(?P<in>in|uit|van)|(?P<tot>tot|voor))?\s*"
                       rf"(?P<maand>{'|'.join(_MAANDEN)})\s+(?P<jaar>{_JAAR})\b", re.IGNORECASE)
#: Een telvraag: "hoeveel …", "het aantal …", "hoe vaak …". Het antwoord is het totaal van de bron, niet een schatting
#: (Kamerstukken ronde 4, K26; Rechtspraak ronde 3, R22).
_TEL_RE = re.compile(r"^\s*(?:hoeveel|hoe\s+vaak|(?:wat\s+is\s+)?(?:het\s+)?aantal)\b", re.IGNORECASE)
#: Een verdeling: "hoe verdelen de uitspraken zich over de instanties", "hoeveel uitspraken per instantie". Het woord na
#: "over de" of "per" wijst een telling van de bron aan (`per_<woord>` in het resultaat, `Telling.per`).
_VERDELING_RE = re.compile(r"\bhoe\s+(?:verdel\w*|verdeeld|is\s+de\s+verdeling\s+van)\b|\bverdeling\b", re.IGNORECASE)
_PER_RE = re.compile(r"\b(?:zich\s+)?(?:over\s+(?:de|het)|per)\s+(?P<w>[A-Za-zÀ-ÿ]+)\s*[?.!]?\s*$|\bper\s+(?P<p>[A-Za-zÀ-ÿ]+)\b",
                     re.IGNORECASE)
#: Woorden in de titel: "hebben de Douanewet in de titel", "met 'invorderingsrente' in hun titel".
_TITEL_RE = re.compile(r"\b(?:met|hebben|heeft|dragen|draagt|staat|staan)\s+(?:de\s+|het\s+|een\s+)?(?P<w>[^?.!,;]+?)\s+"
                       r"in\s+(?:de|hun|zijn|haar|het)\s+titel\b", re.IGNORECASE)
#: Stukken die bij een regeling horen, zonder artikel: "Welke Kamerstukken horen bij de Invorderingswet 1990?"
_HOREN_BIJ_RE = re.compile(r"\b(?:horen|hoort|behoren|behoort)\s+bij\b", re.IGNORECASE)
_VERGADERJAAR_RE = re.compile(r"\bvergaderjaar\s+(?P<a>\d{4})\s*[-/]\s*(?P<b>\d{2,4})\b", re.IGNORECASE)
_OVER_RE = re.compile(r"\bover\s+(?:de\s+|het\s+)?(?P<o>[^?.!,;]+)", re.IGNORECASE)
#: Woorden die in een lijstvraag staan zonder iets te zoeken.
_VULWOORDEN = frozenset("""geef mij me toon noem laat zien lijst wat welke wie is zijn de het een van uit bij in op
    met en of er nu ook alle stuk stukken publicaties staan zit zitten gaan gaat graag alsjeblieft aub kun kan je u
    noemen noemt genoemd over horen hoort hoeveel zoek zoeken vind vinden""".split()) | frozenset(
    w for c in CONNECTORS.values() for w in (*c.verzamelnamen, *c.vulwoorden))
#: Werkwoorden die achter het onderwerp staan zonder iets te zoeken: "memories van toelichting over de inkomstenbelasting
#: die in 2024 zijn verschenen" zocht op "inkomstenbelasting verschenen" en vond niets (meting Kamerstukken K09).
_WERKWOORDEN = frozenset("""werd werden wordt worden zijn is was waren verschenen verschijnt gepubliceerd publiceerde
    ingediend gedaan uitgebracht uitgekomen aangenomen verstuurd gestuurd geschreven gemaakt gewezen uitgesproken
    gegeven genomen vastgesteld deed deden doet gaf gaven die dat""".split())
MAX_ONDERWERP = 4
#: Zo veel stukken toont één pagina van de lijstroute: wat het blok `stukken` draagt (`sjablonen.extern.MAX_LIJST`) en wat
#: de zoektools per pagina geven.
MAX_AANTAL = 25


@dataclass(frozen=True)
class Lijstvraag:
    """De zoekvraag die de code uit een lijstvraag las: de connector en de argumenten van zijn zoektool."""
    connector: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    #: Het aantal dat de vraag noemde als dat boven wat een pagina draagt lag ("de 100 nieuwste"): het antwoord zegt dan
    #: dat het er minder toont, in plaats van stil te kappen (externe review, 10 nov 2026).
    gevraagd: int = 0
    #: Een telvraag: het antwoord begint met het aantal uit de bron (`Telling`).
    tellen: bool = False
    #: Bij een verdeling het woord waarover ("instanties"); de node zoekt de telling van de bron erbij (`per_instantie`).
    verdeling: str = ""
    #: Een zin over de grens van de zoekvraag die de code koos, achter de zoekvraag van het blok ("Kamerstukken koppelt
    #: een stuk niet aan een regeling; …").
    kanttekening: str = ""


def _getal(woord: str) -> int:
    return int(woord) if woord.isdigit() else _TELWOORDEN[woord.lower()]


def _arg(c: ConnectorBeschrijving, sleutel: str, index: int = 0) -> str:
    """Het argument van de zoektool dat op dit metadataveld filtert (`MetadataVeld.filters`), of ''."""
    veld = c.veld(sleutel)
    return veld.filters[index] if veld is not None and len(veld.filters) > index else ""


def lees(vraag: str, aan: frozenset[str],
         regelingen: Callable[[str], list[tuple[str, set[str]]]] | None = None) -> Lijstvraag | None:
    """De lijstvraag in de vraag, voor een connector die aanstaat en de vraag herkent; None als het geen lijstvraag is
    of de code haar niet helemaal kan lezen."""
    tekst = " ".join((vraag or "").split())
    if _INHOUD_RE.search(tekst):
        return None
    c = next((c for c in CONNECTORS.values() if c.naam in aan and c.volgordes and _herkent(c, tekst)), None)
    if c is None or c.geciteerd(tekst) or not (zoektool := sorted(c.tools - {c.leestool})):
        return None
    # Een orgaan is geen volgorde: "Eerste Kamer" las als "eerste", dus oudste eerst (acceptatie 9 nov 2026).
    zonder_organen = _zonder_organen(c, tekst)
    args: dict[str, Any] = {}
    gevraagd = 0
    rest = tekst
    tellen, verdeling = bool(_TEL_RE.match(tekst)), ""
    per = _PER_RE.search(tekst)
    if _VERDELING_RE.search(tekst) or (tellen and per is not None and per.group("p")):
        # "Hoe verdelen … zich over de instanties?", "hoeveel uitspraken per instantie": een telling per instantie. Zonder
        # woord waarover geen route.
        if per is None:
            return None
        tellen, verdeling = True, (per.group("w") or per.group("p")).lower()
        rest = _VERDELING_RE.sub(" ", rest.replace(per.group(0), " "))
    if tellen:
        rest = _TEL_RE.sub(" ", rest)
    if (t := _TITEL_RE.search(rest)) is not None:
        # Woorden in de titel zijn het titelfilter van de connector (`MetadataVeld("titel", filters=…)`).
        woorden = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ'-]+", t.group("w")) if w.lower() not in _VULWOORDEN]
        if not woorden or len(woorden) > MAX_ONDERWERP or not (arg := _arg(c, "titel")):
            return None
        args[arg] = " ".join(woorden)
        rest = rest.replace(t.group(0), " ")
    if (m := _VOLGORDE_RE.search(zonder_organen)) is not None:
        volgorde = "nieuwste" if m.group("nieuw") else "oudste"
        if volgorde not in c.volgordes:
            return None
        args["volgorde"] = volgorde
        if (a := _AANTAL_RE.search(zonder_organen)) is not None:
            gevraagd = _getal(a.group("voor") or a.group("na"))
            args["aantal"] = min(max(gevraagd, 1), MAX_AANTAL)
            rest = rest.replace(a.group(0), " ")
        elif (een := _EEN_RE.search(zonder_organen)) and not _meervoud(c, een.group(0).split()[-1]):
            args["aantal"] = 1
        args.setdefault("aantal", MAX_AANTAL if _ALLE_RE.search(tekst) else 10)
    elif _ALLE_RE.search(tekst) and "aantal" in _zoekargumenten(c):
        args["aantal"] = MAX_AANTAL
    # Zonder volgorde ("Kamerstukken uit vergaderjaar 2025-2026 over invorderingsrente") kiest de zoektool de volgorde en
    # de pagina: relevantie bij woorden of tekst, een dossier op nummer, anders de nieuwste. Dan moet er wel een filter
    # zijn.
    if (d := _DOSSIER_RE.search(tekst)) and (arg := _arg(c, "reeks")):
        args[arg] = re.sub(r"\s+", "-", d.group("d")).upper()
        rest = rest.replace(d.group(0), " ")
    for label, patroon in c.soorten:
        if (s := re.search(patroon, rest, re.IGNORECASE)) and (arg := _arg(c, "soort")):
            # De soort die het brontype zelf is ("uitspraken" bij Rechtspraak) is de algemene naam van een stuk, geen
            # filter: anders sloot "de nieuwste uitspraken van de Hoge Raad" de conclusies stil uit (meting 10 nov 2026).
            if label != c.brontype:
                args[arg] = label
            rest = rest.replace(s.group(0), " ")
            break
    if (wv := _wetsverwijzing(c, rest, regelingen)) is not None:
        if not wv:
            return None
        args.update(wv[0])
        rest = wv[1]
    kanttekening = ""
    if wv is None and (rg := _bij_regeling(c, rest, regelingen)) is not None:
        if not rg:
            return None
        args.update(rg[0])
        rest, kanttekening = rg[1], rg[2]
    for orgaan in c.organen:
        # Het eerste dat past: een gerecht bij naam ("Rechtbank Gelderland") staat vóór de soort gerecht erin.
        if re.search(rf"\b{re.escape(orgaan)}\b", rest, re.IGNORECASE) and (arg := _arg(c, "orgaan")):
            args[arg] = orgaan
            rest = re.sub(rf"\b{re.escape(orgaan)}\b", " ", rest, flags=re.IGNORECASE)
            break
    for veld in c.metadata:
        # Een veld met vaste waarden ("in het belastingrecht"): het filter krijgt de waarde.
        for waarde, patroon in veld.waarden:
            if veld.filters and (w := re.search(patroon, rest, re.IGNORECASE)):
                args[veld.filters[0]] = waarde
                rest = rest.replace(w.group(0), " ")
                break
    if (v := _VERGADERJAAR_RE.search(rest)) and (arg := _arg(c, "jaar")):
        args[arg] = f"{v.group('a')}-{v.group('b')}"
        rest = rest.replace(v.group(0), " ")
    if (mnd := _MAAND_RE.search(rest)) is not None:
        vanaf, tot = _arg(c, "datum", 0), _arg(c, "datum", 1)
        if not (vanaf and tot):
            return None
        j, nr = int(mnd.group("jaar")), _MAANDEN.index(mnd.group("maand").lower()) + 1
        if mnd.group("sinds"):
            args[vanaf] = f"{j}-{nr:02d}"
        elif mnd.group("tot"):
            # "voor maart 2025": tot en met februari.
            vj, vm = (j, nr - 1) if nr > 1 else (j - 1, 12)
            args[tot] = f"{vj}-{vm:02d}"
        else:
            args[vanaf] = args[tot] = f"{j}-{nr:02d}"
        rest = rest.replace(mnd.group(0), " ")
    if (p := _PERIODE_RE.search(rest)) and int(p.group("a")) <= int(p.group("b")):
        vanaf, tot = _arg(c, "datum", 0), _arg(c, "datum", 1)
        if not (vanaf and tot):
            return None
        args[vanaf], args[tot] = p.group("a"), p.group("b")
        rest = rest.replace(p.group(0), " ")
    for j in _JAAR_RE.finditer(rest):
        vanaf, tot = _arg(c, "datum", 0), _arg(c, "datum", 1)
        if j.group("sinds") and vanaf:
            args[vanaf] = j.group("j1")
        elif j.group("in") and vanaf and tot:
            args[vanaf] = args[tot] = j.group("j2")
        elif j.group("tot") and tot:
            args[tot] = str(int(j.group("j3")) - 1)
        rest = rest.replace(j.group(0), " ")
    if (o := _OVER_RE.search(rest)) is not None:
        woorden = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ'-]+", o.group("o"))
                   if w.lower() not in _VULWOORDEN and w.lower() not in _WERKWOORDEN]
        if woorden and (len(woorden) > MAX_ONDERWERP or "tekst" not in _zoekargumenten(c)):
            return None
        if woorden:
            args["tekst"] = f'"{" ".join(woorden)}"' if len(woorden) > 1 else woorden[0]
        # Zonder woorden ging het "over" iets dat de code al plaatste ("gaan over artikel 36 Iw").
        rest = rest.replace(o.group(0), " ")
    rest = _VOLGORDE_RE.sub(" ", rest)
    # Een woord dat de bron aanwijst ("jurisprudentie", "rechtspraak") zoekt niets.
    rest = " ".join(w for w in rest.split() if not _bronwoord(c, w))
    if not args:
        return None
    if _BEGRIP_RE.match(tekst) and set(args) <= {_arg(c, "soort")}:
        return None
    # Wat er overblijft, moet leeg zijn: een woord dat de code niet plaatst, is een vraag die het model beter leest.
    # Ook een getal: een jaartal of nummer dat de code niet plaatste, is een filter dat anders stil wegvalt ("uit 2023 en
    # 2024" werd alleen 2023, meting bekendmakingen 10 nov 2026). Aantal, dossier en vergaderjaar zijn al uit `rest`.
    over = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ]+", rest)
            if w.lower() not in _VULWOORDEN and w.lower() not in _WERKWOORDEN]
    if over:
        return None
    return Lijstvraag(c.naam, zoektool[0], args, gevraagd if gevraagd > MAX_AANTAL else 0, tellen, verdeling, kanttekening)


def _wetsverwijzing(c: ConnectorBeschrijving, tekst: str,
                    regelingen: Callable[[str], list[tuple[str, set[str]]]] | None):
    """Een genoemde bepaling als filter, voor een connector met het metadataveld `wetsverwijzing` (Rechtspraak: de
    uitspraken die een artikel noemen): (argumenten, de rest van de tekst). None als de tekst geen artikel noemt; een lege
    tuple als hij er een noemt dat de code niet eenduidig kan plaatsen (meer artikelen, geen of meer regelingen, of geen
    graaf): dan leest de agent de vraag."""
    veld = c.veld("wetsverwijzing")
    aw = lees_aanwijzing(tekst)
    if veld is None or len(veld.filters) < 2 or not aw.artikelen:
        return None
    if len(aw.artikelen) != 1 or aw.leden or regelingen is None:
        return ()
    genoemd = _zonder_ingesloten(regelingen(tekst), tekst)
    if len(genoemd) != 1:
        return ()
    bwb_id, namen = genoemd[0]
    rest = _ARTIKEL.sub(" ", tekst)
    for naam in sorted(namen, key=len, reverse=True):
        rest = re.sub(rf"(?<![\w.]){re.escape(naam)}(?![\w])", " ", rest, flags=re.IGNORECASE)
    return {veld.filters[0]: bwb_id, veld.filters[1]: aw.artikelen[0]}, rest


def _bij_regeling(c: ConnectorBeschrijving, tekst: str,
                  regelingen: Callable[[str], list[tuple[str, set[str]]]] | None):
    """Stukken die bij een regeling horen, zonder artikel ("Welke Kamerstukken horen bij de Invorderingswet 1990?"):
    (argumenten, de rest van de tekst, een kanttekening). Een connector die stukken aan een regeling koppelt (het veld
    `wetsverwijzing`) zoekt op het bwb-id; een andere zoekt op de naam in de titel (`MetadataVeld("titel")`), en dat zegt
    de kanttekening. None als de vraag dit niet vraagt of geen regeling noemt; een lege tuple als de code de regeling niet
    eenduidig plaatst (meer dan één, of zonder graaf).

    Ronde 4 Kamerstukken, K17: het model zocht zelf, noemde een dossier 20588 dat KOOP niet kent en zette een
    intrekking bij het verkeerde dossier. Deze vraag is een zoekvraag die de code helemaal leest."""
    if not (h := _HOREN_BIJ_RE.search(tekst)) or lees_aanwijzing(tekst).artikelen:
        return None
    if regelingen is None:
        return ()
    genoemd = _zonder_ingesloten(regelingen(tekst), tekst)
    if not genoemd:
        # Geen regeling bij naam: dan is het dit patroon niet ("Welke publicaties horen bij Kamerdossier 36602?" leest het
        # dossierfilter). Wat er overblijft, beslist de rest van `lees`; een naam die de graaf niet kent, blijft over en
        # gaat naar het model (meting Staatsblad ronde 5, B18: de lege tuple brak de hele lijstvraag af, 0 -> 184k).
        return None
    if len(genoemd) != 1 or not (plekken := _plekken(genoemd[0][1], tekst)):
        return ()
    bwb_id, _ = genoemd[0]
    a, b = max(plekken, key=lambda p: p[1] - p[0])
    naam = tekst[a:b]
    rest = (tekst[:a] + " " + tekst[b:]).replace(h.group(0), " ")
    if (veld := c.veld("wetsverwijzing")) is not None and veld.filters:
        return {veld.filters[0]: bwb_id}, rest, ""
    if not (arg := _arg(c, "titel")):
        return ()
    # De zoekvraag zegt al dat het de titel is ("Gezocht op „Invorderingswet 1990” in de titel"); de kanttekening zegt
    # alleen wat dat betekent (Kamerstukken ronde 5, K17: de zin stond er twee keer).
    return {arg: naam}, rest, (f"{c.label} koppelt een stuk niet aan een regeling, dus een stuk over de regeling met een "
                               "andere titel staat er niet bij.")


def _plekken(namen: set[str], tekst: str) -> list[tuple[int, int]]:
    return [m.span() for n in namen for m in re.finditer(rf"(?<![\w.]){re.escape(n)}(?![\w])", tekst, re.IGNORECASE)]


def _zonder_ingesloten(genoemd: list[tuple[str, set[str]]], tekst: str) -> list[tuple[str, set[str]]]:
    """De regelingen die de tekst zelf noemt: een naam die alleen binnen de naam van een andere staat, telt niet
    ("Uitvoeringsregeling Invorderingswet 1990" noemt de Invorderingswet 1990 niet; meting Rechtspraak R23, 11 nov 2026).
    Een regeling zonder namen (de graaf gaf er geen) blijft staan."""
    if len(genoemd) < 2:
        return genoemd
    plekken = {b: _plekken(n, tekst) for b, n in genoemd}

    def ingesloten(b: str, p: tuple[int, int]) -> bool:
        return any(q != p and q[0] <= p[0] and p[1] <= q[1] for a, qs in plekken.items() if a != b for q in qs)
    return [(b, n) for b, n in genoemd if not plekken[b] or any(not ingesloten(b, p) for p in plekken[b])]


def _bronwoord(c: ConnectorBeschrijving, woord: str) -> bool:
    """Een los woord dat de bron zelf aanwijst ("jurisprudentie", "rechtspraak", "kamerstukken"): een verzamelnaam."""
    w = re.sub(r"[^\w-]", "", woord)
    return bool(w) and any(re.search(p, w, re.IGNORECASE) for p in c.signalen)


def _meervoud(c: ConnectorBeschrijving, woord: str) -> bool:
    """Is het woord na "de laatste" een meervoud ("de laatste moties", "de nieuwste uitspraken")? Dan geen aantal 1. Een
    woord op -en of -s dat een soort van de connector is, maar niet de soort zelf; en "stukken"."""
    w = woord.lower()
    if w == "stukken" or w in c.verzamelnamen:  # meervoud of verzamelnaam
        return True
    return w.endswith(("en", "s")) and any(re.search(p, w, re.IGNORECASE) for _, p in c.soorten) and all(
        w != label.lower() for label, _ in c.soorten)


def _zonder_organen(c: ConnectorBeschrijving, tekst: str) -> str:
    for orgaan in c.organen:
        tekst = re.sub(rf"\b{re.escape(orgaan)}\b", " ", tekst, flags=re.IGNORECASE)
    return tekst


def _herkent(c: ConnectorBeschrijving, tekst: str) -> bool:
    """De connector, een soort stuk van de connector ("de laatste vijf moties") of een dossiernummer ("het laatste stuk
    van dossier 32140"): in een lijstvraag wijst elk daarvan de bron aan."""
    return (c.herkent(tekst) or any(re.search(p, tekst, re.IGNORECASE) for _, p in c.soorten)
            or (bool(_DOSSIER_RE.search(tekst)) and bool(_arg(c, "reeks"))))


def _zoekargumenten(c: ConnectorBeschrijving) -> set[str]:
    from .tools import TOOLS

    return {a for t in TOOLS if t["name"] in c.tools - {c.leestool} for a in t["input_schema"]["properties"]}
