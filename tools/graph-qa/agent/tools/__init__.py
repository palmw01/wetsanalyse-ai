"""
Getypeerde domein-toollaag over de kennisgraaf.

Het model kiest voortaan uit deze bewerkingen i.p.v. vrije SPARQL te schrijven:
onze code bouwt de query deterministisch (agent/graph/queries.py) en voert die uit
via de GraphPort. Elke tool draagt in zijn beschrijving het "hoe"; de correctheid
zit in geteste code, niet in prompt-proza. raw_sparql blijft als gated escape.

De registry levert twee dingen aan de loop:
  - anthropic_schemas(): de model-facing tool-schema's
  - dispatch(name, graph, args): voert de tool uit en geeft resultaattekst terug
"""
from __future__ import annotations

import logging
import json
import re
from collections.abc import Callable
from typing import Any

import httpx

from ..graph import queries, schema
from ..graph.results import parse_select
from ..graph.structuur import inhoudsopgave_resultaat
from ..mcp_client import MCPError
from ..ports import GraphPort
from .jas_tools import JAS_TOOL_NAMEN, JAS_TOOLS  # noqa: F401 – re-exporteerd voor orchestrator
from .annotatie_tools import ANNOTATIE_TOOLS, ANNOTATIE_TOOL_NAMEN, dispatch_annotatie
from ..resultaat import BUDGET, TeGroot, compact, fout, geheel, pagina, per_eenheid, voorproef
from ..graph.structuur import natuurlijke_sleutel

logger = logging.getLogger("graph_qa.tools")

Handler = Callable[[GraphPort, dict[str, Any]], str]


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_STR = {"type": "string"}


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

def _aanduiding(a: dict[str, Any]) -> str:
    """Het artikelnummer óf het decimale bepaling-nummer – wat de aanroeper ook meegaf.

    De verwijzings- en contexttools accepteren allebei, want een divisie van een beleidsregel heeft
    geen artikelnummer. Zonder deze samenvoeging zou elk van die tools twee vrijwel identieke
    parameters dragen en zou het model moeten raden welke bij welke regeling hoort.
    """
    waarde = a.get("artikel") or a.get("nummer") or ""
    if not str(waarde).strip():
        raise ValueError("Geef 'artikel' (bv. '9') of 'nummer' (bv. '9.1') mee.")
    return str(waarde).strip()


def _geheel(waarde: Any, standaard: int, laag: int, hoog: int) -> int:
    """Een geheel getal uit de toolargumenten, begrensd; onzin wordt de standaard."""
    try:
        return max(laag, min(hoog, int(waarde)))
    except (TypeError, ValueError):
        return standaard


# Een zoek- of definitietreffer draagt het begin van zijn tekst: genoeg om te kiezen en vaak om te
# citeren, en de rij zegt zelf of het de hele tekst is (`tekst_volledig`). Zo blijft een pagina van
# tien treffers binnen de begroting zonder dat één lange bepaling de rest verdringt.
_VOORPROEF = 600
_VOORPROEF_DEFINITIE = 1500


def _met_voorproef(rij: dict[str, str], maximum: int) -> dict[str, Any]:
    tekst = rij.get("tekst", "")
    if not tekst:
        return compact(rij)
    begin, heel = voorproef(tekst, maximum)
    return compact({**rij, "tekst": begin, "tekst_volledig": None if heel else False})


def _h_search(g: GraphPort, a: dict[str, Any]) -> str:
    limit, offset = _geheel(a.get("limit"), 10, 1, 50), _geheel(a.get("offset"), 0, 0, 10_000)
    rijen = parse_select(g.sparql(queries.fts(
        a["query"], limit, veld=a.get("veld") or None, bwb_id=a.get("bwb_id") or None,
        soort=a.get("soort") or None, offset=offset, meer=True)))
    for r in rijen:
        try:
            r["score"] = f"{float(r['score']):.3g}" if r.get("score") else ""
        except ValueError:
            pass  # geen getal: laat de waarde zoals de index hem gaf
    return pagina([_met_voorproef(r, _VOORPROEF) for r in rijen], tool="search_wetgeving",
                  args={**a, "limit": limit}, limit=limit, offset=offset)


def _zonder_datum(jci: str) -> str:
    """Een jci zonder `&z=…&g=…`: die staart is per onderdeel herhaling van de toestand van het lid."""
    return jci.split("&z=", 1)[0] if jci else jci


def _onderdeelsleutel(iri: str) -> tuple:
    """Documentvolgorde van (geneste) onderdelen uit hun IRI: a … z vóór aa, 2° vóór 10°, en een
    genest onderdeel direct na zijn ouder. `ORDER BY ?o` is lexicaal (a, aa, ab, b)."""
    delen = iri.split(":")
    return tuple((len(delen[i + 1]), delen[i + 1]) for i in range(len(delen) - 1) if delen[i] == "o")


def _offset(a: dict[str, Any]) -> int:
    return _geheel(a.get("offset"), 0, 0, 100_000)


