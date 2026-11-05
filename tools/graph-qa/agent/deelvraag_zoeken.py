"""Bepalingen bij één deelvraag (F3f, zoeken en rangschikken nov 2026): de index op de termen van de deelvraag
(`kandidatenpool`) en de vaste rangschikking (`bepaling_opties`), zonder model. Dezelfde functie bedient de intake
en de methode `deelvraag` van de bronnenrun (`bronnen_vinden`)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .bepaling_namen import _benoem, bwb_van as _bwb, rijen as _rijen
from .graph import queries
from .ports import GraphPort
from .zoektermen import _raakt, kop_raakt, lemmas, onderwerp_van_deelvraag, splitsingen, zoektermen

logger = logging.getLogger(__name__)


#: Hoeveel zoektermen van een deelvraag de query krijgt, en hoeveel dossiertermen meewegen.
MAX_TERMEN = 6
MAX_DOSSIERTERMEN = 12
#: Per regeling en per lijst de treffers van de index; daarbinnen kiest de rangschikking.
MAX_TREFFERS = 50
#: Wat buiten de afbakening lijkt te vallen staat achteraan, hoogstens zoveel extra.
MAX_BUITEN = 2
MAX_PER_DEELVRAAG = 8
BUITEN_TEKST = "valt mogelijk buiten de afbakening"
#: De knooptypes die een bepaling kunnen zijn. Een divisie is de bepaling van een beleidsregel (de Leidraad).
SOORTEN = ("Lid", "Artikel", "Onderdeel", "Divisie")
#: De constante van Reciprocal Rank Fusion (Cormack e.a., 2009): de gangbare waarde, niet op een set afgestemd.
RRF_K = 60
#: Hoeveel bepalingen er per query hun plek in de opbouw krijgen.
PLAATS_PER_QUERY = 100
#: De dossiervelden waaruit de dossiertermen komen; met `dossier_velden` ook aanleiding en doel.
DOSSIERVELDEN = ("analysevraag", "praktijkvoorbeeld", "context")
DOSSIERVELDEN_ALLE = (*DOSSIERVELDEN, "aanleiding", "doel")
#: Hoeveel treffers de similarity-index per deelvraag geeft, vóór het filter op de regelingen.
MAX_GELIJKENIS = 40


@dataclass(frozen=True)
class Zoekprofiel:
    """Wat het zoeken en rangschikken doet (meetlogboek `bronselectie-2026-11-03`). Elke vlag is één ingreep,
    zodat de meting ze apart kan uitzetten; de standaard is wat op de ontwikkelset hielp.

    - `per_term`: per term een eigen lijst uit de index, naast de lijst op alle termen samen. Op één
      OR-query vulde een gewoon woord ("termijn") de 50 treffers, en viel een lid dat alleen dat woord
      draagt (Awb 6:8 lid 1) buiten de pool;
    - `samenstelling`: een samenstelling zoekt ook op haar delen ("bezwaar" en "*schrift*"), en de telling
      vouwt een ellips uit, zodat "bezwaar- of beroepschrift" het "bezwaarschrift" van de vraag raakt;
    - `lemma`: het lemma van een vervoegd woord zoekt mee ("ingediend" → "indienen"). Standaard **uit**: op de
      ontwikkelset hielp het niet (recall gelijk, recall nodig lager) en het laadt spaCy in de intake;
    - `divisies`: ook de divisies van een beleidsregel zijn bepalingen, en een onderdeel telt voor de bepaling
      waarin het volgens de graaf staat (`bwb:inBepaling`), niet volgens zijn IRI;
    - `kop_overal`: elke kandidaat krijgt de kop van zijn deel, niet alleen de voorlopige top;
    - `fusie`: rangschikken met RRF over de lijsten, in plaats van het aantal geraakte woorden;
    - `per_regeling`: de plaatsen op het kaartje gaan om de beurt naar de regelingen, de hoogste soort eerst
      (`overzicht.RANG`: wet vóór AMvB vóór ministeriële regeling vóór beleidsregel), en binnen een regeling
      in de volgorde van de fusie. Een beleidsregel met lange divisies raakt meer lijsten dan een lid van de
      wet en vulde zo het hele kaartje (meetlogboek `bronselectie-2026-11-03`);
    - `lengte`: de bijdrage van de indexlijsten wordt gedempt naar de lengte van de bepaling (de wortel van
      mediaan/lengte, hoogstens 1), zodat een lange divisie niet wint omdat ze veel woorden bevat. Standaard
      **uit**: op de invorderbaarheidsset kostte het recall (0,33 → 0,22).

    Het dossier zoekt mee (meetlogboek `bronselectie-2026-11-04-dossier`). Zonder deze vlaggen weegt het alleen als
    één lijst op het aantal geraakte dossiertermen, uit analysevraag, praktijkvoorbeeld en context. Alle vier zijn
    gemeten op drie ontwikkelsets en één blinde set, en alle vier staan **uit**, want geen ervan won:

    - `dossier_velden`: de dossiertermen komen ook uit de aanleiding en het doel. Dit veranderde niets, ook niet op
      de blinde set, de enige met aanleiding en doel;
    - `dossier_lijsten`: elke dossierterm is een eigen lijst uit de index, per regeling, in de pool en in de fusie
      (in plaats van de ene lijst op aantal). Het filter blijft: een optie raakt een deelvraagterm (spoor K).
      De pool groeide (blind 0,33 → 0,54), maar de dossierlijsten verdrongen de opties van de deelvraag
      (recall nodig 0,10 → 0,05) en de kaartjes gingen meer op elkaar lijken;
    - `dossier_omgeving`: het dossier wijst de omgeving aan (het artikel, of de eerste divisie van een
      beleidsregel), de deelvraag de bepaling daarin. De omgevingen staan in een lijst op de dossiertermen die
      ze raken, gewogen naar hun zeldzaamheid in de pool (idf), en een kandidaat krijgt de rang van zijn
      omgeving. Het effect wisselde per set: bestuurdersaansprakelijkheid 0,22 → 0,28, bezwaar 0,53 → 0,40,
      blind gelijk;
    - `gelijkenis`: de similarity-index (`bwb_similarity`) op de deelvraag met het praktijkvoorbeeld is een
      extra lijst, binnen de regelingen van het werkgebied. Een treffer daarvan telt als raak aan de deelvraag,
      ook zonder haar woorden. Een haperende index kost alleen die lijst. Van de 40 treffers vallen er bijna
      geen binnen de regelingen, en die gaan over iets anders. Als brug over de woordenkloof is de index te zwak.
    """
    per_term: bool = True
    samenstelling: bool = True
    lemma: bool = False
    divisies: bool = True
    kop_overal: bool = True
    fusie: bool = True
    per_regeling: bool = True
    lengte: bool = False
    dossier_velden: bool = False
    dossier_lijsten: bool = False
    dossier_omgeving: bool = False
    gelijkenis: bool = False


#: De rangschikking van 21 okt 2026 (F3f), voor de meting.
F3F = Zoekprofiel(per_term=False, samenstelling=False, lemma=False, divisies=False, kop_overal=False, fusie=False,
                  per_regeling=False)
STANDAARD_PROFIEL = Zoekprofiel()


def _term_lucene(term: str, lemma: str, profiel: Zoekprofiel) -> str:
    delen = [queries._lucene_term(term)]
    if profiel.lemma and lemma:
        delen.append(queries._lucene_term(lemma))
    if profiel.samenstelling:
        delen += [f"({x} AND *{y}*)" for x, y in splitsingen(term)]
    return "(" + " OR ".join(delen) + ")" if len(delen) > 1 else delen[0]


def _lucene(termen: list[str], lemma: dict[str, str] | None = None, profiel: Zoekprofiel = F3F) -> str:
    return "tekst:(" + " OR ".join(_term_lucene(w, (lemma or {}).get(w, ""), profiel) for w in termen) + ")"


def _doel_van(iri: str) -> str:
    """Een onderdeel van een wet telt voor zijn lid (of artikel): de analist kiest op lid-niveau. Uit de
    IRI, en dus alleen de terugval: bij een beleidsregel zegt de IRI niet waar een onderdeel staat
    (`…:artikel:9:o:d` hangt onder divisie 9.2) – daar geldt `bwb:inBepaling` (`plekken`)."""
    return iri.split(":o:", 1)[0] if ":id:" not in iri else iri


def _omschrijving(tekst: str, geraakt: list[str]) -> str:
    begin = " ".join((tekst or "").split())
    if len(begin) > 120:
        begin = begin[:120].rsplit(" ", 1)[0] + " …"
    raakt = f"raakt: {', '.join(geraakt)}" if geraakt else ""
    return " · ".join(d for d in (begin, raakt) if d)[:300]


def kandidatenpool(graph: GraphPort, *, regelingen: list[str], deelvraag: str | None,
                   dossier: dict[str, Any], profiel: Zoekprofiel = STANDAARD_PROFIEL) -> dict[str, Any] | None:
    """Wat de index bij een deelvraag vindt, vóór de rangschikking: per bepaling (lid, artikel zonder
    leden, of divisie) de geraakte teksten en per lijst haar rang, met de termen en het bereik waarmee
    gezocht is. None als er niets te zoeken valt of de graaf hapert. Apart, zodat de meting kan zien wat de
    rangschikking laat vallen.

    De lijsten, per regeling: alle termen samen (per knooptype, zoals sinds F3f) en – met `per_term` – elke
    term apart over alle knooptypes. Een treffer in een lijst van een term is het bewijs dat de bepaling die
    term raakt, met de stemmer van de index in plaats van een eigen telling."""
    vraagtekst = onderwerp_van_deelvraag(deelvraag) if deelvraag else ""
    termen = zoektermen(vraagtekst)[:MAX_TERMEN]
    if not termen:
        vraagtekst = deelvraag or dossier.get("analysevraag") or dossier.get("naam") or ""
        termen = zoektermen(vraagtekst)[:MAX_TERMEN]
    if not termen:
        return None
    velden = DOSSIERVELDEN_ALLE if profiel.dossier_velden else DOSSIERVELDEN
    alle_dossiertermen = zoektermen(" ".join(str(dossier.get(k) or "") for k in velden))[:MAX_DOSSIERTERMEN]
    dossiertermen = [w for w in zoektermen(" ".join(str(dossier.get(k) or "") for k in velden))
                     if w not in termen][:MAX_DOSSIERTERMEN]
    bereik = list(dict.fromkeys(r for r in regelingen if r)) or [None]
    lemma = lemmas(vraagtekst, termen) if profiel.lemma else {}
    soorten = SOORTEN if profiel.divisies else SOORTEN[:3]

    gevonden: dict[str, dict[str, Any]] = {}
    geraakte_artikelen: set[str] = set()

    def neem(iri: str, tekst: str, soort: str, bwb: str, citeertitel: str, lijst: str, rang: int,
             term: str = "", in_bepaling: str | None = None) -> None:
        if not queries.is_bron_iri(iri):
            return
        doel = in_bepaling or _doel_van(iri)
        k = gevonden.setdefault(doel, {"iri": doel, "bwb_id": bwb or _bwb(doel), "citeertitel": citeertitel,
                                       "teksten": [], "eigen": "", "rang": {}, "index_termen": [],
                                       "dossier_index": []})
        if doel == iri and soort != "Onderdeel":
            k["eigen"] = k["eigen"] or tekst
        if tekst and tekst not in k["teksten"]:
            k["teksten"].append(tekst)
        k["rang"][lijst] = min(rang, k["rang"].get(lijst, rang))
        if term and lijst.startswith("dossier:"):
            if term not in k["dossier_index"]:
                k["dossier_index"].append(term)
        elif term and term not in k["index_termen"]:
            k["index_termen"].append(term)
        if ":lid:" in doel:
            geraakte_artikelen.add(doel.split(":lid:", 1)[0])

    treffers: list[tuple] = []

    def lees(lijst: str, query: str, bwb: str | None, term: str = "", soort_van_query: str = "") -> None:
        rang = 0
        for r in _rijen(graph, query):
            if bwb and r.get("bwbId") != bwb:
                continue
            soort = r.get("soort") or soort_van_query
            if soort and soort not in soorten:
                continue
            rang += 1
            treffers.append((r["node"], r.get("tekst", ""), soort, r.get("bwbId", ""), r.get("citeertitel", ""),
                             lijst, rang, term))

    try:
        for bwb in bereik:
            for soort in soorten:
                lees(f"alle:{bwb}:{soort}", queries.fts(_lucene(termen, lemma, profiel), limit=MAX_TREFFERS,
                                                         bwb_id=bwb, soort=soort), bwb, soort_van_query=soort)
            if profiel.per_term:
                for term in termen:
                    lees(f"term:{bwb}:{term}", queries.fts("tekst:" + _term_lucene(term, lemma.get(term, ""), profiel),
                                                           limit=MAX_TREFFERS, bwb_id=bwb), bwb, term)
            if profiel.dossier_lijsten:
                for term in dossiertermen:
                    lees(f"dossier:{bwb}:{term}", queries.fts("tekst:" + _term_lucene(term, "", profiel),
                                                              limit=MAX_TREFFERS, bwb_id=bwb), bwb, term)
        for term in termen[:4]:
            rang = 0
            for r in _rijen(graph, queries.definities_van(term)):
                if bereik != [None] and r.get("bwbId") not in bereik:
                    continue
                rang += 1
                treffers.append((r["node"], r.get("tekst", ""), "Definitie", r.get("bwbId", ""),
                                 r.get("citeertitel", ""), f"definitie:{term}", rang, ""))
    except Exception:  # noqa: BLE001 – een haperende graaf geeft geen opties, geen crash van de intake
        logger.warning("bepalingen zoeken faalde", extra={"categorie": "technisch"}, exc_info=True)
        return None
    if profiel.gelijkenis and deelvraag:
        treffers += _gelijkenis(graph, f"{deelvraag} {dossier.get('praktijkvoorbeeld') or ''}".strip(), bereik,
                                soorten)

    # Een onderdeel telt voor de bepaling waarin het staat – uit de graaf (`bwb:inBepaling`), niet uit zijn IRI.
    bepaling: dict[str, str] = {}
    if profiel.divisies:
        from .plekken import plekken

        onderdelen = [t[0] for t in treffers if t[2] in ("Onderdeel", "Definitie")]
        bepaling = {iri: p["bepaling"] for iri, p in plekken(graph, onderdelen).items() if p.get("bepaling")}
    for iri, tekst, soort, bwb, citeertitel, lijst, rang, term in treffers:
        neem(iri, tekst, soort, bwb, citeertitel, lijst, rang, term, bepaling.get(iri))

    return {"termen": termen, "dossiertermen": dossiertermen, "alle_dossiertermen": alle_dossiertermen,
            "bereik": bereik, "gevonden": gevonden, "geraakte_artikelen": geraakte_artikelen, "lemma": lemma}


def _gelijkenis(graph: GraphPort, tekst: str, bereik: list[str | None], soorten: tuple[str, ...]) -> list[tuple]:
    """De treffers van de similarity-index als één lijst, in de vorm van de treffers van de index, binnen de
    regelingen van het werkgebied. Een haperende of niet ingestelde index kost alleen deze lijst."""
    from .tools import _semantische_treffers

    try:
        rijen = _semantische_treffers(graph.semantic_search(tekst[:2000], MAX_GELIJKENIS))
    except Exception:  # noqa: BLE001 – zonder gelijkenis zoekt de rest gewoon
        logger.warning("gelijkenis bij de deelvraag faalde", extra={"categorie": "technisch"}, exc_info=True)
        return []
    uit, rang = [], 0
    for r in rijen:
        bwb = _bwb(r["node"])
        if bereik != [None] and bwb not in bereik:
            continue
        if r.get("soort") and r["soort"] not in soorten:
            continue
        rang += 1
        uit.append((r["node"], r.get("tekst", ""), r.get("soort", ""), bwb, "", "gelijkenis", rang, ""))
    return uit


def omgeving_van(iri: str) -> str:
    """De omgeving van een bepaling: het artikel van een lid of onderdeel, of de eerste divisie van een
    beleidsregel (`…:id:BWBR…%2FCirculaire.divisie36`), waaronder alle subdivisies vallen."""
    if ":id:" in iri:
        kop, pad = iri.split(":id:", 1)
        return f"{kop}:id:" + "%2F".join(pad.split("%2F")[:2])
    return iri.split(":o:", 1)[0].split(":lid:", 1)[0]


def _omgeving_rang(kandidaten: list[dict[str, Any]], termen: list[str], samenstelling: bool) -> dict[str, int]:
    """Per kandidaat de rang van zijn omgeving: de omgevingen geordend op het gewicht van de dossiertermen die
    hun teksten en koppen samen raken (1 = het zwaarst). Een term weegt naar hoe zeldzaam hij is onder de
    omgevingen van de pool (idf, log(N/df)): "ontvanger" en "betalen" staan overal en zeggen niets over het
    werkgebied, "bestuurder" en "aansprakelijk" wel. Zo wint een grote divisie niet omdat ze veel gewone
    woorden bevat. Een omgeving zonder dossierterm krijgt geen rang."""
    import math

    tekst: dict[str, list[str]] = {}
    for k in kandidaten:
        tekst.setdefault(omgeving_van(k["iri"]), []).extend([k.get("kop", ""), *k["teksten"]])
    geraakt = {o: set(_raakt(termen, " ".join(t), samenstelling)) for o, t in tekst.items()}
    df = {w: sum(w in g for g in geraakt.values()) for w in termen}
    n = len(geraakt)
    gewicht = {o: round(sum(math.log(n / df[w]) for w in g), 9) for o, g in geraakt.items()}
    waarden = sorted({v for v in gewicht.values() if v > 0}, reverse=True)
    rang = {v: i + 1 for i, v in enumerate(waarden)}
    return {k["iri"]: rang[gewicht[omgeving_van(k["iri"])]] for k in kandidaten
            if gewicht[omgeving_van(k["iri"])] > 0}


def _koppen(graph: GraphPort, kandidaten: list[dict[str, Any]], gevonden: dict[str, dict[str, Any]]) -> None:
    """De koppen van de delen waarin de kandidaten staan, in porties; een haperende graaf kost alleen de kop."""
    iris = [k["iri"] for k in kandidaten]
    try:
        for i in range(0, len(iris), PLAATS_PER_QUERY):
            for r in _rijen(graph, queries.plaats_in_opbouw(iris[i:i + PLAATS_PER_QUERY])):
                k = gevonden.get(r["bepaling"])
                if k is not None and r.get("label") and r["label"] not in k["kop"]:
                    k["kop"] = f"{k['kop']} {r['label']}".strip()
    except Exception:  # noqa: BLE001 – zonder kop rangschikt de rest gewoon
        logger.warning("kop van de opbouw niet op te halen", extra={"categorie": "technisch"}, exc_info=True)


def _fusiescore(k: dict[str, Any], dos_rang: dict[int, int], demping: float = 1.0,
                omgeving: int | None = None) -> float:
    """RRF: per lijst 1/(k + rang). De index-lijsten met hun eigen rang (met `demping` voor de lengte; met
    `dossier_lijsten` ook die van de dossiertermen); de kop telt als een lijst waarin elke geraakte term op
    plaats 1 staat, het dossier als een lijst op het aantal geraakte dossiertermen (`dos_rang`, leeg met
    `dossier_lijsten`), de omgeving als een lijst op haar rang."""
    score = demping * sum(1 / (RRF_K + r) for r in k["rang"].values())
    score += len(k["kop_termen"]) / (RRF_K + 1)
    if k["dos"] and dos_rang:
        score += 1 / (RRF_K + dos_rang[len(k["dos"])])
    if omgeving:
        score += 1 / (RRF_K + omgeving)
    return score


def _demping(kandidaten: list[dict[str, Any]]) -> dict[str, float]:
    """Per kandidaat de demping van de indexlijsten: de wortel van mediaan/lengte, hoogstens 1. De lengte is het
    aantal woorden van de eigen tekst (anders alles wat geraakt is); een kandidaat zonder tekst wordt niet
    gedempt."""
    lengtes = {k["iri"]: len((k["eigen"] or " ".join(k["teksten"])).split()) for k in kandidaten}
    gemeten = sorted(n for n in lengtes.values() if n)
    if not gemeten:
        return {}
    mediaan = gemeten[len(gemeten) // 2]
    return {iri: min(1.0, (mediaan / n) ** 0.5) for iri, n in lengtes.items() if n}


def _soortrang(graph: GraphPort, bwb_ids: list[str]) -> dict[str, int]:
    """De rang van elke regeling naar haar soort (`overzicht.RANG`, onbekend = 9). Een haperende graaf kost de
    rang: dan gelden alle regelingen even zwaar en beslist de volgorde van het werkgebied."""
    from .overzicht import RANG

    ids = [b for b in dict.fromkeys(bwb_ids) if b]
    if len(ids) < 2:
        return {}
    try:
        rijen = _rijen(graph, queries.soort_van_regelingen(ids))
    except Exception:  # noqa: BLE001 – zonder soort alleen de volgorde van het werkgebied
        logger.warning("soort van de regelingen niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
        return {}
    soort = {(r.get("regeling") or "").removeprefix(queries.NS): (r.get("soort") or "").casefold() for r in rijen}
    return {b: RANG.get(soort.get(b, ""), 9) for b in ids}


def om_de_beurt(kandidaten: list[dict[str, Any]], rang: dict[str, int], bereik: list[str | None]) -> list[dict[str, Any]]:
    """De kandidaten om de beurt per regeling, de hoogste soort eerst (bij gelijke soort de volgorde van het
    werkgebied), en binnen een regeling in hun eigen volgorde. Een regeling die op is, slaat haar beurt over."""
    rijen: dict[str, list[dict[str, Any]]] = {}
    for k in kandidaten:
        rijen.setdefault(k["bwb_id"], []).append(k)
    if len(rijen) < 2:
        return kandidaten
    plek = {b: i for i, b in enumerate(bereik) if b}
    volgorde = sorted(rijen, key=lambda b: (rang.get(b, 9), plek.get(b, len(plek)), b))
    uit: list[dict[str, Any]] = []
    while any(rijen[b] for b in volgorde):
        for b in volgorde:
            if rijen[b]:
                uit.append(rijen[b].pop(0))
    return uit


def bepaling_opties(graph: GraphPort, *, regelingen: list[str], deelvraag: str | None, dossier: dict[str, Any],
                    buiten: list[str], limit: int = MAX_PER_DEELVRAAG,
                    profiel: Zoekprofiel = STANDAARD_PROFIEL) -> list[dict[str, Any]]:
    """De bepalingen (leden, artikelen zonder leden, of divisies) die bij één deelvraag horen, binnen de
    gekozen regelingen – zonder model, dus dezelfde vraag geeft dezelfde opties.

    Zoeken (`kandidatenpool`): de index op de termen van de deelvraag (zonder deelvraag: de analysevraag),
    per regeling op alle termen samen en per term apart; een onderdeel telt voor zijn lid of divisie, een
    artikel vervalt als een lid ervan geraakt is. Definities van een term in die regelingen komen erbij.

    Rangschikking, vast: Reciprocal Rank Fusion over de lijsten van de index, de kop van het omvattende deel en
    de geraakte dossiertermen (analysevraag, praktijkvoorbeeld, context); bij gelijke score de volgorde van de
    regelingen en de documentvolgorde. Geen gewichten: er is geen set groot genoeg om ze op af te stemmen. Bij
    een deelvraag moet een bepaling een deelvraagterm raken; alleen dossiertermen is geen optie, dus een kaartje
    is zo lang als er echt iets bij de deelvraag gevonden is.

    Een bepaling die meer raakt aan wat de analist buiten het werkgebied liet (`buiten`, de stammen uit
    `zoektermen.uitsluitstammen`, in tekst en kop) dan aan de deelvraag, valt niet stil weg: ze
    staat achteraan, gemarkeerd (`buiten: true`), hoogstens `MAX_BUITEN` extra. Meer, niet ook: "bezwaar-
    of beroepschrift" raakt "beroep", maar gaat even goed over bezwaar."""
    from .overzicht import padsleutel

    pool = kandidatenpool(graph, regelingen=regelingen, deelvraag=deelvraag, dossier=dossier, profiel=profiel)
    if pool is None:
        return []
    termen, dossiertermen, bereik = pool["termen"], pool["dossiertermen"], pool["bereik"]
    gevonden, geraakte_artikelen = pool["gevonden"], pool["geraakte_artikelen"]

    # Een artikel waarvan een lid geraakt is, is als artikel dubbelop: de analist kiest het lid.
    kandidaten = [k for iri, k in gevonden.items() if iri not in geraakte_artikelen]
    for k in kandidaten:
        alles = " ".join(k["teksten"])
        tekst_termen = _raakt(termen, alles, profiel.samenstelling)
        k["dv"] = [w for w in termen if w in tekst_termen or w in k["index_termen"]]
        k["dos"] = _raakt(dossiertermen, alles, profiel.samenstelling)
        k["dos"] += [w for w in k["dossier_index"] if w not in k["dos"]]
        k["kop"] = ""

    # De kop van het omvattende deel: voor elke kandidaat, of (F3f) alleen voor de voorlopige top.
    voor_kop = kandidaten if profiel.kop_overal else \
        sorted(kandidaten, key=lambda k: (-len(k["dv"]), -len(k["dos"])))[:limit * 3]
    if voor_kop:
        _koppen(graph, voor_kop, gevonden)
    for k in kandidaten:
        k["kop_termen"] = [w for w in termen if kop_raakt(w, k["kop"])] if profiel.kop_overal \
            else _raakt(termen, k["kop"])

    def regeling(k: dict[str, Any]) -> int:
        return bereik.index(k["bwb_id"]) if k["bwb_id"] in bereik else len(bereik)

    if profiel.fusie:
        aantallen = sorted({len(k["dos"]) for k in kandidaten if k["dos"]}, reverse=True)
        # Met eigen lijsten per dossierterm telt het dossier daar, niet nog eens als lijst op aantal.
        dos_rang = {} if profiel.dossier_lijsten else {n: i + 1 for i, n in enumerate(aantallen)}
        demping = _demping(kandidaten) if profiel.lengte else {}
        omgeving = _omgeving_rang(kandidaten, pool["alle_dossiertermen"], profiel.samenstelling) \
            if profiel.dossier_omgeving else {}

        def volgorde(k: dict[str, Any]) -> tuple:
            return (-_fusiescore(k, dos_rang, demping.get(k["iri"], 1.0), omgeving.get(k["iri"])), regeling(k),
                    padsleutel(k["iri"]))
    else:
        def volgorde(k: dict[str, Any]) -> tuple:
            return (-len(k["dv"]), -len(k["dos"]), -bool(k["kop_termen"]), regeling(k), padsleutel(k["iri"]))

    binnen_, buiten_ = [], []
    for k in sorted(kandidaten, key=volgorde):
        waar = f"{k['kop']} {' '.join(k['teksten'])}".casefold()
        weg = len([s for s in buiten if s in waar]) > len(k["dv"])
        (buiten_ if weg else binnen_).append({**k, "buiten": weg})
    # Bij een deelvraag moet een bepaling de deelvraag zelf raken; dossiertermen rangschikken alleen. Anders
    # vulde het dossier elk kaartje tot het maximum, en kreeg elke deelvraag dezelfde bepalingen (spoor K).
    # Een treffer van de similarity-index is op de deelvraag zelf gevonden, ook zonder haar woorden: dat is
    # precies de woordenkloof ("melden" tegen "mededeling") die de gelijkenis moet overbruggen.
    past = (lambda k: k["dv"] or "gelijkenis" in k["rang"]) if deelvraag else (lambda k: k["dv"] or k["dos"])
    passend = [k for k in binnen_ if past(k)]
    if profiel.per_regeling:
        passend = om_de_beurt(passend, _soortrang(graph, [k["bwb_id"] for k in passend]), bereik)
    gekozen = passend[:limit] + buiten_[:MAX_BUITEN]

    uit = [{"bron_iri": k["iri"], "bwb_id": k["bwb_id"], "label": "",
            "omschrijving": BUITEN_TEKST if k["buiten"] else _omschrijving(k["eigen"] or k["teksten"][0],
                                                                          k["dv"] + k["dos"]),
            "geraakt": k["dv"] + k["dos"], "buiten": k["buiten"]} for k in gekozen]
    _benoem(graph, uit)
    return uit
