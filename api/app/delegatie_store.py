"""Delegaties (ADR-016 §A5, ADR-012): één lopende per gebruiker, en een regie hoogstens één per werkgebied.

Het slot is een partiële unieke index op `status = 'loopt'`, geen check-then-insert: twee api-replica's kunnen
tegelijk een start krijgen. Een delegatie die `VERWEESD_NA` geen hartslag gaf (graph-qa herstartte, een replica viel
om), telt als `mislukt`. Bij een nieuwe start wordt hij eerst zo vastgelegd, anders zou een verweesde delegatie het
werkgebied of de gebruiker voor altijd blokkeren. Alleen de eigenaar wijzigt zijn delegatie; een afgeronde delegatie
verandert niet meer."""
from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import db
from .delegatie_contracts import EINDSTANDEN, Delegatie, DelegatieStart, DelegatieWijziging

VERWEESD_NA = timedelta(minutes=3)


def _delegatie(row) -> Delegatie:
    d = dict(row._mapping)
    status = d["status"]
    if status == "loopt" and db.utcnow() - db.aware(d["hartslag"]) > VERWEESD_NA:
        status = "mislukt"
    return Delegatie(**{**d, "status": status, "gestart": db.aware(d["gestart"]),
                        "hartslag": db.aware(d["hartslag"]), "afgerond": db.aware(d["afgerond"])})


def _slot(werkgebied_id: str, user_id: str):
    """Wie het slot van deze start kan hebben: een delegatie van dezelfde gebruiker, of een regie in dit werkgebied."""
    t = db.delegaties
    regie_hier = and_(t.c.soort == "regie", t.c.werkgebied_id == werkgebied_id) if werkgebied_id else None
    return or_(t.c.user_id == user_id, regie_hier) if regie_hier is not None else t.c.user_id == user_id


async def _werkgebied_bestaat(conn, werkgebied_id: str) -> None:
    t = db.werkgebieden
    if (await conn.execute(select(t.c.id).where(t.c.id == werkgebied_id))).first() is None:
        raise HTTPException(404, f"Onbekend werkgebied: {werkgebied_id}")


async def _sluit_verweesde(conn, werkgebied_id: str, user_id: str) -> None:
    t = db.delegaties
    grens = db.utcnow() - VERWEESD_NA
    await conn.execute(
        update(t).where(t.c.status == "loopt", t.c.hartslag < grens, _slot(werkgebied_id, user_id))
        .values(status="mislukt", afgerond=db.utcnow(), uitkomst={"reden": "verweesd"}))


async def _lopende(conn, werkgebied_id: str, user_id: str) -> Delegatie | None:
    t = db.delegaties
    row = (await conn.execute(select(t).where(t.c.status == "loopt", _slot(werkgebied_id, user_id)))).first()
    return _delegatie(row) if row is not None else None


async def start(user_id: str, inv: DelegatieStart) -> Delegatie:
    """Een nieuwe delegatie, of 409 `delegatie_loopt_al` met de delegatie die het slot heeft (een regie in dit
    werkgebied, of een delegatie van dezelfde gebruiker). Het gesprek is van de gebruiker en hoort bij het
    werkgebied van de delegatie (leeg bij een los gesprek)."""
    g = db.gesprekken
    nu = db.utcnow()
    delegatie_id = uuid.uuid4().hex[:16]
    async with db.get_engine().begin() as conn:
        if inv.werkgebied_id:
            await _werkgebied_bestaat(conn, inv.werkgebied_id)
        gesprek = (await conn.execute(select(g.c.user_id, g.c.werkgebied_id).where(g.c.id == inv.gesprek_id))).first()
        if gesprek is None or gesprek.user_id != user_id:
            raise HTTPException(404, f"Onbekend gesprek: {inv.gesprek_id}")
        if (gesprek.werkgebied_id or "") != inv.werkgebied_id:
            raise HTTPException(409, {"fout": "ander_werkgebied",
                                      "melding": "Het gesprek hoort niet bij dit werkgebied."})
        await _sluit_verweesde(conn, inv.werkgebied_id, user_id)
        try:
            async with conn.begin_nested():
                await conn.execute(insert(db.delegaties).values(
                    id=delegatie_id, soort=inv.soort, werkgebied_id=inv.werkgebied_id, gesprek_id=inv.gesprek_id,
                    user_id=user_id, opdracht=inv.opdracht, plan_id=inv.plan_id, plan=inv.plan, status="loopt",
                    uitkomst={}, budget_aandeel=inv.budget_aandeel, gestart=nu, hartslag=nu))
        except IntegrityError:
            bestaand = await _lopende(conn, inv.werkgebied_id, user_id)
            raise HTTPException(409, {"fout": "delegatie_loopt_al", "delegatie_id": bestaand.id if bestaand else "",
                                      "werkgebied_id": bestaand.werkgebied_id if bestaand else "",
                                      "melding": "Er loopt al een regie in dit werkgebied, of werk van jou."}) from None
        row = (await conn.execute(select(db.delegaties).where(db.delegaties.c.id == delegatie_id))).first()
    return _delegatie(row)


async def haal(delegatie_id: str) -> Delegatie:
    t = db.delegaties
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(t).where(t.c.id == delegatie_id))).first()
    if row is None:
        raise HTTPException(404, f"Onbekende delegatie: {delegatie_id}")
    return _delegatie(row)


async def lijst(*, werkgebied_id: str | None = None, gesprek_id: str | None = None, user_id: str | None = None,
                limit: int = 20) -> list[Delegatie]:
    """De laatste delegaties in een werkgebied (gedeeld, zoals het werkgebied), of van een gesprek van de gebruiker."""
    t = db.delegaties
    q = select(t)
    async with db.get_engine().connect() as conn:
        if werkgebied_id is not None:
            await _werkgebied_bestaat(conn, werkgebied_id)
            q = q.where(t.c.werkgebied_id == werkgebied_id)
        if gesprek_id is not None:
            q = q.where(t.c.gesprek_id == gesprek_id, t.c.user_id == user_id)
        rows = (await conn.execute(q.order_by(t.c.gestart.desc(), t.c.id).limit(limit))).all()
    return [_delegatie(r) for r in rows]


async def wijzig(delegatie_id: str, user_id: str, inv: DelegatieWijziging) -> Delegatie:
    """Hartslag of afronden. Een delegatie van een ander geeft 404; een afgeronde delegatie 409, behalve dezelfde
    eindstand nog eens (een herhaald verzoek)."""
    huidig = await haal(delegatie_id)
    if huidig.user_id != user_id:
        raise HTTPException(404, f"Onbekende delegatie: {delegatie_id}")
    t = db.delegaties
    nu = db.utcnow()
    waarden: dict = {"hartslag": nu}
    if inv.status in EINDSTANDEN:
        waarden.update(status=inv.status, afgerond=nu, uitkomst=inv.uitkomst or {})
    async with db.get_engine().begin() as conn:
        uit = await conn.execute(update(t).where(and_(t.c.id == delegatie_id, t.c.status == "loopt")).values(**waarden))
        if uit.rowcount == 0:
            row = (await conn.execute(select(t).where(t.c.id == delegatie_id))).first()
            if row is not None and row.status == inv.status:
                return _delegatie(row)
            raise HTTPException(409, {"fout": "delegatie_afgerond", "status": row.status if row else "",
                                      "melding": "Deze delegatie is al afgerond."})
        row = (await conn.execute(select(t).where(t.c.id == delegatie_id))).first()
    return _delegatie(row)
