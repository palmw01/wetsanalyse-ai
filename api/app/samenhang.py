"""Samenhang van één bepaling: bronstructuur, annotaties en letterlijke verwijzingen als graaf.

Voor de 3D-weergave in de werkplek. De graaf bestaat uit drie soorten relaties, en alleen die:

- **structuur** – de bronboom zelf (`parent_iri`): regeling → … → artikel → leden en onderdelen;
- **verwijzingen** – `bwb:heeftVerwijzing`/`bwb:verwijstNaar` zoals de BWB-import ze uit de tekst
  haalde, één stap uitgaand en inkomend. Een doel buiten het artikel wordt een *randknoop*; de
  werkplek kan die later zelf openen;
- **annotaties** – actuele markeringen van de gedeelde laag en hun JAS-klasse.

Er wordt niets afgeleid: geen juridische afhankelijkheid, geen gewicht, geen positie. De reikwijdte
is het artikel (of de Leidraad-divisie) waartoe het gevraagde doel behoort, ook als een lid werd
gevraagd, zodat een lid zijn broers en de verwijzing ertussen laat zien.

Een **structuurdeel** als doel (hoofdstuk, titeldeel, afdeling, paragraaf) is een overzicht: het deel
met de structuur en de artikelen eronder, zonder leden, onderdelen, markeringen en verwijzingen. Een
overzichtsantwoord ("welke artikelen gaan over invordering?") noemt hoofdstukken; met alle leden en
onderdelen erbij werd zo'n deel een kluwen van honderden knopen. Wie verder wil, opent een artikel.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel

from . import annotatie_v2_store as store
from .graaf_projectie_v2 import _select

logger = logging.getLogger(__name__)

MAX_VERWIJZINGEN = 200
_IRI = re.compile(r"urn:bwb:(BWB[RV]\d+)(?::[^<>\s\"{}|^`\\]*)?")
# Wat in het overzicht van een structuurdeel staat; leden en onderdelen horen bij het artikel.
_OVERZICHT = {"Hoofdstuk", "Titeldeel", "Afdeling", "Paragraaf", "Artikel", "Divisie"}
_SOORT = {"Regeling": "regeling", "Artikel": "artikel", "Divisie": "artikel", "Lid": "lid", "Onderdeel": "onderdeel"}
_PREFIXES = "PREFIX bwb: <urn:bwb-ns:>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"

Soort = Literal["regeling", "deel", "artikel", "lid", "onderdeel", "markering", "klasse", "extern"]
Groep = Literal["structuur", "verwijzingen", "annotaties"]


class Knoop(BaseModel):
    id: str
    soort: Soort
    label: str
    tekst: str = ""
    klasse: str = ""
    lifecycle: str = ""
    element_id: str = ""
    bwb_id: str = ""
    artikel: str = ""
    lid: str = ""
    rand: bool = False
    # Alleen bij een markering: wat de werkplek nodig heeft om op herkomst en review te filteren.
    herkomst: str = ""             # agent | mens
    aandacht: str = ""             # groen | geel, leeg = gewoon voorstel
    subtype: str = ""
    beslist_door: str = ""         # regel | model | specificiteit, leeg zonder spoor
    twijfel: bool = False


class Relatie(BaseModel):
    bron: str
    doel: str
    soort: Literal["bevat", "verwijst_naar", "markeert", "heeft_klasse"]
    groep: Groep
    anker_tekst: str = ""


class Samenhang(BaseModel):
    schema_versie: Literal[1] = 1
    doel: dict
    snapshot_id: str
    artikel_iri: str
    knopen: list[Knoop]
    relaties: list[Relatie]
    verwijzingen_beschikbaar: bool
    afgekapt: bool = False


def artikel_van(nodes: dict[str, dict], iri: str) -> str:
    """Het dichtstbijzijnde artikel (of divisie) boven of op `iri`; anders `iri` zelf."""
    for kandidaat in store.keten(nodes, iri):
        if nodes[kandidaat].get("type") in {"Artikel", "Divisie"}:
            return kandidaat
    return iri


def _label(node: dict) -> str:
    """Het label van een bronknoop. De bronboom draagt `bwb:label`, en dat is bij een hoofdstuk of
    afdeling alleen het woord ("Hoofdstuk"), met het nummer apart: zonder dit zeiden inspector en kop
    van de graaf "gaan over Hoofdstuk". Hier en niet in `bronmodel`: daar raakt het label de
    snapshot-identiteit van bestaande lagen."""
    label, nummer = (node.get("label") or "").strip(), (node.get("nummer") or "").strip()
    if nummer and label and node.get("type") in _OVERZICHT - {"Artikel", "Divisie"} and nummer not in label:
        return f"{label} {nummer}"
    return label


def plaats(iri: str) -> dict[str, str]:
    """BWB-id, artikel en lid uit een bron-IRI; leeg als de IRI dat niet draagt."""
    m = _IRI.fullmatch(iri)
    if not m:
        return {"bwb_id": "", "artikel": "", "lid": ""}
    rest = iri.split(":")
    waarde = {k: rest[i + 1] for i, k in enumerate(rest[:-1]) if k in {"artikel", "lid"}}
    return {"bwb_id": m.group(1), "artikel": waarde.get("artikel", ""), "lid": waarde.get("lid", "")}


def _uitgaand(iris: list[str]) -> str:
    waarden = " ".join(f"<{i}>" for i in iris)
    return _PREFIXES + f"""SELECT DISTINCT ?van ?naar ?anker ?label ?stub WHERE {{
  VALUES ?van {{ {waarden} }}
  ?van bwb:heeftVerwijzing ?v . ?v bwb:naar ?naar .
  OPTIONAL {{ ?v bwb:ankerTekst ?anker }}
  OPTIONAL {{ ?naar rdfs:label ?label }}
  OPTIONAL {{ ?naar bwb:doelLabel ?stub }}
}} LIMIT {MAX_VERWIJZINGEN + 1}"""


def _inkomend(iris: list[str]) -> str:
    waarden = " ".join(f"<{i}>" for i in iris)
    return _PREFIXES + f"""SELECT DISTINCT ?van ?naar ?anker ?label WHERE {{
  VALUES ?naar {{ {waarden} }}
  {{ ?van bwb:verwijstNaar ?naar . }}
  UNION {{ ?v bwb:naar ?naar . ?van bwb:heeftVerwijzing ?v . OPTIONAL {{ ?v bwb:ankerTekst ?anker }} }}
  FILTER(STRSTARTS(STR(?van), "urn:bwb:"))
  OPTIONAL {{ ?van rdfs:label ?label }}
}} LIMIT {MAX_VERWIJZINGEN + 1}"""


async def _verwijzingen(iris: list[str]) -> tuple[list[dict], list[dict]] | None:
    """Uitgaande en inkomende rijen, of None als de graaf de vraag niet kon beantwoorden."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            return await _select(client, _uitgaand(iris)), await _select(client, _inkomend(iris))
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("verwijzingen voor samenhang niet beschikbaar", extra={"fout": type(exc).__name__})
        return None


