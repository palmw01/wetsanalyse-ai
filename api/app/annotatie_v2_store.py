"""Atomische node-lagen. PostgreSQL is waarheid; RDF is een herbouwbare projectie.

Een database-slot serialiseert de kleine schrijftransacties, ook over API-processen.
Dit voorkomt gedeeltelijke batches en eigenaarverplaatsingen; geen process-local locks.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from bronmodel import BronFout, valideer_ankers

from . import db
from .annotatie_v2_contracts import Batch, Beslissing, Element
from .validation import GELDIGE_JAS_KLASSEN


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def nodes_van(snapshot: dict) -> dict[str, dict]:
    nodes = snapshot["nodes"]
    return nodes if isinstance(nodes, dict) else {n["bron_iri"]: n for n in nodes}


def keten(nodes: dict, iri: str) -> list[str]:
    chain: list[str] = []
    while iri:
        if iri not in nodes or iri in chain:
            raise HTTPException(422, "Onvolledige of cyclische bronstructuur.")
        chain.append(iri)
        iri = nodes[iri].get("parent_iri") or ""
    return chain


def bereik_van(snapshot: dict, iri: str | None = None) -> set[str]:
    nodes = nodes_van(snapshot)
    iri = iri or snapshot["doel"]["bron_iri"]
    if iri not in nodes:
        raise HTTPException(404, "Bronnode bestaat niet in deze bronstand.")
    return {key for key in nodes if iri in keten(nodes, key)}


def valideer(element: Element, snapshot: dict, scope: set[str]) -> dict:
    if element.klasse not in GELDIGE_JAS_KLASSEN or not element.tekst.strip():
        raise HTTPException(422, "Ongeldige klasse of leeg fragment.")
    nodes = nodes_van(snapshot)
    seen = set()
    for anker in element.ankers:
        if anker.bron_iri not in scope:
            raise HTTPException(422, "Anker valt buiten het gevraagde bereik.")
        node = nodes[anker.bron_iri]
        if (anker.eind <= anker.start or anker.eind > len(node.get("tekst", ""))
                or node.get("bron_hash") != anker.bron_hash
                or node.get("tekst", "")[anker.start:anker.eind] != anker.tekst):
            raise HTTPException(422, "Anker komt niet overeen met de actuele brontekst.")
        key = (anker.bron_iri, anker.start, anker.eind)
        if key in seen:
            raise HTTPException(422, "Dubbel anker.")
        seen.add(key)
    if element.tekst != " ".join(a.tekst for a in element.ankers):
        raise HTTPException(422, "Elementtekst moet de ankerfragmenten in volgorde bevatten.")
    try:
        owner = valideer_ankers(snapshot, [a.model_dump() for a in element.ankers])
    except BronFout as exc:
        raise HTTPException(422, str(exc)) from exc
    result = element.model_dump(mode="json")
    result.update(eigenaar_iri=owner, snapshot_id=snapshot["snapshot_id"])
    return result


@asynccontextmanager
async def schrijftransactie():
    # Elke laagwijziging loopt via `_raak`, die de laag hier noteert. Pas ná een geslaagde commit gaan
    # die lagen naar de graaf; bij een fout (ook een 409/412) komt de regel eronder nooit aan de beurt.
    te_projecteren: set[str] = set()
    async with db.get_engine().begin() as conn:
        conn.info["te_projecteren"] = te_projecteren
        try:
            try:
                async with conn.begin_nested():
                    await conn.execute(insert(db.annotatie_v2_state).values(id=1, revisie=0))
            except IntegrityError:
                pass
            await conn.execute(select(db.annotatie_v2_state).where(
                db.annotatie_v2_state.c.id == 1).with_for_update())
            yield conn
        finally:
            conn.info.pop("te_projecteren", None)
    from .graaf_projectie_v2 import na_mutatie
    na_mutatie(sorted(te_projecteren))


@asynccontextmanager
async def leestransactie():
    async with db.get_engine().connect() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execution_options(isolation_level="REPEATABLE READ")
        async with conn.begin():
            yield conn


async def _audit(conn, actor: str, actie: str, detail: dict, element_id: str | None = None):
    await conn.execute(insert(db.annotatie_v2_audit).values(
        actor=actor, actie=actie, detail=detail, element_id=element_id, tijdstip=db.utcnow()))


async def _lagen(conn) -> dict[str, dict]:
    rows = (await conn.execute(select(db.annotatie_v2_lagen))).mappings().all()
    return {r["bron_iri"]: dict(r) for r in rows}


def publiek_laag(layer: dict) -> dict:
    return {k: v for k, v in layer.items() if k != "updated"}


async def _bewaar_snapshot(conn, snapshot: dict):
    table = db.annotatie_v2_snapshots
    if not (await conn.execute(select(table.c.id).where(table.c.id == snapshot["snapshot_id"]))).first():
        await conn.execute(insert(table).values(id=snapshot["snapshot_id"], inhoud=snapshot))


async def _laag(conn, layers: dict, iri: str, snapshot_id: str, expected: dict) -> dict:
    layer = layers.get(iri)
    revision = layer["revisie"] if layer else 0
    if expected.get(iri, 0) != revision:
        raise HTTPException(412, {"fout": "revisie_conflict", "bron_iri": iri, "revisie": revision})
    if layer and layer["status"] != "in_review":
        raise HTTPException(409, "Heropen de laag voordat je haar wijzigt.")
    if layer is None:
        layer = dict(id=uuid.uuid4().hex, bron_iri=iri, revisie=0, status="in_review",
                     snapshot_id=snapshot_id, geprojecteerd_revisie=0, updated=db.utcnow())
        await conn.execute(insert(db.annotatie_v2_lagen).values(**layer))
        layers[iri] = layer
    return layer


async def _raak(conn, layer: dict, snapshot_id: str):
    layer.update(revisie=layer["revisie"] + 1, snapshot_id=snapshot_id, updated=db.utcnow())
    conn.info.get("te_projecteren", set()).add(layer["id"])
    await conn.execute(update(db.annotatie_v2_lagen).where(
        db.annotatie_v2_lagen.c.id == layer["id"]).values(**layer))
    await conn.execute(update(db.annotatie_v2_state).where(db.annotatie_v2_state.c.id == 1).values(
        revisie=db.annotatie_v2_state.c.revisie + 1))


async def batch(req: Batch, snapshot: dict, actor: str, *, mens: bool = False) -> dict:
    fingerprint = digest({"request": req.model_dump(mode="json"), "actor": actor, "mens": mens})
    async with schrijftransactie() as conn:
        cached = (await conn.execute(select(db.annotatie_v2_batches).where(
            db.annotatie_v2_batches.c.id == req.batch_id))).mappings().first()
        if cached:
            if cached["payload_hash"] != fingerprint:
                raise HTTPException(409, "Batch-ID is al gebruikt voor andere inhoud of gebruiker.")
            return cached["antwoord"]
        if req.snapshot_id != snapshot["snapshot_id"]:
            raise HTTPException(409, "Bronstand gewijzigd; laad het bereik opnieuw.")
        scope = bereik_van(snapshot)
        values = [valideer(e, snapshot, scope) for e in req.elementen]
        if not set(req.dekking.bereik) <= scope:
            raise HTTPException(422, "Dekking valt buiten het gevraagde bereik.")
        if req.dekking.voltooid:
            text_nodes = {i for i in scope if nodes_van(snapshot)[i].get("tekst")}
            if not text_nodes <= set(req.dekking.bereik):
                raise HTTPException(422, "Voltooide dekking mist tekstsegmenten.")
            if len(text_nodes) > 1 and not req.dekking.parent_context:
                raise HTTPException(422, "Volledige ouderdekking vereist analyse van de oudercontext.")
        await _bewaar_snapshot(conn, snapshot)
        layers = await _lagen(conn)
        touched = {}
        all_elements = (await conn.execute(select(db.annotatie_v2_elementen))).mappings().all()
        current = {r["id"]: r["inhoud"] for r in all_elements}
        # Een nieuwe brontekst heropent de getroffen laag, maar wist nooit het oude oordeel.
        changed_owners = {e["eigenaar_iri"] for e in current.values() if not e.get("verouderd") and any(
            a["bron_iri"] in scope and nodes_van(snapshot)[a["bron_iri"]]["bron_hash"] != a["bron_hash"]
            for a in e["ankers"])}
        for iri in changed_owners:
            layer = layers.get(iri)
            if layer and layer["status"] != "in_review":
                if req.verwachte_revisies.get(iri, 0) != layer["revisie"]:
                    raise HTTPException(412, "Laag is intussen gewijzigd.")
                layer["status"] = "in_review"
                await _audit(conn, actor, "laag-bron-gewijzigd", {"laag_id": layer["id"], "snapshot_id": req.snapshot_id})
        # Iedere volledig behandelde tekstnode krijgt ook zonder gevonden elementen een laag.
        reuse = req.run.get("modus") == "hergebruik" and not values
        if reuse and not (await dekking(snapshot, conn))["voltooid"]:
            raise HTTPException(409, "Dit bereik is nog niet volledig geannoteerd.")
        # Dekkingsregistratie is geen inhoudswijziging: een ouderanalyse mag afgeronde,
        # ongewijzigde kindlagen hergebruiken zonder hun status/revisie aan te raken.
        existing_keys = {digest({"klasse": e["klasse"], "ankers": e["ankers"]})
                         for e in current.values() if not e.get("verouderd")}
        owners = set() if reuse else ({v["eigenaar_iri"] for v in values
            if digest({"klasse": v["klasse"], "ankers": v["ankers"]}) not in existing_keys}
            | {i for i in req.dekking.bereik if i not in layers} | changed_owners)
        for iri in sorted(owners):
            touched[iri] = await _laag(conn, layers, iri, req.snapshot_id, req.verwachte_revisies)
        # Verouder alleen werkelijk gewijzigde bronankers; oordelen blijven als historie staan.
        for old in current.values():
            if reuse or old.get("verouderd") or not any(a["bron_iri"] in scope for a in old["ankers"]):
                continue
            if any(a["bron_iri"] in scope and nodes_van(snapshot)[a["bron_iri"]]["bron_hash"] != a["bron_hash"]
                   for a in old["ankers"]):
                owner = old["eigenaar_iri"]
                if owner not in touched:
                    touched[owner] = await _laag(conn, layers, owner, req.snapshot_id, req.verwachte_revisies)
                old["verouderd"] = True
                await conn.execute(update(db.annotatie_v2_elementen).where(
                    db.annotatie_v2_elementen.c.id == old["id"]).values(inhoud=old))
                await _audit(conn, actor, "bron-gewijzigd", {"snapshot_id": req.snapshot_id}, old["id"])
        saved = []
        for value in values:
            # Canonieke ankers onderscheiden identieke woorden op verschillende plekken.
            key = digest({"klasse": value["klasse"], "ankers": value["ankers"]})
            existing = next((x for x in current.values() if not x.get("verouderd")
                             and digest({"klasse": x["klasse"], "ankers": x["ankers"]}) == key), None)
            if existing:
                saved.append(existing)
                continue  # nooit menselijke historie of afwijzingen met agentwerk overschrijven
            element_id = value["id"] or uuid.uuid4().hex
            if element_id in current:
                raise HTTPException(409, "Element-ID bestaat al; gebruik de correctieroute.")
            value.update(id=element_id, laag_id=touched[value["eigenaar_iri"]]["id"],
                         lifecycle="human_approved" if mens else "voorgesteld", herkomst="mens" if mens else "agent",
                         aangemaakt_door=actor, beslissingen=[], verouderd=False, geproduceerd_door=req.run)
            await conn.execute(insert(db.annotatie_v2_elementen).values(
                id=element_id, laag_id=value["laag_id"], inhoud=value))
            await _audit(conn, actor, "element-gemaakt", {"batch_id": req.batch_id}, element_id)
            current[element_id] = value
            saved.append(value)
        for layer in touched.values():
            await _raak(conn, layer, req.snapshot_id)
        if req.dekking.voltooid:
            await conn.execute(insert(db.annotatie_v2_dekking).values(id=uuid.uuid4().hex,
                bron_iri=snapshot["doel"]["bron_iri"], snapshot_id=req.snapshot_id,
                inhoud={**req.dekking.model_dump(), "run": req.run, "batch_id": req.batch_id,
                        "tijd": db.utcnow().isoformat()}))
        result = {"schema_versie": 2, "batch_id": req.batch_id, "doel": snapshot["doel"],
                  "annotatie_doel": {**snapshot["doel"], "snapshot_id": req.snapshot_id},
                  "snapshot_id": req.snapshot_id, "lagen": [publiek_laag(x) for x in touched.values()],
                  "elementen": saved}
        await _audit(conn, actor, "batch", {"batch_id": req.batch_id,
            "bron_iri": snapshot["doel"]["bron_iri"], "run": req.run, "dekking": req.dekking.model_dump()})
        await conn.execute(insert(db.annotatie_v2_batches).values(
            id=req.batch_id, payload_hash=fingerprint, antwoord=result))
        return result


async def dekking(snapshot: dict, conn=None) -> dict:
    if conn is None:
        async with db.get_engine().connect() as connection:
            return await dekking(snapshot, connection)
    rows = (await conn.execute(select(db.annotatie_v2_dekking))).mappings().all()
    snapshots = {r.id: r.inhoud for r in (await conn.execute(select(db.annotatie_v2_snapshots))).all()}
    target = snapshot["doel"]["bron_iri"]
    scope = bereik_van(snapshot)
    nodes = nodes_van(snapshot)
    covered: set[str] = set()
    complete = False
    parent_context = False
    # Per bronnode de recentste structurele meting die nog over déze tekst gaat (zelfde hash): een
    # oudere meting wijst met haar offsets naar een tekst die er niet meer staat.
    structureel: dict[str, tuple[str, dict]] = {}
    def signature(tree: dict, keys: set[str]):
        return {i: (tree[i].get("parent_iri"), tree[i]["bron_hash"]) for i in keys}
    for row in rows:
        old_snapshot = snapshots.get(row["snapshot_id"])
        if old_snapshot is None:
            continue
        old = nodes_van(old_snapshot)
        reached = set(row["inhoud"].get("bereik", []))
        tijd = str(row["inhoud"].get("tijd", ""))
        for iri, meting in (row["inhoud"].get("structureel") or {}).items():
            if (iri in scope and iri in old and old[iri]["bron_hash"] == nodes[iri]["bron_hash"]
                    and tijd >= structureel.get(iri, ("", {}))[0]):
                structureel[iri] = (tijd, meting)
        covered.update(i for i in reached & scope if i in old
                       and old[i]["bron_hash"] == nodes[i]["bron_hash"]
                       and old[i].get("parent_iri") == nodes[i].get("parent_iri"))
        if target not in old or row["bron_iri"] not in old:
            continue
        if target not in bereik_van(old_snapshot, row["bron_iri"]):
            continue
        old_scope = bereik_van(old_snapshot, target)
        same = signature(old, old_scope) == signature(nodes, scope)
        text_nodes = {i for i in scope if nodes[i].get("tekst")}
        context = len(text_nodes) <= 1 or row["inhoud"].get("parent_context", False)
        if same and text_nodes <= reached and context:
            complete, parent_context = True, True
    return {"status": "ok", "doel": snapshot["doel"], "snapshot_id": snapshot["snapshot_id"],
            "voltooid": complete, "bereik": sorted(covered), "parent_context": parent_context,
            "structureel": {iri: m for iri, (_t, m) in sorted(structureel.items())}}


async def weergave(snapshot: dict) -> dict:
    scope = bereik_van(snapshot)
    nodes = nodes_van(snapshot)
    async with leestransactie() as conn:
        layers = await _lagen(conn)
        rows = (await conn.execute(select(db.annotatie_v2_elementen))).mappings().all()
        elements, refs = [], []
        for row in rows:
            value = dict(row["inhoud"])
            anchor_ids = {a["bron_iri"] for a in value["ankers"]}
            value["verouderd"] = value.get("verouderd", False) or any(
                a["bron_iri"] in nodes and nodes[a["bron_iri"]]["bron_hash"] != a["bron_hash"]
                for a in value["ankers"])
            if value["eigenaar_iri"] in scope:
                elements.append(value)
            elif anchor_ids & scope:
                refs.append({"id": value["id"], "eigenaar_iri": value["eigenaar_iri"],
                             "klasse": value["klasse"], "label": "Onderdeel van een ruimere annotatie",
                             "detail_url": f"/v1/annotatie/elementen/{value['id']}"})
        return {"schema_versie": 2, "doel": snapshot["doel"], "snapshot_id": snapshot["snapshot_id"],
                "segmenten": [n for n in nodes.values() if n["bron_iri"] in scope and n.get("tekst")],
                "lagen": [publiek_laag(l) for i, l in layers.items() if i in scope],
                "elementen": elements, "verwijzingen": refs, "dekking": await dekking(snapshot, conn)}


async def detail(element_id: str) -> dict:
    async with db.get_engine().connect() as conn:
        e, l = db.annotatie_v2_elementen, db.annotatie_v2_lagen
        row = (await conn.execute(select(e.c.inhoud, l).join_from(e, l, e.c.laag_id == l.c.id).where(
            e.c.id == element_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Element niet gevonden.")
        layer = {key: row[key] for key in l.c.keys()}
        source = (await conn.execute(select(db.annotatie_v2_snapshots.c.inhoud).where(
            db.annotatie_v2_snapshots.c.id == row["inhoud"]["snapshot_id"]))).scalar_one()
        anchor_ids = {a["bron_iri"] for a in row["inhoud"]["ankers"]}
        return {"status": "ok", "element": row["inhoud"], "laag": publiek_laag(layer),
                "snapshot_id": row["inhoud"]["snapshot_id"],
                "bronnen": [n for i, n in nodes_van(source).items() if i in anchor_ids],
                "bronverwijzing": {"bron_iri": row["inhoud"]["eigenaar_iri"]}}


async def historische_snapshot(snapshot_id: str) -> dict:
    async with db.get_engine().connect() as conn:
        snapshot = (await conn.execute(select(db.annotatie_v2_snapshots.c.inhoud).where(
            db.annotatie_v2_snapshots.c.id == snapshot_id))).scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(404, "Opgeslagen bronversie niet gevonden.")
        return snapshot


async def beslis(element_id: str, req: Beslissing, snapshot: dict, actor: str) -> dict:
    if req.snapshot_id != snapshot["snapshot_id"]:
        raise HTTPException(409, "Bronstand gewijzigd.")
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(db.annotatie_v2_elementen).where(
            db.annotatie_v2_elementen.c.id == element_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Element niet gevonden.")
        old = row["inhoud"]
        nodes = nodes_van(snapshot)
        if old.get("verouderd") or any(a["bron_iri"] not in nodes or
            nodes[a["bron_iri"]]["bron_hash"] != a["bron_hash"] for a in old["ankers"]):
            raise HTTPException(409, "Verouderd element is alleen-lezen.")
        layers = await _lagen(conn)
        old_layer = await _laag(conn, layers, old["eigenaar_iri"], req.snapshot_id, req.verwachte_revisies)
        frozen = old["lifecycle"] in {"human_approved", "rejected", "published"} and (
            old.get("herkomst") != "mens" or bool(old.get("beslissingen")))
        if frozen and req.type not in {"heropen", "comment"}:
            raise HTTPException(409, "Heropen het element voordat je het wijzigt.")
        value = dict(old)
        touched = {old["eigenaar_iri"]: old_layer}
        if req.type == "edit":
            allowed = {"klasse", "tekst", "toelichting", "ankers"}
            if set(req.wijziging) - allowed:
                raise HTTPException(422, "Niet-toegestane correctievelden.")
            candidate = Element.model_validate({**old, **req.wijziging})
            value.update(valideer(candidate, snapshot, set(nodes)))
            owner = value["eigenaar_iri"]
            if owner not in touched:
                touched[owner] = await _laag(conn, layers, owner, req.snapshot_id, req.verwachte_revisies)
            value.update(laag_id=touched[owner]["id"], lifecycle="edited", gewijzigd_door="mens")
        elif req.type != "comment":
            value["lifecycle"] = {"approve": "human_approved", "reject": "rejected", "heropen": "voorgesteld"}[req.type]
        decision = {"type": req.type, "actor": actor, "tijd": db.utcnow().isoformat(),
                    "comment": req.comment, "review_reason": req.review_reason, "wijziging": req.wijziging}
        value["beslissingen"] = [*old.get("beslissingen", []), decision]
        await _bewaar_snapshot(conn, snapshot)
        await conn.execute(update(db.annotatie_v2_elementen).where(
            db.annotatie_v2_elementen.c.id == element_id).values(laag_id=value["laag_id"], inhoud=value))
        for layer in touched.values():
            await _raak(conn, layer, req.snapshot_id)
        await _audit(conn, actor, req.type, {**decision, "oude_eigenaar": old["eigenaar_iri"],
                                           "nieuwe_eigenaar": value["eigenaar_iri"]}, element_id)
        return {"element": value, "lagen": [publiek_laag(l) for l in touched.values()]}


async def laag_detail(laag_id: str) -> dict:
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(db.annotatie_v2_lagen).where(
            db.annotatie_v2_lagen.c.id == laag_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Laag niet gevonden.")
        return dict(row)


async def zet_status(laag_id: str, status: str, expected: int, actor: str, snapshot: dict | None = None) -> dict:
    if status not in {"in_review", "geaccordeerd"}:
        raise HTTPException(422, "Onbekende laagstatus.")
    async with schrijftransactie() as conn:
        layer = next((l for l in (await _lagen(conn)).values() if l["id"] == laag_id), None)
        if layer is None:
            raise HTTPException(404, "Laag niet gevonden.")
        if layer["revisie"] != expected:
            raise HTTPException(412, "Laag is intussen gewijzigd.")
        elements = (await conn.execute(select(db.annotatie_v2_elementen.c.inhoud).where(
            db.annotatie_v2_elementen.c.laag_id == laag_id))).scalars().all()
        if status == "geaccordeerd" and snapshot is not None:
            nodes = nodes_van(snapshot)
            if any(not e.get("verouderd") and any(a["bron_iri"] not in nodes or
                nodes[a["bron_iri"]]["bron_hash"] != a["bron_hash"] for a in e["ankers"]) for e in elements):
                raise HTTPException(409, "Brontekst gewijzigd; annoteer de actuele bron vóór afronden.")
        if status == "geaccordeerd" and any(not e.get("verouderd") and e["lifecycle"] not in
            {"human_approved", "rejected", "published"} for e in elements):
            raise HTTPException(409, "Beoordeel eerst alle actuele elementen van deze laag.")
        layer["status"] = status
        await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "laag-status", {"laag_id": laag_id, "status": status})
        return publiek_laag(layer)


async def verwijder(element_id: str, expected: int, actor: str) -> dict:
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(db.annotatie_v2_elementen).where(
            db.annotatie_v2_elementen.c.id == element_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Element niet gevonden.")
        value = row["inhoud"]
        if value["herkomst"] != "mens" or value.get("aangemaakt_door") != actor or value.get("beslissingen"):
            raise HTTPException(409, "Alleen een eigen, nog niet beoordeelde markering kan worden verwijderd.")
        layers = await _lagen(conn)
        layer = await _laag(conn, layers, value["eigenaar_iri"], value["snapshot_id"],
                            {value["eigenaar_iri"]: expected})
        await conn.execute(delete(db.annotatie_v2_elementen).where(db.annotatie_v2_elementen.c.id == element_id))
        await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "element-verwijderd", {"element": value}, element_id)
        return {"verwijderd": element_id, "laag": publiek_laag(layer)}


async def overzicht(actor: str | None, bwb_id: str, limit: int, offset: int) -> list[dict]:
    from collections import Counter
    async with leestransactie() as conn:
        layers = await _lagen(conn)
        elements = (await conn.execute(select(db.annotatie_v2_elementen.c.inhoud))).scalars().all()
        snapshots = {r.id: r.inhoud for r in (await conn.execute(select(db.annotatie_v2_snapshots))).all()}
        results = []
        for layer in sorted(layers.values(), key=lambda l: l["updated"], reverse=True):
            snapshot = snapshots[layer["snapshot_id"]]
            nodes = nodes_van(snapshot)
            node = nodes[layer["bron_iri"]]
            lineage = [nodes[i] for i in keten(nodes, layer["bron_iri"])]
            article = next((n.get("nummer", "") for n in lineage if n["type"] in {"Artikel", "Divisie"}), "")
            lid = next((n.get("nummer", "") for n in lineage if n["type"] == "Lid"), "")
            law = node.get("bwb_id") or snapshot.get("bwb_id") or snapshot["doel"].get("bwb_id", "")
            if bwb_id and law != bwb_id:
                continue
            local = [e for e in elements if e["laag_id"] == layer["id"]]
            if actor and not any(e.get("aangemaakt_door") == actor or
                any(b.get("actor") == actor for b in e.get("beslissingen", [])) for e in local):
                continue
            current = [e for e in local if not e.get("verouderd")]
            results.append({**publiek_laag(layer), "slug": layer["id"], "bwbId": law,
                "artikel": article, "lid": lid, "label": node.get("label", ""), "soort": node["type"],
                "citeertitel": node.get("citeertitel") or snapshot["doel"].get("citeertitel") or law,
                "werkgebied": "", "aantal_elementen": len(current), "te_beoordelen": sum(
                    e["lifecycle"] not in {"human_approved", "rejected", "published"} for e in current),
                "per_klasse": dict(Counter(e["klasse"] for e in current)),
                "per_aandacht": dict(Counter(e.get("aandacht") for e in current if e.get("aandacht"))),
                "laatste_model": "", "laag_sleutel": layer["bron_iri"], "verouderd": len(local) - len(current),
                "updated": db.aware(layer["updated"]).isoformat()})
        return results[offset:offset + limit]


async def audit_weergave(view: dict) -> list[dict]:
    ids = {e["id"] for e in view["elementen"]}
    layer_ids = {l["id"] for l in view["lagen"]}
    scope = {s["bron_iri"] for s in view["segmenten"]} | {view["doel"]["bron_iri"]}
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(db.annotatie_v2_audit).order_by(db.annotatie_v2_audit.c.id))).mappings().all()
        return [{**dict(r), "tijdstip": db.aware(r["tijdstip"]).isoformat()} for r in rows
                if r["element_id"] in ids or (r["element_id"] is None and (
                    r["detail"].get("laag_id") in layer_ids or r["detail"].get("bron_iri") in scope))]
