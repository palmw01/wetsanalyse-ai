"""Begrippen: opslag, koppelingen, actualiteit, de accorderingspoort en de export (spoor D, levering 2).

Een begrip hoort bij één werkgebied; het begrippenkader is impliciet (`urn:wa:kader:<werkgebied>`).

- **Eén schrijfpad** (`_gewijzigd`): eerst een rij-lock op het werkgebied, dan op het begrip – altijd
  in die volgorde, zodat er geen deadlock kan ontstaan. Het werkgebiedslot dekt ook de regel "één
  primaire duiding per element per werkgebied" bij gelijktijdige verzoeken. `verwachte_revisie` →
  412; daarna revisie +1, een volledige kopie in `begrip_revisies` en een regel in `werkgebied_audit`.
  De revisie van het werkgebied zelf blijft staan: die gaat over de scope.
- **Een geaccordeerd begrip dat verandert, is weer een concept.** Alleen accorderen zet de status
  op `geaccordeerd`; elke andere mutatie zet hem terug.
- **Een koppeling draagt haar bewijsstand.** Annotatie-elementen worden hard verwijderd; een
  koppeling cascadeert daar niet in mee, maar wordt bij het lezen `verdwenen`. De actualiteit komt
  uit Postgres, zonder graaf: `actueel`, `gewijzigd` (tekst, klasse of ankers anders, of het element
  verouderd), `verworpen` of `verdwenen`.
- **De poort** (`poort`) rekent de server; de werkplek toont dezelfde zinnen.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import annotatie_v2_store as annotaties, db
from .begrip_contracts import (
    BegripInhoud, BegripInvoer, BegripWijziging, KoppelInvoer, KoppelWijziging,
)
from .werkgebied_inventaris import inventaris
from .werkgebied_store import _audit as werkgebied_audit

Resolver = Callable[[dict], Awaitable[dict]]

BEOORDEELD = {"human_approved", "edited", "published"}
DRAGEND = {"duiding", "definitie"}


def kader_iri(werkgebied_id: str) -> str:
    return f"urn:wa:kader:{werkgebied_id}"


def begrip_iri(begrip_id: str) -> str:
    return f"urn:wa:begrip:{begrip_id}"


def element_hash(el: dict) -> str:
    """Wat een passage inhoudelijk is: tekst, klasse, subtype en ankers. Een oordeel van een jurist
    (de lifecycle) hoort er niet bij – een akkoord maakt een passage niet "gewijzigd"."""
    ankers = [{k: a.get(k) for k in ("bron_iri", "start", "eind", "tekst", "bron_hash")} for a in el.get("ankers", [])]
    return annotaties.digest({"tekst": el.get("tekst", ""), "klasse": el.get("klasse", ""),
                              "jas_subtype": el.get("jas_subtype", ""), "ankers": ankers})


# --- lezen ------------------------------------------------------------------------------------

def _koppeling(row) -> dict:
    return {"id": row.id, "begrip_id": row.begrip_id, "element_id": row.element_id, "rol": row.rol,
            "motivatie": row.motivatie, "bewijs": row.bewijs, "beoordeling": row.beoordeling,
            "beoordeeld_door": row.beoordeeld_door,
            "beoordeeld_op": db.aware(row.beoordeeld_op).isoformat() if row.beoordeeld_op else None,
            "toegevoegd_door": row.toegevoegd_door, "toegevoegd": db.aware(row.toegevoegd).isoformat()}


def actualiteit(k: dict, huidig: dict | None) -> dict:
    """De stand van de passage nu, naast de bewaarde bewijsstand."""
    if huidig is None:
        stand = "verdwenen"
    elif huidig.get("lifecycle") == "rejected":
        stand = "verworpen"
    elif huidig.get("verouderd") or element_hash(huidig) != k["bewijs"].get("element_hash"):
        stand = "gewijzigd"
    else:
        stand = "actueel"
    lifecycle = (huidig or {}).get("lifecycle")
    return {**k, "actualiteit": stand, "lifecycle_nu": lifecycle,
            "annotatie_beoordeeld": lifecycle in BEOORDEELD}


def _meervoud(n: int, een: str, meer: str) -> str:
    return een if n == 1 else meer.format(n=n)


def poort(inhoud: dict, koppelingen: list[dict]) -> dict:
    """Mag dit begrip geaccordeerd worden, en zo nee, waarom niet. `koppelingen` met actualiteit."""
    redenen = []
    if not inhoud.get("definitie", "").strip():
        redenen.append("Er is nog geen definitie.")
    if not inhoud.get("definitie_herkomst"):
        redenen.append("De herkomst van de definitie is niet gekozen.")
    if not inhoud.get("context", "").strip():
        redenen.append("De context ontbreekt.")
    dragend = [k for k in koppelingen if k["rol"] in DRAGEND and k["beoordeling"] != "afgewezen"]
    if not any(k["rol"] == "duiding" for k in dragend):
        redenen.append("Er is nog geen passage die dit begrip aanduidt.")
    open_ = sum(k["beoordeling"] == "open" for k in dragend)
    if open_:
        redenen.append(_meervoud(open_, "1 dragende koppeling is nog niet beoordeeld.",
                                 "{n} dragende koppelingen zijn nog niet beoordeeld."))
    niet_actueel = sum(k["actualiteit"] != "actueel" for k in dragend)
    if niet_actueel:
        redenen.append(_meervoud(niet_actueel, "1 dragende passage is gewijzigd, verworpen of verdwenen.",
                                 "{n} dragende passages zijn gewijzigd, verworpen of verdwenen."))
    onbeoordeeld = sum(k["actualiteit"] == "actueel" and not k["annotatie_beoordeeld"] for k in dragend)
    if onbeoordeeld:
        redenen.append(_meervoud(onbeoordeeld, "1 dragende annotatie is nog niet door een jurist beoordeeld.",
                                 "{n} dragende annotaties zijn nog niet door een jurist beoordeeld."))
    return {"mag": not redenen, "redenen": redenen}


async def _huidige_elementen(conn, ids: set[str]) -> dict[str, dict]:
    if not ids:
        return {}
    e = db.annotatie_v2_elementen
    rows = (await conn.execute(select(e.c.inhoud).where(e.c.id.in_(sorted(ids))))).scalars().all()
    return {v["id"]: v for v in rows}


async def _koppelingen_van(conn, werkgebied_id: str, begrip_id: str | None = None) -> list[dict]:
    k = db.begrip_koppelingen
    q = select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.verwijderd.is_(None))
    if begrip_id:
        q = q.where(k.c.begrip_id == begrip_id)
    rows = [_koppeling(r) for r in (await conn.execute(q.order_by(k.c.toegevoegd, k.c.id))).all()]
    huidig = await _huidige_elementen(conn, {r["element_id"] for r in rows})
    return [actualiteit(r, huidig.get(r["element_id"])) for r in rows]


def _aandacht(status: str, p: dict, koppelingen: list[dict]) -> list[str]:
    """Wat de lijst bij een begrip noemt. Bij een geaccordeerd begrip: alleen wat sindsdien veranderde."""
    if status == "geaccordeerd":
        weg = [k for k in koppelingen if k["rol"] in DRAGEND and k["beoordeling"] != "afgewezen"
               and k["actualiteit"] != "actueel"]
        return [_meervoud(len(weg), "Herbeoordelen: 1 dragende passage veranderde na het accorderen.",
                          "Herbeoordelen: {n} dragende passages veranderden na het accorderen.")] if weg else []
    return p["redenen"]


def _begrip(row, koppelingen: list[dict]) -> dict:
    p = poort(row.inhoud, koppelingen)
    return {"id": row.id, "iri": begrip_iri(row.id), "werkgebied_id": row.werkgebied_id,
            "kader_iri": kader_iri(row.werkgebied_id), "status": row.status, "revisie": row.revisie,
            "inhoud": row.inhoud, "aangemaakt_door": row.aangemaakt_door,
            "aangemaakt": db.aware(row.aangemaakt).isoformat(), "gewijzigd": db.aware(row.gewijzigd).isoformat(),
            "geaccordeerd_door": row.geaccordeerd_door,
            "geaccordeerd_op": db.aware(row.geaccordeerd_op).isoformat() if row.geaccordeerd_op else None,
            "geaccordeerd_revisie": row.geaccordeerd_revisie,
            "koppelingen": koppelingen, "accorderen": p, "aandachtspunten": _aandacht(row.status, p, koppelingen)}


async def _werkgebied_bestaat(conn, werkgebied_id: str, slot: bool = False):
    t = db.werkgebieden
    q = select(t).where(t.c.id == werkgebied_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None or row.gearchiveerd is not None:
        raise HTTPException(404, "Werkgebied bestaat niet.")
    return row


async def haal(werkgebied_id: str, begrip_id: str) -> dict:
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                                  b.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Begrip bestaat niet.")
        return _begrip(row, await _koppelingen_van(conn, werkgebied_id, begrip_id))


async def lijst(werkgebied_id: str) -> list[dict]:
    """De begrippen van het werkgebied, zonder de koppelingen zelf (wel tellingen en aandacht)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        rows = (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.verwijderd.is_(None))
                                   .order_by(b.c.aangemaakt, b.c.id))).all()
        alle = await _koppelingen_van(conn, werkgebied_id)
    uit = []
    for row in rows:
        ks = [k for k in alle if k["begrip_id"] == row.id]
        volledig = _begrip(row, ks)
        uit.append({**{k: v for k, v in volledig.items() if k != "koppelingen"},
                    "aantal_koppelingen": len(ks),
                    "element_ids": sorted({k["element_id"] for k in ks})})
    return uit