def _h_get_artikel(g: GraphPort, a: dict[str, Any]) -> str:
    rijen = parse_select(g.sparql(queries.get_artikel(a["bwb_id"], a["artikel"])))
    kop = rijen[0] if rijen else {}
    artikel = compact({"iri": queries.artikel_iri(a["bwb_id"], a["artikel"]), "tekst": kop.get("tekst", ""),
                       "jci": kop.get("jci", "")})
    # De leden (of de onderdelen direct onder een artikel zonder leden) als hele eenheden, in de
    # volgorde van de query (numeriek op lidnummer). Een lid wordt nooit doorgeknipt.
    eenheden, gezien = [], set()
    for r in rijen:
        for iri, rij in ((r.get("lid"), {"lid": r.get("lid"), "nummer": r.get("lidnummer"), "tekst": r.get("lidtekst")}),
                         (r.get("o"), {"onderdeel": r.get("o"), "nummer": r.get("onderdeel"), "tekst": r.get("onderdeeltekst")})):
            if iri and iri not in gezien:
                gezien.add(iri)
                eenheden.append(compact(rij))
    return per_eenheid(eenheden, tool="get_artikel", args={k: v for k, v in a.items() if k != "offset"},
                       offset=_offset(a), extra={"artikel": artikel},
                       toelichting="Onderdelen onder een LID staan hier niet in: haal die op met get_lid.")


def _h_get_lid(g: GraphPort, a: dict[str, Any]) -> str:
    rijen = parse_select(g.sparql(queries.get_lid(a["bwb_id"], a["artikel"], a["lid"])))
    kop = rijen[0] if rijen else {}
    lid = compact({"iri": queries.lid_iri(a["bwb_id"], a["artikel"], a["lid"]), "nummer": kop.get("nummer", ""),
                   "tekst": kop.get("tekst", ""), "jci": kop.get("jci", "")})
    onderdelen = {r["o"]: compact({"onderdeel": r["o"], "nummer": r.get("onummer"), "tekst": r.get("otekst"),
                                   "jci": _zonder_datum(r.get("ojci", ""))}) for r in rijen if r.get("o")}
    eenheden = [onderdelen[iri] for iri in sorted(onderdelen, key=_onderdeelsleutel)]
    return per_eenheid(eenheden, tool="get_lid", args={k: v for k, v in a.items() if k != "offset"},
                       offset=_offset(a), extra={"lid": lid},
                       toelichting="Citeer de jci van het ONDERDEEL, niet die van het hele lid.")


def _h_get_bepaling(g: GraphPort, a: dict[str, Any]) -> str:
    rijen = parse_select(g.sparql(queries.get_bepaling(a["bwb_id"], a["nummer"])))
    if not rijen:
        raise ValueError(f"Bepaling {a['nummer']!r} niet gevonden in {a['bwb_id']}.")
    kop = rijen[0]
    bepaling = compact({k: kop.get(k, "") for k in ("nummer", "soort", "label", "tekst", "jci")})
    subs = {r["sub"]: compact({"sub": r["sub"], "nummer": r.get("subnummer"), "label": r.get("sublabel"),
                               "begin": r.get("subbegin")}) for r in rijen if r.get("sub")}
    eenheden = sorted(subs.values(), key=lambda r: (natuurlijke_sleutel(r.get("nummer", "")), r["sub"]))
    return per_eenheid(eenheden, tool="get_bepaling", args={k: v for k, v in a.items() if k != "offset"},
                       offset=_offset(a), extra={"bepaling": bepaling},
                       toelichting="Subdivisies met het begin van hun tekst; de volledige tekst via "
                                   "get_bepaling(nummer=<subnummer>).")


def _lijst(g: GraphPort, a: dict[str, Any], tool: str, bouw: Callable[..., str], standaard: int, hoogste: int,
           toelichting: str = "") -> str:
    """Een gerangschikte lijst via SPARQL: limit + 1 rijen vanaf offset, en het contract erom."""
    limit = _geheel(a.get("limit"), standaard, 1, hoogste)
    offset = _offset(a)
    rijen = parse_select(g.sparql(bouw(limit=limit, offset=offset, meer=True)))
    return pagina(rijen, tool=tool, args={**a, "limit": limit}, limit=limit, offset=offset, toelichting=toelichting)


def _h_list_regelingen(g: GraphPort, a: dict[str, Any]) -> str:
    return _lijst(g, a, "list_regelingen", queries.list_regelingen, 100, 200)


def _h_regeling_info(g: GraphPort, a: dict[str, Any]) -> str:
    # Een aggregatie over één regeling: precies één rij.
    return geheel(parse_select(g.sparql(queries.get_regeling_info(a["bwb_id"])))[:1], tool="get_regeling_info",
                  extra={"regeling": queries.regeling_iri(a["bwb_id"])})


def _h_verwijzingen(g: GraphPort, a: dict[str, Any]) -> str:
    return _lijst(g, a, "follow_verwijzingen",
                  lambda **p: queries.follow_verwijzingen(a["bwb_id"], _aanduiding(a), a.get("lid"), **p), 50, 200)


def _h_verwijst_naar_deze(g: GraphPort, a: dict[str, Any]) -> str:
    limit, offset = _geheel(a.get("limit"), 50, 1, 200), _geheel(a.get("offset"), 0, 0, 100_000)
    rijen = parse_select(g.sparql(queries.verwijst_naar_deze(
        a["bwb_id"], _aanduiding(a), a.get("lid"), limit, offset=offset, meer=True)))
    return pagina(rijen, tool="verwijst_naar_deze", args={**a, "limit": limit}, limit=limit, offset=offset)


# De querydiepte van de inhoudsopgave. Hoe diep het RESULTAAT gaat, kiest `structuur` binnen de
# begroting; wat dieper ligt staat ingeklapt met een ingang (`vanaf` = de IRI van dat deel).
_INHOUD_DIEPTE = 4


