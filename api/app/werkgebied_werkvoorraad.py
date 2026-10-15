"""De annotatie-werkvoorraad van een werkgebied (spoor D, fase B): wat Lex nog moet annoteren.

- Alleen bronselecties met rol `analyseren`; contextbronnen worden geteld, niet meegenomen.
- Per selectie de **annotatie-eenheden** (`bronmodel.annotatie_eenheden`, de regel van de
  keuzekaart: een artikel met leden gaat per lid). Een eenheid die in meer selecties valt, staat er
  één keer.
- Per eenheid de stand, uit Postgres (lagen, elementen, dekking) en zonder de graaf behalve voor de
  bronboom: `afgerond` (elke laag in de subtree geaccordeerd), `te_beoordelen` (voorstellen zonder
  oordeel), `beoordeeld`, `zonder_markeringen` (geannoteerd, niets gevonden) of `nieuw`.
  `te_annoteren` zijn de eenheden die `nieuw` zijn.
- De schatting is de mediaan van het verbruik van de laatste annotatiebeurten van deze gebruiker,
  keer het aantal. Zonder geschiedenis geen getal.
- Een onbereikbare bron maakt de werkvoorraad `volledig: false` met een open punt; nooit stil kleiner.
"""
from __future__ import annotations

from statistics import median

from bronmodel import BronFout, annotatie_eenheden, subtree
from sqlalchemy import select

from . import annotatie_v2_store as store, db, verbruik
from .werkgebied_inventaris import Resolver, bronbomen, bwb_van

SCHATTING_BASIS = 20                    # de laatste n annotatiebeurten
_BEOORDEELD = {"human_approved", "edited"}


def _label(nodes: dict[str, dict], iri: str) -> str:
    """Het pad onder de regeling ('Artikel 9, Lid 1'): een lid alleen zegt in een werkgebied niets."""
    keten = []
    while iri and iri in nodes and nodes[iri].get("parent_iri"):
        keten.append(nodes[iri].get("label") or nodes[iri].get("nummer") or "")
        iri = nodes[iri]["parent_iri"]
    return ", ".join(x for x in reversed(keten) if x)


def _regeling(nodes: dict[str, dict], iri: str) -> str:
    while nodes.get(iri, {}).get("parent_iri"):
        iri = nodes[iri]["parent_iri"]
    return nodes.get(iri, {}).get("label", "")


async def _annotatiestaat() -> tuple[dict[str, dict], list[dict], list[dict], dict[str, dict]]:
    async with store.leestransactie() as conn:
        lagen = {r["bron_iri"]: dict(r) for r in
                 (await conn.execute(select(db.annotatie_v2_lagen))).mappings().all()}
        elementen = list((await conn.execute(select(db.annotatie_v2_elementen.c.inhoud))).scalars().all())
        dekking = [dict(r) for r in (await conn.execute(select(db.annotatie_v2_dekking))).mappings().all()]
        snapshots = {r.id: r.inhoud for r in (await conn.execute(select(db.annotatie_v2_snapshots))).all()}
    return lagen, elementen, dekking, snapshots


def _gedekt(dekking: list[dict], snapshots: dict[str, dict], nodes: dict[str, dict]) -> set[str]:
    """De bronnodes die een annotatiebeurt over déze tekst bereikte, ook als hij niets vond."""
    uit: set[str] = set()
    for row in dekking:
        oud = snapshots.get(row["snapshot_id"])
        if oud is None:
            continue
        oude = store.nodes_van(oud)
        uit.update(i for i in row["inhoud"].get("bereik", [])
                   if i in nodes and i in oude and oude[i]["bron_hash"] == nodes[i]["bron_hash"])
    return uit


def _stand(bereik: set[str], lagen: dict[str, dict], elementen: list[dict], gedekt: set[str]) -> dict:
    eigen = [e for e in elementen if e.get("eigenaar_iri") in bereik]
    te_beoordelen = sum(1 for e in eigen if e.get("lifecycle") not in _BEOORDEELD | {"rejected"})
    eigen_lagen = [lagen[i] for i in bereik if i in lagen]
    if eigen_lagen and all(laag["status"] == "geaccordeerd" for laag in eigen_lagen):
        status = "afgerond"
    elif te_beoordelen:
        status = "te_beoordelen"
    elif eigen:
        status = "beoordeeld"
    elif eigen_lagen or bereik & gedekt:
        status = "zonder_markeringen"
    else:
        status = "nieuw"
    return {"status": status, "voorstellen": len(eigen), "te_beoordelen": te_beoordelen}