async def primaire_duidingen(werkgebied_id: str) -> dict[str, dict]:
    """Per element het begrip dat het primair aanduidt – voor de inventaris in de werkplek."""
    k, b = db.begrip_koppelingen, db.begrippen
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(k.c.element_id, b.c.id, b.c.inhoud).join_from(k, b, k.c.begrip_id == b.c.id)
                                   .where(k.c.werkgebied_id == werkgebied_id, k.c.rol == "duiding",
                                          k.c.verwijderd.is_(None), b.c.verwijderd.is_(None)))).all()
    return {r.element_id: {"begrip_id": r.id, "naam": r.inhoud.get("naam", "")} for r in rows}


async def revisies(werkgebied_id: str, begrip_id: str, limit: int = 100) -> list[dict]:
    await haal(werkgebied_id, begrip_id)
    r = db.begrip_revisies
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(r).where(r.c.begrip_id == begrip_id)
                                   .order_by(r.c.revisie.desc()).limit(limit))).all()
    return [{"revisie": x.revisie, "actie": x.actie, "detail": x.detail, "status": x.status, "inhoud": x.inhoud,
             "actor": x.actor, "tijdstip": db.aware(x.tijdstip).isoformat()} for x in rows]


# --- bewijs vastleggen -------------------------------------------------------------------------

