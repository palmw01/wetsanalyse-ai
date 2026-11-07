"""Wat de kennisgraaf over bepalingen weet, naast de bronboom: de regeling, de opbouw en de verwijzingen (ADR-009, aanvulling).

Eén graaflezing voor het werkgebiedrapport en het paneel naast het gesprek (ADR-008, *Detail bij een antwoord*); de vorm staat in
`bepaling_graaf_contract`. ADR-009 is de eigenaar. De api haalt het op en zet het in het document, net als de toestanden: PDF en
Markdown zien de graaf nooit zelf.

- **Best-effort.** Een haperende graaf geeft `volledig: False`, en het rapport zegt dat (`graaf_onvolledig`); nooit een 500 en
  nooit een stille leegte.
- **Alleen strikt gelezen IRI's gaan de query in** (`BRON_IRI`): de IRI's komen uit Postgres en de bronboom, maar een query
  bouw je niet op vertrouwen.
- **Een begrensde lijst is nooit een totaal.** Elke rijenquery draagt een expliciete grens (`LIMIT n+1`); raakt hij die, dan
  is het resultaat `volledig: False` en zegt de lijst dat ze onvolledig is (`verwijzingen_volledig`). Tellingen komen uit een
  eigen telquery (`met_inkomend`), nooit uit het aantal rijen.
- **Deterministisch.** Meer waarden voor één veld (twee afkortingen) geven de kleinste; de volgorde van de rijen doet er niet toe.
"""
from __future__ import annotations

import re

import httpx
from bronmodel.taal import BRON_IRI

from . import graaf as graaf_mod
from .graaf_client import sparql_select
from .knoopinfo import BWB
from .samenhang import _PREFIXES

_BWB = re.compile(r"BWB[RV]\d+")
_PER_QUERY = 200
#: De grens op de verwijzingsrijen per blok van `_PER_QUERY` bronnodes. De query vraagt er één meer: zo zie je dat hij geraakt is.
MAX_VERWIJZINGSRIJEN = 5000

_REGELINGEN = """PREFIX bwb: <urn:bwb-ns:>
SELECT ?r ?soort ?verantwoordelijke ?organisatie ?afkorting ?toestand ?url WHERE {{ VALUES ?r {{ {waarden} }}
  OPTIONAL {{ ?r bwb:soort ?soort }} OPTIONAL {{ ?r bwb:eerstverantwoordelijke ?verantwoordelijke }}
  OPTIONAL {{ ?r bwb:eerstverantwoordelijkeOrganisatie ?organisatie }} OPTIONAL {{ ?r bwb:afkorting ?afkorting }}
  OPTIONAL {{ ?r bwb:toestandUrl ?toestand }} OPTIONAL {{ ?r bwb:bronUrl ?url }}
}}"""

_STRUCTUUR = """PREFIX bwb: <urn:bwb-ns:>
SELECT ?d ?titel ?inwerking ?bron WHERE {{ VALUES ?d {{ {waarden} }}
  OPTIONAL {{ ?d bwb:titel ?titel }} OPTIONAL {{ ?d bwb:inwerking ?inwerking }} OPTIONAL {{ ?d bwb:bron ?bron }}
}}"""


_VERWIJZINGEN = """PREFIX bwb: <urn:bwb-ns:>
SELECT ?van ?naar ?anker ?vindplaats ?doellabel ?jci ?regeling WHERE {{ VALUES ?van {{ {waarden} }}
  ?van bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar .
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }} OPTIONAL {{ ?naar bwb:vindplaats ?vindplaats }} OPTIONAL {{ ?naar bwb:doelLabel ?doellabel }}
  OPTIONAL {{ ?naar bwb:jci ?jci }}
  BIND(EXISTS {{ ?naar bwb:nummer ?n }} || EXISTS {{ ?naar bwb:citeertitel ?c }} AS ?inGraaf)
  BIND(IRI(CONCAT("urn:bwb:", REPLACE(STRAFTER(STR(?naar), "urn:bwb:"), ":.*$", ""))) AS ?r)
  OPTIONAL {{ ?r bwb:citeertitel ?regeling }}
}} ORDER BY ?van ?naar ?anker LIMIT {grens}"""

