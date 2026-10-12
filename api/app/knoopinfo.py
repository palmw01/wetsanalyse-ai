"""Wat de kennisgraaf over één knoop weet – voor de inspector van de graaf in de werkplek.

`/samenhang` en `/graaf` leveren structuur, verwijzingen en markeringen; de tekst komt uit de
weergave. Wat de BWB-import en de WTI-verrijking verder aan een knoop hangen – inwerkingtreding,
terugwerkende kracht, de wijzigingspublicatie, grondslag en bevoegdheid, regelingen die de bepaling
noemen, gedefinieerde begrippen, de titels en ondertekening van een regeling – bleef onzichtbaar.

Alleen lezen, en niets afgeleid: elke waarde is een triple uit de graaf. De bekende predicaten krijgen
een groep en een Nederlandse naam (`FEITEN`); al het andere staat in `ruw`, zodat er nooit iets
ontbreekt. Een knoop die niet in de graaf staat (een niet-geïmporteerde bepaling) geeft lege groepen.
"""
from __future__ import annotations

from typing import Literal

import httpx

from .graaf_projectie_v2 import _select
from .samenhang import _IRI, _PREFIXES, MAX_VERWIJZINGEN, plaats

BWB = "urn:bwb-ns:"
ELI = "http://data.europa.eu/eli/ontology#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
OWL_SAMEAS = "http://www.w3.org/2002/07/owl#sameAs"
DCT_SUBJECT = "http://purl.org/dc/terms/subject"
# Een pseudo-predicaat voor de inkomende grondslag (`?x bwb:heeftGrondslag <knoop>`).
BERUST_OP_DEZE = "^" + BWB + "heeftGrondslag"
MAX_TRIPLES = 1000

Soort = Literal["tekst", "datum", "knoop", "link"]

# De vaste volgorde van de groepen in de inspector.
GROEPEN = ["Geldigheid", "Herkomst van de tekst", "Regeling", "Grondslag en bevoegdheid", "Genoemd in", "Begrip", "Vindplaats"]

# Predicaat → (groep, naam, soort). Volgorde binnen een groep = volgorde hier.
FEITEN: dict[str, tuple[str, str, Soort]] = {
    BWB + "inwerking": ("Geldigheid", "In werking", "datum"),
    BWB + "terugwerkendTot": ("Geldigheid", "Terugwerkende kracht tot", "datum"),
    BWB + "geldigVanaf": ("Geldigheid", "Toestand geldig vanaf", "datum"),
    BWB + "geldigTot": ("Geldigheid", "Toestand geldig tot", "datum"),
    BWB + "toestandUrl": ("Geldigheid", "Toestand", "link"),
    BWB + "bron": ("Herkomst van de tekst", "Wijzigingspublicatie", "tekst"),
    BWB + "effect": ("Herkomst van de tekst", "Effect", "tekst"),
    BWB + "status": ("Herkomst van de tekst", "Status", "tekst"),
    BWB + "wijzigingsbronnen": ("Herkomst van de tekst", "Wijzigingsbron", "tekst"),
    BWB + "ondertekeningsdatum": ("Herkomst van de tekst", "Ondertekend op", "datum"),
    BWB + "ondertekendDoor": ("Herkomst van de tekst", "Ondertekend door", "knoop"),
    BWB + "uitgiftedatum": ("Herkomst van de tekst", "Uitgegeven op", "datum"),
    BWB + "publicatiejaar": ("Herkomst van de tekst", "Publicatiejaar", "tekst"),
    BWB + "publicatienr": ("Herkomst van de tekst", "Publicatienummer", "tekst"),
    BWB + "dossier": ("Herkomst van de tekst", "Kamerstukdossier", "tekst"),
    BWB + "eerstverantwoordelijke": ("Herkomst van de tekst", "Eerstverantwoordelijke", "tekst"),
    BWB + "uitgegevenDoor": ("Herkomst van de tekst", "Uitgegeven door", "knoop"),
    BWB + "citeertitel": ("Regeling", "Citeertitel", "tekst"),
    BWB + "afkorting": ("Regeling", "Afkorting", "tekst"),
    BWB + "soort": ("Regeling", "Soort", "tekst"),
    BWB + "opschrift": ("Regeling", "Opschrift", "tekst"),
    ELI + "title_alternative": ("Regeling", "Opschrift", "tekst"),
    DCT_SUBJECT: ("Regeling", "Onderwerp", "knoop"),
    BWB + "aanhef": ("Regeling", "Aanhef", "tekst"),
    BWB + "considerans": ("Regeling", "Considerans", "tekst"),
    BWB + "heeftGrondslag": ("Grondslag en bevoegdheid", "Berust op", "knoop"),
    BERUST_OP_DEZE: ("Grondslag en bevoegdheid", "Berust hierop", "knoop"),
    BWB + "grondslagVoor": ("Grondslag en bevoegdheid", "Grondslag voor", "knoop"),
    BWB + "bevoegdheidVoor": ("Grondslag en bevoegdheid", "Bevoegdheid voor", "knoop"),
    BWB + "inFamilie": ("Grondslag en bevoegdheid", "Wetsfamilie", "knoop"),
    BWB + "verwijzingDoor": ("Genoemd in", "Genoemd in", "knoop"),
    BWB + "definieertBegrip": ("Begrip", "Definieert", "tekst"),
    BWB + "jci": ("Vindplaats", "JCI", "tekst"),
    BWB + "bronUrl": ("Vindplaats", "Op wetten.overheid.nl", "link"),
    OWL_SAMEAS: ("Vindplaats", "Op wetten.overheid.nl", "link"),
    BWB + "refKey": ("Vindplaats", "Sleutel", "tekst"),
    RDF_TYPE: ("Vindplaats", "Type in de graaf", "tekst"),
}
# Van de regeling erboven: welke toestand je leest. Alleen als de knoop zelf geen regeling is.
REGELING_GELDIGHEID = [BWB + "geldigVanaf", BWB + "geldigTot", BWB + "toestandUrl"]
# `rdf:type` dat niets zegt: elke citeerbare knoop draagt hem.
_TYPE_ZONDER_BETEKENIS = {BWB + "Citeerbaar"}


