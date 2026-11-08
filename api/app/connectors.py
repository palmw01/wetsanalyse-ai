"""Het register van de bronconnectors (ADR-013, fase 1b): welke de beheerder heeft aangezet.

Welke connectors er bestaan, staat in de code: een bronconnector is een getypeerde tool in graph-qa met een
eigen soort vindplaats, geen configuratie. `BEKEND` is daarom gelijk aan `tools.CONNECTORS` van graph-qa
(`tests/poort/test_waardensets.py` bewaakt het). Het register zegt alleen *aan* of *uit*; een connector zonder
rij staat uit. Elke wijziging is een regel in `connector_audit`, append-only.

De routes staan in `routers/admin.py` (beheer) en `routers/connectors.py` (graph-qa). Graph-qa leest het register per
beurt (`GET /v1/connectors`) en zet daarnaast zijn eigen straatvlag
(`CONNECTOR_<NAAM>`): een connector draait alleen als beide aan staan. Credentials en een rate-limit per connector
komen met de eerste connector die ze nodig heeft (EUR-Lex); Kamerstukken is openbaar en vraagt er geen.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import insert, select, update

from . import db

#: naam → (label, brontype, beschrijving). De volgorde is die van de beheertab.
BEKEND: dict[str, tuple[str, str, str]] = {
    "kamerstukken": ("Kamerstukken", "kamerstuk",
                     "Wetsgeschiedenis uit de officiële publicaties: memorie van toelichting, nota's, verslagen en het "
                     "advies van de Raad van State. Openbaar, zonder sleutel."),
}
Naam = Literal["kamerstukken"]


class Connector(BaseModel):
    model_config = ConfigDict(extra="forbid")
    naam: str
    label: str
    brontype: str
    beschrijving: str
    aan: bool
    door: str = ""
    bijgewerkt: str = ""


class ConnectorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aan: bool


class AuditRegel(BaseModel):
    actie: str
    door: str
    details: dict
    tijdstip: str


async def lijst() -> list[Connector]:
    async with db.get_engine().connect() as conn:
        rijen = {r["naam"]: r for r in (await conn.execute(select(db.connectors))).mappings().all()}
    uit = []
    for naam, (label, brontype, beschrijving) in BEKEND.items():
        r = rijen.get(naam)
        uit.append(Connector(naam=naam, label=label, brontype=brontype, beschrijving=beschrijving,
                             aan=bool(r and r["aan"]), door=(r["door"] if r else "") or "",
                             bijgewerkt=db.aware(r["bijgewerkt"]).isoformat() if r else ""))
    return uit


async def zet(naam: str, aan: bool, door: str) -> Connector:
    if naam not in BEKEND:
        raise KeyError(naam)
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(select(db.connectors.c.aan).where(db.connectors.c.naam == naam))).scalar()
        if oud is None:
            await conn.execute(insert(db.connectors).values(naam=naam, aan=aan, door=door, bijgewerkt=nu))
        elif bool(oud) != aan:
            await conn.execute(update(db.connectors).where(db.connectors.c.naam == naam)
                               .values(aan=aan, door=door, bijgewerkt=nu))
        if oud is None or bool(oud) != aan:
            await conn.execute(insert(db.connector_audit).values(
                naam=naam, actie="aan" if aan else "uit", door=door,
                details={"was": bool(oud) if oud is not None else None}, tijdstip=nu))
    return next(c for c in await lijst() if c.naam == naam)


async def audit(naam: str, limit: int = 50) -> list[AuditRegel]:
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(db.connector_audit).where(db.connector_audit.c.naam == naam)
                                    .order_by(db.connector_audit.c.id.desc()).limit(limit))).mappings().all()
    return [AuditRegel(actie=r["actie"], door=r["door"], details=r["details"] or {},
                       tijdstip=db.aware(r["tijdstip"]).isoformat()) for r in rijen]