def bronknoop(node: dict, rand: bool = False) -> Knoop:
    """Een bronknoop uit een knoop van de bronboom (snapshot)."""
    iri = node["bron_iri"]
    return Knoop(id=iri, soort=_SOORT.get(node.get("type", ""), "deel"), label=_label(node) or iri,
                 tekst=node.get("tekst", ""), rand=rand, **plaats(iri))


def markeringen(elementen: list[dict], aanwezig: set[str]) -> tuple[list[Knoop], list[Relatie]]:
    """Actuele markeringen als knopen, met hun klasse en de bronknopen die ze markeren (alleen
    `aanwezig`). Afgewezen en verouderde elementen blijven weg; een terugval zonder klasse krijgt geen
    klasseknoop."""
    knopen: dict[str, Knoop] = {}
    relaties: list[Relatie] = []
    for el in elementen:
        if el.get("lifecycle") == "rejected" or el.get("verouderd"):
            continue
        eid, klasse = f"element:{el['id']}", el["klasse"]
        spoor = el.get("trace") or {}
        knopen[eid] = Knoop(id=eid, soort="markering", label=el["tekst"], tekst=el["tekst"], klasse=klasse,
                            lifecycle=el.get("lifecycle", ""), element_id=el["id"],
                            herkomst=el.get("herkomst") or "", aandacht=el.get("aandacht") or "",
                            subtype=el.get("jas_subtype") or "",
                            beslist_door=(spoor.get("beslissing") or {}).get("door") or "",
                            twijfel=bool(spoor.get("twijfel")), **plaats(el["eigenaar_iri"]))
        for anker in sorted({a["bron_iri"] for a in el["ankers"]} & aanwezig):
            relaties.append(Relatie(bron=eid, doel=anker, soort="markeert", groep="annotaties"))
        if not klasse:
            continue
        knopen.setdefault(f"klasse:{klasse}", Knoop(id=f"klasse:{klasse}", soort="klasse", label=klasse, klasse=klasse))
        relaties.append(Relatie(bron=eid, doel=f"klasse:{klasse}", soort="heeft_klasse", groep="annotaties"))
    return list(knopen.values()), relaties


