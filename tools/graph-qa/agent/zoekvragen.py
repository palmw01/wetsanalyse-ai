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
    ("aansprakelijk", re.compile(r"\b(?:is|zijn)\b[^.;]{0,60}\b(?:hoofdelijk\s+)?aansprakelijk\b", re.I)),
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


def genoemd_in(gebeurtenis: str, tekst: str) -> bool:
    """Of het dossier de gebeurtenis zelf noemt: haar eerste inhoudswoord, als woord of begin van een woord
    ("Kwijtschelding voor particulieren"). Een gedeelde stam is niet genoeg: "betalen" noemt "betaling" niet."""
    woorden = zoektermen(gebeurtenis)
    return bool(woorden) and re.search(rf"\b{re.escape(woorden[0])}", tekst, re.I) is not None


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
                                                       "zin": " ".join(zin.split())[:300],
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
