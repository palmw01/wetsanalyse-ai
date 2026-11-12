"""Het register van de werkplaats (ADR-016 deel B, stap B1): onderdelen, versies, audit en beleid.

Alle SQL van de werkplaats staat hier. Eén levenscyclus voor elke soort: wat een soort is (de toets, het lege begin, de
hash) staat in `bronmodel.werkplaats`, dezelfde code die de generator in graph-qa gebruikt.

- **Opslaan is aanvullen.** Een versie is een volledige snapshot en wordt nooit gewijzigd of verwijderd. Dezelfde
  inhoud als de laatste versie geeft geen nieuwe versie.
- **De toets van poort 1 draait bij elke opslag**; de uitkomst staat bij de versie. Een versie die de toets niet haalt,
  wordt bewaard: wie een skill schrijft, slaat halverwege op. Alleen een geldige versie kan naar de proef of een PR
  (`bruikbaar`).
- **De stand wordt afgeleid**: *concept* of *ingetrokken*. *Voorgesteld* en *actief* komen in latere stappen erbij, ook
  afgeleid; er is geen kolom die uit de pas kan lopen.
- **De audit draagt geen inhoud**: het onderdeel, het versienummer, de hash en wie. Ook de logregels niet.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from bronmodel import werkplaats as wp
from fastapi import HTTPException
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from . import db

logger = logging.getLogger("wetsanalyse.werkplaats")

#: Het beleid zonder rij in de tabel: een analist mag concepten maken. De vlag `WERKPLAATS` staat alleen op acceptatie.
BELEID = {"analist_mag_maken": True}


def _fout(status: int, melding: str, **extra: Any) -> HTTPException:
    """Een handeling die het register weigert (stijl C: de store gooit de HTTP-fout in de transactie). De werkplek
    toont `melding`; `bevindingen` zegt waarom een versie niet bewaard kan worden."""
    return HTTPException(status, {"melding": melding, **extra})


def _bevindingen(lijst: list[wp.Bevinding]) -> list[dict[str, str]]:
    return [{"code": b.code, "melding": b.melding, "bestand": b.bestand} for b in lijst]


def _tijd(waarde) -> str:
    return db.aware(waarde).isoformat() if waarde else ""


def _onderdeel(r, versies: int, laatste: dict[str, Any] | None, zelfde_naam: int) -> dict[str, Any]:
    return {
        "id": r["id"], "soort": r["soort"], "naam": r["naam"], "eigenaar": r["eigenaar"], "gedeeld": bool(r["gedeeld"]),
        "stand": "ingetrokken" if r["ingetrokken_op"] else "concept",
        "ingetrokken_op": _tijd(r["ingetrokken_op"]), "ingetrokken_door": r["ingetrokken_door"] or "",
        "gemaakt": _tijd(r["gemaakt"]), "bijgewerkt": _tijd(r["bijgewerkt"]),
        "versies": versies, "laatste": laatste,
        # Hoeveel andere concepten van dezelfde soort en naam er zijn (van andere eigenaren): twee juristen kunnen elk
        # een concept van dezelfde skill hebben.
        "zelfde_naam": zelfde_naam,
    }


def _versie(r, *, met_inhoud: bool) -> dict[str, Any]:
    uit = {"id": r["id"], "nummer": r["nummer"], "hash": r["hash"], "basis_hash": r["basis_hash"] or "",
           "toelichting": r["toelichting"] or "", "geldig": bool(r["geldig"]), "bevindingen": r["bevindingen"] or [],
           "door": r["door"], "gemaakt": _tijd(r["gemaakt"])}
    if met_inhoud:
        uit["bestanden"] = r["bestanden"]
    return uit


_KOP = [c for c in db.werkplaats_versies.c if c.name != "bestanden"]


async def _audit(conn, onderdeel_id: str, actie: str, door: str, **details: Any) -> None:
    await conn.execute(insert(db.werkplaats_audit).values(
        onderdeel_id=onderdeel_id, actie=actie, door=door, details=details, tijdstip=db.utcnow()))


def toets(soort: str, naam: str, bestanden: dict[str, str]) -> list[dict[str, str]]:
    """Poort 1, zonder op te slaan."""
    return _bevindingen(wp.toets(soort, naam, bestanden))


def _weiger(soort: str, naam: str, bestanden: dict[str, str]) -> None:
    """Wat het register nooit bewaart: een ongeldige soort of naam, een pad dat geen pad is, een snapshot boven de grens."""
    if fout := wp.naam_fout(soort, naam):
        raise _fout(422, fout)
    if hard := wp.weiger(bestanden):
        raise _fout(422, "Deze versie kan niet worden bewaard.", bevindingen=_bevindingen(hard))


async def _schrijf_versie(conn, onderdeel_id: str, soort: str, naam: str, nummer: int, bestanden: dict[str, str],
                          toelichting: str, basis_hash: str, door: str) -> dict[str, Any]:
    bevindingen = _bevindingen(wp.toets(soort, naam, bestanden))
    rij = {"id": uuid.uuid4().hex, "onderdeel_id": onderdeel_id, "nummer": nummer, "hash": wp.hash_van(bestanden),
           "basis_hash": basis_hash, "bestanden": bestanden, "toelichting": toelichting, "geldig": not bevindingen,
           "bevindingen": bevindingen, "door": door, "gemaakt": db.utcnow()}
    await conn.execute(insert(db.werkplaats_versies).values(**rij))
    await _audit(conn, onderdeel_id, "versie", door, nummer=nummer, hash=rij["hash"], geldig=rij["geldig"],
                 bevindingen=len(bevindingen), bestanden=len(bestanden))
    # Tellingen, geen inhoud: de naam en de tekst van een concept horen niet in de telemetrie.
    logger.info("werkplaats versie", extra={"categorie": "functioneel", "soort": soort, "nummer": nummer,
                                             "geldig": rij["geldig"], "bestanden": len(bestanden)})
    return _versie(rij, met_inhoud=False)


async def maak(soort: str, naam: str, eigenaar: str, bestanden: dict[str, str] | None, toelichting: str,
               basis_hash: str = "") -> dict[str, Any]:
    """Een nieuw onderdeel met versie 1. Zonder bestanden begint het met het lege begin van de soort."""
    if fout := wp.naam_fout(soort, naam):
        raise _fout(422, fout)
    bestanden = bestanden if bestanden is not None else wp.begin(soort, naam)
    _weiger(soort, naam, bestanden)
    t = db.werkplaats_onderdelen
    nu = db.utcnow()
    oid = uuid.uuid4().hex
    try:
        async with db.get_engine().begin() as conn:
            eigen = (await conn.execute(select(t.c.soort, t.c.naam).where(
                t.c.eigenaar == eigenaar, t.c.ingetrokken_op.is_(None)))).all()
            if (soort, naam) in {(r[0], r[1]) for r in eigen}:
                raise _fout(409, f"Je hebt al een concept van {naam}.")
            if len(eigen) >= wp.MAX_ONDERDELEN:
                raise _fout(409, f"Je hebt het maximum van {wp.MAX_ONDERDELEN} concepten; trek er eerst een in.")
            await conn.execute(insert(t).values(id=oid, soort=soort, naam=naam, eigenaar=eigenaar, gedeeld=False,
                                                ingetrokken_op=None, ingetrokken_door="", gemaakt=nu, bijgewerkt=nu))
            await _audit(conn, oid, "aangemaakt", eigenaar, soort=soort)
            await _schrijf_versie(conn, oid, soort, naam, 1, bestanden, toelichting, basis_hash, eigenaar)
    except IntegrityError as exc:
        # Twee keer tegelijk hetzelfde concept: de unieke index laat er één door.
        raise _fout(409, f"Je hebt al een concept van {naam}.") from exc
    return await lees(oid)


async def nieuwe_versie(onderdeel_id: str, bestanden: dict[str, str], toelichting: str, na_versie: int,
                        door: str) -> dict[str, Any]:
    """Een volgende versie. `na_versie` is de versie waarop de aanroeper voortbouwt: is er intussen een nieuwere, dan
    weigert het register (409). Dezelfde inhoud als de laatste versie geeft die versie terug, zonder nieuwe."""
    t, v = db.werkplaats_onderdelen, db.werkplaats_versies
    try:
        async with db.get_engine().begin() as conn:
            o = (await conn.execute(select(t).where(t.c.id == onderdeel_id))).mappings().first()
            if o is None:
                raise _fout(404, "Onbekend onderdeel.")
            if o["ingetrokken_op"]:
                raise _fout(409, "Dit onderdeel is ingetrokken.")
            _weiger(o["soort"], o["naam"], bestanden)
            laatste = (await conn.execute(select(*_KOP).where(v.c.onderdeel_id == onderdeel_id)
                                          .order_by(v.c.nummer.desc()).limit(1))).mappings().first()
            if laatste["nummer"] != na_versie:
                raise _fout(409, f"Er is intussen versie {laatste['nummer']}; bouw daarop voort.")
            if laatste["hash"] == wp.hash_van(bestanden):
                return _versie(laatste, met_inhoud=False)
            if laatste["nummer"] >= wp.MAX_VERSIES:
                raise _fout(409, f"Dit onderdeel heeft het maximum van {wp.MAX_VERSIES} versies.")
            versie = await _schrijf_versie(conn, onderdeel_id, o["soort"], o["naam"], laatste["nummer"] + 1, bestanden,
                                           toelichting, laatste["basis_hash"] or "", door)
            await conn.execute(update(t).where(t.c.id == onderdeel_id).values(bijgewerkt=db.utcnow()))
            return versie
    except IntegrityError as exc:
        # Twee opslagen tegelijk op dezelfde versie: het unieke nummer laat er één door.
        raise _fout(409, "Er is intussen een nieuwere versie; bouw daarop voort.") from exc


async def _samenvatting(conn, rijen) -> list[dict[str, Any]]:
    """De onderdelen met hun aantal versies, hun laatste versie (zonder inhoud) en hoeveel andere concepten dezelfde
    soort en naam hebben."""
    if not rijen:
        return []
    t, v = db.werkplaats_onderdelen, db.werkplaats_versies
    ids = [r["id"] for r in rijen]
    versies: dict[str, list] = {}
    for r in (await conn.execute(select(*_KOP).where(v.c.onderdeel_id.in_(ids)).order_by(v.c.nummer))).mappings().all():
        versies.setdefault(r["onderdeel_id"], []).append(r)
    telling = {(r[0], r[1]): r[2] for r in (await conn.execute(
        select(t.c.soort, t.c.naam, func.count()).where(t.c.ingetrokken_op.is_(None)).group_by(t.c.soort, t.c.naam))).all()}
    uit = []
    for r in rijen:
        eigen = versies.get(r["id"], [])
        anderen = telling.get((r["soort"], r["naam"]), 0) - (0 if r["ingetrokken_op"] else 1)
        uit.append(_onderdeel(r, len(eigen), _versie(eigen[-1], met_inhoud=False) if eigen else None, max(anderen, 0)))
    return uit


async def lijst(userid: str, *, alles: bool, soort: str | None = None) -> list[dict[str, Any]]:
    """De eigen onderdelen en wat gedeeld is; met `alles` (een beheerder) elk onderdeel. Nieuwste eerst."""
    t = db.werkplaats_onderdelen
    vraag = select(t).order_by(t.c.bijgewerkt.desc(), t.c.id)
    if not alles:
        vraag = vraag.where((t.c.eigenaar == userid) | (t.c.gedeeld.is_(True) & t.c.ingetrokken_op.is_(None)))
    if soort:
        vraag = vraag.where(t.c.soort == soort)
    async with db.get_engine().connect() as conn:
        return await _samenvatting(conn, (await conn.execute(vraag)).mappings().all())


async def lees(onderdeel_id: str) -> dict[str, Any]:
    """Eén onderdeel met al zijn versies, zonder inhoud."""
    t, v = db.werkplaats_onderdelen, db.werkplaats_versies
    async with db.get_engine().connect() as conn:
        r = (await conn.execute(select(t).where(t.c.id == onderdeel_id))).mappings().first()
        if r is None:
            raise _fout(404, "Onbekend onderdeel.")
        [uit] = await _samenvatting(conn, [r])
        rijen = (await conn.execute(select(*_KOP).where(v.c.onderdeel_id == onderdeel_id).order_by(v.c.nummer))).mappings().all()
    return {**uit, "versielijst": [_versie(x, met_inhoud=False) for x in rijen]}


async def versie(onderdeel_id: str, nummer: int) -> dict[str, Any]:
    """Eén versie, met de bestanden en de bevindingen."""
    v = db.werkplaats_versies
    async with db.get_engine().connect() as conn:
        r = (await conn.execute(select(v).where(v.c.onderdeel_id == onderdeel_id, v.c.nummer == nummer))).mappings().first()
    if r is None:
        raise _fout(404, "Onbekende versie.")
    return _versie(r, met_inhoud=True)


def bruikbaar(versie: dict[str, Any], onderdeel: dict[str, Any]) -> bool:
    """Mag deze versie naar de proef of een PR? Alleen een geldige versie van een onderdeel dat niet is ingetrokken.
    De proef (B3) en de promotie (B4) vragen het hier; er is geen tweede regel."""
    return bool(versie["geldig"]) and onderdeel["stand"] != "ingetrokken"


async def trek_in(onderdeel_id: str, door: str) -> dict[str, Any]:
    t = db.werkplaats_onderdelen
    async with db.get_engine().begin() as conn:
        r = (await conn.execute(select(t).where(t.c.id == onderdeel_id))).mappings().first()
        if r is None:
            raise _fout(404, "Onbekend onderdeel.")
        if not r["ingetrokken_op"]:
            nu = db.utcnow()
            await conn.execute(update(t).where(t.c.id == onderdeel_id).values(
                ingetrokken_op=nu, ingetrokken_door=door, gedeeld=False, bijgewerkt=nu))
            await _audit(conn, onderdeel_id, "ingetrokken", door, eigenaar=r["eigenaar"])
    return await lees(onderdeel_id)


async def deel(onderdeel_id: str, gedeeld: bool, door: str) -> dict[str, Any]:
    """Een onderdeel delen voor de proef van anderen, of dat terugdraaien. Alleen een beheerder (de route toetst dat)."""
    t = db.werkplaats_onderdelen
    async with db.get_engine().begin() as conn:
        r = (await conn.execute(select(t).where(t.c.id == onderdeel_id))).mappings().first()
        if r is None:
            raise _fout(404, "Onbekend onderdeel.")
        if r["ingetrokken_op"]:
            raise _fout(409, "Dit onderdeel is ingetrokken.")
        if bool(r["gedeeld"]) != gedeeld:
            await conn.execute(update(t).where(t.c.id == onderdeel_id).values(gedeeld=gedeeld, bijgewerkt=db.utcnow()))
            await _audit(conn, onderdeel_id, "gedeeld" if gedeeld else "niet_gedeeld", door, eigenaar=r["eigenaar"])
    return await lees(onderdeel_id)


async def audit(onderdeel_id: str, limit: int = 100) -> list[dict[str, Any]]:
    a = db.werkplaats_audit
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(a).where(a.c.onderdeel_id == onderdeel_id)
                                    .order_by(a.c.id.desc()).limit(limit))).mappings().all()
    return [{"actie": r["actie"], "door": r["door"], "details": r["details"] or {}, "tijdstip": _tijd(r["tijdstip"])}
            for r in rijen]


async def beleid() -> dict[str, Any]:
    b = db.werkplaats_beleid
    async with db.get_engine().connect() as conn:
        r = (await conn.execute(select(b).where(b.c.id == 1))).mappings().first()
    if r is None:
        return {**BELEID, "door": "", "bijgewerkt": ""}
    return {"analist_mag_maken": bool(r["analist_mag_maken"]), "door": r["door"] or "", "bijgewerkt": _tijd(r["bijgewerkt"])}


async def zet_beleid(analist_mag_maken: bool, door: str) -> dict[str, Any]:
    b = db.werkplaats_beleid
    nu = db.utcnow()
    async with db.get_engine().begin() as conn:
        oud = (await conn.execute(select(b.c.analist_mag_maken).where(b.c.id == 1))).scalar()
        if oud is None:
            await conn.execute(insert(b).values(id=1, analist_mag_maken=analist_mag_maken, door=door, bijgewerkt=nu))
        elif bool(oud) != analist_mag_maken:
            await conn.execute(update(b).where(b.c.id == 1).values(analist_mag_maken=analist_mag_maken, door=door, bijgewerkt=nu))
        was = BELEID["analist_mag_maken"] if oud is None else bool(oud)
        if was != analist_mag_maken:
            await _audit(conn, "", "beleid", door, analist_mag_maken=analist_mag_maken, was=was)
    return await beleid()
