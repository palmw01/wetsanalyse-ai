"""Service-laag voor het berichtensysteem: release notes en aankondigingen.

Beheerders schrijven berichten (draft → gepubliceerd); analisten lezen ze via het
panel in de navigatie. Leesbewijzen (`bericht_leesbewijzen`) registreren per user
welke berichten al gezien zijn.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import delete, func, insert, select, text, update

from . import db


GELDIGE_TYPES = Literal["info", "update", "waarschuwing", "kritiek"]


class BerichtError(ValueError):
    """Ongeldige bericht-operatie (onbekend id)."""


def _row_to_dict(row, *, gelezen: bool | None = None) -> dict:
    m = dict(row)
    result = {
        "id":              m["id"],
        "titel":           m["titel"],
        "inhoud":          m["inhoud"],
        "type":            m["type"],
        "versie":          m.get("versie"),
        "gepubliceerd":    bool(m["gepubliceerd"]),
        "aangemaakt_door": m["aangemaakt_door"],
        "created":         db.aware(m["created"]),
        "updated":         db.aware(m["updated"]),
    }
    if gelezen is not None:
        result["gelezen"] = gelezen
    return result


async def list_berichten(userid: str) -> list[dict]:
    """Gepubliceerde berichten voor een analist, met gelezen-vlag, nieuwste eerst (max 20)."""
    b = db.berichten
    lb = db.bericht_leesbewijzen
    stmt = (
        select(b, lb.c.userid.isnot(None).label("gelezen"))
        .outerjoin(lb, (lb.c.bericht_id == b.c.id) & (lb.c.userid == userid))
        .where(b.c.gepubliceerd.is_(True))
        .order_by(b.c.created.desc())
        .limit(20)
    )
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(stmt)).mappings().all()
    return [_row_to_dict(r, gelezen=bool(r["gelezen"])) for r in rows]


async def ongelezen_aantal(userid: str) -> int:
    """Aantal gepubliceerde berichten zonder leesbewijs voor deze user (gecapped op 99+)."""
    b = db.berichten
    lb = db.bericht_leesbewijzen
    u = db.users
    stmt = (
        select(func.count())
        .select_from(b)
        .outerjoin(lb, (lb.c.bericht_id == b.c.id) & (lb.c.userid == userid))
        .where(b.c.gepubliceerd.is_(True))
        .where(lb.c.userid.is_(None))
        # Toon alleen berichten gepubliceerd ná aanmaken van de user-account zodat nieuwe
        # gebruikers geen badge van historische berichten krijgen.
        .where(
            b.c.created >= select(u.c.created).where(u.c.userid == userid).scalar_subquery()
        )
    )
    async with db.get_engine().connect() as conn:
        result = await conn.scalar(stmt)
    return int(result or 0)


async def markeer_alles_gelezen(userid: str) -> None:
    """Zet leesbewijzen voor alle nog-ongelezen gepubliceerde berichten van deze user."""
    b = db.berichten
    lb = db.bericht_leesbewijzen
    nu = db.utcnow()
    # Eén portable INSERT ... SELECT ... WHERE NOT EXISTS — werkt op Postgres én SQLite
    # zonder try/except IntegrityError (dat breekt Postgres-transacties in aborted state).
    stmt = insert(lb).from_select(
        ["bericht_id", "userid", "gelezen_op"],
        select(b.c.id, text(f"'{userid}'"), text(f"'{nu.isoformat()}'"))
        .where(b.c.gepubliceerd.is_(True))
        .where(
            ~select(lb.c.bericht_id)
            .where(lb.c.bericht_id == b.c.id)
            .where(lb.c.userid == userid)
            .correlate(b)
            .exists()
        ),
    )
    async with db.get_engine().begin() as conn:
        await conn.execute(stmt)


async def list_alle_berichten() -> list[dict]:
    """Alle berichten (ook ongepubliceerde), voor de admin-beheerlijst."""
    stmt = select(db.berichten).order_by(db.berichten.c.created.desc())
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(stmt)).mappings().all()
    return [_row_to_dict(r) for r in rows]


async def maak_bericht(
    titel: str,
    inhoud: str,
    bericht_type: str,
    versie: str | None,
    aangemaakt_door: str,
) -> dict:
    """Maak een nieuw concept-bericht (gepubliceerd=False)."""
    nu = db.utcnow()
    values = {
        "titel":           titel.strip()[:256],
        "inhoud":          inhoud[:10000],
        "type":            bericht_type,
        "versie":          versie.strip()[:32] if versie else None,
        "gepubliceerd":    False,
        "aangemaakt_door": aangemaakt_door,
        "created":         nu,
        "updated":         nu,
    }
    async with db.get_engine().begin() as conn:
        result = await conn.execute(insert(db.berichten).values(**values).returning(*db.berichten.c))
        row = result.mappings().first()
    return _row_to_dict(row)


async def update_bericht(
    bericht_id: int,
    titel: str,
    inhoud: str,
    bericht_type: str,
    versie: str | None,
) -> dict:
    """Werk een bericht bij (inhoud/metadata). Leesbewijzen blijven staan."""
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        result = await conn.execute(
            update(db.berichten)
            .where(db.berichten.c.id == bericht_id)
            .values(
                titel=titel.strip()[:256],
                inhoud=inhoud[:10000],
                type=bericht_type,
                versie=versie.strip()[:32] if versie else None,
                updated=nu,
            )
            .returning(*db.berichten.c)
        )
        row = result.mappings().first()
    if row is None:
        raise BerichtError(f"Bericht {bericht_id} niet gevonden.")
    return _row_to_dict(row)


async def set_gepubliceerd(bericht_id: int, gepubliceerd: bool) -> dict:
    """Publiceer of depubliceer een bericht."""
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        result = await conn.execute(
            update(db.berichten)
            .where(db.berichten.c.id == bericht_id)
            .values(gepubliceerd=gepubliceerd, updated=nu)
            .returning(*db.berichten.c)
        )
        row = result.mappings().first()
    if row is None:
        raise BerichtError(f"Bericht {bericht_id} niet gevonden.")
    return _row_to_dict(row)


async def verwijder_bericht(bericht_id: int) -> None:
    """Verwijder een bericht + alle bijbehorende leesbewijzen (cascade in één transactie)."""
    async with db.get_engine().begin() as conn:
        await conn.execute(
            delete(db.bericht_leesbewijzen).where(db.bericht_leesbewijzen.c.bericht_id == bericht_id)
        )
        result = await conn.execute(
            delete(db.berichten).where(db.berichten.c.id == bericht_id)
        )
    if result.rowcount == 0:
        raise BerichtError(f"Bericht {bericht_id} niet gevonden.")