def verwijzingen(rijen: list[tuple[str, dict]], knopen: dict[str, Knoop]) -> list[Relatie]:
    """Verwijzingsrelaties uit SPARQL-rijen, als `(richting, rij)` met richting "uit" of "in". Een doel
    buiten `knopen` wordt een randknoop (geïmporteerd: artikel of lid; anders `extern`) – `knopen` wordt
    daarvoor aangevuld. Elke verwijzing één keer."""
    relaties: list[Relatie] = []
    gezien: set[tuple[str, str]] = set()
    for richting, r in rijen:
        van, naar = r.get("van", ""), r.get("naar", "")
        buiten = naar if richting == "uit" else van
        if not van or not naar or not _IRI.fullmatch(buiten) or (van, naar) in gezien:
            continue
        gezien.add((van, naar))
        if buiten not in knopen:
            label = r.get("label") or r.get("stub") or buiten.removeprefix("urn:bwb:")
            knopen[buiten] = Knoop(id=buiten, soort="extern" if not r.get("label") else
                                   ("lid" if plaats(buiten)["lid"] else "artikel"),
                                   label=label, rand=True, **plaats(buiten))
        relaties.append(Relatie(bron=van, doel=naar, soort="verwijst_naar", groep="verwijzingen",
                                anker_tekst=r.get("anker", "")))
    return relaties


async def samenhang(snapshot: dict) -> dict:
    nodes = store.nodes_van(snapshot)
    artikel_iri = artikel_van(nodes, snapshot["doel"]["bron_iri"])
    scope = store.bereik_van(snapshot, artikel_iri)
    deel = nodes[artikel_iri].get("type") not in {"Artikel", "Divisie"}
    if deel:
        scope = {i for i in scope if nodes[i].get("type") in _OVERZICHT}
        weergave = {"elementen": []}
    else:
        weergave = await store.weergave({**snapshot, "doel": nodes[artikel_iri]})

    knopen: dict[str, Knoop] = {}
    relaties: list[Relatie] = []

    # Structuur: de keten van regeling naar artikel, en alles binnen het artikel.
    keten = store.keten(nodes, artikel_iri)
    for iri in [*reversed(keten), *sorted(scope - {artikel_iri}, key=lambda i: nodes[i].get("volgorde", 0))]:
        knopen[iri] = bronknoop(nodes[iri])
        ouder = nodes[iri].get("parent_iri") or ""
        if ouder in knopen:
            relaties.append(Relatie(bron=ouder, doel=iri, soort="bevat", groep="structuur"))
    regeling = next((i for i in keten if nodes[i].get("type") == "Regeling"), keten[-1])
    knopen[regeling] = knopen[regeling].model_copy(update={"label": snapshot.get("citeertitel") or knopen[regeling].label})

    # Annotaties: actuele markeringen en hun klasse.
    m_knopen, m_relaties = markeringen(weergave["elementen"], set(knopen))
    knopen.update({k.id: k for k in m_knopen})
    relaties += m_relaties

    # Verwijzingen: één stap, uitgaand en inkomend, alleen wat letterlijk in de bron staat.
    # Bij een structuurdeel geen verwijzingen: die hangen aan de leden, en die staan niet in het overzicht.
    rijen = ([], []) if deel else await _verwijzingen(sorted(scope))
    afgekapt = False
    if rijen is not None:
        uit, inn = rijen
        afgekapt = len(uit) > MAX_VERWIJZINGEN or len(inn) > MAX_VERWIJZINGEN
        relaties += verwijzingen([("uit", r) for r in uit[:MAX_VERWIJZINGEN]]
                                 + [("in", r) for r in inn[:MAX_VERWIJZINGEN]], knopen)
    return Samenhang(doel=snapshot["doel"], snapshot_id=snapshot["snapshot_id"], artikel_iri=artikel_iri,
                     knopen=list(knopen.values()), relaties=relaties,
                     verwijzingen_beschikbaar=rijen is not None, afgekapt=afgekapt).model_dump()
