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
from collections.abc import Callable
from typing import Any

import httpx

from ..graph import queries, schema
from ..mcp_client import MCPError
from ..ports import GraphPort
from .jas_tools import JAS_TOOL_NAMEN, JAS_TOOLS  # noqa: F401 – re-exporteerd voor orchestrator

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


def _h_search(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(
        queries.fts(
            a["query"],
            a.get("limit", 10),
            veld=a.get("veld") or None,
            bwb_id=a.get("bwb_id") or None,
            soort=a.get("soort") or None,
            offset=a.get("offset", 0),
        )
    )


def _h_get_artikel(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.get_artikel(a["bwb_id"], a["artikel"]))


def _h_get_lid(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.get_lid(a["bwb_id"], a["artikel"], a["lid"]))


def _h_get_bepaling(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.get_bepaling(a["bwb_id"], a["nummer"]))


def _h_list_regelingen(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.list_regelingen())


def _h_regeling_info(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.get_regeling_info(a["bwb_id"]))


def _h_verwijzingen(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.follow_verwijzingen(a["bwb_id"], _aanduiding(a), a.get("lid")))


def _h_verwijst_naar_deze(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(
        queries.verwijst_naar_deze(a["bwb_id"], _aanduiding(a), a.get("lid"), a.get("limit", 50))
    )


def _h_inhoudsopgave(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.inhoudsopgave(a["bwb_id"], a.get("vanaf") or None, a.get("diepte", 2)))


def _h_zoek_definitie(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.zoek_definitie(a["term"], a.get("bwb_id") or None, a.get("limit", 25)))


def _h_grondslagen(g: GraphPort, a: dict[str, Any]) -> str:
    # `_aanduiding` niet gebruiken: die EIST een aanduiding, en hier is 'geen' een geldige vraag
    # (de grondslag van de regeling als geheel).
    aanduiding = a.get("artikel") or a.get("nummer") or None
    return g.sparql(queries.grondslagen(a["bwb_id"], aanduiding))


def _h_geldigheid(g: GraphPort, a: dict[str, Any]) -> str:
    aanduiding = a.get("artikel") or a.get("nummer") or None
    return g.sparql(queries.geldigheid(a["bwb_id"], aanduiding, a.get("lid") or None))


def _h_bijlagen(g: GraphPort, a: dict[str, Any]) -> str:
    # `nummer` blijft de naam in het schema (dat is wat een jurist zegt), maar de query accepteert
    # ook een stuk van het label — niet elke bijlage draagt een nummer.
    return g.sparql(queries.bijlagen(a["bwb_id"], a.get("nummer") or None))


def _h_context(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.context(a["bwb_id"], _aanduiding(a), a.get("lid")))


def _h_referenced_by(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.referenced_by(a["bwb_id"], _aanduiding(a)))


def _h_resolve_begrip(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(queries.resolve_begrip(a["term"]))


def _h_schema(g: GraphPort, a: dict[str, Any]) -> str:
    return schema.graph_schema(g)


def _h_raw_sparql(g: GraphPort, a: dict[str, Any]) -> str:
    return g.sparql(a["query"])


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


def _h_semantic_search(g: GraphPort, a: dict[str, Any], settings: Any) -> str:
    if settings is None or not getattr(settings, "similarity_index", ""):
        return _NIET_GECONFIGUREERD
    try:
        limit = int(a.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(50, limit))  # clamp zoals search_wetgeving (kosten/DoS begrenzen)
    try:
        return g.semantic_search(a["query"], limit)
    except MCPError as exc:
        # De index staat geconfigureerd maar bestaat niet in de graaf. Dat is de normale toestand
        # ná een herstart: de GraphDB-opslag is niet-persistent, en de similarity-index wordt niet
        # door de import-job herbouwd. Het model kan hier prima omheen (tekstueel zoeken werkt),
        # maar een beheerder moet het wél weten — vandaar de waarschuwing in de log naast de
        # terugvalmelding. Zonder dit zag je alleen een cryptische toolfout in de trace.
        logger.warning(
            "similarity-index niet bruikbaar; semantic_search valt terug op tekstueel zoeken",
            extra={"index": getattr(settings, "similarity_index", ""), "fout": str(exc)[:200]},
        )
        return _INDEX_ONBRUIKBAAR


# ------------------------------------------------------------------
# Tool-definities
# ------------------------------------------------------------------

_BWB = {"type": "string", "description": "BWB-id van de regeling, bijv. 'BWBR0004770'."}
_ART = {"type": "string", "description": "Artikelnummer, bijv. '9' of '9a'."}
# Beleidsregels en circulaires hebben divisies met decimale nummers ('25.1.1') in plaats van
# artikelen met leden. De verwijzings- en contexttools accepteren daarom beide vormen; wie alleen
# `artikel` aanbood liet de ~800 bepalingen van de Leidraad Invordering buiten bereik.
_NUM = {
    "type": "string",
    "description": "Bepaling-nummer van een beleidsregel/circulaire, bijv. '9.1' of '25.1.1'. "
                   "Gebruik dit i.p.v. 'artikel' als het nummer een punt bevat.",
}
_LID = {"type": "string", "description": "Optioneel lidnummer, bijv. '1'."}

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
            "die het woord gebruikt; veld='citeertitel' vindt een regeling op naam."
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
                "offset": {"type": "integer", "description": "Sla de eerste N treffers over (volgende pagina)."},
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
            "is voor exacte termen. Combineer beide bij twijfel (hybride)."
        ),
        "input_schema": _obj(
            {
                "query": {"type": "string", "description": "Natuurlijke omschrijving van wat je zoekt."},
                "limit": {"type": "integer", "description": "Max. aantal treffers (default 10)."},
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
            "definitieartikel zijn dat er tientallen en dan kapt de lengtelimiet het resultaat "
            "af. Gebruik daarvoor get_lid, die ze wél levert."
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART}, ["bwb_id", "artikel"]),
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
            "Citeer de vindplaats van het ONDERDEEL, niet die van het hele lid."
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "lid": {"type": "string", "description": "Lidnummer, bijv. '1'."}},
            ["bwb_id", "artikel", "lid"],
        ),
        "handler": _h_get_lid,
    },
    {
        "name": "get_bepaling",
        "description": (
            "Haal een bepaling op via haar NUMMER binnen een regeling – werkt voor artikelen ('9', "
            "'25', '22a') én voor beleidsregels/circulaires met decimale nummers zoals '9.1' (bv. de "
            "Leidraad Invordering 2008), waar get_artikel/get_lid niet passen."
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "nummer": {"type": "string", "description": "Bepaling-nummer, bijv. '9.1' of '22a'."}},
            ["bwb_id", "nummer"],
        ),
        "handler": _h_get_bepaling,
    },
    {
        "name": "list_regelingen",
        "description": (
            "Alle regelingen die in de kennisgraaf zitten.\n"
            "GEEFT TERUG: IRI, citeertitel en soort (wet/beleidsregel/circulaire/…) per regeling.\n"
            "Gebruik dit om te zien wat er beschikbaar is voordat je zoekt, of om een BWB-id "
            "bij een naam te vinden."
        ),
        "input_schema": _obj({}, []),
        "handler": _h_list_regelingen,
    },
    {
        "name": "get_regeling_info",
        "description": (
            "Metadata van één regeling: citeertitel, opschrift, soort (wet/regeling/"
            "beleidsregel), geldigheid, uitgevende organisatie en ondertekenaar."
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
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID},
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
            "artikel toepast of eraan refereert, gebruik dan deze."
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID,
             "limit": {"type": "integer", "description": "Max. aantal (1-200, default 50)."}},
            ["bwb_id"],
        ),
        "handler": _h_verwijst_naar_deze,
    },
    {
        "name": "referenced_by",
        "description": (
            "Welke REGELINGEN naar dit artikel verwijzen (WTI-relatie verwijzingDoor). Grofmazig "
            "overzicht; voor de citerende bepaling zelf is verwijst_naar_deze de juiste tool.\n"
            "GEEFT TERUG: regeling-IRI en citeertitel."
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM}, ["bwb_id"]),
        "handler": _h_referenced_by,
    },
    {
        "name": "inhoudsopgave",
        "description": (
            "De STRUCTUUR van een regeling: welke hoofdstukken, afdelingen, paragrafen, artikelen "
            "of divisies zitten erin (en waarin zitten ze)? Gebruik dit om een regeling te "
            "verkennen of een werkgebied af te bakenen, vóór je gaat zoeken.\n"
            "GEEFT TERUG per deel: niveau, ouder, soort, nummer, titel, label en jci. Laat 'vanaf' "
            "weg voor de hele regeling, of geef een hoofdstuk-/artikelnummer om daar te beginnen.\n"
            "LET OP: de rijen staan op IRI-volgorde, niet op documentvolgorde – sorteer nummers "
            "zelf numeriek (artikel 10 komt ná artikel 2)."
        ),
        "input_schema": _obj(
            {
                "bwb_id": _BWB,
                "vanaf": {"type": "string", "description": "Begin bij dit deel, bijv. '6' of '25.1'. Leeg = hele regeling."},
                "diepte": {"type": "integer", "description": "Aantal niveaus (1-4, default 2)."},
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
            "bij een regeling) en levert geen wettelijke definitie. Begin bij deze tool."
        ),
        "input_schema": _obj(
            {
                "term": {"type": "string", "description": "Het begrip, bijv. 'bestuurder'."},
                "bwb_id": {"type": "string", "description": "Optioneel: beperk tot één regeling."},
                "limit": {"type": "integer", "description": "Max. aantal treffers (1-100, default 25)."},
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
            "'artikel' weg voor de regeling als geheel."
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM}, ["bwb_id"]),
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
            "melden op welke toestand een analyse berust."
        ),
        "input_schema": _obj({"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID}, ["bwb_id"]),
        "handler": _h_geldigheid,
    },
    {
        "name": "bijlagen",
        "description": (
            "De bijlagen van een regeling, of de inhoud van één bijlage (tarieftabellen, modellen, "
            "lijsten). Zonder 'nummer' krijg je de lijst; mét 'nummer' de tekst en de onderdelen.\n"
            "GEEFT TERUG: nummer, titel, jci en – bij één bijlage – haar artikelen/onderdelen."
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "nummer": {
                "type": "string",
                "description": "Bijlagenummer ('1') of een stuk van de titel ('artikel 1cb') – niet "
                               "elke bijlage heeft een nummer. Leeg = de lijst.",
            }},
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
            "op artikelen ('artikel') én divisies ('nummer')."
        ),
        "input_schema": _obj(
            {"bwb_id": _BWB, "artikel": _ART, "nummer": _NUM, "lid": _LID},
            ["bwb_id"],
        ),
        "handler": _h_context,
    },
    {
        "name": "resolve_begrip",
        "description": (
            "Zoek een juridisch begrip in de SKOS-thesaurus op label en geef het "
            "concept-IRI plus gerelateerde begrippen."
        ),
        "input_schema": _obj({"term": {"type": "string", "description": "Begrip of deel ervan."}}, ["term"]),
        "handler": _h_resolve_begrip,
    },
    {
        "name": "graph_schema",
        "description": (
            "Geef de live omvang van de graaf (aantallen per type) en de lijst regelingen. "
            "Gebruik dit bij twijfel over wat er in de graaf zit."
        ),
        "input_schema": _obj({}, []),
        "handler": _h_schema,
    },
    {
        "name": "raw_sparql",
        "description": (
            "LAATSTE REDMIDDEL: voer een eigen read-only SPARQL-query (SELECT/CONSTRUCT/"
            "DESCRIBE) uit als geen enkele andere tool volstaat. Updates worden geweigerd."
        ),
        "input_schema": _obj({"query": {"type": "string", "description": "SPARQL SELECT/CONSTRUCT/DESCRIBE."}}, ["query"]),
        "handler": _h_raw_sparql,
    },
]

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


def dispatch(name: str, graph: GraphPort, args: dict[str, Any] | None, settings: Any = None) -> str:
    tool = _BY_NAME.get(name)
    if tool is None:
        return f"Onbekende tool: {name}"
    try:
        if tool.get("needs_settings"):
            return tool["handler"](graph, args or {}, settings)
        return tool["handler"](graph, args or {})
    except (ValueError, MCPError, KeyError) as exc:
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