def _h_inhoudsopgave(g: GraphPort, a: dict[str, Any]) -> str:
    bwb_id, vanaf = a["bwb_id"], a.get("vanaf") or None
    rijen = parse_select(g.sparql(queries.inhoudsopgave(bwb_id, vanaf, _INHOUD_DIEPTE)))
    if not rijen:
        raise ValueError(f"Geen structuur gevonden voor {bwb_id}" + (f" vanaf {vanaf!r}" if vanaf else "")
                         + ". Controleer het BWB-id (list_regelingen) of het deel.")
    args = {k: v for k, v in a.items() if k != "offset"}
    return inhoudsopgave_resultaat(rijen, bwb_id=bwb_id, wortel=rijen[0]["ouder"], args=args,
                                   query_diepte=_INHOUD_DIEPTE, offset=_geheel(a.get("offset"), 0, 0, 100_000))


def _h_zoek_definitie(g: GraphPort, a: dict[str, Any]) -> str:
    limit, offset = _geheel(a.get("limit"), 25, 1, 100), _geheel(a.get("offset"), 0, 0, 100_000)
    rijen = parse_select(g.sparql(queries.zoek_definitie(
        a["term"], a.get("bwb_id") or None, limit, offset=offset, meer=True)))
    return pagina([_met_voorproef(r, _VOORPROEF_DEFINITIE) for r in rijen], tool="zoek_definitie",
                  args={**a, "limit": limit}, limit=limit, offset=offset)


def _h_grondslagen(g: GraphPort, a: dict[str, Any]) -> str:
    # `_aanduiding` niet gebruiken: die EIST een aanduiding, en hier is 'geen' een geldige vraag
    # (de grondslag van de regeling als geheel).
    aanduiding = a.get("artikel") or a.get("nummer") or None
    return _lijst(g, a, "grondslagen", lambda **p: queries.grondslagen(a["bwb_id"], aanduiding, **p), 50, 200)


def _h_geldigheid(g: GraphPort, a: dict[str, Any]) -> str:
    aanduiding = a.get("artikel") or a.get("nummer") or None
    return _lijst(g, a, "geldigheid",
                  lambda **p: queries.geldigheid(a["bwb_id"], aanduiding, a.get("lid") or None, **p), 50, 200)


def _h_bijlagen(g: GraphPort, a: dict[str, Any]) -> str:
    # `nummer` blijft de naam in het schema (dat is wat een jurist zegt), maar de query accepteert
    # ook een stuk van het label — niet elke bijlage draagt een nummer.
    sleutel = a.get("nummer") or None
    if sleutel is None:
        return _lijst(g, a, "bijlagen", lambda **p: queries.bijlagen(a["bwb_id"], None, **p), 50, 200)
    limit, offset = _geheel(a.get("limit"), 50, 1, 200), _offset(a)
    rijen = parse_select(g.sparql(queries.bijlagen(a["bwb_id"], sleutel, limit=limit, offset=offset, meer=True)))
    if not rijen:
        raise ValueError(f"Geen bijlage {sleutel!r} in {a['bwb_id']}.")
    kop = rijen[0]
    bijlage = compact({k: kop.get(k, "") for k in ("nummer", "titel", "label", "tekst", "jci")})
    delen = [compact({"deel": r.get("deel"), "nummer": r.get("deelnummer"), "tekst": r.get("deeltekst")})
             for r in rijen]
    delen = [d for d in delen if d]
    return pagina(delen, tool="bijlagen", args={**a, "limit": limit}, limit=limit, offset=offset,
                  extra={"bijlage": bijlage})


def _h_context(g: GraphPort, a: dict[str, Any]) -> str:
    return _lijst(g, a, "get_context",
                  lambda **p: queries.context(a["bwb_id"], _aanduiding(a), a.get("lid"), **p), 100, 200)


def _h_referenced_by(g: GraphPort, a: dict[str, Any]) -> str:
    return _lijst(g, a, "referenced_by", lambda **p: queries.referenced_by(a["bwb_id"], _aanduiding(a), **p), 50, 200)


def _h_resolve_begrip(g: GraphPort, a: dict[str, Any]) -> str:
    return _lijst(g, a, "resolve_begrip", lambda **p: queries.resolve_begrip(a["term"], **p), 25, 100)


def _h_schema(g: GraphPort, a: dict[str, Any]) -> str:
    deel = schema.graph_schema(g)
    # Omvang en vocabulaire als één reeks rijen, gepagineerd; de regelingen zelf staan in
    # list_regelingen (hier alleen hun aantal), zodat dit resultaat niet meegroeit met de graaf.
    rijen = ([compact({"deel": "aantal", **r}) for r in deel["aantallen"]]
             + [compact({"deel": "vocabulaire", **r}) for r in deel["vocabulaire"]])
    return per_eenheid(rijen, tool="graph_schema", args={}, offset=_offset(a),
                       extra={"iri_patronen": deel["iri_patronen"], "regelingen": len(deel["regelingen"])},
                       toelichting=deel["toelichting"] + " De regelingen zelf: list_regelingen.")


# raw_sparql is de afgeschermde ontsnapping. Het contract geldt ook hier, maar vrije SPARQL
# herschrijven is foutgevoelig (subqueries met hun eigen LIMIT, modifiers na een geneste groep). Dus
# streng: alleen SELECT, met een eigen LIMIT op het hoogste niveau, en het hele antwoord binnen de
# begroting – of een foutresultaat dat zegt hoe de query aan te passen. Nooit een half antwoord.
_RAW_MAX = 200
_STAART_RE = re.compile(r"\}\s*((?:GROUP\s+BY|HAVING|ORDER\s+BY)[^{}]*?)?\s*LIMIT\s+(\d+)(\s+OFFSET\s+\d+)?\s*$",
                        re.IGNORECASE)


