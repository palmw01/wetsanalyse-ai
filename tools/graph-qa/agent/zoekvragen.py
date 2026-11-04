"""De bronselectie langs de vier zoekvragen (skill `references/zoekvragen-bronselectie.md`, P17), zonder model.

Het vertrekpunt is de **gebeurtenis** in de term van de wet ("kwijtschelding", "verrekening"). De analist beschrijft
haar vaak in eigen woorden ("de schuld laten vervallen", "een teruggave inhouden"), en daarom zoekt het zoeken op die
woorden de wet mis (meetlogboek `bronselectie-2026-11-04-dossier`). Twee stappen:

- `gebeurtenis_opties` – wat de gebeurtenis kan zijn. De wet ordent zich naar haar gebeurtenissen: een afdeling
  heet "Verrekening", een hoofddivisie van de Leidraad ook. De termen van het hele dossier (met de naam) zoeken in
  de index; elke treffer telt voor de koppen erboven, en een kop scoort op de dossiertermen die eronder vallen,
  gewogen naar hun zeldzaamheid onder de koppen (idf: "ontvanger" staat overal en zegt niets). Uit de kop komt de
  gebeurtenis ("Afdeling 3 – Uitstel van betaling, kwijtschelding en verjaring" geeft er drie). Wat het dossier
  letterlijk noemt, gaat voor. De analist kiest (`bronselectie`, kaartje `bs_gebeurtenis`); dit is een voorstel.
- `grondslag` – zoekvraag a, het bestaansrecht: de bepalingen die de gebeurtenis in het leven roepen of toestaan.
  Een bepaling is een kandidaat als één zin de gebeurtenis noemt én een signaal van bestaansrecht draagt ("is
  bevoegd", "kan … worden verleend", "verleent", "worden regels gesteld"). Een beleidsregel geeft geen
  bestaansrecht (zij vult in: zoekvraag d), en een zin die met "Geen" begint, beperkt (zoekvraag b).

De signalen zijn aanwijzingen, geen juridische kwalificatie: de analist beoordeelt elke kandidaat.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

from .bepaling_namen import bwb_van, rijen as _rijen
from .graph import queries
from .ports import GraphPort
from .zoektermen import _stamdeel, zoektermen

logger = logging.getLogger(__name__)

#: De dossiervelden die de gebeurtenis kunnen aanwijzen, de naam voorop: die draagt haar vaak letterlijk.
DOSSIERVELDEN = ("naam", "analysevraag", "aanleiding", "doel", "context", "praktijkvoorbeeld")
MAX_TERMEN = 16
MAX_TREFFERS = 50
MAX_OPTIES = 5
MAX_GRONDSLAG = 8
#: Per kop zoveel delen in één query naar de opbouw.
PER_QUERY = 100

#: Een kop zonder gebeurtenis: wat overblijft na het weghalen van "Algemene bepalingen over" en dergelijke.
_KOP_VOORVOEGSEL = re.compile(
    r"^(?:(?:algemene|bijzondere|overige|aanvullende|inleidende|slot-?|overgangs-?)\s*(?:en\s+\w+\s+)?"
    r"(?:algemene\s+)?bepalingen?|algemeen)(?:\s+(?:over|inzake|betreffende|omtrent|met betrekking tot))?\s*",
    re.I)
_KOP_GENERIEK = {"", "begripsbepalingen", "begripsbepaling", "definities", "toepassingsbereik", "reikwijdte",
                 "inwerkingtreding", "citeertitel", "slotbepaling", "overgangsrecht", "diversen", "wijziging"}
#: Een kop in delen: "Uitstel van betaling, kwijtschelding en verjaring". Niet op "of": "… 5 percent of meer".
_KOP_DELEN = re.compile(r",\s*|\s+en\s+")
#: Een gebeurtenis is een term of een korte woordgroep; een lange kop ("Door de ontvanger aan te houden
#: vrijwaringsrekening bij een bank …") beschrijft iets, maar noemt geen gebeurtenis.
MAX_WOORDEN = 4

#: Bestaansrecht (zoekvraag a): een bevoegdheid, een plicht of een recht dat de gebeurtenis mogelijk maakt.
BESTAANSRECHT = (
    ("bevoegd", re.compile(r"\bis\b[^.;]{0,80}\bbevoegd\b|\bbevoegdheid\b", re.I)),
    ("kan worden", re.compile(r"\bkan\b[^.;]{0,120}\bworden\s+(?:verleend|toegekend|opgelegd|vastgesteld|verrekend|"
                              r"ingevorderd|gegeven|toegestaan|aansprakelijk gesteld)\b", re.I)),
    ("verleent", re.compile(r"\b(?:verleent|verlenen|wordt[^.;]{0,80}verleend)\b", re.I)),
    ("regels gesteld", re.compile(r"\b(?:worden|wordt)\s+(?:bij\s+[^.;]{0,60})?regels\s+gesteld\b", re.I)),
    ("verplicht", re.compile(r"\bis\b[^.;]{0,60}\bverplicht\b", re.I)),
    ("aansprakelijk", re.compile(r"\b(?:is|zijn)\b[^.;]{0,60}\b(?:hoofdelijk\s+)?aansprakelijk\b"
                                 r"|\baansprakelijk\s+(?:is|zijn)\b", re.I)),
)
_ZIN = re.compile(r"(?<=[.;:])\s+")


def _dossiertekst(dossier: dict[str, Any]) -> str:
    return " ".join(str(dossier.get(k) or "") for k in DOSSIERVELDEN)


def _bepaling_van(iri: str, soort: str) -> str | None:
    """Het artikel of de divisie waarin een treffer staat: een lid of onderdeel van een wet telt voor zijn
    artikel (uit de IRI; bij een wet klopt die). Een onderdeel van een beleidsregel zegt in zijn IRI niet waar het
    staat: dat valt af, de divisie zelf draagt de tekst ook."""
    if soort in ("Artikel", "Divisie"):
        return iri
    if ":id:" in iri:
        return None
    return iri.split(":o:", 1)[0].split(":lid:", 1)[0]


def _kop_telt(deel: str, soort: str) -> bool:
    """Een kop die een gebeurtenis kan dragen: de opbouw van een wet, en bij een beleidsregel alleen de
    hoofddivisie (`…:artikel:24`, "Verrekening"); haar subdivisies heten naar een vraag ("Wanneer verrekening")."""
    return soort != "Divisie" or ":id:" not in deel


def kop_gebeurtenissen(label: str) -> list[str]:
    """De gebeurtenissen in een kop: na het nummer ("Afdeling 2 – "), zonder een algemene aanhef ("Algemene
    bepalingen over"), in delen ("Uitstel van betaling, kwijtschelding en verjaring" → drie)."""
    tekst = label.split(" – ", 1)[1] if " – " in label else label
    tekst = _KOP_VOORVOEGSEL.sub("", tekst.strip()).strip(" .")
    uit = []
    for deel in _KOP_DELEN.split(tekst):
        deel = deel.strip(" .")
        # Een afgebroken ellips ("Uitstel- en …") is geen gebeurtenis op zichzelf.
        if deel.casefold() in _KOP_GENERIEK or deel.endswith("-") or not zoektermen(deel) \
                or len(zoektermen(deel)) > MAX_WOORDEN:
            continue
        uit.append(deel[0].lower() + deel[1:] if deel[:2] != deel[:2].upper() else deel)
    return uit


def _sleutel(gebeurtenis: str) -> str:
    """Twee koppen noemen dezelfde gebeurtenis als hun eerste inhoudswoord dezelfde stam heeft
    ("Kwijtschelding" en "Kwijtschelding in andere gevallen")."""
    woorden = zoektermen(gebeurtenis)
    return _stamdeel(woorden[0]) if woorden else gebeurtenis.casefold()


def gebeurtenis_opties(graph: GraphPort, *, regelingen: list[str], dossier: dict[str, Any],
                       limit: int = MAX_OPTIES) -> list[dict[str, Any]]:
    """De gebeurtenissen waar het werkgebied over kan gaan, in volgorde: eerst wat het dossier letterlijk noemt,
    dan op het gewicht van de dossiertermen onder hun koppen. Elke optie draagt haar koppen als bewijs. Leeg als
    er geen regeling of geen dossiertekst is, of als de graaf hapert (dan typt de analist haar zelf)."""
    tekst = _dossiertekst(dossier)
    termen = zoektermen(tekst)[:MAX_TERMEN]
    bereik = [r for r in dict.fromkeys(regelingen) if r]
    if not termen or not bereik:
        return []
    try:
        treffers: dict[str, set[str]] = {}          # artikel of divisie → de dossiertermen die het raakt
        for bwb in bereik:
            for term in termen:
                for r in _rijen(graph, queries.fts("tekst:" + queries._lucene_term(term), limit=MAX_TREFFERS,
                                                   bwb_id=bwb)):
                    if r.get("bwbId") and r["bwbId"] != bwb:
                        continue
                    if (b := _bepaling_van(r["node"], r.get("soort", ""))) and queries.is_bron_iri(b):
                        treffers.setdefault(b, set()).add(term)
        koppen: dict[str, tuple[str, set[str]]] = {}  # deel → (label, de termen eronder)
        bepalingen = sorted(treffers)
        for i in range(0, len(bepalingen), PER_QUERY):
            for r in _rijen(graph, queries.plaats_in_opbouw(bepalingen[i:i + PER_QUERY])):
                if not r.get("label") or not _kop_telt(r["deel"], r.get("soort", "")):
                    continue
                label, onder = koppen.setdefault(r["deel"], (r["label"], set()))
                onder |= treffers.get(r["bepaling"], set())
    except Exception:  # noqa: BLE001 – zonder voorstel typt de analist de gebeurtenis zelf
        logger.warning("gebeurtenissen voorstellen faalde", extra={"categorie": "technisch"}, exc_info=True)
        return []
    if not koppen:
        return []
    df = {t: sum(t in onder for _, onder in koppen.values()) for t in termen}
    n = len(koppen)
    namen = _regelingnamen(graph, [bwb_van(d) for d in koppen])
    opties: dict[str, dict[str, Any]] = {}
    for deel, (label, onder) in koppen.items():
        gewicht = sum(math.log(n / df[t]) for t in onder if df[t])
        for g in kop_gebeurtenissen(label):
            o = opties.setdefault(_sleutel(g), {"gebeurtenis": g, "score": 0.0, "koppen": [], "termen": set()})
            if len(g) < len(o["gebeurtenis"]):
                o["gebeurtenis"] = g
            o["score"] += gewicht
            o["termen"] |= onder
            o["koppen"].append((gewicht, f"{label} ({namen.get(bwb_van(deel), bwb_van(deel))})"))
    for o in opties.values():
        o["genoemd"] = genoemd_in(o["gebeurtenis"], tekst)
    volgorde = sorted(opties.values(), key=lambda o: (not o["genoemd"], -o["score"], o["gebeurtenis"]))
    return [{"gebeurtenis": o["gebeurtenis"], "genoemd": o["genoemd"], "score": round(o["score"], 3),
             "koppen": [k for _, k in sorted(o["koppen"], key=lambda x: -x[0])][:3],
             "termen": sorted(o["termen"])} for o in volgorde if o["score"] > 0 or o["genoemd"]][:limit]


#: Een stam die zo specifiek is dat een vervoeging de gebeurtenis noemt ("uitbetaald" → uitbetaling). Een korte
#: stam ("betal") staat in te veel woorden: "betalen" noemt "betaling" niet.
MIN_STAM_GENOEMD = 7


def genoemd_in(gebeurtenis: str, tekst: str) -> bool:
    """Of het dossier de gebeurtenis zelf noemt: haar eerste inhoudswoord als woord of begin van een woord
    ("Kwijtschelding voor particulieren"), of een vervoeging met dezelfde specifieke stam ("waarop wordt
    uitbetaald" noemt de uitbetaling)."""
    woorden = zoektermen(gebeurtenis)
    if not woorden:
        return False
    if re.search(rf"\b{re.escape(woorden[0])}", tekst, re.I):
        return True
    # De eerste letters van een lange stam: de spelling wisselt tussen open en gesloten lettergreep ("uitbetal-ing",
    # "uitbetaa-ld"), dus de hele stam vergelijken mist de vervoeging.
    # Het begin groeit mee met de stam (op twee letters na): bij een samenstelling ("belastingrente") is een kort
    # begin ("belasti") ook het begin van een ander woord ("belastingschuldige").
    stam = queries._stam(woorden[0])
    begin = stam[:max(MIN_STAM_GENOEMD, len(stam) - 2)]
    return len(stam) >= MIN_STAM_GENOEMD and re.search(rf"\b{re.escape(begin)}", tekst, re.I) is not None


def _regelingnamen(graph: GraphPort, bwbs: list[str]) -> dict[str, str]:
    from .regelingnamen import regelingnamen
    try:
        return regelingnamen(graph, bwbs)
    except Exception:  # noqa: BLE001 – zonder naam staat het BWB-id er
        return {}


def _raakt_woord(stam: str, tekst: str) -> bool:
    """Een stam aan het begin van een woord: "vallen" raakt "vallen buiten", niet "in andere gevallen"."""
    return re.search(rf"\b{re.escape(stam)}", tekst, re.I) is not None


def bestaansrecht_signaal(zin: str) -> str:
    """Het signaal van bestaansrecht in één zin, of leeg. Een zin die met "Geen" begint, beperkt (zoekvraag b)."""
    if re.match(r"\s*geen\b", zin, re.I):
        return ""
    return next((naam for naam, patroon in BESTAANSRECHT if patroon.search(zin)), "")


def grondslag(graph: GraphPort, *, gebeurtenis: str, regelingen: list[str], buiten: list[str] | None = None,
              limit: int = MAX_GRONDSLAG) -> list[dict[str, Any]]:
    """Zoekvraag a: de bepalingen (lid of artikel) waarin één zin de gebeurtenis noemt en een signaal van
    bestaansrecht draagt, binnen de regelingen van het werkgebied, de wet vóór de lagere regeling. Een beleidsregel
    valt af, en een bepaling die méér raakt aan wat buiten de afbakening valt (`buiten`, stammen) dan aan de
    gebeurtenis ook. Leeg als de graaf hapert."""
    from .deelvraag_zoeken import _soortrang, om_de_beurt
    from .overzicht import RANG

    woorden = zoektermen(gebeurtenis)
    bereik = [r for r in dict.fromkeys(regelingen) if r]
    if not woorden or not bereik:
        return []
    stammen = [_stamdeel(w) for w in woorden]
    # De afbakening noemt de gebeurtenis vaak zelf ("kwijtschelding voor ondernemers valt erbuiten"): haar eigen
    # stam is dan geen reden om een bepaling weg te laten.
    buiten = [b for b in buiten or [] if not any(b.startswith(s) or s.startswith(b) for s in stammen)]
    lucene = "tekst:(" + " AND ".join(queries._lucene_term(w) for w in woorden) + ")"
    rang = _soortrang(graph, bereik) if len(bereik) > 1 else {}
    gevonden: dict[str, dict[str, Any]] = {}
    try:
        for bwb in bereik:
            if rang.get(bwb, 0) >= RANG["beleidsregel"]:
                continue
            for n, r in enumerate(_rijen(graph, queries.fts(lucene, limit=MAX_TREFFERS, bwb_id=bwb))):
                soort, iri, tekst = r.get("soort", ""), r["node"], r.get("tekst", "")
                if soort == "Divisie" or ":id:" in iri or not queries.is_bron_iri(iri):
                    continue
                doel = iri.split(":o:", 1)[0] if soort == "Onderdeel" else iri
                # Zoals `bepaling_opties`: weg als de tekst méér raakt aan wat buiten de afbakening valt dan aan de
                # gebeurtenis. Eén gedeelde stam ("belastin" uit "gemeentelijke belastingen") is geen reden.
                if sum(_raakt_woord(b, tekst) for b in buiten) > sum(_raakt_woord(st, tekst) for st in stammen):
                    continue
                for zin in _ZIN.split(tekst):
                    if all(_raakt_woord(st, zin) for st in stammen) and (signaal := bestaansrecht_signaal(zin)):
                        k = gevonden.setdefault(doel, {"bron_iri": doel, "bwb_id": bwb, "signaal": signaal,
                                                       "zin": " ".join(zin.split())[:300], "tekst": tekst[:2000],
                                                       "_volgorde": (rang.get(bwb, 0), n)})
                        k["_volgorde"] = min(k["_volgorde"], (rang.get(bwb, 0), n))
                        break
    except Exception:  # noqa: BLE001 – zonder grondslag zoeken de andere methoden gewoon
        logger.warning("grondslag zoeken faalde", extra={"categorie": "technisch"}, exc_info=True)
        return []
    # Een artikel waarvan een lid gevonden is, is dubbelop: de analist kiest het lid.
    leden_van = {i.split(":lid:", 1)[0] for i in gevonden if ":lid:" in i}
    kandidaten = [k for i, k in gevonden.items() if i not in leden_van]
    # De wet ordent zich naar haar gebeurtenissen: de grondslag staat vooraan in het deel waarvan de kop de
    # gebeurtenis draagt (Iw afdeling 3 "… kwijtschelding …", Uitv.reg. hoofdstuk II "Kwijtschelding …"). Die
    # bepalingen eerst, in documentvolgorde; de rest daarna, op hun rang in de index.
    onder_kop = _onder_kop(graph, [k["bron_iri"] for k in kandidaten], stammen)
    from .overzicht import padsleutel

    def volgorde(k: dict[str, Any]) -> tuple:
        if k["bron_iri"] in onder_kop:
            return (0, k["_volgorde"][0], padsleutel(k["bron_iri"]))
        return (1, *k["_volgorde"])
    for k in kandidaten:
        k["onder_kop"] = onder_kop.get(k["bron_iri"], "")
    uit = sorted(kandidaten, key=volgorde)
    # Om de beurt per regeling, de wet eerst: anders vullen de leden van één wet de lijst, en valt de grondslag
    # in de lagere regeling eraf (Uitv.reg. Iw art. 7 achter acht leden van Iw art. 26).
    uit = om_de_beurt(uit, rang, bereik)
    return [{k: v for k, v in x.items() if k != "_volgorde"} for x in uit[:limit]]


def _onder_kop(graph: GraphPort, iris: list[str], stammen: list[str]) -> dict[str, str]:
    """Per bepaling de kop van een deel erboven die de gebeurtenis noemt, of niets. Een haperende graaf kost
    alleen de voorkeur voor de kop."""
    artikel = {i: i.split(":o:", 1)[0].split(":lid:", 1)[0] for i in iris}
    uit: dict[str, str] = {}
    try:
        delen = sorted(set(artikel.values()))
        for i in range(0, len(delen), PER_QUERY):
            for r in _rijen(graph, queries.plaats_in_opbouw(delen[i:i + PER_QUERY])):
                label = r.get("label") or ""
                if any(_raakt_woord(s, g) for g in kop_gebeurtenissen(label) for s in stammen):
                    for iri, a in artikel.items():
                        if a == r["bepaling"]:
                            uit.setdefault(iri, label)
    except Exception:  # noqa: BLE001
        logger.warning("kop bij de grondslag niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
    return uit


# --- de pool: vanuit de grondslag naar b, c en d (PR 4) -------------------------------------------------

#: Zoekvraag c, rechtsgevolgen: wat door de gebeurtenis ontstaat, verandert of vervalt, en de rechtsbescherming.
RECHTSGEVOLG = (
    ("beschikking", re.compile(r"\bbij\s+(?:voor\s+(?:bezwaar|beroep|administratief\s+beroep)\s+vatbare\s+)?"
                               r"beschikking\b|\bde\s+beschikking\b", re.I)),
    ("beroep", re.compile(r"\bberoepschrift\b|\bberoep\s+instellen\b|\bop\s+het\s+beroep\b|\bhoger\s+beroep\b", re.I)),
    ("uitspraak", re.compile(r"\buitspraak\b", re.I)),
    ("vervalt", re.compile(r"\bvervalt\b|\bkomt\s+te\s+vervallen\b", re.I)),
    ("vastgesteld", re.compile(r"\bstelt\b[^.;]{0,80}\bvast\b|\bwordt\b[^.;]{0,60}\bvastgesteld\b", re.I)),
    ("uitbetaling", re.compile(r"\bbetaalt\b[^.;]{0,60}\buit\b", re.I)),
    ("bekendmaking", re.compile(r"\bkennisgeving\b|\bmaakt\b[^.;]{0,60}\bbekend\b", re.I)),
    ("niet-ontvankelijk", re.compile(r"\bniet-ontvankelijk", re.I)),
)
#: Zoekvraag d binnen de regeling: een bepaling die een term of de reikwijdte invult.
INVULLING = (
    ("verstaan", re.compile(r"\bwordt\b[^.;]{0,100}\bverstaan\b|\bverstaat\b", re.I)),
    ("begrepen", re.compile(r"\b(?:wordt|worden)\b[^.;]{0,60}\bbegrepen\b", re.I)),
    ("gelijkgesteld", re.compile(r"\bgelijkgesteld\b", re.I)),
)
#: Zoekvraag a in de omgeving: het bereik van een afdeling of hoofdstuk, een uitbreiding of beperking van het recht.
REIKWIJDTE = re.compile(r"\b(?:deze|dit)\s+(?:afdeling|hoofdstuk|paragraaf|titel|artikel)\s+(?:heeft|is)\s+"
                        r"(?:betrekking|van\s+toepassing)\s+op\b", re.I)
#: Zoekvraag b, rechtsgeldigheid: een beperking en de procedure. Voorwaarde en tijd komen uit de JAS-regels.
RECHTSGELDIGHEID = (
    ("geen … wordt", re.compile(r"^\s*geen\b[^.;]{0,100}\b(?:wordt|worden)\b", re.I)),
    ("procedure", re.compile(r"\b(?:verzoek|aanvraag|indienen|ingediend|indiening|formulier|gegevens\s+verstrekt|"
                             r"verstrekt\s+de\s+gegevens|ondertekend)\b", re.I)),
)
MAX_OMGEVING = 150
#: De subdivisies van de beleidsregel bij de gebeurtenis (Leidraad art. 26 heeft er tientallen): een ruim plafond,
#: want de deelvragen kiezen er later uit (PR 5).
MAX_BELEID = 200
MAX_DELEN = 25
VOLGORDE = {"a": 0, "b": 1, "c": 2, "d": 3}


def _jas_regels() -> list:
    """De regels voor voorwaarde en tijdsaanduiding uit de annotatiedetectoren (ADR-001): dezelfde kennis, nu als
    signaal van zoekvraag b. Alleen het patroon, niet de keten."""
    from .jas_pipeline.detectoren.regels import alle_regels

    return [r for r in alle_regels() if {"Voorwaarde", "Tijdsaanduiding"} & set(r.klassen)]


def zoekvraag_van(tekst: str) -> tuple[str, str, str]:
    """De zoekvraag van een bepaling buiten de grondslag uit haar tekst: (zoekvraag, signaal, zin), of leeg. De
    sterkste wint, zoals de skill zegt: een gevolg (c) vóór een invulling (d) vóór een voorwaarde of procedure (b);
    het bereik van een afdeling ("Deze afdeling heeft betrekking op …") is een begrenzing van het recht (a)."""
    zinnen = _ZIN.split(tekst or "")
    for zin in zinnen:
        if REIKWIJDTE.search(zin):
            return "a", "reikwijdte", zin
    for zoekvraag, patronen in (("c", RECHTSGEVOLG), ("d", INVULLING), ("b", RECHTSGELDIGHEID)):
        for zin in zinnen:
            for naam, patroon in patronen:
                if patroon.search(zin):
                    return zoekvraag, naam, zin
    for zin in zinnen:
        for regel in _jas_regels():
            if regel.vind(zin):
                return "b", regel.id, zin
    return "", "", ""


def q_subdivisies(hoofddivisies: list[str], limit: int) -> str:
    """De subdivisies met tekst onder deze hoofddivisies van een beleidsregel, op elke diepte."""
    from .graph.queries import PREFIXES

    waarden = " ".join(f"<{queries._iri_veilig(h)}>" for h in sorted(set(hoofddivisies)))
    return PREFIXES + f"""SELECT DISTINCT ?hoofd ?sub ?tekst WHERE {{
  VALUES ?hoofd {{ {waarden} }}
  ?hoofd bwb:heeftDivisie+ ?sub .
  ?sub bwb:tekst ?tekst .
}} ORDER BY ?hoofd ?sub LIMIT {limit + 1}"""


_HOOFDDIVISIE = re.compile(r"Circulaire\.divisie([0-9A-Za-z]+)")


def _hoofddivisie(iri: str) -> str:
    """De hoofddivisie (`…:artikel:26`) van een divisie van een beleidsregel, ook van een subdivisie
    (`…:id:…Circulaire.divisie26%2F…`)."""
    if ":artikel:" in iri:
        return iri.split(":artikel:", 1)[0] + ":artikel:" + iri.split(":artikel:", 1)[1].split(":", 1)[0]
    m = _HOOFDDIVISIE.search(iri)
    return f"urn:bwb:{bwb_van(iri)}:artikel:{m.group(1)}" if m else ""


#: Zonder gekozen regelingen: hoogstens zoveel regelingen waarvan een kop de gebeurtenis draagt.
MAX_REGELINGEN_GEBEURTENIS = 6


def regelingen_van_gebeurtenis(graph: GraphPort, gebeurtenis: str) -> list[str]:
    """De regelingen waarvan een kop de gebeurtenis draagt, in de volgorde van de index: het bereik van een werkgebied
    zonder gekozen regelingen. Zonder dat zocht Lex in de hele graaf (werkgebied Rekeningafspraken, 4 nov 2026: Awb
    8:75 en de "katvanger" bij een vraag over uitbetaling). Leeg als de graaf hapert."""
    woorden = zoektermen(gebeurtenis)
    if not woorden:
        return []
    stammen = [_stamdeel(w) for w in woorden]
    uit: list[str] = []
    try:
        for r in _rijen(graph, queries.zoek_opbouw(gebeurtenis, limit=50)):
            bwb = r.get("bwbId") or bwb_van(r["node"])
            if bwb and bwb not in uit and any(st in g.casefold() for g in kop_gebeurtenissen(r.get("label") or "")
                                              for st in stammen):
                uit.append(bwb)
    except Exception:  # noqa: BLE001
        logger.warning("regelingen van de gebeurtenis niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
    return uit[:MAX_REGELINGEN_GEBEURTENIS]


def pool(graph: GraphPort, *, gebeurtenis: str, regelingen: list[str], buiten: list[str] | None = None
         ) -> dict[str, Any]:
    """Zoekvragen a–d vanaf de gebeurtenis, zonder model: per kandidaat `{bron_iri, bwb_id, zoekvraag, signaal,
    zin, via}`. Bewust nog niet in de bronnenrun: de deelvragen rangschikken erbinnen (PR 5).

    - **a** de grondslag (`grondslag`), en in de omgeving het bereik van een afdeling;
    - de **omgeving**: de delen van een wet of lagere regeling waarvan de kop de gebeurtenis draagt
      (`queries.zoek_opbouw`), met hun artikelen (`bepalingen_in_delen`) en per lid de zoekvraag uit de tekst
      (`zoekvraag_van`: c vóór d vóór b); zonder signaal geen kandidaat;
    - **d** buiten de wet: de begripsbepalingen van termen in a–c (`bronnen_vinden.definities_in`), en de
      subdivisies van de hoofddivisies van een beleidsregel die de gebeurtenis in hun kop dragen of naar de
      grondslag verwijzen (`q_inkomend`).

    De afbakening werkt zoals bij `grondslag`. Een plafond of een haperende graaf maakt `volledig` false; wat er
    al was, blijft."""
    from .bronnen_vinden import definities_in, q_inkomend, q_teksten
    from .deelvraag_zoeken import _soortrang, om_de_beurt
    from .overzicht import RANG, padsleutel

    woorden = zoektermen(gebeurtenis)
    bereik = [r for r in dict.fromkeys(regelingen) if r] or regelingen_van_gebeurtenis(graph, gebeurtenis)
    leeg = {"grondslag": [], "kandidaten": [], "omgeving": [], "volledig": True, "regelingen": bereik}
    if not woorden or not bereik:
        return leeg
    stammen = [_stamdeel(w) for w in woorden]
    buiten = [b for b in buiten or [] if not any(b.startswith(st) or st.startswith(b) for st in stammen)]
    rang = _soortrang(graph, bereik)

    def beleid(bwb: str) -> bool:
        return rang.get(bwb, 0) >= RANG["beleidsregel"]

    def valt_buiten(tekst: str) -> bool:
        return sum(_raakt_woord(b, tekst) for b in buiten) > sum(_raakt_woord(st, tekst) for st in stammen)

    def kop_draagt(label: str) -> bool:
        return any(st in g.casefold() for g in kop_gebeurtenissen(label) for st in stammen)

    gs = grondslag(graph, gebeurtenis=gebeurtenis, regelingen=bereik, buiten=buiten)
    kandidaten: dict[str, dict[str, Any]] = {
        k["bron_iri"]: {"bron_iri": k["bron_iri"], "bwb_id": k["bwb_id"], "zoekvraag": "a", "signaal": k["signaal"],
                        "zin": k["zin"], "tekst": k.get("tekst", ""), "via": "grondslag"} for k in gs}
    volledig, delen, hoofddivisies, teksten = True, [], set(), []
    try:
        for bwb in bereik:
            for r in _rijen(graph, queries.zoek_opbouw(gebeurtenis, bwb_id=bwb, limit=MAX_DELEN)):
                if not kop_draagt(r.get("label") or ""):
                    continue
                if beleid(bwb):
                    if (hd := _hoofddivisie(r["node"])):
                        hoofddivisies.add(hd)
                else:
                    delen.append(r["node"])
        artikelen: list[str] = []
        if delen:
            for r in _rijen(graph, queries.bepalingen_in_delen(delen)):
                if r["bepaling"] not in artikelen:
                    artikelen.append(r["bepaling"])
        artikelen.sort(key=padsleutel)
        if len(artikelen) > MAX_OMGEVING:
            volledig, artikelen = False, artikelen[:MAX_OMGEVING]
        per_eenheid: dict[str, list[str]] = {}
        for i in range(0, len(artikelen), PER_QUERY):
            for r in _rijen(graph, q_teksten(artikelen[i:i + PER_QUERY])):
                eenheid = r["deel"].split(":o:", 1)[0]
                per_eenheid.setdefault(eenheid, []).append(r.get("tekst", ""))
        # Een uitsluitstam die in de helft of meer van de omgeving staat, onderscheidt niets: "belastin" (uit
        # "gemeentelijke belastingen valt erbuiten") stond in bijna elk lid en haalde Uitv.reg. 12 (vermogen) weg.
        alles = [" ".join(t) for t in per_eenheid.values()]
        buiten[:] = [b for b in buiten if 2 * sum(_raakt_woord(b, t) for t in alles) < max(1, len(alles))]
        # Een artikel met leden telt per lid; het artikel zelf alleen als het geen leden heeft.
        met_leden = {e.split(":lid:", 1)[0] for e in per_eenheid if ":lid:" in e}
        for eenheid, delen_tekst in per_eenheid.items():
            if eenheid in met_leden or eenheid in kandidaten:
                continue
            tekst = " ".join(delen_tekst)
            teksten.append({"deel": eenheid, "tekst": tekst})
            if valt_buiten(tekst):
                continue
            zoekvraag, signaal, zin = zoekvraag_van(tekst)
            if zoekvraag:
                kandidaten[eenheid] = {"bron_iri": eenheid, "bwb_id": bwb_van(eenheid), "zoekvraag": zoekvraag,
                                       "signaal": signaal, "zin": " ".join(zin.split())[:300], "tekst": tekst[:2000],
                                       "via": "omgeving"}
        # De beleidsregel die naar de grondslag verwijst (Leidraad art. 26 → Iw art. 26).
        gs_artikelen = sorted({k["bron_iri"].split(":lid:", 1)[0] for k in gs})
        if gs_artikelen:
            for r in _rijen(graph, q_inkomend(gs_artikelen, MAX_BELEID)):
                if beleid(bwb_van(r["bron"])) and (hd := _hoofddivisie(r["bron"])):
                    hoofddivisies.add(hd)
        if hoofddivisies:
            rijen = _rijen(graph, q_subdivisies(sorted(hoofddivisies), MAX_BELEID))
            if len(rijen) > MAX_BELEID:
                volledig, rijen = False, rijen[:MAX_BELEID]
            for r in rijen:
                if r["sub"] in kandidaten or valt_buiten(r.get("tekst", "")):
                    continue
                kandidaten[r["sub"]] = {"bron_iri": r["sub"], "bwb_id": bwb_van(r["sub"]), "zoekvraag": "d",
                                        "signaal": "beleidsregel", "zin": " ".join((r.get("tekst") or "").split())[:300],
                                        "tekst": (r.get("tekst") or "")[:2000], "via": "beleidsregel"}
        # Definities van termen in a–c.
        abc = [t for t in teksten if kandidaten.get(t["deel"], {}).get("zoekvraag") in ("a", "b", "c")] + \
              [{"deel": k["bron_iri"], "tekst": k["zin"]} for k in gs]
        defs, ok = definities_in(graph, abc, [b for b in bereik if not beleid(b)])
        volledig &= ok
        for d in defs:
            if d["node"] not in kandidaten:
                kandidaten[d["node"]] = {"bron_iri": d["node"], "bwb_id": bwb_van(d["node"]), "zoekvraag": "d",
                                         "signaal": f"definitie van “{d['begrip']}”", "zin": "", "tekst": d["begrip"],
                                         "via": "definitie"}
    except Exception:  # noqa: BLE001 – wat er al is blijft; de meting zegt dat het onvolledig is
        logger.warning("zoekvragen-pool onvolledig", extra={"categorie": "technisch"}, exc_info=True)
        volledig = False
    per = sorted(kandidaten.values(), key=lambda k: (VOLGORDE[k["zoekvraag"]], padsleutel(k["bron_iri"])))
    uit = [k for z in "abcd" for k in om_de_beurt([k for k in per if k["zoekvraag"] == z], rang, bereik)]
    return {"grondslag": gs, "kandidaten": uit, "omgeving": delen + sorted(hoofddivisies), "volledig": volledig,
            "regelingen": bereik}


# --- de deelvraag in de pool (PR 5) -------------------------------------------------------------------

#: De vraagvorm van een deelvraag wijst de zoekvraag aan (skill `references/zoekvragen-bronselectie.md`): "onder welke
#: voorwaarden" vraagt om rechtsgeldigheid (b), "wat kan iemand doen als" om rechtsgevolgen (c). Een aanwijzing voor
#: het soort bron, geen filter: bijna elke deelvraag vraagt ook om definities en beleid. Volgorde: de eerste die past.
VRAAGVORM = (
    ("d", re.compile(r"^\s*(?:wat\s+(?:is|zijn|betekent)\b|wat\s+wordt\s+(?:verstaan|bedoeld))", re.I)),
    ("a", re.compile(r"\b(?:wie\s+(?:mag|kan|is\s+bevoegd)|op\s+grond\s+waarvan|welke\s+(?:bevoegdheid|grondslag))\b", re.I)),
    ("c", re.compile(r"\b(?:welke\s+(?:gevolgen|rechten|plichten|verplichtingen)|wat\s+(?:kan|moet)\b[^?]{0,60}\bdoen|"
                     r"wat\s+gebeurt|hoe\s+[^?]{0,40}\bbezwaar|(?:hoe|wanneer)\s+[^?]{0,40}\baansprakelijk\s+stel)", re.I)),
    ("b", re.compile(r"\b(?:onder\s+welke\s+voorwaarden|aan\s+welke\s+(?:eisen|voorwaarden)|welke\s+(?:eisen|voorwaarden|"
                     r"uitzonderingen|beperkingen)|binnen\s+welke\s+termijn|in\s+welke\s+gevallen|wanneer\b|"
                     r"hoe\s+(?:vraag|dien|meld|wordt|moet))", re.I)),
)
#: Woorden die de vorm van de vraag dragen en niet haar onderwerp: ze staan in elke regeling, en zoeken erop haalde
#: "katvanger" en "bodemzaken" bij een vraag over rekeningafspraken (4 nov 2026). Ze wijzen de zoekvraag aan.
METHODEWOORDEN = {"voorwaarden", "voorwaarde", "eisen", "eis", "uitzonderingen", "uitzondering", "beperkingen",
                  "beperking", "rechten", "recht", "plichten", "plicht", "verplichtingen", "verplichting", "gevolgen",
                  "gevolg", "gevallen", "geval", "regels", "bepalingen", "mogelijkheden", "uitvoering", "wijzigen",
                  "beëindigen", "maken", "doen", "gebeurt", "geldt", "gelden", "welk", "iemand", "haar", "hun"}
#: Woorden zonder onderwerp die in een deelvraag staan ("omdat", "laten", "telt … mee"): ze raakten in de pool willekeurige
#: bepalingen. Alleen voor de rangschikking binnen de pool; het zoeken per deelvraag houdt `zoektermen` ongewijzigd.
LEGE_WOORDEN = {"omdat", "laten", "genoeg", "telt", "tellen", "mee", "gaat", "gaan", "vraagt", "vragen", "intussen",
                "door", "waarom", "tijdens", "alleen", "ook", "nog", "zelf", "andere", "bepaalde", "eerst", "daarna",
                "hierbij", "daarvan", "erbij", "worden", "wordt", "zijn", "hebben", "heeft", "kunnen", "moet"}
#: Vaste plaatsen voor het zoeken op de woorden van de deelvraag (`bepaling_opties`) naast de pool. Gemeten op de vier
#: ontwikkelsets (PR 5): 3 vaste plaatsen gaven 0,19/0,39/0,40/0,46 recall nodig, geen 0,29/0,44/0,40/0,46. Het zoeken
#: op woorden vult dus alleen aan als de pool minder opties geeft dan er plaatsen zijn.
PLAATSEN_WOORDEN = 0


def zoekvraag_van_deelvraag(vraag: str) -> str:
    """De zoekvraag die de vorm van de deelvraag aanwijst, of leeg."""
    return next((z for z, patroon in VRAAGVORM if patroon.search(vraag or "")), "")


def termen_van_deelvraag(vraag: str) -> list[str]:
    """De inhoudswoorden van een deelvraag: haar onderwerp zonder de woorden van de vraagvorm."""
    from .zoektermen import onderwerp_van_deelvraag

    return [w for w in zoektermen(onderwerp_van_deelvraag(vraag) or vraag or "")
            if w not in METHODEWOORDEN and w not in LEGE_WOORDEN]


def opties_bij_deelvraag(kandidaten: list[dict[str, Any]], vraag: str, *, limit: int = 8,
                         gebeurtenis: str = "") -> list[dict[str, Any]]:
    """De kandidaten uit de pool die bij een deelvraag horen, zonder graafverkeer.

    Een inhoudswoord weegt naar hoe zeldzaam het is in de pool (idf, log((N+1)/(df+1))): "verzoek" en
    "belastingschuld" staan in bijna elke kandidaat en zeggen niets, "spaargeld" en "afgewezen" wel. Past de zoekvraag
    van een kandidaat bij de vraagvorm, dan telt dat als het sterkste woord van de deelvraag: zo komt het beroep (c)
    bij "wat kan iemand doen als het verzoek wordt afgewezen?", ook zonder de woorden van de vraag. Een kandidaat
    zonder woord en zonder passende zoekvraag doet niet mee. Bij gelijke stand de volgorde van de pool (a, b, c, d en
    daarbinnen de documentvolgorde), en daarvóór: noemt de kandidaat de gebeurtenis zelf ("het bedrag van de
    kwijtschelding"), dan gaat hij voor op een die dat niet doet (in een kop die meer gebeurtenissen bundelt, zoals
    "Uitstel van betaling, kwijtschelding en verjaring"). Elke optie draagt `geraakt` en `past`."""
    import math

    from .zoektermen import _raakt

    termen = termen_van_deelvraag(vraag)
    zoekvraag = zoekvraag_van_deelvraag(vraag)
    stammen = [_stamdeel(w) for w in zoektermen(gebeurtenis)]
    geraakt = [_raakt(termen, f"{k.get('tekst') or ''} {k.get('zin') or ''}", True) for k in kandidaten]
    n = len(kandidaten)
    df = {t: sum(t in g for g in geraakt) for t in termen}
    gewicht = {t: math.log((n + 1) / (df[t] + 1)) for t in termen if df[t]}
    bonus = max(gewicht.values(), default=1.0) or 1.0
    gescoord = []
    for i, (k, g) in enumerate(zip(kandidaten, geraakt)):
        past = bool(zoekvraag) and k["zoekvraag"] == zoekvraag
        score = sum(gewicht.get(t, 0.0) for t in g) + (bonus if past else 0.0)
        if g or past:
            noemt = bool(stammen) and all(_raakt_woord(st, f"{k.get('tekst') or ''} {k.get('zin') or ''}")
                                          for st in stammen)
            gescoord.append((round(score, 9), not noemt, i, {**k, "geraakt": g, "past": past}))
    return [k for *_, k in sorted(gescoord, key=lambda x: (-x[0], x[1], x[2]))][:limit]