async def bewijzen(werkgebied: dict, element_ids: list[str], resolve: Resolver) -> dict[str, dict]:
    """De bewijsstand per element. Alleen elementen uit de inventaris van dit werkgebied: actueel,
    niet verworpen en binnen de selecties (een contextbron mag). Gelezen vóór de schrijftransactie,
    want de inventaris vraagt de graaf."""
    inv = await inventaris(werkgebied["bronnen"], resolve)
    per_id = {e["id"]: e for e in inv["elementen"]}
    labels = {s["id"]: s["label"] or s["bron_iri"] for s in inv["selecties"]}
    sel_iri = {s["id"]: s["bron_iri"] for s in inv["selecties"]}
    onbekend = [i for i in element_ids if i not in per_id]
    if onbekend:
        raise HTTPException(422, {"fout": "element_buiten_werkgebied", "element_ids": onbekend,
                                  "melding": "Niet elk element valt binnen dit werkgebied, of het is verworpen "
                                             "of bestaat niet meer."})
    uit = {}
    for eid in dict.fromkeys(element_ids):
        inv_el = per_id[eid]
        detail = await annotaties.detail(eid)
        el = detail["element"]
        sel = inv_el["selecties"][0]
        knoop = next((n for n in detail["bronnen"] if n["bron_iri"] == el["eigenaar_iri"]), None)
        vindplaats = labels[sel] if el["eigenaar_iri"] == sel_iri[sel] or not knoop \
            else f"{labels[sel]} · {knoop.get('label', '')}"
        uit[eid] = {"tekst": el.get("tekst", ""), "klasse": el.get("klasse", ""),
                    "jas_subtype": el.get("jas_subtype", ""), "ankers": el.get("ankers", []),
                    "eigenaar_iri": el["eigenaar_iri"], "laag_id": el.get("laag_id", ""),
                    "snapshot_id": el.get("snapshot_id", detail.get("snapshot_id", "")),
                    "lifecycle": el.get("lifecycle", ""), "vindplaats": vindplaats,
                    "element_hash": element_hash(el)}
    return uit


# --- schrijven ---------------------------------------------------------------------------------

