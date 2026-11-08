"""Regies (ADR-012): één lopende per werkgebied en één per gebruiker.

Het slot is een partiële unieke index op `status = 'loopt'`, geen check-then-insert: twee api-replica's kunnen
tegelijk een start krijgen. Een regie die `VERWEESD_NA` geen hartslag gaf (graph-qa herstartte, een replica viel om),
telt als `mislukt`. Bij een nieuwe start wordt hij eerst zo vastgelegd, anders zou een verweesde regie het werkgebied
voor altijd blokkeren. Alleen de eigenaar wijzigt zijn regie; een afgeronde regie verandert niet meer."""
from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import db
from .regie_contracts import EINDSTANDEN, Regie, RegieStart, RegieWijziging

VERWEESD_NA = timedelta(minutes=3)


def _regie(row) -> Regie:
    d = dict(row._mapping)
    status = d["status"]
    if status == "loopt" and db.utcnow() - db.aware(d["hartslag"]) > VERWEESD_NA:
        status = "mislukt"
    return Regie(**{**d, "status": status, "gestart": db.aware(d["gestart"]),
                    "hartslag": db.aware(d["hartslag"]), "afgerond": db.aware(d["afgerond"])})


async def _werkgebied_bestaat(conn, werkgebied_id: str) -> None:
    t = db.werkgebieden
    if (await conn.execute(select(t.c.id).where(t.c.id == werkgebied_id))).first() is None:
        raise HTTPException(404, f"Onbekend werkgebied: {werkgebied_id}")


async def _sluit_verweesde(conn, werkgebied_id: str, user_id: str) -> None:
    t = db.regies
    grens = db.utcnow() - VERWEESD_NA
    await conn.execute(
        update(t).where(t.c.status == "loopt", t.c.hartslag < grens,
                        or_(t.c.werkgebied_id == werkgebied_id, t.c.user_id == user_id))
        .values(status="mislukt", afgerond=db.utcnow(), uitkomst={"reden": "verweesd"}))


async def _lopende(conn, werkgebied_id: str, user_id: str) -> Regie | None:
    t = db.regies
    row = (await conn.execute(select(t).where(
        t.c.status == "loopt", or_(t.c.werkgebied_id == werkgebied_id, t.c.user_id == user_id)))).first()
    return _regie(row) if row is not None else None


async def start(werkgebied_id: str, user_id: str, inv: RegieStart) -> Regie:
    """Een nieuwe regie, of 409 `regie_loopt_al` met de regie die het slot heeft (hier of in een ander
    werkgebied van dezelfde gebruiker). Het regiegesprek is van de gebruiker en hoort bij het werkgebied."""
    g = db.gesprekken
    nu = db.utcnow()
    regie_id = uuid.uuid4().hex[:16]
    async with db.get_engine().begin() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        gesprek = (await conn.execute(select(g.c.user_id, g.c.werkgebied_id).where(g.c.id == inv.gesprek_id))).first()
        if gesprek is None or gesprek.user_id != user_id:
            raise HTTPException(404, f"Onbekend gesprek: {inv.gesprek_id}")
        if gesprek.werkgebied_id != werkgebied_id:
            raise HTTPException(409, {"fout": "ander_werkgebied",
                                      "melding": "Het regiegesprek hoort niet bij dit werkgebied."})
        await _sluit_verweesde(conn, werkgebied_id, user_id)
        try:
            async with conn.begin_nested():
                await conn.execute(insert(db.regies).values(
                    id=regie_id, werkgebied_id=werkgebied_id, gesprek_id=inv.gesprek_id, user_id=user_id,
                    opdracht=inv.opdracht, plan_id=inv.plan_id, plan=inv.plan, status="loopt", uitkomst={},
                    budget_aandeel=inv.budget_aandeel, gestart=nu, hartslag=nu))
        except IntegrityError:
            bestaand = await _lopende(conn, werkgebied_id, user_id)
            raise HTTPException(409, {"fout": "regie_loopt_al", "regie_id": bestaand.id if bestaand else "",
                                      "werkgebied_id": bestaand.werkgebied_id if bestaand else "",
                                      "melding": "Er loopt al een regie in dit werkgebied of van jou."}) from None
        row = (await conn.execute(select(db.regies).where(db.regies.c.id == regie_id))).first()
    return _regie(row)


async def haal(werkgebied_id: str, regie_id: str) -> Regie:
    t = db.regies
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(t).where(t.c.id == regie_id, t.c.werkgebied_id == werkgebied_id))).first()
    if row is None:
        raise HTTPException(404, f"Onbekende regie: {regie_id}")
    return _regie(row)


async def lijst(werkgebied_id: str, limit: int = 20) -> list[Regie]:
    t = db.regies
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        rows = (await conn.execute(select(t).where(t.c.werkgebied_id == werkgebied_id)
                                   .order_by(t.c.gestart.desc(), t.c.id).limit(limit))).all()
    return [_regie(r) for r in rows]


async def wijzig(werkgebied_id: str, regie_id: str, user_id: str, inv: RegieWijziging) -> Regie:
    """Hartslag of afronden. Een regie van een ander geeft 404; een afgeronde regie 409, behalve dezelfde
    eindstand nog eens (een herhaald verzoek)."""
    huidig = await haal(werkgebied_id, regie_id)
    if huidig.user_id != user_id:
        raise HTTPException(404, f"Onbekende regie: {regie_id}")
    t = db.regies
    nu = db.utcnow()
    waarden: dict = {"hartslag": nu}
    if inv.status in EINDSTANDEN:
        waarden.update(status=inv.status, afgerond=nu, uitkomst=inv.uitkomst or {})
    async with db.get_engine().begin() as conn:
        uit = await conn.execute(update(t).where(and_(t.c.id == regie_id, t.c.status == "loopt")).values(**waarden))
        if uit.rowcount == 0:
            row = (await conn.execute(select(t).where(t.c.id == regie_id))).first()
            if row is not None and row.status == inv.status:
                return _regie(row)
            raise HTTPException(409, {"fout": "regie_afgerond", "status": row.status if row else "",
                                      "melding": "Deze regie is al afgerond."})
        row = (await conn.execute(select(t).where(t.c.id == regie_id))).first()
    return _regie(row)