async def schatting(userid: str) -> dict | None:
    """Mediaan van het verbruik van de laatste annotatiebeurten van `userid`, per bepaling.

    Een annotatiebeurt is een run waarvan het bericht een annotatie-artefact draagt (of, van vóór de
    artefacten, een `annotatie_doel`). Een reeks boekt per onderdeel een eigen run, dus elk lid telt.
    """
    k = db.token_verbruik.c
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(
            select(k.run_id, k.invoer + k.uitvoer + k.cache_lees + k.cache_schrijf)
            .where(k.userid == (userid or "").strip().lower(), k.bron == "agent", k.run_id.is_not(None))
            .order_by(k.id.desc()).limit(SCHATTING_BASIS * 10))).all()
        run_ids = [r[0] for r in rijen if r[0]]
        if not run_ids:
            return None
        b = db.gesprek_berichten.c
        berichten = (await conn.execute(
            select(b.run_id, b.inhoud).where(b.run_id.in_(run_ids)))).all()
    annotatie = {run for run, inhoud in berichten
                 if ((inhoud or {}).get("artefact") or {}).get("soort") == "annotatie"
                 or (inhoud or {}).get("annotatie_doel")}
    verbruikt = [totaal for run, totaal in rijen if run in annotatie][:SCHATTING_BASIS]
    if not verbruikt:
        return None
    return {"per_bepaling": int(median(verbruikt)), "basis": len(verbruikt)}


async def werkvoorraad(selecties: list[dict], resolve: Resolver, userid: str) -> dict:
    analyse = [s for s in selecties if s["rol"] == "analyseren"]
    per_bwb, fouten = await bronbomen(analyse, resolve)
    lagen, elementen, dekking, snapshots = await _annotatiestaat()
    alle_nodes = {i: n for snap in per_bwb.values() for i, n in store.nodes_van(snap).items()}
    gedekt = _gedekt(dekking, snapshots, alle_nodes)

    eenheden: dict[str, dict] = {}
    samenvatting, open_punten = [], []
    for sel in analyse:
        regel = {"id": sel["id"], "bron_iri": sel["bron_iri"], "label": sel["label"],
                 "bereik": sel["bereik"], "eenheden": 0, "per_stand": {}, "onbereikbaar": None}
        samenvatting.append(regel)
        snap = per_bwb.get(bwb_van(sel))
        try:
            if snap is None:
                raise BronFout(fouten.get(bwb_van(sel), "Bron niet beschikbaar."))
            lijst = snap["nodes"] if isinstance(snap["nodes"], list) else list(snap["nodes"].values())
            iris = annotatie_eenheden(lijst, sel["bron_iri"], onderliggend=sel["bereik"] == "onderliggend")
        except BronFout as exc:
            regel["onbereikbaar"] = str(exc) if snap is None else \
                "De bepaling staat niet (meer) in de actuele bronstand."
            open_punten.append(f"{sel['label'] or sel['bron_iri']}: {regel['onbereikbaar']}")
            continue
        nodes = store.nodes_van(snap)
        for iri in iris:
            if iri not in eenheden:
                bereik = {n["bron_iri"] for n in subtree(lijst, iri)}
                eenheden[iri] = {"bron_iri": iri, "label": _label(nodes, iri),
                                 "regeling": _regeling(nodes, iri), "bwb_id": bwb_van(sel),
                                 "stand": _stand(bereik, lagen, elementen, gedekt), "selecties": []}
            eenheden[iri]["selecties"].append(sel["id"])
            status = eenheden[iri]["stand"]["status"]
            regel["eenheden"] += 1
            regel["per_stand"][status] = regel["per_stand"].get(status, 0) + 1

    te_annoteren = [e["bron_iri"] for e in eenheden.values() if e["stand"]["status"] == "nieuw"]
    schat = await schatting(userid)
    stand = await verbruik.stand(userid)
    return {
        "selecties": samenvatting,
        "eenheden": list(eenheden.values()),
        "te_annoteren": te_annoteren,
        "context_niet_meegenomen": sum(1 for s in selecties if s["rol"] != "analyseren"),
        "volledig": not open_punten,
        "open_punten": open_punten,
        "schatting": {**schat, "totaal": schat["per_bepaling"] * len(te_annoteren)} if schat else None,
        "schatting_toelichting": (
            f"Mediaan van je laatste {schat['basis']} annotatiebeurten, keer het aantal bepalingen."
            if schat else "Nog geen annotatiebeurten van jou om een schatting op te baseren."),
        "budget": {"resterend": stand.resterend, "budget": stand.budget, "actief": stand.actief,
                   "geblokkeerd": stand.geblokkeerd},
    }