def _h_raw_sparql(g: GraphPort, a: dict[str, Any]) -> str:
    query = str(a["query"]).strip()
    zonder_prefix = re.sub(r"^\s*(PREFIX\s+\S*\s*<[^>]*>\s*)*", "", query, flags=re.IGNORECASE)
    if not re.match(r"SELECT\b", zonder_prefix, re.IGNORECASE):
        return fout("alleen_select", "raw_sparql neemt alleen SELECT-queries aan; het resultaat moet uit rijen bestaan.")
    staart = _STAART_RE.search(query)
    if staart is None:
        return fout("limit_ontbreekt",
                    f"Zet een LIMIT (≤ {_RAW_MAX}) aan het eind van de query, na de laatste }} – en voor "
                    "meer rijen ORDER BY + OFFSET, zodat elke pagina een vaste volgorde heeft.")
    if int(staart.group(2)) > _RAW_MAX:
        return fout("limit_te_hoog", f"LIMIT is hoogstens {_RAW_MAX}; pagineer met ORDER BY + OFFSET.")
    rijen = [compact(r) for r in parse_select(g.sparql(query))]
    try:
        return geheel(rijen, tool="raw_sparql",
                      toelichting="Het resultaat van de query zoals geschreven; meer rijen via ORDER BY + OFFSET.")
    except TeGroot as exc:
        return fout("resultaat_te_groot", f"{len(rijen)} rijen passen niet binnen de begroting; verklein de LIMIT "
                    "of selecteer minder kolommen.", omvang=exc.omvang, budget=BUDGET)


# Twee verschillende oorzaken, voor het model dezelfde uitweg. Het onderscheid is er voor de mens
# die de logs leest: niets ingesteld is een configuratiekwestie, een ontbrekende index is de normale
# toestand na een herstart van de niet-persistente graaf.
_NIET_GECONFIGUREERD = (
    "Semantisch zoeken is nog niet geconfigureerd (geen similarity-index). "
    "Gebruik search_wetgeving voor tekstueel zoeken."
)
_INDEX_ONBRUIKBAAR = (
    "Semantisch zoeken is nu niet beschikbaar (de similarity-index bestaat niet). "
    "Gebruik search_wetgeving voor tekstueel zoeken."
)


# De similarity-index levert Turtle: per treffer een subject met zijn typen, en `limit` telt TRIPLES,
# niet treffers (één bepaling met drie typen kost er drie). Vraag daarom ruim op en lees de subjecten
# in volgorde; zo bestaat er ook een echte `offset`.
_SUBJECT_RE = re.compile(r"^<(urn:bwb:[^>\s]+)>\s+a\s+([^.]+)\.", re.MULTILINE)
_TRIPLES_PER_TREFFER = 6


def _semantische_treffers(turtle: str) -> list[dict[str, str]]:
    uit, gezien = [], set()
    for m in _SUBJECT_RE.finditer(turtle or ""):
        iri = m.group(1)
        if iri in gezien:
            continue
        gezien.add(iri)
        soorten = [t.strip().removeprefix("bwb:") for t in m.group(2).split(",")]
        soort = next((t for t in soorten if t in queries.FTS_TYPES), "")
        uit.append(compact({"node": iri, "soort": soort}))
    return uit


def _h_semantic_search(g: GraphPort, a: dict[str, Any], settings: Any) -> str:
    if settings is None or not getattr(settings, "similarity_index", ""):
        return _NIET_GECONFIGUREERD
    limit, offset = _geheel(a.get("limit"), 10, 1, 50), _geheel(a.get("offset"), 0, 0, 450)
    try:
        treffers = _semantische_treffers(
            g.semantic_search(a["query"], (offset + limit + 1) * _TRIPLES_PER_TREFFER))
        return pagina(treffers[offset:], tool="semantic_search", args={**a, "limit": limit},
                      limit=limit, offset=offset,
                      toelichting="Gerangschikt op betekenis; alleen de vindplaats. Haal de tekst op met "
                                  "get_artikel/get_lid/get_bepaling.")
    except MCPError as exc:
        # De index staat geconfigureerd maar bestaat niet in de graaf. Dat is de toestand vlak ná
        # een herstart: de GraphDB-opslag is niet-persistent. De importer bouwt hem zelf opnieuw
        # (`ensure_similarity_index`), dus dit hoort tijdelijk te zijn — blijft het staan, dan is
        # die herbouw stukgelopen en zegt de importlog waarom.
        # Het model kan hier prima omheen (tekstueel zoeken werkt),
        # maar een beheerder moet het wél weten — vandaar de waarschuwing in de log naast de
        # terugvalmelding. Zonder dit zie je alleen een cryptische toolfout in de trace.
        logger.warning(
            "similarity-index niet bruikbaar; semantic_search valt terug op tekstueel zoeken",
            extra={"index": getattr(settings, "similarity_index", ""), "fout": str(exc)[:200]},
        )
        return _INDEX_ONBRUIKBAAR


# ------------------------------------------------------------------
# Tool-definities
# ------------------------------------------------------------------

