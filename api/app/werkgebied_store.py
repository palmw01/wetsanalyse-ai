"""Werkgebieden: opslag, revisies en audit (spoor D, levering 1).

Gedeeld tussen analisten, zoals de annotaties. Elke mutatie neemt een rij-lock op het werkgebied
(`SELECT … FOR UPDATE`), toetst `verwachte_revisie` (412 bij een tussentijdse wijziging), hoogt de
revisie op en schrijft een auditregel. Het annotatieslot (`annotatie_v2_state`) wordt niet
geraakt: een werkgebied schrijft geen annotaties.

Archiveren en een bronselectie weghalen zijn soft: een tijdstip, zodat de historie klopt en de
annotaties van de bron onaangeroerd blijven.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import HTTPException
from sqlalchemy import func, insert, select, update

from . import db
from .werkgebied_contracts import (
    BronselectieInvoer, BronselectieWijziging, WerkgebiedInvoer, WerkgebiedWijziging,
)


def _werkgebied(row) -> dict:
    return {"id": row.id, "naam": row.naam, "analysevraag": row.analysevraag,
            "afbakening": row.afbakening, "peildatum": row.peildatum, "status": row.status,
            "revisie": row.revisie, "aangemaakt_door": row.aangemaakt_door,
            "aangemaakt": db.aware(row.aangemaakt).isoformat(),
            "gewijzigd": db.aware(row.gewijzigd).isoformat(),
            "gearchiveerd": db.aware(row.gearchiveerd).isoformat() if row.gearchiveerd else None}


def _selectie(row) -> dict:
    return {"id": row.id, "bron_iri": row.bron_iri, "bereik": row.bereik, "rol": row.rol,
            "reden": row.reden, "label": row.label, "bwb_id": row.bwb_id,
            "snapshot_id": row.snapshot_id, "bron_hash": row.bron_hash,
            "toegevoegd_door": row.toegevoegd_door, "toegevoegd": db.aware(row.toegevoegd).isoformat()}


async def _audit(conn, werkgebied_id: str, actor: str, actie: str, detail: dict) -> None:
    await conn.execute(insert(db.werkgebied_audit).values(
        werkgebied_id=werkgebied_id, actor=actor, actie=actie, detail=detail, tijdstip=db.utcnow()))


@asynccontextmanager
async def _gewijzigd(werkgebied_id: str, verwacht: int, actor: str, actie: str, detail: dict):
    """Rij-lock, revisietoets, revisie +1 en een auditregel: het gemeenschappelijke schrijfpad."""
    t = db.werkgebieden
    async with db.get_engine().begin() as conn:
        row = (await conn.execute(select(t).where(t.c.id == werkgebied_id).with_for_update())).first()
        if row is None or row.gearchiveerd is not None:
            raise HTTPException(404, "Werkgebied bestaat niet.")
        if row.revisie != verwacht:
            raise HTTPException(412, {"fout": "revisie_conflict", "revisie": row.revisie,
                                      "melding": "Iemand anders wijzigde dit werkgebied intussen; laad het opnieuw."})
        yield conn, row
        await conn.execute(update(t).where(t.c.id == werkgebied_id).values(
            revisie=row.revisie + 1, gewijzigd=db.utcnow()))
        await _audit(conn, werkgebied_id, actor, actie, {**detail, "revisie": row.revisie + 1})


async def maak(invoer: WerkgebiedInvoer, actor: str) -> dict:
    nu, wid = db.utcnow(), str(uuid.uuid4())
    async with db.get_engine().begin() as conn:
        await conn.execute(insert(db.werkgebieden).values(
            id=wid, naam=invoer.naam, analysevraag=invoer.analysevraag, afbakening=invoer.afbakening,
            peildatum=invoer.peildatum, status="in_voorbereiding", revisie=1, aangemaakt_door=actor,
            aangemaakt=nu, gewijzigd=nu))
        await _audit(conn, wid, actor, "aangemaakt", {"naam": invoer.naam, "revisie": 1})
    return await haal(wid)


async def lijst(gearchiveerd: bool = False) -> list[dict]:
    t, s = db.werkgebieden, db.werkgebied_bronselecties
    aantal = (select(s.c.werkgebied_id, func.count().label("n")).where(s.c.verwijderd.is_(None))
              .group_by(s.c.werkgebied_id).subquery())
    q = (select(t, func.coalesce(aantal.c.n, 0).label("aantal_bronnen"))
         .outerjoin(aantal, aantal.c.werkgebied_id == t.c.id)
         .where(t.c.gearchiveerd.is_not(None) if gearchiveerd else t.c.gearchiveerd.is_(None))
         .order_by(t.c.gewijzigd.desc(), t.c.id))
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(q)).all()
    return [{**_werkgebied(r), "aantal_bronnen": r.aantal_bronnen} for r in rows]


async def selecties(werkgebied_id: str) -> list[dict]:
    s = db.werkgebied_bronselecties
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(s).where(s.c.werkgebied_id == werkgebied_id,
                                                   s.c.verwijderd.is_(None))
                                   .order_by(s.c.toegevoegd, s.c.id))).all()
    return [_selectie(r) for r in rows]


async def haal(werkgebied_id: str, met_gearchiveerd: bool = False) -> dict:
    t = db.werkgebieden
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(t).where(t.c.id == werkgebied_id))).first()
    if row is None or (row.gearchiveerd is not None and not met_gearchiveerd):
        raise HTTPException(404, "Werkgebied bestaat niet.")
    return {**_werkgebied(row), "bronnen": await selecties(werkgebied_id)}


async def wijzig(werkgebied_id: str, w: WerkgebiedWijziging, actor: str) -> dict:
    velden = {k: (v.value if hasattr(v, "value") else v) for k, v in w.model_dump().items()
              if k in w.model_fields_set and k != "verwachte_revisie"}
    if "naam" in velden and not (velden["naam"] or "").strip():
        raise HTTPException(422, "Naam is verplicht.")
    async with _gewijzigd(werkgebied_id, w.verwachte_revisie, actor, "gewijzigd",
                          {"velden": sorted(velden)}) as (conn, _):
        if velden:
            await conn.execute(update(db.werkgebieden).where(db.werkgebieden.c.id == werkgebied_id)
                               .values(**velden))
    return await haal(werkgebied_id)


async def archiveer(werkgebied_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, verwacht, actor, "gearchiveerd", {}) as (conn, _):
        await conn.execute(update(db.werkgebieden).where(db.werkgebieden.c.id == werkgebied_id)
                           .values(gearchiveerd=db.utcnow()))
    return await haal(werkgebied_id, met_gearchiveerd=True)


async def voeg_bron_toe(werkgebied_id: str, invoer: BronselectieInvoer, bron: dict, actor: str
                        ) -> tuple[dict, bool]:
    """Neemt een geverifieerde bron op. Geeft (selectie, nieuw) terug.

    `bron` komt uit de resolver: {bron_iri, label, bwb_id, snapshot_id, bron_hash}. Staat dezelfde
    bron er al met dezelfde rol en hetzelfde bereik, dan is dit idempotent: de bestaande selectie,
    zonder revisiesprong. Met een andere rol of ander bereik: 409 – wijzig dan de bestaande.
    """
    s = db.werkgebied_bronselecties
    async with db.get_engine().connect() as conn:
        bestaand = (await conn.execute(select(s).where(
            s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == bron["bron_iri"],
            s.c.verwijderd.is_(None)))).first()
    if bestaand is not None:
        if bestaand.rol == invoer.rol.value and bestaand.bereik == invoer.bereik.value:
            return _selectie(bestaand), False
        raise HTTPException(409, {"fout": "al_opgenomen", "selectie": _selectie(bestaand)})
    sid = str(uuid.uuid4())
    async with _gewijzigd(werkgebied_id, invoer.verwachte_revisie, actor, "bron-toegevoegd",
                          {"selectie": sid, "bron_iri": bron["bron_iri"], "rol": invoer.rol.value,
                           "bereik": invoer.bereik.value}) as (conn, _):
        # Opnieuw kijken onder het slot: een gelijktijdige toevoeging van dezelfde bron.
        dubbel = (await conn.execute(select(s.c.id).where(
            s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == bron["bron_iri"],
            s.c.verwijderd.is_(None)))).first()
        if dubbel is not None:
            raise HTTPException(409, {"fout": "al_opgenomen"})
        await conn.execute(insert(s).values(
            id=sid, werkgebied_id=werkgebied_id, bron_iri=bron["bron_iri"], bereik=invoer.bereik.value,
            rol=invoer.rol.value, reden=invoer.reden, label=bron.get("label", ""),
            bwb_id=bron.get("bwb_id", ""), snapshot_id=bron.get("snapshot_id", ""),
            bron_hash=bron.get("bron_hash", ""), toegevoegd_door=actor, toegevoegd=db.utcnow()))
    async with db.get_engine().connect() as conn:
        return _selectie((await conn.execute(select(s).where(s.c.id == sid))).first()), True


async def _selectie_onder_slot(conn, werkgebied_id: str, selectie_id: str):
    s = db.werkgebied_bronselecties
    row = (await conn.execute(select(s).where(s.c.id == selectie_id, s.c.werkgebied_id == werkgebied_id,
                                              s.c.verwijderd.is_(None)))).first()
    if row is None:
        raise HTTPException(404, "Bronselectie bestaat niet.")
    return row


async def wijzig_bron(werkgebied_id: str, selectie_id: str, w: BronselectieWijziging, actor: str) -> dict:
    velden = {k: (v.value if hasattr(v, "value") else v) for k, v in w.model_dump().items()
              if k in w.model_fields_set and k != "verwachte_revisie" and v is not None}
    async with _gewijzigd(werkgebied_id, w.verwachte_revisie, actor, "bron-gewijzigd",
                          {"selectie": selectie_id, "velden": sorted(velden)}) as (conn, _):
        await _selectie_onder_slot(conn, werkgebied_id, selectie_id)
        if velden:
            await conn.execute(update(db.werkgebied_bronselecties)
                               .where(db.werkgebied_bronselecties.c.id == selectie_id).values(**velden))
    return await haal(werkgebied_id)


async def verwijder_bron(werkgebied_id: str, selectie_id: str, verwacht: int, actor: str) -> dict:
    s = db.werkgebied_bronselecties
    async with db.get_engine().connect() as conn:
        bron_iri = (await conn.execute(select(s.c.bron_iri).where(s.c.id == selectie_id))).scalar()
    async with _gewijzigd(werkgebied_id, verwacht, actor, "bron-verwijderd",
                          {"selectie": selectie_id, "bron_iri": bron_iri or ""}) as (conn, _):
        await _selectie_onder_slot(conn, werkgebied_id, selectie_id)
        await conn.execute(update(s).where(s.c.id == selectie_id).values(verwijderd=db.utcnow()))
    return await haal(werkgebied_id)


async def audit(werkgebied_id: str, limit: int = 100) -> list[dict]:
    a = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(a).where(a.c.werkgebied_id == werkgebied_id)
                                   .order_by(a.c.id.desc()).limit(limit))).all()
    return [{"id": r.id, "actor": r.actor, "actie": r.actie, "detail": r.detail,
             "tijdstip": db.aware(r.tijdstip).isoformat()} for r in rows]