def _uitgaand(iri: str) -> str:
    return _PREFIXES + f"""SELECT ?p ?o ?isIri ?naam ?functie WHERE {{
  <{iri}> ?p ?o .
  BIND(isIRI(?o) AS ?isIri)
  OPTIONAL {{ ?o bwb:citeertitel ?titel }}
  OPTIONAL {{ ?o rdfs:label ?label }}
  OPTIONAL {{ ?o bwb:naam ?eigenNaam }}
  OPTIONAL {{ ?o bwb:functie ?functie }}
  BIND(COALESCE(?titel, ?eigenNaam, ?label) AS ?naam)
}} LIMIT {MAX_TRIPLES}"""


def _berust_hierop(iri: str) -> str:
    return _PREFIXES + f"""SELECT ?o ?naam WHERE {{
  ?o bwb:heeftGrondslag <{iri}> .
  OPTIONAL {{ ?o bwb:citeertitel ?titel }}
  OPTIONAL {{ ?o rdfs:label ?label }}
  BIND(COALESCE(?titel, ?label) AS ?naam)
}} LIMIT {MAX_TRIPLES}"""


def _verwijzingen(iri: str) -> str:
    """De `bwb:Verwijzing`-knopen van en naar deze knoop: wat een lijn in de graaf niet draagt (soort,
    soort doel, pad, betrouwbaarheid). Voor de relatielijst in de inspector."""
    return _PREFIXES + f"""SELECT ?richting ?van ?naar ?anker ?soort ?doelSoort ?doelPad ?betrouwbaarheid WHERE {{
  {{ BIND("uit" AS ?richting) BIND(<{iri}> AS ?van) <{iri}> bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar . }}
  UNION {{ BIND("in" AS ?richting) BIND(<{iri}> AS ?naar) ?v bwb:naar <{iri}> . ?van bwb:heeftVerwijzing ?v .
          FILTER(STRSTARTS(STR(?van), "urn:bwb:")) }}
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }}
  OPTIONAL {{ ?v bwb:soort ?soort }}
  OPTIONAL {{ ?v bwb:doelSoort ?doelSoort }}
  OPTIONAL {{ ?v bwb:doelPad ?doelPad }}
  OPTIONAL {{ ?v bwb:betrouwbaarheid ?betrouwbaarheid }}
}} LIMIT {MAX_VERWIJZINGEN * 2}"""


def _regeling_geldigheid(regeling: str) -> str:
    waarden = " ".join(f"<{p}>" for p in REGELING_GELDIGHEID)
    return _PREFIXES + f"""SELECT ?p ?o ?isIri WHERE {{
  VALUES ?p {{ {waarden} }}
  <{regeling}> ?p ?o .
  BIND(isIRI(?o) AS ?isIri)
}}"""