_BWB = {"type": "string", "description": "BWB-id van de regeling, bijv. 'BWBR0004770'."}
_ART = {
    "type": "string",
    "description": "Artikelnummer, bijv. '9', '22a', of met een dubbele punt zoals '3:40' "
                   "en '5:2' — die vorm gebruikt de Algemene wet bestuursrecht.",
}
# Beleidsregels en circulaires hebben divisies met decimale nummers ('25.1.1') in plaats van
# artikelen met leden. De verwijzings- en contexttools accepteren daarom beide vormen; wie alleen
# `artikel` aanbood liet de ~800 bepalingen van de Leidraad Invordering buiten bereik.
_NUM = {
    "type": "string",
    "description": "Bepaling-nummer van een beleidsregel/circulaire, bijv. '9.1' of '25.1.1'. "
                   "Gebruik dit i.p.v. 'artikel' als het nummer een punt bevat.",
}
_LID = {"type": "string", "description": "Optioneel lidnummer, bijv. '1'."}
_OFFSET = {"type": "integer", "description": "Sla de eerste N over: neem dit over uit 'vervolg'."}
# Elke graaftool levert hetzelfde contract (`agent/resultaat.py`); deze zin staat in elke beschrijving,
# zodat het model weet dat een onvolledig resultaat zelf zegt hoe je de rest krijgt.
_CONTRACT = (
    "\nRESULTAAT: JSON met 'resultaten' en 'volledig'. Is 'volledig' false, dan staat in 'vervolg' de "
    "exacte aanroep voor het volgende deel – vul niets aan dat je niet hebt opgehaald."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_wetgeving",
        "description": (
            "Full-text zoeken in alle wetteksten (Lucene, Nederlandse analyzer). Gebruik dit om "
            "bepalingen te vinden als je de vindplaats nog niet kent.\n"
            "GEEFT TERUG per treffer: score, knooptype, label, tekst, jci-vindplaats, BWB-id en "
            "citeertitel – genoeg om direct te kunnen citeren, dus een tweede call is niet nodig.\n"
            "Lucene-syntax: AND/OR/NOT, \"exacte frase\", wildcard*.\n"
            "AFBAKENEN loont: met 'veld' zoek je in één geïndexeerd veld (" + ", ".join(queries.FTS_VELDEN) + "), "
            "met 'bwb_id' binnen één regeling, met 'soort' op één knooptype. "
            "veld='definieertBegrip' vindt wáár de wet een begrip definieert i.p.v. elke bepaling "
            "die het woord gebruikt; veld='citeertitel' vindt een regeling op naam.\n"
            "Een lange tekst komt als begin mee met tekst_volledig=false: haal de bepaling dan op."
            + _CONTRACT
        ),
        "input_schema": _obj(
            {
                "query": {"type": "string", "description": "Zoekterm(en) in Lucene-syntax."},
                "veld": {
                    "type": "string",
                    "enum": list(queries.FTS_VELDEN),
                    "description": "Beperk tot één geïndexeerd veld. Weglaten = alle velden.",
                },
                "bwb_id": {"type": "string", "description": "Beperk tot één regeling, bijv. 'BWBR0004770'."},
                "soort": {
                    "type": "string",
                    "enum": list(queries.FTS_TYPES),
                    "description": "Beperk tot één knooptype, bijv. 'Artikel' of 'Onderdeel'.",
                },
                "limit": {"type": "integer", "description": "Max. aantal treffers (1-50, default 10)."},
                "offset": _OFFSET,
            },
            ["query"],
        ),
        "handler": _h_search,
    },
    {
        "name": "semantic_search",
        "description": (
            "Semantisch (op betekenis) zoeken met vector-embeddings. Gebruik dit als de gebruiker "
            "een situatie omschrijft of andere woorden gebruikt dan de wettekst; search_wetgeving "
            "is voor exacte termen. Combineer beide bij twijfel (hybride).\n"
            "GEEFT TERUG per treffer: de vindplaats (graaf-IRI) en het knooptype, gerangschikt op "
            "betekenis – geen tekst; haal die op met get_artikel/get_lid/get_bepaling." + _CONTRACT
        ),
        "input_schema": _obj(
            {
                "query": {"type": "string", "description": "Natuurlijke omschrijving van wat je zoekt."},
                "limit": {"type": "integer", "description": "Max. aantal treffers (1-50, default 10)."},
                "offset": _OFFSET,
            },
            ["query"],
        ),
        "handler": _h_semantic_search,
        "needs_settings": True,
    },
    {
        "name": "get_artikel",
        "description": (
            "De tekst van één ARTIKEL met al zijn leden.\n"
            "GEEFT TERUG: artikeltekst, jci-vindplaats, en per lid het nummer en de tekst; "
            "plus de onderdelen die rechtstreeks onder het artikel hangen (een opsomming bij "
            "een artikel zónder leden).\n"
            "LET OP: onderdelen die onder een LID hangen komen hier niet mee – bij een "
            "definitieartikel zijn dat er tientallen. Gebruik daarvoor get_lid, die ze wél levert."
            + _CONTRACT
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "offset": _OFFSET}, ["bwb_id", "artikel"]),
        "handler": _h_get_artikel,
    },
    {
        "name": "get_lid",
        "description": (
            "De tekst van één LID, mét zijn onderdelen (ook geneste).\n"
            "GEEFT TERUG: lidnummer, lidtekst, jci-vindplaats en de onderdelen in volgorde, "
            "elk mét zijn eigen jci.\n"
            "Dit is de juiste tool voor een definitielid: de eigen tekst is dan vaak alleen de "
            "aanhef ('Deze wet verstaat onder:') en de definities zitten in de onderdelen. "
            "Citeer de vindplaats van het ONDERDEEL, niet die van het hele lid." + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "lid": {"type": "string", "description": "Lidnummer, bijv. '1'."},
             "offset": _OFFSET},
            ["bwb_id", "artikel", "lid"],
        ),
        "handler": _h_get_lid,
    },
    {
        "name": "get_bepaling",
        "description": (
            "Haal een bepaling op via haar NUMMER binnen een regeling – werkt voor artikelen ('9', "
            "'25', '22a') én voor beleidsregels/circulaires met decimale nummers zoals '9.1' (bv. de "
            "Leidraad Invordering 2008), waar get_artikel/get_lid niet passen.\n"
            "GEEFT TERUG: de bepaling (nummer, soort, label, tekst, jci) en, bij een container, haar "
            "subdivisies met het begin van hun tekst." + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "nummer": {"type": "string", "description": "Bepaling-nummer, bijv. '9.1' of '22a'."},
             "offset": _OFFSET},
            ["bwb_id", "nummer"],
        ),
        "handler": _h_get_bepaling,
    },
    {
        "name": "list_regelingen",
        "description": (
            "Alle regelingen die in de kennisgraaf zitten.\n"
            "GEEFT TERUG: IRI, citeertitel, soort (wet/beleidsregel/ministeriele-regeling/…) en de "
            "officiële afkortingen per regeling.\n"
            "Gebruik dit om te zien wat er beschikbaar is voordat je zoekt, of om een BWB-id bij een "
            "naam of afkorting te vinden ('Awb', 'Leidr. Inv.') — raad een BWB-id nooit." + _CONTRACT
        ),
        "input_schema": _obj({"limit": {"type": "integer", "description": "Max. aantal (1-200, default 100)."}, "offset": _OFFSET}, []),
        "handler": _h_list_regelingen,
    },
    {
        "name": "get_regeling_info",
        "description": (
            "Metadata van één regeling: citeertitel, opschrift, soort (wet/regeling/"
            "beleidsregel), geldigheid, uitgevende organisatie en ondertekenaar." + _CONTRACT
        ),
        "input_schema": _obj({"bwb_id": _BWB}, ["bwb_id"]),
        "handler": _h_regeling_info,
    },
    {
        "name": "follow_verwijzingen",
        "description": (
            "UITGAANDE verwijzingen vanuit een bepaling: waar verwijst dit artikel/lid naar?\n"
            "GEEFT TERUG per verwijzing: ankertekst (de woorden waarmee ze in de bron staat), "
            "soort (intref/extref/tekstueel) en het doel mét label, jci, BWB-id en citeertitel – "
            "je hoeft het doel dus niet apart op te zoeken.\n"
            "Werkt op artikelen ('artikel') én op divisies van beleidsregels ('nummer', bijv. '25.1')."
            + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID, "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."}, "offset": _OFFSET},
            ["bwb_id"],
        ),
        "handler": _h_verwijzingen,
    },
    {
        "name": "verwijst_naar_deze",
        "description": (
            "INKOMENDE verwijzingen op BEPALINGniveau: welke artikelen/leden citeren deze bepaling?\n"
            "GEEFT TERUG per citerende bepaling: haar IRI, label, jci en de ankertekst waarmee ze "
            "verwijst.\n"
            "VERSCHIL met referenced_by: die noemt alleen de REGELINGEN die ergens hierheen "
            "verwijzen (grofmazig, uit de WTI); deze noemt de bepaling zelf. Wil je weten wie een "
            "artikel toepast of eraan refereert, gebruik dan deze." + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID,
             "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."},
             "offset": _OFFSET},
            ["bwb_id"],
        ),
        "handler": _h_verwijst_naar_deze,
    },
    {
        "name": "referenced_by",
        "description": (
            "Welke REGELINGEN naar dit artikel verwijzen (WTI-relatie verwijzingDoor). Grofmazig "
            "overzicht; voor de citerende bepaling zelf is verwijst_naar_deze de juiste tool.\n"
            "GEEFT TERUG: regeling-IRI en citeertitel." + _CONTRACT
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."},
                              "offset": _OFFSET}, ["bwb_id"]),
        "handler": _h_referenced_by,
    },
    {
        "name": "inhoudsopgave",
        "description": (
            "De STRUCTUUR van een regeling: welke hoofdstukken, afdelingen, paragrafen, artikelen "
            "of divisies zitten erin (en waarin zitten ze)? Gebruik dit om een regeling te "
            "verkennen of een werkgebied af te bakenen, vóór je gaat zoeken.\n"
            "GEEFT TERUG de boom in DOCUMENTVOLGORDE: per deel niveau, soort, nummer en titel; "
            "opeenvolgende artikelen zonder titel als 'bereik' (bijv. '32–48a', aantal 32). Zo diep "
            "als past; een deel dat ingeklapt is draagt zijn 'iri' en tellingen – vraag het op met "
            "vanaf=<die iri>. Ook de totale 'telling' per soort." + _CONTRACT
        ),
        "input_schema": _obj(
            {
                "bwb_id": _BWB,
                "vanaf": {"type": "string", "description": "Begin bij dit deel: de 'iri' van een ingeklapt "
                          "deel uit een eerder resultaat, of een nummer ('6', '25.1'). Leeg = hele regeling."},
                "offset": _OFFSET,
            },
            ["bwb_id"],
        ),
        "handler": _h_inhoudsopgave,
    },
    {
        "name": "zoek_definitie",
        "description": (
            "Waar DEFINIEERT de wet dit begrip? Zoekt op de begrippen die de wettekst zelf "
            "definieert (bwb:definieertBegrip), meestal in de onderdelen van een definitielid.\n"
            "GEEFT TERUG: het definiërende tekstdeel met zijn tekst, nummer, jci-vindplaats, BWB-id "
            "en citeertitel – dus een citeerbare wettelijke definitie.\n"
            "VERSCHIL met resolve_begrip: die zoekt in de SKOS-thesaurus (redactionele trefwoorden "
            "bij een regeling) en levert geen wettelijke definitie. Begin bij deze tool." + _CONTRACT
        ),
        "input_schema": _obj(
            {
                "term": {"type": "string", "description": "Het begrip, bijv. 'bestuurder'."},
                "bwb_id": {"type": "string", "description": "Optioneel: beperk tot één regeling."},
                "limit": {"type": "integer", "description": "Max. aantal treffers (1-100, default 25)."},
                "offset": _OFFSET,
            },
            ["term"],
        ),
        "handler": _h_zoek_definitie,
    },
    {
        "name": "grondslagen",
        "description": (
            "De delegatieketen: waarop berust deze regeling/bepaling, en wat berust erop?\n"
            "GEEFT TERUG per relatie: 'berust-op' (grondslag van deze regeling), 'grondslag-voor' "
            "en 'bevoegdheid-voor' (regelingen die op DIT tekstdeel berusten), 'in-familie' "
            "(verwante regelingen) en 'berust-op-mij'.\n"
            "Gebruik dit bij vragen over delegatie, uitvoeringsregelingen en bevoegdheid. Laat "
            "'artikel' weg voor de regeling als geheel." + _CONTRACT
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."},
                              "offset": _OFFSET}, ["bwb_id"]),
        "handler": _h_grondslagen,
    },
    {
        "name": "geldigheid",
        "description": (
            "Welke TOESTAND is dit, en sinds wanneer geldt deze tekst?\n"
            "GEEFT TERUG voor de bepaling: inwerkingtredingsdatum, terugwerkende kracht, "
            "wijzigingsbron(nen), effect en status; voor de regeling: geldig vanaf/tot, "
            "toestand-URL, ondertekenings- en uitgiftedatum en dossiernummer.\n"
            "Gebruik dit bij vragen over peildatum, versies of terugwerkende kracht, en om te "
            "melden op welke toestand een analyse berust." + _CONTRACT
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID,
                              "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."},
                              "offset": _OFFSET}, ["bwb_id"]),
        "handler": _h_geldigheid,
    },
    {
        "name": "bijlagen",
        "description": (
            "De bijlagen van een regeling, of de inhoud van één bijlage (tarieftabellen, modellen, "
            "lijsten). Zonder 'nummer' krijg je de lijst; mét 'nummer' de tekst en de onderdelen.\n"
            "GEEFT TERUG: nummer, titel, jci en – bij één bijlage – haar artikelen/onderdelen." + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "nummer": {
                "type": "string",
                "description": "Bijlagenummer ('1') of een stuk van de titel ('artikel 1cb') – niet "
                               "elke bijlage heeft een nummer. Leeg = de lijst.",
            }, "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."}, "offset": _OFFSET},
            ["bwb_id"],
        ),
        "handler": _h_bijlagen,
    },
    {
        "name": "get_context",
        "description": (
            "GraphRAG: een bepaling mét haar hele structurele buurt in ÉÉN call – label, tekst en "
            "jci; het hoofdstuk/de afdeling waar ze in zit (twee niveaus omhoog); haar leden; de "
            "uitgaande verwijzingen; wie ernaar verwijst (regeling én bepaling); en de vorige/"
            "volgende bepaling in het document.\n"
            "GEEFT TERUG: rijen met ?relatie als sleutel (1-zelf-label … 9-gevolgd-door).\n"
            "Gebruik dit voor context- en samenhangvragen i.p.v. losse tools te combineren. Werkt "
            "op artikelen ('artikel') én divisies ('nummer')." + _CONTRACT
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID, "limit": {"type": "integer", "description": "Max. aantal (1-200, default 100)."}, "offset": _OFFSET},
            ["bwb_id"],
        ),
        "handler": _h_context,
    },
    {
        "name": "resolve_begrip",
        "description": (
            "Zoek een juridisch begrip in de SKOS-thesaurus op label en geef het "
            "concept-IRI plus gerelateerde begrippen.\n"
            "GEEFT TERUG per concept: IRI, label en gerelateerde begrippen." + _CONTRACT
        ),
        "input_schema": _obj({"term": {"type": "string", "description": "Begrip of deel ervan."},
                              "limit": {"type": "integer", "description": "Max. aantal (1-100, default 25)."}, "offset": _OFFSET}, ["term"]),
        "handler": _h_resolve_begrip,
    },
    {
        "name": "graph_schema",
        "description": (
            "Geef de live omvang van de graaf (aantallen per type) en de lijst regelingen. "
            "Gebruik dit bij twijfel over wat er in de graaf zit.\n"
            "GEEFT TERUG: aantallen per type, IRI-patronen en de regelingen, met de vocabulaire "
            "(klassen, relaties, eigenschappen) als resultaten – de namen voor raw_sparql." + _CONTRACT
        ),
        "input_schema": _obj({"offset": _OFFSET}, []),
        "handler": _h_schema,
    },
    {
        "name": "raw_sparql",
        "description": (
            "LAATSTE REDMIDDEL: voer een eigen read-only SPARQL SELECT-query uit als geen enkele andere "
            "tool volstaat. Eisen: alleen SELECT, met LIMIT (≤ 200) aan het eind na de laatste }; voor "
            "meer rijen ORDER BY + OFFSET. Het hele resultaat moet binnen de begroting passen, anders "
            "volgt een fout met de reden. Updates worden geweigerd.\n"
            "GEEFT TERUG: de rijen van de query." + _CONTRACT
        ),
        "input_schema": _obj({"query": {"type": "string", "description": "SPARQL SELECT met LIMIT."}}, ["query"]),
        "handler": _h_raw_sparql,
    },
]

