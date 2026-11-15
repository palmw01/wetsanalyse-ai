"""De modelkeuzes van Lex: welk modelprofiel de beheerder aan een agentprofiel of een stap gaf.

Welke sleutels er zijn, staat in de code (`bronmodel.modelkeuzes`: `agent:<profiel>` per agentprofiel van Lex, `stap:<rol>`
per modelstap zonder profiel, plus `stap:subagent`). De tabel `modelkeuzes` zegt per sleutel welk profiel; een rij
ontbreekt = de sleutel volgt het standaardprofiel. Elke wijziging is een regel in `modelkeuze_audit`, append-only.

Lex neemt van een profiel alleen de modelnaam over (besluit gebruiker 15 nov 2026): endpoint en sleutel blijven die van
de straat. Een profiel dat Lex niet kan gebruiken (`bronmodel.modelkeuzes.bruikbaar_voor_lex`) is niet te kiezen (422),
en valt het later af – iemand gaf het een ander endpoint –, dan volgt de sleutel weer de standaard; het beheer toont het
dan als `niet_bruikbaar`.

Stijl C: de store gooit de HTTP-fouten, de routers (`routers/admin.py`, `routers/modelkeuzes.py`) zijn dun.
"""
from __future__ import annotations

from typing import Literal

from bronmodel.modelkeuzes import KEUZES, PER_SLEUTEL, bruikbaar_voor_lex
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, insert, select, update

from . import db, profiles
from .config import get_settings
from .llm_profile import LlmProfile


class Keuze(BaseModel):
    """Eén sleutel zoals het beheer hem toont."""

    model_config = ConfigDict(extra="forbid")
    sleutel: str
    soort: Literal["agent", "stap"]
    label: str
    groep: str
    beschrijving: str
    waarschuwing: str = ""
    #: Het gekozen profiel, of `None`: de sleutel volgt het standaardprofiel.
    profiel: str | None = None
    #: Het model dat Lex hiervoor nu gebruikt (het gekozen profiel, anders de standaard; leeg = de env van graph-qa).
    model: str = ""
    #: Leeg, of waarom het gekozen profiel nu niet bruikbaar is (de sleutel volgt dan de standaard).
    niet_bruikbaar: str = ""
    door: str = ""
    bijgewerkt: str = ""


class ProfielStand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Leeg als Lex het profiel kan gebruiken, anders waarom niet.
    niet_bruikbaar: str = ""
    #: De sleutels die dit profiel gekozen hebben.
    gebruikt_door: list[str] = []


class Overzicht(BaseModel):
    model_config = ConfigDict(extra="forbid")
    standaard: str | None = None
    standaard_model: str = ""
    #: Lex kan het standaardprofiel niet gebruiken: dan houden sleutels zonder keuze het env-model van graph-qa.
    standaard_niet_bruikbaar: str = ""
    keuzes: list[Keuze]
    profielen: dict[str, ProfielStand]


class KeuzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Het profiel, of `None` om terug te gaan naar het standaardprofiel.
    profiel: str | None = None


class AuditRegel(BaseModel):
    actie: str
    door: str
    details: dict
    tijdstip: str


class Gekozen(BaseModel):
    profiel: str
    model: str
    #: `keuze`: de beheerder koos dit voor deze sleutel; `standaard`: de sleutel volgt het standaardprofiel.
    bron: Literal["keuze", "standaard"]


class Stand(BaseModel):
    """Het leesmodel zonder beheerrecht (`GET /v1/modelkeuzes`): voor graph-qa en voor wie wil zien welk model Lex
    gebruikt. Alleen profielnaam en modelnaam, nooit endpoint of sleutel. Een sleutel zonder bruikbaar model (geen
    keuze en een standaard die Lex niet kan gebruiken) ontbreekt: dan geldt de env van graph-qa."""

    standaard: Gekozen | None = None
    keuzes: dict[str, Gekozen]


def _reden(p: LlmProfile) -> str:
    return bruikbaar_voor_lex(p.model, p.api_base, get_settings().llm_api_base)


async def _rijen() -> dict[str, dict]:
    async with db.get_engine().connect() as conn:
        return {r["sleutel"]: dict(r) for r in (await conn.execute(select(db.modelkeuzes))).mappings().all()}


