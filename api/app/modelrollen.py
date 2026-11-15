"""Het modelprofiel per rol van Lex: welk profiel de beheerder aan een rol gaf.

Welke rollen er zijn, staat in de code (`bronmodel.modelrollen`, gelijk aan `llm_stap.Rol` van graph-qa plus de
subagent). De tabel `modelrollen` zegt per rol welk profiel; een rij ontbreekt = de rol volgt het standaardprofiel.
Elke wijziging is een regel in `modelrol_audit`, append-only.

Lex neemt van een profiel alleen de modelnaam over (besluit gebruiker 15 nov 2026): endpoint en sleutel blijven die van
de straat. Een profiel dat Lex niet kan gebruiken (`bronmodel.modelrollen.bruikbaar_voor_lex`) is niet te kiezen (422),
en valt het later af – iemand gaf het een ander endpoint –, dan laat `voor_de_agent` het weg en volgt de rol het
standaardprofiel; de beheertab toont het dan als `niet_bruikbaar`.

Stijl C: de store gooit de HTTP-fouten, de routers (`routers/admin.py`, `routers/modelrollen.py`) zijn dun.
"""
from __future__ import annotations

from bronmodel.modelrollen import PER_NAAM, ROLLEN, bruikbaar_voor_lex
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, insert, select, update

from . import db, profiles
from .config import get_settings
from .llm_profile import LlmProfile


class Modelrol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    naam: str
    label: str
    groep: str
    beschrijving: str
    waarschuwing: str = ""
    #: Het gekozen profiel, of `None`: de rol volgt het standaardprofiel.
    profiel: str | None = None
    #: Het model dat Lex voor deze rol gebruikt, zoals de api het nu afleidt (het gekozen profiel, anders de standaard).
    model: str = ""
    #: Leeg, of waarom het gekozen profiel nu niet bruikbaar is (de rol volgt dan de standaard).
    niet_bruikbaar: str = ""
    door: str = ""
    bijgewerkt: str = ""


class Overzicht(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Het standaardprofiel en zijn model; `standaard_niet_bruikbaar` als Lex het niet kan gebruiken (dan de env).
    standaard: str | None = None
    standaard_model: str = ""
    standaard_niet_bruikbaar: str = ""
    rollen: list[Modelrol]
    #: Per profiel: leeg als Lex het kan gebruiken, anders waarom niet. Voor de keuzelijst in de beheertab.
    profielen: dict[str, str]


class ModelrolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Het profiel, of `None` om terug te gaan naar het standaardprofiel.
    profiel: str | None = None


class AuditRegel(BaseModel):
    actie: str
    door: str
    details: dict
    tijdstip: str


class Keuze(BaseModel):
    profiel: str
    model: str


class VoorDeAgent(BaseModel):
    """Wat graph-qa leest (`GET /v1/modelrollen`): alleen wat bruikbaar is, met de modelnaam."""

    standaard: Keuze | None = None
    rollen: dict[str, Keuze]


def _reden(p: LlmProfile) -> str:
    return bruikbaar_voor_lex(p.model, p.api_base, get_settings().llm_api_base)


async def _rijen() -> dict[str, dict]:
    async with db.get_engine().connect() as conn:
        return {r["rol"]: dict(r) for r in (await conn.execute(select(db.modelrollen))).mappings().all()}


async def overzicht() -> Overzicht:
    alle = {p.name: p for p in await profiles.list_profiles()}
    redenen = {n: _reden(p) for n, p in alle.items()}
    standaard = next((p for p in alle.values() if p.is_default), None)
    std_reden = redenen.get(standaard.name, "") if standaard else "Er is geen standaardprofiel."
    std_model = standaard.model if standaard and not std_reden else ""
    rijen = await _rijen()
    rollen = []
    for r in ROLLEN:
        rij = rijen.get(r.naam)
        gekozen = alle.get(rij["profiel"]) if rij else None
        reden = (redenen[gekozen.name] if gekozen else "Het profiel bestaat niet meer.") if rij else ""
        rollen.append(Modelrol(
            naam=r.naam, label=r.label, groep=r.groep, beschrijving=r.beschrijving, waarschuwing=r.waarschuwing,
            profiel=rij["profiel"] if rij else None,
            model=gekozen.model if gekozen and not reden else std_model,
            niet_bruikbaar=reden, door=(rij or {}).get("door", "") or "",
            bijgewerkt=db.aware(rij["bijgewerkt"]).isoformat() if rij else ""))
    return Overzicht(standaard=standaard.name if standaard else None, standaard_model=std_model,
                     standaard_niet_bruikbaar=std_reden, rollen=rollen, profielen=redenen)


async def voor_de_agent() -> VoorDeAgent:
    o = await overzicht()
    std = Keuze(profiel=o.standaard, model=o.standaard_model) if o.standaard and o.standaard_model else None
    return VoorDeAgent(standaard=std, rollen={
        r.naam: Keuze(profiel=r.profiel, model=r.model)
        for r in o.rollen if r.profiel and not r.niet_bruikbaar and r.model})


async def zet(rol: str, profiel: str | None, door: str) -> Modelrol:
    if rol not in PER_NAAM:
        raise HTTPException(status_code=404, detail={"melding": f"Onbekende rol: {rol}"})
    if profiel is not None:
        p = await profiles.get_profile(profiel)
        if p is None:
            raise HTTPException(status_code=404, detail={"melding": f"Onbekend profiel: {profiel}"})
        if reden := _reden(p):
            raise HTTPException(status_code=422, detail={"fout": "niet_bruikbaar", "melding": reden})
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(select(db.modelrollen.c.profiel).where(db.modelrollen.c.rol == rol)
                                  .with_for_update())).scalar()
        if oud != profiel:
            if profiel is None:
                await conn.execute(delete(db.modelrollen).where(db.modelrollen.c.rol == rol))
            elif oud is None:
                await conn.execute(insert(db.modelrollen).values(rol=rol, profiel=profiel, door=door, bijgewerkt=nu))
            else:
                await conn.execute(update(db.modelrollen).where(db.modelrollen.c.rol == rol)
                                   .values(profiel=profiel, door=door, bijgewerkt=nu))
            await conn.execute(insert(db.modelrol_audit).values(
                rol=rol, actie="standaard" if profiel is None else "gekozen", door=door,
                details={"was": oud, "wordt": profiel}, tijdstip=nu))
    return next(r for r in (await overzicht()).rollen if r.naam == rol)


async def audit(rol: str, limit: int = 50) -> list[AuditRegel]:
    if rol not in PER_NAAM:
        raise HTTPException(status_code=404, detail={"melding": f"Onbekende rol: {rol}"})
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(db.modelrol_audit).where(db.modelrol_audit.c.rol == rol)
                                    .order_by(db.modelrol_audit.c.id.desc()).limit(limit))).mappings().all()
    return [AuditRegel(actie=r["actie"], door=r["door"], details=r["details"] or {},
                       tijdstip=db.aware(r["tijdstip"]).isoformat()) for r in rijen]


async def rollen_met_profiel(conn, naam: str) -> list[str]:
    """De rollen die dit profiel gebruiken, in de transactie van de aanroeper (`profiles.delete_profile`)."""
    rijen = (await conn.execute(select(db.modelrollen.c.rol).where(db.modelrollen.c.profiel == naam))).scalars().all()
    return [PER_NAAM[r].label if r in PER_NAAM else r for r in rijen]
