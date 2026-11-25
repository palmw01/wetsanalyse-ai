"""Het register van de plugins (plan docs/architectuur/plan-contenttoets.md, C4): welke de beheerder aanbiedt.

Welke plugins er bestaan, staat in de code (`bronmodel.plugins`): een plugin is een methode naast de wetsanalyse met een
eigen skill, profiel en route in graph-qa, geen configuratie. Het register zegt alleen *aan* of *uit*; een plugin zonder
rij staat uit. Elke wijziging is een regel in `plugin_audit`, append-only. Hetzelfde patroon als `app/connectors.py`.

Per gesprek zet de jurist een aangeboden plugin aan of uit (`gesprekken.plugins`, het menu *Bronnen en tools*). Graph-qa
draait de plugin alleen als hij in de beurt meekomt én zijn eigen straatvlag hem aanzet (`CONTENTTOETS`, een proefvlag).
"""
from __future__ import annotations

from typing import Literal

from bronmodel.plugins import NAMEN, PLUGINS
from pydantic import BaseModel, ConfigDict
from sqlalchemy import insert, select, update

from . import db

#: naam → de beschrijving uit `bronmodel.plugins`. De volgorde is die van de beheertab.
BEKEND = {p.naam: p for p in PLUGINS}
Naam = Literal[NAMEN]  # type: ignore[valid-type]


class Plugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    naam: str
    label: str
    beschrijving: str
    commando: str
    aan: bool
    door: str = ""
    bijgewerkt: str = ""


class PluginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aan: bool


class AuditRegel(BaseModel):
    actie: str
    door: str
    details: dict
    tijdstip: str


async def lijst() -> list[Plugin]:
    async with db.get_engine().connect() as conn:
        rijen = {r["naam"]: r for r in (await conn.execute(select(db.plugins))).mappings().all()}
    uit = []
    for naam, p in BEKEND.items():
        r = rijen.get(naam)
        uit.append(Plugin(naam=naam, label=p.label, beschrijving=p.beschrijving, commando=p.commando,
                          aan=bool(r and r["aan"]), door=(r["door"] if r else "") or "",
                          bijgewerkt=db.aware(r["bijgewerkt"]).isoformat() if r else ""))
    return uit


async def zet(naam: str, aan: bool, door: str) -> Plugin:
    if naam not in BEKEND:
        raise KeyError(naam)
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(select(db.plugins.c.aan).where(db.plugins.c.naam == naam))).scalar()
        if oud is None:
            await conn.execute(insert(db.plugins).values(naam=naam, aan=aan, door=door, bijgewerkt=nu))
        elif bool(oud) != aan:
            await conn.execute(update(db.plugins).where(db.plugins.c.naam == naam).values(aan=aan, door=door, bijgewerkt=nu))
        if oud is None or bool(oud) != aan:
            await conn.execute(insert(db.plugin_audit).values(
                naam=naam, actie="aan" if aan else "uit", door=door,
                details={"was": bool(oud) if oud is not None else None}, tijdstip=nu))
    return next(p for p in await lijst() if p.naam == naam)


async def audit(naam: str, limit: int = 50) -> list[AuditRegel]:
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(db.plugin_audit).where(db.plugin_audit.c.naam == naam)
                                    .order_by(db.plugin_audit.c.id.desc()).limit(limit))).mappings().all()
    return [AuditRegel(actie=r["actie"], door=r["door"], details=r["details"] or {},
                       tijdstip=db.aware(r["tijdstip"]).isoformat()) for r in rijen]
