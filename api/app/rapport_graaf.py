"""Wat de kennisgraaf het werkgebiedrapport geeft, naast de bronboom: de regeling, de opbouw en de verwijzingen (ADR-009, aanvulling).

De api haalt het op en zet het in het document, net als de toestanden: PDF en Markdown zien de graaf nooit zelf.

- **Best-effort.** Een haperende graaf geeft `volledig: False`, en het rapport zegt dat (`graaf_onvolledig`); nooit een 500 en
  nooit een stille leegte.
- **Alleen strikt gelezen IRI's gaan de query in** (`BRON_IRI`): de IRI's komen uit Postgres en de bronboom, maar een query
  bouw je niet op vertrouwen.
- **Deterministisch.** Meer waarden voor één veld (twee afkortingen) geven de kleinste; de volgorde van de rijen doet er niet toe.
"""
from __future__ import annotations

import re

import httpx
from bronmodel.taal import BRON_IRI

from .graaf_client import sparql_select

_BWB = re.compile(r"BWB[RV]\d+")
_PER_QUERY = 200

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
  BIND(IRI(CONCAT("urn:bwb:", REPLACE(STRAFTER(STR(?naar), "urn:bwb:"), ":.*$", ""))) AS ?r)
  OPTIONAL {{ ?r bwb:citeertitel ?regeling }}
}}"""


def _waarden(iris: list[str]) -> str:
    return " ".join(f"<{i}>" for i in iris)


def regelingen_query(bwb_ids: list[str]) -> str:
    return _REGELINGEN.format(waarden=_waarden([f"urn:bwb:{b}" for b in sorted(set(bwb_ids)) if _BWB.fullmatch(b)]))


def structuur_query(iris: list[str]) -> str:
    return _STRUCTUUR.format(waarden=_waarden(iris))


def verwijzingen_query(iris: list[str]) -> str:
    return _VERWIJZINGEN.format(waarden=_waarden(iris))


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


async def lees(bwb_ids: list[str], structuur_iris: list[str], bron_iris: list[str] = ()) -> dict:
    """Per regeling de WTI-gegevens en de toestand; per structuurdeel of artikel de titel, inwerkingtreding en laatste wijziging;
    per bronnode in het dossier de verwijzingen die eruit vertrekken, met de ankertekst letterlijk."""
    uit: dict = {"volledig": True, "regelingen": {}, "structuur": {}, "verwijzingen": []}
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
                for r in await sparql_select(client, verwijzingen_query(bronnen[i:i + _PER_QUERY])):
                    if not (r.get("van") and r.get("naar")):
                        continue
                    sleutel = (r["van"], r["naar"], r.get("anker") or "")
                    oud = gezien.get(sleutel, {})
                    gezien[sleutel] = {"van": r["van"], "naar": r["naar"], "anker": r.get("anker") or "",
                                       "label": min(filter(None, [oud.get("label"), r.get("vindplaats") or r.get("doellabel")]), default=""),
                                       "jci": min(filter(None, [oud.get("jci"), r.get("jci")]), default=""),
                                       "regeling": min(filter(None, [oud.get("regeling"), r.get("regeling")]), default="")}
            uit["verwijzingen"] = [gezien[k] for k in sorted(gezien)]
    except (httpx.HTTPError, ConnectionError, ValueError):
        return {**uit, "volledig": False}
    return uit