async def _rijen(iri: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Uitgaande triples, de inkomende grondslag, de geldigheid van de regeling erboven, en de
    verwijzingen van en naar de knoop."""
    regeling = f"urn:bwb:{plaats(iri)['bwb_id']}"
    async with httpx.AsyncClient(timeout=20) as client:
        uit = await _select(client, _uitgaand(iri))
        inn = await _select(client, _berust_hierop(iri))
        reg = await _select(client, _regeling_geldigheid(regeling)) if regeling != iri else []
        verw = await _select(client, _verwijzingen(iri))
    return uit, inn, reg, verw


_VOORVOEGSELS = {BWB: "bwb:", ELI: "eli:", "http://www.w3.org/2002/07/owl#": "owl:",
                 "http://www.w3.org/2000/01/rdf-schema#": "rdfs:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
                 "http://purl.org/dc/terms/": "dct:", "http://www.w3.org/ns/oa#": "oa:", "urn:jas-ns:": "jas:"}


def compact(iri: str) -> str:
    """`urn:bwb-ns:inwerking` → `bwb:inwerking`; een onbekende namespace blijft heel."""
    for ns, voorvoegsel in _VOORVOEGSELS.items():
        if iri.startswith(ns):
            return voorvoegsel + iri[len(ns):]
    return iri


def _is_iri(rij: dict) -> bool:
    return str(rij.get("isIri", "")).lower() in {"true", "1"}


def _waarde(rij: dict, soort: Soort) -> dict:
    """Eén waarde voor de inspector: de tekst, en bij een IRI die IRI (de werkplek kiest hem in de
    graaf of maakt er een link van)."""
    o = rij.get("o", "")
    if not _is_iri(rij):
        return {"tekst": o}
    if soort == "link" or not o.startswith("urn:bwb:"):
        return {"tekst": o, "link": o}
    naam = rij.get("naam") or o.removeprefix("urn:bwb:")
    if rij.get("functie"):
        naam = f"{naam} ({rij['functie']})"
    return {"tekst": naam, "iri": o}


def knoop_info_uit(iri: str, uit: list[dict], inn: list[dict], reg: list[dict], verw: list[dict] | None = None) -> dict:
    """Het antwoord uit de rijen; puur, zodat het zonder graaf te testen is."""
    per_feit: dict[tuple[str, str], list[dict]] = {}
    volgorde = list(dict.fromkeys(FEITEN.values()))

    def voeg(p: str, rij: dict) -> None:
        if p not in FEITEN or (p == RDF_TYPE and rij.get("o") in _TYPE_ZONDER_BETEKENIS):
            return
        groep, naam, soort = FEITEN[p]
        waarde = _waarde(rij, soort)
        if p == RDF_TYPE:
            waarde = {"tekst": compact(rij.get("o", ""))}
        lijst = per_feit.setdefault((groep, naam), [])
        if waarde not in lijst:
            lijst.append(waarde)

    for rij in uit:
        voeg(rij.get("p", ""), rij)
    for rij in inn:
        voeg(BERUST_OP_DEZE, {**rij, "isIri": "true"})
    for rij in reg:
        # Een eigen waarde (de knoop ís een regeling) gaat voor; die van de regeling erboven vult aan.
        if (FEITEN[rij["p"]][0], FEITEN[rij["p"]][1]) not in per_feit:
            voeg(rij["p"], rij)

    groepen = []
    for groep in GROEPEN:
        feiten = [{"eigenschap": naam, "waarden": sorted(per_feit[(g, naam)], key=lambda w: w["tekst"].casefold())}
                  for g, naam, _ in volgorde if g == groep and (g, naam) in per_feit]
        # Dezelfde naam kan uit twee predicaten komen (bronUrl en sameAs): één feit, ontdubbeld.
        samen: dict[str, list[dict]] = {}
        for f in feiten:
            samen.setdefault(f["eigenschap"], [])
            samen[f["eigenschap"]] += [w for w in f["waarden"] if w not in samen[f["eigenschap"]]]
        if samen:
            groepen.append({"naam": groep, "feiten": [{"eigenschap": n, "waarden": w} for n, w in samen.items()]})

    ruw = sorted(({"predicaat": compact(r.get("p", "")), "waarde": r.get("o", ""), **({"iri": r["o"]} if _is_iri(r) else {})}
                  for r in uit), key=lambda r: (r["predicaat"], r["waarde"]))
    verwijzingen = sorted(({"richting": r.get("richting", ""), "van": r.get("van", ""), "naar": r.get("naar", ""),
                            "anker": r.get("anker", ""), "soort": r.get("soort", ""), "doel_soort": r.get("doelSoort", ""),
                            "doel_pad": r.get("doelPad", ""), "betrouwbaarheid": r.get("betrouwbaarheid", "")}
                           for r in verw or []), key=lambda v: (v["richting"], v["van"], v["naar"], v["anker"]))
    verwijzingen = [v for i, v in enumerate(verwijzingen) if v not in verwijzingen[:i]]
    return {"schema_versie": 1, "bron_iri": iri, "beschikbaar": True, "groepen": groepen, "ruw": ruw,
            "verwijzingen": verwijzingen}


async def knoop_info(iri: str) -> dict:
    """Wat de graaf over `iri` weet. `ValueError` bij een IRI die geen bronknoop kan zijn: hij gaat
    letterlijk een query in."""
    if not _IRI.fullmatch(iri or ""):
        raise ValueError("Ongeldige bron-IRI.")
    return knoop_info_uit(iri, *await _rijen(iri))