TOOLS += ANNOTATIE_TOOLS
_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS + JAS_TOOLS}


def anthropic_schemas(only: set[str] | frozenset[str] | None = None) -> list[dict[str, Any]]:
    """Model-facing tool-schema's; filter op een toegestane set (None = alle).

    De JAS-kennistools zijn **opt-in**: ze doen alleen mee als `only` ze bij naam noemt. Ze stonden
    alleen in `_BY_NAME` – uitvoerbaar via `dispatch`, maar nooit aangeboden aan het model, zodat
    `anthropic_schemas(only=JAS_TOOL_NAMEN)` een lege lijst gaf. Ze bij `only=None` meeleveren zou
    het andere uiterste zijn: dan krijgt de QA-agent er twee tools bij die hij niet nodig heeft,
    terwijl ze voor de klasseer-agent bedoeld zijn.
    """
    beschikbaar = TOOLS if only is None else TOOLS + JAS_TOOLS
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in beschikbaar
        if only is None or t["name"] in only
    ]


# GraphDB's eigen bewoording wanneer de repository niet bestaat: `Repository inning doesn't exist`.
# Op de naam matchen kan niet — die staat in de config, niet hier — dus op de vaste vorm eromheen.
_GRAAF_WEG_RE = re.compile(r"repository\b.{0,80}?\bdoes\s*n['o]?t\s+exist", re.IGNORECASE | re.DOTALL)