#: Verwijzingen hangen aan het lid, niet aan het artikel (graph-qa CLAUDE.md): vanuit de bepaling en alles eronder.
_UIT = """<{iri}> (bwb:heeftLid|bwb:heeftOnderdeel)* ?van . ?van bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar .
     OPTIONAL {{ ?v bwb:ankerTekst ?anker }}"""
_IN = """<{iri}> (bwb:heeftLid|bwb:heeftOnderdeel)* ?naar . ?v bwb:naar ?naar . ?van bwb:heeftVerwijzing ?v .
     FILTER(STRSTARTS(STR(?van), "urn:bwb:") && ?van != <{iri}> && !STRSTARTS(STR(?van), "{iri}:"))"""
#: De tellingen uit de triples van de bepaling zelf.
_TELPREDICATEN = ("grondslagVoor", "bevoegdheidVoor", "verwijzingDoor")


def _waarden(iris: list[str]) -> str:
    return " ".join(f"<{i}>" for i in iris)


def regelingen_query(bwb_ids: list[str]) -> str:
    return _REGELINGEN.format(waarden=_waarden([f"urn:bwb:{b}" for b in sorted(set(bwb_ids)) if _BWB.fullmatch(b)]))


def structuur_query(iris: list[str]) -> str:
    return _STRUCTUUR.format(waarden=_waarden(iris))


def verwijzingen_query(iris: list[str]) -> str:
    return _VERWIJZINGEN.format(waarden=_waarden(iris), grens=MAX_VERWIJZINGSRIJEN + 1)


def _tellingen(iri: str) -> str:
    """Het echte aantal, los van de begrensde rijen: de rijen dragen alleen de voorbeelden. Zonder dit toonde het paneel bij
    meer dan de grens een te laag aantal, alsof het alles was (review #1064)."""
    waarden = " ".join(f"bwb:{p}" for p in _TELPREDICATEN)
    return _PREFIXES + f"""SELECT ?wat ?n WHERE {{
  {{ SELECT ("uit" AS ?wat) (COUNT(*) AS ?n) WHERE {{ SELECT DISTINCT ?van ?naar ?anker WHERE {{ {_UIT.format(iri=iri)} }} }} }}
  UNION {{ SELECT ("in" AS ?wat) (COUNT(DISTINCT ?van) AS ?n) WHERE {{ {_IN.format(iri=iri)} }} }}
  UNION {{ SELECT (STR(?p) AS ?wat) (COUNT(DISTINCT ?o) AS ?n) WHERE {{ VALUES ?p {{ {waarden} }} <{iri}> ?p ?o . FILTER(isIRI(?o)) }} GROUP BY ?p }}
}}"""


def aantallen_uit(rijen: list[dict]) -> dict[str, int]:
    """`{"uit": n, "in": n, "grondslagVoor": n, …}` uit de rijen van `_tellingen`; een rij die geen getal is valt weg."""
    uit: dict[str, int] = {}
    for r in rijen:
        wat, n = str(r.get("wat", "")).removeprefix(BWB), str(r.get("n", ""))
        if wat and n.isdigit():
            uit[wat] = int(n)
    return uit


def geldige_iris(iris) -> list[str]:
    return sorted({i for i in iris if BRON_IRI.fullmatch(i)})


def _kleinste(rijen: list[dict], veld: str) -> str:
    return min((r[veld] for r in rijen if r.get(veld)), default="")


def _per(rijen: list[dict], sleutel: str) -> dict[str, list[dict]]:
    uit: dict[str, list[dict]] = {}
    for r in rijen:
        if r.get(sleutel):
            uit.setdefault(r[sleutel], []).append(r)
    return uit