@asynccontextmanager
async def _gewijzigd(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str, actie: str, detail: dict):
    """Werkgebiedslot, begripslot, revisietoets; daarna revisie +1, revisiekopie en audit.

    De aanroeper muteert via `stand`: `inhoud` en `status` en extra kolommen in `waarden`. Zet hij
    `geen_wijziging`, dan gebeurt er niets (idempotent). `detail` wordt pas ná het blok gelezen, dus
    de aanroeper mag het daarin nog aanvullen."""
    b = db.begrippen
    async with db.get_engine().begin() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                                  b.c.verwijderd.is_(None)).with_for_update())).first()
        if row is None:
            raise HTTPException(404, "Begrip bestaat niet.")
        if row.revisie != verwacht:
            raise HTTPException(412, {"fout": "revisie_conflict", "revisie": row.revisie})
        stand = {"inhoud": row.inhoud, "status": None, "waarden": {}, "geen_wijziging": False}
        yield conn, row, stand
        if stand["geen_wijziging"]:
            return
        status = stand["status"] or ("concept" if row.status == "geaccordeerd" else row.status)
        nieuw, nu = row.revisie + 1, db.utcnow()
        await conn.execute(update(b).where(b.c.id == begrip_id).values(
            revisie=nieuw, gewijzigd=nu, status=status, inhoud=stand["inhoud"], **stand["waarden"]))
        await _revisieregel(conn, begrip_id, nieuw, actie, detail, status, stand["inhoud"], actor, nu)
        await werkgebied_audit(conn, werkgebied_id, actor, actie,
                               {**detail, "begrip_id": begrip_id, "begrip_revisie": nieuw})


async def _revisieregel(conn, begrip_id, revisie, actie, detail, status, inhoud, actor, tijdstip):
    await conn.execute(insert(db.begrip_revisies).values(
        begrip_id=begrip_id, revisie=revisie, actie=actie, detail=detail, status=status, inhoud=inhoud,
        actor=actor, tijdstip=tijdstip))


async def _koppel(conn, werkgebied_id: str, begrip_id: str, bewijs: dict[str, dict], rol: str,
                  motivatie: str, actor: str) -> list[str]:
    """Voegt de koppelingen toe die er nog niet zijn; geeft de nieuwe element-id's terug. Draait onder
    het werkgebiedslot: daarop rust de regel van één primaire duiding per element."""
    k = db.begrip_koppelingen
    bestaand = set((await conn.execute(select(k.c.element_id).where(
        k.c.begrip_id == begrip_id, k.c.rol == rol, k.c.verwijderd.is_(None)))).scalars().all())
    nieuw = [eid for eid in bewijs if eid not in bestaand]
    if rol == "duiding" and nieuw:
        await _toets_primair(conn, werkgebied_id, begrip_id, nieuw)
    nu = db.utcnow()
    for eid in nieuw:
        await conn.execute(insert(k).values(
            id=str(uuid.uuid4()), begrip_id=begrip_id, werkgebied_id=werkgebied_id, element_id=eid, rol=rol,
            motivatie=motivatie, bewijs=bewijs[eid], beoordeling="open", toegevoegd_door=actor, toegevoegd=nu))
    return nieuw