async def overzicht() -> Overzicht:
    alle = {p.name: p for p in await profiles.list_profiles()}
    redenen = {n: _reden(p) for n, p in alle.items()}
    standaard = next((p for p in alle.values() if p.is_default), None)
    std_reden = redenen.get(standaard.name, "") if standaard else "Er is geen standaardprofiel."
    std_model = standaard.model if standaard and not std_reden else ""
    rijen = await _rijen()
    gebruikt: dict[str, list[str]] = {}
    keuzes = []
    for k in KEUZES:
        rij = rijen.get(k.sleutel)
        gekozen = alle.get(rij["profiel"]) if rij else None
        reden = (redenen[gekozen.name] if gekozen else "Het profiel bestaat niet meer.") if rij else ""
        if rij:
            gebruikt.setdefault(rij["profiel"], []).append(k.sleutel)
        keuzes.append(Keuze(
            sleutel=k.sleutel, soort=k.soort, label=k.label, groep=k.groep, beschrijving=k.beschrijving,  # type: ignore[arg-type]
            waarschuwing=k.waarschuwing, profiel=rij["profiel"] if rij else None,
            model=gekozen.model if gekozen and not reden else std_model,
            niet_bruikbaar=reden, door=(rij or {}).get("door", "") or "",
            bijgewerkt=db.aware(rij["bijgewerkt"]).isoformat() if rij else ""))
    return Overzicht(standaard=standaard.name if standaard else None, standaard_model=std_model,
                     standaard_niet_bruikbaar=std_reden, keuzes=keuzes,
                     profielen={n: ProfielStand(niet_bruikbaar=r, gebruikt_door=gebruikt.get(n, []))
                                for n, r in redenen.items()})


async def stand() -> Stand:
    o = await overzicht()
    std = Gekozen(profiel=o.standaard, model=o.standaard_model, bron="standaard") \
        if o.standaard and o.standaard_model else None
    uit: dict[str, Gekozen] = {}
    for k in o.keuzes:
        if k.profiel and not k.niet_bruikbaar and k.model:
            uit[k.sleutel] = Gekozen(profiel=k.profiel, model=k.model, bron="keuze")
        elif std:
            uit[k.sleutel] = std
    return Stand(standaard=std, keuzes=uit)


async def zet(sleutel: str, profiel: str | None, door: str) -> Keuze:
    if sleutel not in PER_SLEUTEL:
        raise HTTPException(status_code=404, detail={"melding": f"Onbekende sleutel: {sleutel}"})
    if profiel is not None:
        p = await profiles.get_profile(profiel)
        if p is None:
            raise HTTPException(status_code=404, detail={"melding": f"Onbekend profiel: {profiel}"})
        if reden := _reden(p):
            raise HTTPException(status_code=422, detail={"fout": "niet_bruikbaar", "melding": reden})
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(select(db.modelkeuzes.c.profiel).where(db.modelkeuzes.c.sleutel == sleutel)
                                  .with_for_update())).scalar()
        if oud != profiel:
            if profiel is None:
                await conn.execute(delete(db.modelkeuzes).where(db.modelkeuzes.c.sleutel == sleutel))
            elif oud is None:
                await conn.execute(insert(db.modelkeuzes).values(sleutel=sleutel, profiel=profiel, door=door,
                                                                 bijgewerkt=nu))
            else:
                await conn.execute(update(db.modelkeuzes).where(db.modelkeuzes.c.sleutel == sleutel)
                                   .values(profiel=profiel, door=door, bijgewerkt=nu))
            await conn.execute(insert(db.modelkeuze_audit).values(
                sleutel=sleutel, actie="standaard" if profiel is None else "gekozen", door=door,
                details={"was": oud, "wordt": profiel}, tijdstip=nu))
    return next(k for k in (await overzicht()).keuzes if k.sleutel == sleutel)


async def audit(sleutel: str, limit: int = 50) -> list[AuditRegel]:
    if sleutel not in PER_SLEUTEL:
        raise HTTPException(status_code=404, detail={"melding": f"Onbekende sleutel: {sleutel}"})
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(db.modelkeuze_audit).where(db.modelkeuze_audit.c.sleutel == sleutel)
                                    .order_by(db.modelkeuze_audit.c.id.desc()).limit(limit))).mappings().all()
    return [AuditRegel(actie=r["actie"], door=r["door"], details=r["details"] or {},
                       tijdstip=db.aware(r["tijdstip"]).isoformat()) for r in rijen]


async def gebruikt_door(conn, naam: str) -> list[str]:
    """De sleutels die dit profiel gekozen hebben, in de transactie van de aanroeper (`profiles.delete_profile`)."""
    return list((await conn.execute(select(db.modelkeuzes.c.sleutel).where(db.modelkeuzes.c.profiel == naam)
                                    .order_by(db.modelkeuzes.c.sleutel))).scalars().all())
