"""Werkgebieden: opslag, revisies en audit (spoor D, levering 1).

Gedeeld tussen analisten, zoals de annotaties. Elke mutatie neemt een rij-lock op het werkgebied
(`SELECT … FOR UPDATE`), toetst `verwachte_revisie` (412 bij een tussentijdse wijziging), hoogt de
revisie op en schrijft een auditregel. Het annotatieslot (`annotatie_v2_state`) wordt niet
geraakt: een werkgebied schrijft geen annotaties.

Een bronselectie weghalen is soft: een tijdstip, zodat de historie klopt. Een werkgebied
**verwijderen** is echt wissen, net als een annotatie: het werkgebied en alles wat eraan hangt gaat uit
de database (`wis`), de auditregels blijven als bewijs, en de annotaties van de bronnen blijven
onaangeroerd – die horen bij een bronnode, niet bij een werkgebied.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import db
from .werkgebied_contracts import (
    BronselectieInvoer, BronselectieWijziging, WerkgebiedInvoer, WerkgebiedWijziging,
)


def _werkgebied(row) -> dict:
    return {"id": row.id, "naam": row.naam, "analysevraag": row.analysevraag,
            "afbakening": row.afbakening, "aanleiding": row.aanleiding, "context": row.context,
            "doel": row.doel, "praktijkvoorbeeld": row.praktijkvoorbeeld,
            "peildatum": row.peildatum, "status": row.status,
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
    # Wat geaudit wordt, kan de begrippengraaf raken: na de commit projecteren (fase F3). Een mutatie
    # die niets aan de graph verandert, kost alleen het lezen en vergelijken (`begrip_projectie.projecteer`).
    db.noteer_na_commit(conn, "werkgebieden", werkgebied_id)
    await conn.execute(insert(db.werkgebied_audit).values(
        werkgebied_id=werkgebied_id, actor=actor, actie=actie, detail=detail, tijdstip=db.utcnow()))


#: Elke tabel met een `werkgebied_id`, behalve de audit: wat `wis` leegmaakt. Een nieuwe tabel met die
#: kolom hoort hier (of bewust niet); `tests/test_werkgebied_verwijderen.py` bewaakt dat.
WERKGEBIED_TABELLEN = ("werkgebied_bronselecties", "werkgebied_element_besluiten", "werkgebied_deelvragen",
                       "begrippen", "begrip_koppelingen", "begrip_relaties", "begrip_voorstellen",
                       "begrip_kaartruns", "bronnen_runs", "bron_kandidaten", "begrippen_runs",
                       "betekenisgroepen", "begrippen_batches")
#: Wat bij een verwijderd object in de audit staat (oude stand: archiveren, een soft verwijderd begrip).
VERWIJDERD_ACTIES = ("werkgebied-verwijderd", "gearchiveerd")


async def niet_gevonden(werkgebied_id: str, begrip_id: str | None = None) -> HTTPException:
    """De 404 voor een werkgebied of begrip dat er niet is. Was het er wel en is het verwijderd, dan
    zegt de 404 wanneer en door wie (uit de audit), zodat een paneel of oud gesprek dat kan tonen in
    plaats van een kale fout – zoals een verwijderde annotatie."""
    a = db.werkgebied_audit
    acties = (*VERWIJDERD_ACTIES, "begrip-verwijderd") if begrip_id else VERWIJDERD_ACTIES
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(a).where(a.c.werkgebied_id == werkgebied_id, a.c.actie.in_(acties))
                                   .order_by(a.c.id.desc()))).all()
    soort = "Werkgebied"
    for r in rows:
        if r.actie == "begrip-verwijderd" and (r.detail or {}).get("begrip_id") != begrip_id:
            continue
        if r.actie == "begrip-verwijderd":
            soort = "Begrip"
        return HTTPException(404, {"fout": "verwijderd", "soort": soort.lower(), "op": db.aware(r.tijdstip).isoformat(),
                                   "door": r.actor, "melding": f"{soort} is verwijderd."})
    return HTTPException(404, "Begrip bestaat niet." if begrip_id else "Werkgebied bestaat niet.")


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


async def _van_intake(intake_id: str) -> str | None:
    t = db.werkgebieden
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(t.c.id).where(t.c.intake_id == intake_id))).scalar()


async def maak(invoer: WerkgebiedInvoer, actor: str) -> dict:
    """Een nieuw werkgebied. Met een `intake_id` idempotent: bestaat er al een uit die intake, dan
    komt dat terug (ook als het intussen gewijzigd is; gearchiveerd geeft 404).

    De deelvragen uit het samenstellen komen in dezelfde transactie mee, actief en op volgorde;
    dezelfde vraag twee keer (genormaliseerd) telt één keer."""
    if invoer.intake_id and (bestaand := await _van_intake(invoer.intake_id)):
        return await haal(bestaand)
    nu, wid = db.utcnow(), str(uuid.uuid4())
    try:
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(db.werkgebieden).values(
                id=wid, naam=invoer.naam, analysevraag=invoer.analysevraag, afbakening=invoer.afbakening,
                aanleiding=invoer.aanleiding, context=invoer.context, doel=invoer.doel,
                praktijkvoorbeeld=invoer.praktijkvoorbeeld,
                peildatum=invoer.peildatum, status="in_voorbereiding", revisie=1, aangemaakt_door=actor,
                aangemaakt=nu, gewijzigd=nu, intake_id=invoer.intake_id))
            deelvragen = await _deelvragen_bij_aanmaken(conn, wid, invoer, actor, nu)
            await _audit(conn, wid, actor, "aangemaakt", {"naam": invoer.naam, "revisie": 1,
                                                          **({"intake_id": invoer.intake_id} if invoer.intake_id else {}),
                                                          **({"deelvragen": deelvragen} if deelvragen else {})})
    except IntegrityError:
        # Twee gelijktijdige klikken (of replica's): de unieke index besliste, de ander wint.
        if invoer.intake_id and (bestaand := await _van_intake(invoer.intake_id)):
            return await haal(bestaand)
        raise
    return await haal(wid)


async def _deelvragen_bij_aanmaken(conn, wid: str, invoer: WerkgebiedInvoer, actor: str, nu) -> int:
    from .werkgebied_deelvragen import normaliseer  # die module leest dit schrijfpad zelf
    gezien: set[str] = set()
    for d in invoer.deelvragen:
        if (sleutel := normaliseer(d.vraag)) in gezien:
            continue
        gezien.add(sleutel)
        await conn.execute(insert(db.werkgebied_deelvragen).values(
            id=str(uuid.uuid4()), werkgebied_id=wid, vraag=d.vraag, volgorde=len(gezien) - 1, status="actief",
            herkomst=d.herkomst, reden="", aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
    return len(gezien)


async def lijst(door: str | None = None) -> list[dict]:
    """Alle werkgebieden; met `door` alleen die waar deze gebruiker iets aan deed (de audit), zoals
    *Door mij bewerkt* bij de annotaties."""
    t, s, a = db.werkgebieden, db.werkgebied_bronselecties, db.werkgebied_audit
    aantal = (select(s.c.werkgebied_id, func.count().label("n")).where(s.c.verwijderd.is_(None))
              .group_by(s.c.werkgebied_id).subquery())
    q = (select(t, func.coalesce(aantal.c.n, 0).label("aantal_bronnen"))
         .outerjoin(aantal, aantal.c.werkgebied_id == t.c.id)
         .where(t.c.gearchiveerd.is_(None))
         .order_by(t.c.gewijzigd.desc(), t.c.id))
    if door:
        q = q.where(t.c.id.in_(select(a.c.werkgebied_id).where(a.c.actor == door)))
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
        raise await niet_gevonden(werkgebied_id)
    from . import werkgebied_deelvragen  # leest dit schrijfpad zelf; dus hier, niet bovenaan
    return {**_werkgebied(row), "bronnen": await selecties(werkgebied_id),
            "deelvragen": await werkgebied_deelvragen.lijst(werkgebied_id)}


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


async def verwijder(werkgebied_id: str, verwacht: int, actor: str) -> dict:
    """Echt wissen, onder het rij-slot en met de revisietoets: het werkgebied en alles wat eraan hangt.
    De audit krijgt een laatste regel en blijft staan; via die regel volgt de begrippengraaf (de
    projectie vindt geen werkgebied meer en haalt de graph weg)."""
    t = db.werkgebieden
    async with db.get_engine().begin() as conn:
        row = (await conn.execute(select(t).where(t.c.id == werkgebied_id).with_for_update())).first()
        if row is None or row.gearchiveerd is not None:
            raise await niet_gevonden(werkgebied_id)
        if row.revisie != verwacht:
            raise HTTPException(412, {"fout": "revisie_conflict", "revisie": row.revisie,
                                      "melding": "Iemand anders wijzigde dit werkgebied intussen; laad het opnieuw."})
        await wis(conn, werkgebied_id)
        await _audit(conn, werkgebied_id, actor, "werkgebied-verwijderd", {"naam": row.naam, "revisie": row.revisie})
    return {"verwijderd": werkgebied_id}


async def wis(conn, werkgebied_id: str) -> None:
    """Alles van één werkgebied uit de database, behalve de audit. Twee tabellen dragen geen
    `werkgebied_id` en gaan via hun ouder: de begriprevisies en de koppelingen van de deelvragen."""
    t = db.metadata.tables
    begrippen = (await conn.execute(select(db.begrippen.c.id).where(db.begrippen.c.werkgebied_id == werkgebied_id))).scalars().all()
    deelvragen = (await conn.execute(select(db.werkgebied_deelvragen.c.id)
                                     .where(db.werkgebied_deelvragen.c.werkgebied_id == werkgebied_id))).scalars().all()
    if begrippen:
        await conn.execute(delete(db.begrip_revisies).where(db.begrip_revisies.c.begrip_id.in_(begrippen)))
    if deelvragen:
        k = db.werkgebied_deelvraag_koppelingen
        await conn.execute(delete(k).where(k.c.deelvraag_id.in_(deelvragen)))
    for naam in WERKGEBIED_TABELLEN:
        await conn.execute(delete(t[naam]).where(t[naam].c.werkgebied_id == werkgebied_id))
    await conn.execute(delete(db.werkgebieden).where(db.werkgebieden.c.id == werkgebied_id))


async def voeg_bron_toe(werkgebied_id: str, invoer: BronselectieInvoer, bron: dict, actor: str,
                        binnen: Callable[[Any], Awaitable[None]] | None = None) -> tuple[dict, bool]:
    """Neemt een geverifieerde bron op. Geeft (selectie, nieuw) terug.

    `bron` komt uit de resolver: {bron_iri, label, bwb_id, snapshot_id, bron_hash}. Staat dezelfde
    bron er al met dezelfde rol en hetzelfde bereik, dan is dit idempotent: de bestaande selectie,
    zonder revisiesprong. Met een andere rol of ander bereik: 409 – wijzig dan de bestaande.

    `binnen(conn)` draait in dezelfde transactie, na het opnemen: zo landt een kandidaat die wordt
    opgenomen samen met zijn selectie, of geen van beide (`bronnen_run_store.opnemen`).
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
        if binnen is not None:
            await binnen(conn)
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
        # Kwam de bron uit een voorstel van Lex, dan is hij weer een voorstel (fase A). Geen nieuwe run
        # nodig: de vorige vond hem al, met zijn bewijs.
        k = db.bron_kandidaten
        await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.bron_iri == (bron_iri or ""),
                                           k.c.status == "opgenomen")
                           .values(status="voorgesteld", besloten_door=None, besloten_op=None, gewijzigd=db.utcnow()))
    return await haal(werkgebied_id)


async def audit(werkgebied_id: str, limit: int = 100) -> list[dict]:
    a = db.werkgebied_audit
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(a).where(a.c.werkgebied_id == werkgebied_id)
                                   .order_by(a.c.id.desc()).limit(limit))).all()
    return [{"id": r.id, "actor": r.actor, "actie": r.actie, "detail": r.detail,
             "tijdstip": db.aware(r.tijdstip).isoformat()} for r in rows]