async def maak(werkgebied: dict, invoer: BegripInvoer, actor: str, resolve: Resolver) -> dict:
    bewijs = await bewijzen(werkgebied, invoer.element_ids, resolve) if invoer.element_ids else {}
    bid, nu = str(uuid.uuid4()), db.utcnow()
    inhoud = invoer.inhoud.model_dump(mode="json")
    async with db.get_engine().begin() as conn:
        await _werkgebied_bestaat(conn, werkgebied["id"], slot=True)
        await conn.execute(insert(db.begrippen).values(
            id=bid, werkgebied_id=werkgebied["id"], status="concept", revisie=1, inhoud=inhoud,
            aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
        nieuw = await _koppel(conn, werkgebied["id"], bid, bewijs, invoer.rol.value, "", actor)
        detail = {"naam": inhoud["naam"], "element_ids": nieuw, "rol": invoer.rol.value}
        await _revisieregel(conn, bid, 1, "begrip-aangemaakt", detail, "concept", inhoud, actor, nu)
        await werkgebied_audit(conn, werkgebied["id"], actor, "begrip-aangemaakt",
                               {**detail, "begrip_id": bid, "begrip_revisie": 1})
    return await haal(werkgebied["id"], bid)


async def wijzig(werkgebied_id: str, begrip_id: str, w: BegripWijziging, actor: str) -> dict:
    nieuw = w.inhoud.model_dump(mode="json")
    # `_gewijzigd` leest `detail` pas na het blok: de velden zijn pas onder het slot bekend.
    detail: dict = {}
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "begrip-gewijzigd",
                          detail) as (_, row, stand):
        detail["velden"] = sorted(k for k in nieuw if nieuw.get(k) != row.inhoud.get(k))
        stand["inhoud"] = nieuw
        stand["geen_wijziging"] = not detail["velden"]
    return await haal(werkgebied_id, begrip_id)


async def verwijder(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    """Soft: het begrip en zijn koppelingen krijgen een tijdstip; de annotaties blijven onaangeroerd.
    Daarmee is een primaire duiding weer vrij."""
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "begrip-verwijderd", {}) as (conn, _, stand):
        nu = db.utcnow()
        stand["waarden"] = {"verwijderd": nu}
        await conn.execute(update(db.begrip_koppelingen).where(
            db.begrip_koppelingen.c.begrip_id == begrip_id, db.begrip_koppelingen.c.verwijderd.is_(None))
            .values(verwijderd=nu))
    return {"verwijderd": begrip_id}


async def koppel(werkgebied: dict, begrip_id: str, invoer: KoppelInvoer, actor: str, resolve: Resolver) -> dict:
    bewijs = await bewijzen(werkgebied, invoer.element_ids, resolve)
    detail = {"rol": invoer.rol.value}
    async with _gewijzigd(werkgebied["id"], begrip_id, invoer.verwachte_revisie, actor, "begrip-gekoppeld",
                          detail) as (conn, _, stand):
        nieuw = await _koppel(conn, werkgebied["id"], begrip_id, bewijs, invoer.rol.value, invoer.motivatie, actor)
        detail["element_ids"] = nieuw
        stand["geen_wijziging"] = not nieuw
    return await haal(werkgebied["id"], begrip_id)


async def wijzig_koppeling(werkgebied_id: str, begrip_id: str, koppeling_id: str, w: KoppelWijziging,
                           actor: str) -> dict:
    k = db.begrip_koppelingen
    velden = {f: (v.value if hasattr(v, "value") else v) for f in ("rol", "motivatie", "beoordeling")
              if (v := getattr(w, f)) is not None}
    detail = {"koppeling": koppeling_id, "velden": sorted(velden)}
    if "beoordeling" in velden:
        detail["beoordeling"] = velden["beoordeling"]
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "koppeling-gewijzigd",
                          detail) as (conn, _, stand):
        row = (await conn.execute(select(k).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                                  k.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Koppeling bestaat niet.")
        if velden.get("rol") == "duiding" and row.rol != "duiding":
            # Dezelfde regel als bij koppelen: hooguit één primaire duiding per element.
            await _toets_primair(conn, werkgebied_id, begrip_id, [row.element_id])
        if "beoordeling" in velden:
            velden.update(beoordeeld_door=actor, beoordeeld_op=db.utcnow())
        if not velden:
            stand["geen_wijziging"] = True
        else:
            await conn.execute(update(k).where(k.c.id == koppeling_id).values(**velden))
    return await haal(werkgebied_id, begrip_id)


async def _toets_primair(conn, werkgebied_id: str, begrip_id: str, element_ids: list[str]) -> None:
    """Hooguit één primaire duiding per element per werkgebied. Draait onder het werkgebiedslot."""
    k, b = db.begrip_koppelingen, db.begrippen
    elders = (await conn.execute(select(k.c.element_id, b.c.id, b.c.inhoud).join_from(k, b, k.c.begrip_id == b.c.id)
                                 .where(k.c.werkgebied_id == werkgebied_id, k.c.rol == "duiding",
                                        k.c.verwijderd.is_(None), k.c.begrip_id != begrip_id,
                                        k.c.element_id.in_(element_ids)))).first()
    if elders is not None:
        naam = elders.inhoud.get("naam", "")
        raise HTTPException(409, {"fout": "al_primair", "element_id": elders.element_id, "begrip_id": elders.id,
                                  "begrip_naam": naam,
                                  "melding": f"Dit element duidt al het begrip \"{naam}\" aan. Koppel het hier "
                                             f"als definitie of context, of wijzig het daar."})


async def ontkoppel(werkgebied_id: str, begrip_id: str, koppeling_id: str, verwacht: int, actor: str) -> dict:
    k = db.begrip_koppelingen
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "koppeling-verwijderd",
                          {"koppeling": koppeling_id}) as (conn, _, __):
        row = (await conn.execute(select(k.c.id).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                                       k.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Koppeling bestaat niet.")
        await conn.execute(update(k).where(k.c.id == koppeling_id).values(verwijderd=db.utcnow()))
    return await haal(werkgebied_id, begrip_id)


async def accordeer(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "begrip-geaccordeerd", {}) as (conn, row, stand):
        p = poort(row.inhoud, await _koppelingen_van(conn, werkgebied_id, begrip_id))
        if not p["mag"]:
            raise HTTPException(409, {"fout": "poort", "redenen": p["redenen"],
                                      "melding": "Nog niet te accorderen: " + " ".join(p["redenen"])})
        stand["status"] = "geaccordeerd"
        stand["waarden"] = {"geaccordeerd_door": actor, "geaccordeerd_op": db.utcnow(),
                            "geaccordeerd_revisie": row.revisie + 1}
    return await haal(werkgebied_id, begrip_id)


async def heropen(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "begrip-heropend", {}) as (_, row, stand):
        if row.status != "geaccordeerd":
            raise HTTPException(409, "Het begrip is niet geaccordeerd.")
        stand["status"] = "concept"
    return await haal(werkgebied_id, begrip_id)


# --- export ------------------------------------------------------------------------------------

EXPORT_SCHEMA = "begrippen-export-v1"
_KOLOMMEN = ["begrip_iri", "begrip", "status", "revisie", "definitie", "definitie_herkomst", "context",
             "jas_klasse", "alternatieve_termen", "rol", "beoordeling", "actualiteit", "annotatie_beoordeeld",
             "passage", "klasse_passage", "vindplaats", "bron_iri", "element_id", "motivatie"]


def _cel(value) -> str:
    # Zelfde verdediging als de annotatie-export: een voorloopapostrof houdt een formule tegen.
    value = str(value)
    return "'" + value if value[:1] in {"=", "+", "-", "@", "\t", "\r"} else value


async def export(werkgebied_id: str, actor: str) -> dict:
    wg = (await _lees_werkgebied(werkgebied_id))
    begrippen = [await haal(werkgebied_id, b["id"]) for b in await lijst(werkgebied_id)]
    return {"schema": EXPORT_SCHEMA, "kader_iri": kader_iri(werkgebied_id),
            "werkgebied": {"id": wg.id, "naam": wg.naam, "analysevraag": wg.analysevraag},
            "export": {"actor": actor, "op": db.utcnow().isoformat()},
            "toelichting": "Begrippen zijn analyse-uitkomsten van dit werkgebied, geen wettelijke definities.",
            "begrippen": begrippen}


async def _lees_werkgebied(werkgebied_id: str):
    async with db.get_engine().connect() as conn:
        return await _werkgebied_bestaat(conn, werkgebied_id)


def json_export(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode()


def csv_export(data: dict) -> bytes:
    """Eén rij per koppeling, zodat elke passage een eigen vindplaats heeft; een begrip zonder
    koppelingen krijgt één rij zonder passage."""
    tekst = io.StringIO()
    w = csv.writer(tekst)
    w.writerow(_KOLOMMEN)
    for b in data["begrippen"]:
        i = b["inhoud"]
        kop = [b["iri"], i["naam"], b["status"], b["revisie"], i.get("definitie", ""),
               i.get("definitie_herkomst") or "", i.get("context", ""), i.get("jas_klasse", ""),
               "; ".join(i.get("alternatieve_termen", []))]
        if not b["koppelingen"]:
            w.writerow([_cel(v) for v in kop] + [""] * (len(_KOLOMMEN) - len(kop)))
        for k in b["koppelingen"]:
            bron = k["bewijs"].get("ankers", [{}])[0].get("bron_iri", "") if k["bewijs"].get("ankers") \
                else k["bewijs"].get("eigenaar_iri", "")
            w.writerow([_cel(v) for v in kop + [
                k["rol"], k["beoordeling"], k["actualiteit"], "ja" if k["annotatie_beoordeeld"] else "nee",
                k["bewijs"].get("tekst", ""), k["bewijs"].get("klasse", ""), k["bewijs"].get("vindplaats", ""),
                bron, k["element_id"], k["motivatie"]]])
    return tekst.getvalue().encode("utf-8-sig")