def _graaf_is_weg(exc: Exception) -> bool:
    """Zegt deze fout dat de repository zelf ontbreekt (en niet dat de query fout was)?"""
    return bool(_GRAAF_WEG_RE.search(str(exc)))


def dispatch(name: str, graph: GraphPort, args: dict[str, Any] | None, settings: Any = None,
             *, annotaties=None) -> str:
    tool = _BY_NAME.get(name)
    if tool is None:
        return f"Onbekende tool: {name}"
    try:
        if name in ANNOTATIE_TOOL_NAMEN:
            if annotaties is None and settings is not None:
                from ..annotatie_read import AnnotatieReadApi
                annotaties = AnnotatieReadApi(settings, getattr(settings, "annotatie_read_user_id", ""))
            try:
                return dispatch_annotatie(name, args or {}, annotaties)
            except (ValueError, TypeError, KeyError) as exc:
                return json.dumps({"status": "invalid_request", "volledig": False,
                                   "reden": "ongeldige_argumenten", "melding": str(exc)}, ensure_ascii=False)
        if tool.get("needs_settings"):
            return tool["handler"](graph, args or {}, settings)
        return tool["handler"](graph, args or {})
    except TeGroot as exc:
        # Eén ondeelbare eenheid past niet: zichtbaar geen resultaat, nooit een ingekort.
        logger.error("ondeelbare_eenheid_te_groot", extra={"tool": name, "omvang": exc.omvang, "budget": BUDGET})
        return fout("ondeelbare_eenheid_te_groot", str(exc), omvang=exc.omvang, budget=BUDGET)
    except (ValueError, MCPError, KeyError) as exc:
        if _graaf_is_weg(exc):
            # De repository bestaat niet. Niet "tijdelijk onbereikbaar" en geen tikfout in de query:
            # GraphDB is leeg opgekomen na een herstart (de opslag is niet-persistent) en de graaf
            # wordt opnieuw geïmporteerd. Zonder deze tak krijgt de jurist de kale GraphDB-tekst
            # `Repository inning doesn't exist` te zien — een correcte weigering om uit eigen
            # geheugen te citeren, maar zonder enige aanwijzing wat er aan de hand is of hoe lang
            # het duurt. De graafwacht-job herstelt dit binnen een kwartier.
            logger.error(
                "de kennisgraaf is leeg: repository ontbreekt",
                extra={"graaf_weg": True, "tool": name, "fout": str(exc)[:200]},
            )
            return (
                f"Fout bij tool '{name}': de kennisgraaf is op dit moment niet beschikbaar — de "
                "repository ontbreekt. Dat gebeurt na een herstart van de graafdatabase; hij wordt "
                "automatisch opnieuw gevuld en is doorgaans binnen een kwartier terug. Beantwoord "
                "de vraag NIET uit eigen kennis; meld dit en stel voor het straks opnieuw te "
                "proberen."
            )
        # Verwachte fouten (ongeldig argument, MCP-fout, ontbrekende sleutel): als tekst teruggeven.
        return f"Fout bij tool '{name}': {exc}"
    except httpx.HTTPError as exc:
        # Transport-/statusfout naar de graaf (timeout, connection-reset): NIET de hele beurt breken —
        # geef 'm als tool-resultaat terug zodat de agent kan herstellen/rapporteren.
        logger.warning("tool '%s' netwerkfout naar de graaf", name, exc_info=True)
        return f"Fout bij tool '{name}': de kennisgraaf was tijdelijk onbereikbaar ({type(exc).__name__})."
    except Exception as exc:  # noqa: BLE001 – vangnet: nooit de agent-beurt laten crashen op een tool
        logger.error("tool '%s' onverwachte fout", name, exc_info=True)
        return f"Fout bij tool '{name}': {exc}"