async def structuur_voor(bron_iris: list[str]) -> list[str]:
    """De `structuur_iris` voor `lees` bij losse bepalingen (het paneel): de delen boven elke bepaling en de bepaling zelf, uit
    `graaf.plaatsen`. Het rapport heeft de bronboom al en leidt ze daar zelf uit af (`werkgebied_export.structuur_iris`)."""
    iris = geldige_iris(bron_iris)
    if not iris:
        return []
    return sorted({p["iri"] for r in await graaf_mod.plaatsen(iris) for p in r.get("pad") or [] if p.get("iri")} | set(iris))


async def lees(bwb_ids: list[str], structuur_iris: list[str], bron_iris: list[str] = (), *, met_inkomend: bool = False) -> dict:
    """Per regeling de WTI-gegevens en de toestand; per structuurdeel of artikel de titel, inwerkingtreding en laatste wijziging;
    per bronnode de verwijzingen die eruit vertrekken, met de ankertekst letterlijk.

    Met `met_inkomend` ook per bronnode de tellingen (`tellingen`: uit, in, grondslagVoor, bevoegdheidVoor, verwijzingDoor) uit
    een eigen telquery; het paneel wil ze, het rapport niet (inkomende verwijzingen uit de hele graaf zijn daar ruis)."""
    uit: dict = {"volledig": True, "regelingen": {}, "structuur": {}, "verwijzingen": [], "verwijzingen_volledig": True}
    if met_inkomend:
        uit["tellingen"] = {}
    bwbs = sorted({b for b in bwb_ids if _BWB.fullmatch(b)})
    iris, bronnen = geldige_iris(structuur_iris), geldige_iris(bron_iris)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if bwbs:
                for iri, rijen in _per(await sparql_select(client, regelingen_query(bwbs)), "r").items():
                    uit["regelingen"][iri.removeprefix("urn:bwb:")] = {
                        "soort": _kleinste(rijen, "soort"), "verantwoordelijke": _kleinste(rijen, "verantwoordelijke"),
                        "organisatie": _kleinste(rijen, "organisatie"), "afkorting": _kleinste(rijen, "afkorting"),
                        "toestand_url": _kleinste(rijen, "toestand"), "url": _kleinste(rijen, "url")}
            for i in range(0, len(iris), _PER_QUERY):
                for iri, rijen in _per(await sparql_select(client, structuur_query(iris[i:i + _PER_QUERY])), "d").items():
                    uit["structuur"][iri] = {"titel": _kleinste(rijen, "titel"), "inwerking": _kleinste(rijen, "inwerking")[:10],
                                             "gewijzigd_bij": _kleinste(rijen, "bron")}
            gezien: dict[tuple[str, str, str], dict] = {}
            for i in range(0, len(bronnen), _PER_QUERY):
                rijen = await sparql_select(client, verwijzingen_query(bronnen[i:i + _PER_QUERY]))
                if len(rijen) > MAX_VERWIJZINGSRIJEN:     # de grens geraakt: de lijst is niet alles, en dat zegt het rapport
                    uit["verwijzingen_volledig"] = uit["volledig"] = False
                    rijen = rijen[:MAX_VERWIJZINGSRIJEN]
                for r in rijen:
                    if not (r.get("van") and r.get("naar")):
                        continue
                    sleutel = (r["van"], r["naar"], r.get("anker") or "")
                    oud = gezien.get(sleutel, {})
                    gezien[sleutel] = {"van": r["van"], "naar": r["naar"], "anker": r.get("anker") or "",
                                       "label": min(filter(None, [oud.get("label"), r.get("vindplaats") or r.get("doellabel")]), default=""),
                                       "jci": min(filter(None, [oud.get("jci"), r.get("jci")]), default=""),
                                       "regeling": min(filter(None, [oud.get("regeling"), r.get("regeling")]), default=""),
                                       "in_graaf": oud.get("in_graaf", False) or r.get("inGraaf") != "false"}
            uit["verwijzingen"] = [gezien[k] for k in sorted(gezien)]
            if met_inkomend:
                for iri in bronnen:
                    uit["tellingen"][iri] = aantallen_uit(await sparql_select(client, _tellingen(iri)))
    except (httpx.HTTPError, ConnectionError, ValueError):
        return {**uit, "volledig": False}
    return uit
