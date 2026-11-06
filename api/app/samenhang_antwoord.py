"""De ketting bij een antwoord: `GET /v1/annotatie/samenhang/antwoord`.

Een doel is de diepste bepaling die het bericht aanwijst. Per doel: de keten erboven, het doel, één niveau
eronder, de markeringen daarop, de begrippen die daar gelden en de uitgaande verwijzingen. Niets anders, ook geen
broers: alles zien is een aparte keuze (`/samenhang`, `/graaf`). Daarom een eigen route: de invariant van
`/samenhang` ("drie soorten relaties en niets anders") blijft zo letterlijk waar.

**Begrippen.** Een wettelijk begrip komt uit `bwb:definieertBegrip` in de regeling van het doel. Het staat er alleen
als de term letterlijk in de getoonde tekst voorkomt én het doel binnen het geldingsbereik van de definitie valt;
een bereik dat niet op te lossen is, telt niet. `komt_voor_in` zegt dus alleen dat de term er letterlijk staat, geen
juridische relatie. Een begrip uit een werkgebied hangt aan een koppeling met een getoonde markering; in een los
gesprek alleen een geaccordeerd generiek begrip, want een concept uit andermans werkgebied is ruis.

Een haperende graaf is `begrippen_beschikbaar: false`, nooit "geen begrippen".
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Literal

import httpx
from bronmodel import BronFout
from bronmodel.definities import Geldigheid, geldigheid_uit, losse_termen, term_vindplaats
from pydantic import BaseModel

from . import annotatie_v2_store as store
from . import begrip_store, graaf
from .bron_resolver import bwb_van
from .graaf_projectie_v2 import _select
from .samenhang import (
    MAX_VERWIJZINGEN,
    Knoop,
    Relatie,
    _uitgaand,
    artikel_van,
    bronknoop,
    citeertitel_van,
    markeringen,
    verwijzingen,
)

logger = logging.getLogger(__name__)

#: Boven deze grens geen enkele markering op dat doel maar de telling: een willekeurig deel is erger.
MAX_MARKERINGEN = 30
MAX_BEGRIPPEN = 12
MAX_KINDEREN = 30

_DEFINITIES: dict[tuple[str, str], list[dict]] = {}
_PREFIXES = "PREFIX bwb: <urn:bwb-ns:>\n"


class Definitie(BaseModel):
    bron_iri: str
    vindplaats: str
    aanhef: str
    tekst: str
    bereik: str          # regeling | artikel | lid | structuur
    formule: str = ""


class AntwoordKnoop(Knoop):
    """Een knoop van de ketting. Een subklasse, zodat `/graaf` met duizenden knopen niet groeit."""
    soort: Literal["regeling", "deel", "artikel", "lid", "onderdeel", "markering", "extern", "begrip"]
    status: str = ""
    begrip_bron: Literal["", "wet", "werkgebied", "generiek"] = ""
    werkgebied_id: str = ""
    definities: list[Definitie] = []


class AntwoordRelatie(Relatie):
    soort: Literal["bevat", "verwijst_naar", "markeert", "definieert", "komt_voor_in", "duidt"]
    groep: Literal["structuur", "verwijzingen", "annotaties", "begrippen"]


class Ingekort(BaseModel):
    kinderen: dict[str, int] = {}
    markeringen: dict[str, int] = {}
    begrippen: int = 0
    onzekere_verwijzingen: int = 0


class AntwoordKeten(BaseModel):
    schema_versie: Literal[1] = 1
    keten: Literal[True] = True
    doel: dict
    doelen: list[str]
    snapshot_id: str
    artikel_iri: str
    knopen: list[AntwoordKnoop]
    relaties: list[AntwoordRelatie]
    verwijzingen_beschikbaar: bool
    afgekapt: bool = False
    begrippen_beschikbaar: bool
    ingekort: Ingekort
    fouten: list[dict]


def _definities_query(bwb: str) -> str:
    return _PREFIXES + f"""SELECT ?node ?begrip WHERE {{
  GRAPH <urn:bwb:graph:{bwb}> {{ ?node bwb:definieertBegrip ?begrip }}
}} ORDER BY ?node"""


async def _definities(bwb: str, snapshot_id: str) -> list[dict]:
    """De begripsbepalingen van een regeling, per bronstand één keer."""
    sleutel = (bwb, snapshot_id)
    if sleutel not in _DEFINITIES:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await _select(client, _definities_query(bwb))
        for oud in [k for k in _DEFINITIES if k[0] == bwb]:
            del _DEFINITIES[oud]        # een vorige toestand van deze regeling is voorbij
        _DEFINITIES[sleutel] = rijen
    return _DEFINITIES[sleutel]


def _aanhef_en_geldigheid(nodes: dict, iri: str) -> tuple[str, Geldigheid]:
    """De aanhef (de tekst van de dichtstbijzijnde houder met een formule) en de formule. De houders eerst: in de
    definitie zelf kan "voor de toepassing van" over iets anders gaan. Zonder formule de ouder, en de hele regeling."""
    ouders = store.keten(nodes, iri)[1:]
    for ouder in ouders:
        if nodes[ouder].get("type") in {"Regeling"}:
            break
        g = geldigheid_uit(nodes[ouder].get("tekst", ""))
        if g.soort:
            return nodes[ouder].get("tekst", ""), g
    g = geldigheid_uit(nodes[iri].get("tekst", ""))
    return (nodes[ouders[0]].get("tekst", "") if ouders else ""), g


def _geldt_voor(nodes: dict, definitie: str, g: Geldigheid, doel: str) -> bool:
    """Valt het doel binnen het bereik van deze definitie? Niet op te lossen is nee."""
    keten = store.keten(nodes, doel)
    if g.soort in {"", "regeling"}:
        return True
    if g.soort == "artikel":
        return artikel_van(nodes, definitie) in keten
    if g.soort == "artikel_n":
        artikel = artikel_van(nodes, definitie)
        regeling = artikel.split(":artikel:")[0]
        return f"{regeling}:artikel:{g.waarde}" in keten
    if g.soort == "lid":
        lid = next((i for i in store.keten(nodes, definitie) if nodes[i].get("type") == "Lid"), "")
        return bool(lid) and lid in keten
    if g.soort == "structuur":
        woord = {"titel": "Titeldeel"}.get(g.waarde, g.waarde.capitalize())
        houder = next((i for i in store.keten(nodes, definitie) if nodes[i].get("type") == woord), "")
        return bool(houder) and houder in keten
    return False


def _wettelijke_begrippen(nodes: dict, bwb: str, rijen: list[dict], doelen: dict[str, list[str]],
                          ) -> tuple[list[AntwoordKnoop], list[AntwoordRelatie], dict[str, AntwoordKnoop], int]:
    """Begrippen uit `rijen` (`?node ?begrip`) die in de getoonde tekst staan en daar gelden. `doelen` is per doel de
    getoonde tekstnodes (doel plus kinderen). Eén begrip met al zijn definities; een doel dat zelf definieert hoort
    erbij, ook als de term daar niet nog eens voorkomt. Het laatste getal: begrippen boven de grens."""
    begrippen: dict[str, AntwoordKnoop] = {}
    relaties: list[AntwoordRelatie] = []
    gezien: set[tuple[str, str, str]] = set()
    bepalingen: dict[str, AntwoordKnoop] = {}
    te_veel: set[str] = set()
    for rij in rijen:
        definitie = rij.get("node", "")
        if definitie not in nodes:
            continue
        aanhef, g = _aanhef_en_geldigheid(nodes, definitie)
        for term in losse_termen(rij.get("begrip", "")):
            sleutel = f"term:{bwb}:{term.lower()}"
            for doel, getoond in doelen.items():
                if not _geldt_voor(nodes, definitie, g, doel):
                    continue
                treffers = [(i, f) for i in getoond if (f := term_vindplaats(term, nodes[i].get("tekst", "")))]
                eigen = definitie == doel or definitie in getoond
                if not treffers and not eigen:
                    continue
                if sleutel not in begrippen:
                    if len(begrippen) >= MAX_BEGRIPPEN:
                        te_veel.add(sleutel)
                        continue
                    begrippen[sleutel] = AntwoordKnoop(id=sleutel, soort="begrip", label=term, bwb_id=bwb,
                                                       begrip_bron="wet")
                b = begrippen[sleutel]
                if not any(d.bron_iri == definitie for d in b.definities):
                    b.definities = [*b.definities, Definitie(
                        bron_iri=definitie, vindplaats=nodes[definitie].get("vindplaats") or "", aanhef=aanhef,
                        tekst=nodes[definitie].get("tekst", ""), bereik=g.soort or "regeling", formule=g.formule)]
                    b.tekst = b.tekst or nodes[definitie].get("tekst", "")
                    bepalingen.setdefault(definitie, AntwoordKnoop.model_validate(
                        bronknoop(nodes[definitie], rand=True, nodes=nodes).model_dump()))
                    relaties.append(AntwoordRelatie(bron=definitie, doel=sleutel, soort="definieert", groep="begrippen"))
                for iri, fragment in treffers:
                    if (sleutel, iri, fragment) not in gezien:
                        gezien.add((sleutel, iri, fragment))
                        relaties.append(AntwoordRelatie(bron=sleutel, doel=iri, soort="komt_voor_in", groep="begrippen",
                                                        anker_tekst=fragment))
    return list(begrippen.values()), relaties, bepalingen, len(te_veel)


def _naar_kortste_markering(relaties: list[AntwoordRelatie], tekst: dict[str, tuple[str, str]]) -> None:
    """`komt_voor_in` wijst naar de kortste markering op die bepaling die het fragment bevat; anders de bepaling."""
    per_bron: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for eid, (bron, inhoud) in tekst.items():
        per_bron[bron].append((eid, inhoud))
    for r in relaties:
        if r.soort != "komt_voor_in":
            continue
        passend = [(len(t), e) for e, t in per_bron.get(r.doel, []) if r.anker_tekst in t]
        if passend:
            r.doel = min(passend)[1]


async def _werkgebied_begrippen(werkgebied_id: str, element_ids: set[str]) -> tuple[list[AntwoordKnoop], list[AntwoordRelatie]]:
    data = await begrip_store.samenhang(werkgebied_id)
    koppelingen = [k for k in data["koppelingen"] if k["beoordeling"] != "afgewezen" and k["element_id"] in element_ids]
    gekoppeld = {k["begrip_id"] for k in koppelingen}
    knopen = [AntwoordKnoop(id=f"begrip:{b['id']}", soort="begrip", label=b["naam"], tekst=b["definitie"], status=b["status"],
                            begrip_bron="werkgebied", werkgebied_id=werkgebied_id)
              for b in data["begrippen"] if b["id"] in gekoppeld]
    aanwezig = {k.id for k in knopen}
    relaties = [AntwoordRelatie(bron=f"begrip:{k['begrip_id']}", doel=f"element:{k['element_id']}", soort="duidt",
                                groep="begrippen", anker_tekst=k["rol"])
                for k in koppelingen if f"begrip:{k['begrip_id']}" in aanwezig]
    return knopen, relaties


async def _generieke_begrippen(element_ids: set[str]) -> tuple[list[AntwoordKnoop], list[AntwoordRelatie]]:
    rijen = await begrip_store.generiek_bij_elementen(element_ids)
    knopen = {r["id"]: AntwoordKnoop(id=f"begrip:{r['id']}", soort="begrip", label=r["naam"], tekst=r["definitie"],
                                     status=r["status"], begrip_bron="generiek") for r in rijen}
    relaties = [AntwoordRelatie(bron=f"begrip:{r['id']}", doel=f"element:{r['element_id']}", soort="duidt",
                                groep="begrippen", anker_tekst=r["rol"]) for r in rijen]
    return list(knopen.values()), relaties


def _bestaand_doel(nodes: dict, iri: str) -> str:
    """Het doel zelf, of de diepste bestaande ouder ("artikel 9 lid 14" → artikel 9); "" als niets bestaat."""
    while iri and iri not in nodes:
        iri = re.sub(r":[^:]+:[^:]+$", "", iri) if iri.count(":") > 2 else ""
    return iri


async def antwoord(bron_iris: list[str], werkgebied_id: str = "") -> dict:
    """De ketting van één of meer doelen, ontdubbeld, in de vorm van `/samenhang`."""
    fouten: list[dict] = []
    per_bwb: dict[str, list[str]] = {}
    for iri in bron_iris:
        try:
            per_bwb.setdefault(bwb_van({"bron_iri": iri}), []).append(iri)
        except BronFout as exc:
            fouten.append({"bron_iri": iri, "reden": str(exc)})

    knopen: dict[str, AntwoordKnoop] = {}
    relaties: list[AntwoordRelatie] = []
    ingekort = Ingekort()
    doelen: list[str] = []
    getoond_per_bwb: dict[str, dict[str, list[str]]] = {}
    bomen: dict[str, dict] = {}
    alle_nodes: dict[str, dict] = {}
    for bwb, iris in per_bwb.items():
        try:
            snapshot = await graaf.lees_bron({"bron_iri": f"urn:bwb:{bwb}"})
        except BronFout as exc:
            fouten += [{"bron_iri": i, "reden": str(exc)} for i in iris]
            continue
        nodes = store.nodes_van(snapshot)
        bomen[bwb] = snapshot
        alle_nodes.update(nodes)
        getoond = getoond_per_bwb.setdefault(bwb, {})
        kinderen: dict[str, list[str]] = defaultdict(list)
        for n in nodes.values():
            if n.get("parent_iri"):
                kinderen[n["parent_iri"]].append(n["bron_iri"])
        for iri in iris:
            doel = _bestaand_doel(nodes, iri)
            if not doel:
                fouten.append({"bron_iri": iri, "reden": "Bronnode bestaat niet in deze bronstand."})
                continue
            if doel != iri:
                fouten.append({"bron_iri": iri, "reden": "Dit onderdeel bestaat niet; de graaf toont de bepaling erboven."})
            if doel not in doelen:
                doelen.append(doel)
            for ouder in reversed(store.keten(nodes, doel)):
                if ouder not in knopen:
                    knopen[ouder] = AntwoordKnoop.model_validate(bronknoop(nodes[ouder], nodes=nodes).model_dump())
                    if nodes[ouder].get("type") == "Regeling":
                        knopen[ouder].label = citeertitel_van(snapshot) or knopen[ouder].label
                    if p := nodes[ouder].get("parent_iri"):
                        relaties.append(AntwoordRelatie(bron=p, doel=ouder, soort="bevat", groep="structuur"))
            eronder = kinderen.get(doel, [])
            toon = eronder if len(eronder) <= MAX_KINDEREN else []
            if eronder and not toon:
                ingekort.kinderen[doel] = len(eronder)
            for kind in toon:
                if kind not in knopen:
                    knopen[kind] = AntwoordKnoop.model_validate(bronknoop(nodes[kind], nodes=nodes).model_dump())
                    relaties.append(AntwoordRelatie(bron=doel, doel=kind, soort="bevat", groep="structuur"))
            getoond[doel] = [doel, *toon]

    if not doelen:
        return {"schema_versie": 1, "keten": True, "doel": {}, "doelen": [], "snapshot_id": "", "artikel_iri": "", "knopen": [],
                "relaties": [], "verwijzingen_beschikbaar": False, "afgekapt": False, "begrippen_beschikbaar": False,
                "ingekort": ingekort.model_dump(), "fouten": fouten}

    # Markeringen: alleen op wat er staat, met per doel een grens. De klasse draagt de kleur van de knoop.
    elementen = await store.actuele_elementen(alle_nodes)
    per_doel: list[dict] = []
    for tekstnodes in (t for g in getoond_per_bwb.values() for t in g.values()):
        hier = set(tekstnodes)
        raak = [e for e in elementen if e.get("lifecycle") != "rejected" and not e.get("verouderd")
                and hier & {a["bron_iri"] for a in e["ankers"]}]
        if len(raak) > MAX_MARKERINGEN:
            ingekort.markeringen[tekstnodes[0]] = len(raak)
        else:
            per_doel += raak
    uniek = {e["id"]: e for e in per_doel}
    m_knopen, m_relaties = markeringen(list(uniek.values()), set(knopen))
    for k in m_knopen:
        if k.soort == "markering":
            knopen[k.id] = AntwoordKnoop.model_validate(k.model_dump())
    relaties += [AntwoordRelatie.model_validate(r.model_dump()) for r in m_relaties if r.soort == "markeert"]

    # Begrippen. Een haperende graaf verzwijgt niets: dat staat in `begrippen_beschikbaar`.
    begrippen_beschikbaar = True
    b_relaties: list[AntwoordRelatie] = []
    for bwb, getoond in getoond_per_bwb.items():
        try:
            rijen = await _definities(bwb, bomen[bwb]["snapshot_id"])
        except (httpx.HTTPError, ConnectionError, ValueError) as exc:
            logger.warning("definities voor de ketting niet beschikbaar", extra={"fout": type(exc).__name__})
            begrippen_beschikbaar = False
            continue
        b_knopen, rel, bepalingen, te_veel = _wettelijke_begrippen(store.nodes_van(bomen[bwb]), bwb, rijen, getoond)
        ingekort.begrippen += te_veel
        knopen.update({k.id: k for k in b_knopen})
        for iri, k in bepalingen.items():
            knopen.setdefault(iri, k)
        b_relaties += rel
    tekst_per_markering = {f"element:{e['id']}": (a["bron_iri"], e["tekst"]) for e in uniek.values() for a in e["ankers"]
                           if a["bron_iri"] in knopen}
    _naar_kortste_markering(b_relaties, tekst_per_markering)
    relaties += b_relaties

    element_ids = set(uniek)
    if element_ids:
        w_knopen, w_relaties = await (_werkgebied_begrippen(werkgebied_id, element_ids) if werkgebied_id
                                      else _generieke_begrippen(element_ids))
        knopen.update({k.id: k for k in w_knopen})
        relaties += w_relaties

    # Verwijzingen: uitgaand, één stap, vanaf wat er staat. Een tekstuele verwijzing naar een artikel dat niet in de
    # eigen boom staat, is geen knoop maar een telling: het doel is onzeker.
    bepalingen = sorted({i for g in getoond_per_bwb.values() for t in g.values() for i in t})
    beschikbaar = True
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await _select(client, _uitgaand(bepalingen))
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        logger.warning("verwijzingen voor de ketting niet beschikbaar", extra={"fout": type(exc).__name__})
        beschikbaar, rijen = False, []
    afgekapt = len(rijen) > MAX_VERWIJZINGEN
    zeker = []
    for r in rijen[:MAX_VERWIJZINGEN]:
        naar = r.get("naar", "")
        if r.get("betrouwbaarheid") == "laag" and not r.get("label") and naar not in alle_nodes:
            ingekort.onzekere_verwijzingen += 1
        else:
            zeker.append(("uit", r))
    buiten: dict = dict.fromkeys(knopen)     # `verwijzingen` vult aan wat er nog niet is
    v_relaties = verwijzingen(zeker, buiten)
    knopen.update({k: AntwoordKnoop.model_validate(v.model_dump()) for k, v in buiten.items() if v is not None})
    relaties += [AntwoordRelatie.model_validate(r.model_dump()) for r in v_relaties]

    eerste = doelen[0]
    eerste_bwb = next(b for b, g in getoond_per_bwb.items() if eerste in g)
    nodes = store.nodes_van(bomen[eerste_bwb])
    return AntwoordKeten(doel=nodes[eerste], doelen=doelen, snapshot_id=bomen[eerste_bwb]["snapshot_id"],
                         artikel_iri=artikel_van(nodes, eerste), knopen=list(knopen.values()), relaties=relaties,
                         verwijzingen_beschikbaar=beschikbaar, afgekapt=afgekapt,
                         begrippen_beschikbaar=begrippen_beschikbaar, ingekort=ingekort, fouten=fouten).model_dump()
