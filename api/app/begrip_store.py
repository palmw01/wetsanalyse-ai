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
from sqlalchemy import delete, insert, select, update

from . import annotatie_v2_store as annotaties, db
from .begrip_contracts import (
    BegripInhoud, BegripInvoer, BegripWijziging, KoppelInvoer, KoppelWijziging,
)
from .werkgebied_inventaris import inventaris
from .werkgebied_store import _audit as werkgebied_audit, niet_gevonden

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
            "toegevoegd_door": row.toegevoegd_door, "toegevoegd": db.aware(row.toegevoegd).isoformat(),
            "bevestigingen": row.bevestigingen or []}


def referentie_hash(k: dict) -> str:
    """De stand waartegen de actualiteit rekent: de nieuwste bevestiging (fase F1), anders het bewijs
    van het koppelen. Het bewijs zelf verandert nooit."""
    bev = k.get("bevestigingen") or []
    return bev[-1]["element_hash"] if bev else k["bewijs"].get("element_hash", "")


def actualiteit(k: dict, huidig: dict | None) -> dict:
    """De stand van de passage nu, naast de bewaarde bewijsstand."""
    if huidig is None:
        stand = "verdwenen"
    elif huidig.get("lifecycle") == "rejected":
        stand = "verworpen"
    elif huidig.get("verouderd") or element_hash(huidig) != referentie_hash(k):
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
    if not inhoud.get("context", "").strip():
        redenen.append("De toelichting ontbreekt.")
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
    # Wat een koppeling verving (herkoppelen, fase F1): de oude bewijsstand blijft zo bij de nieuwe te lezen.
    vervangen = {r.vervangen_door: r for r in (await conn.execute(select(k).where(
        k.c.vervangen_door.in_([r["id"] for r in rows])))).all()} if rows else {}
    for r in rows:
        if (oud := vervangen.get(r["id"])) is not None:
            r["vervangt"] = {"koppeling_id": oud.id, "element_id": oud.element_id, "bewijs": oud.bewijs,
                             "vervangen_op": db.aware(oud.verwijderd).isoformat() if oud.verwijderd else None}
    huidig = await _huidige_elementen(conn, {r["element_id"] for r in rows})
    return [actualiteit(r, huidig.get(r["element_id"])) for r in rows]


def _aandacht(status: str, p: dict, koppelingen: list[dict]) -> list[str]:
    """Wat de lijst bij een begrip noemt. Bij een geaccordeerd begrip: alleen wat sindsdien veranderde."""
    if status == "geaccordeerd":
        dragend = [k for k in koppelingen if k["rol"] in DRAGEND and k["beoordeling"] != "afgewezen"]
        weg = [k for k in dragend if k["actualiteit"] != "actueel"]
        uit = [_meervoud(len(weg), "Herbeoordelen: 1 dragende passage veranderde na het accorderen.",
                         "Herbeoordelen: {n} dragende passages veranderden na het accorderen.")] if weg else []
        # Na herkoppelen (fase F1) kan een dragende passage op een nog niet beoordeelde annotatie rusten.
        open_ = sum(k["actualiteit"] == "actueel" and not k["annotatie_beoordeeld"] for k in dragend)
        if open_:
            uit.append(_meervoud(open_, "1 dragende annotatie is nog niet door een jurist beoordeeld.",
                                 "{n} dragende annotaties zijn nog niet door een jurist beoordeeld."))
        return uit
    return p["redenen"]


def _begrip(row, koppelingen: list[dict], opvolging: dict | None = None) -> dict:
    p = poort(row.inhoud, koppelingen)
    o = (opvolging or {}).get(row.id, {})
    return {"id": row.id, "iri": begrip_iri(row.id), "werkgebied_id": row.werkgebied_id,
            "kader_iri": kader_iri(row.werkgebied_id), "status": row.status, "revisie": row.revisie,
            "inhoud": slank(row.inhoud), "aangemaakt_door": row.aangemaakt_door,
            "aangemaakt": db.aware(row.aangemaakt).isoformat(), "gewijzigd": db.aware(row.gewijzigd).isoformat(),
            "geaccordeerd_door": row.geaccordeerd_door,
            "geaccordeerd_op": db.aware(row.geaccordeerd_op).isoformat() if row.geaccordeerd_op else None,
            "geaccordeerd_revisie": row.geaccordeerd_revisie,
            "koppelingen": koppelingen, "accorderen": p,
            "aandachtspunten": [] if row.status == "vervangen" else _aandacht(row.status, p, koppelingen),
            # Opvolging (fase F2): door welk begrip dit vervangen is, en welke dit vervangt.
            "vervangen_door": o.get("vervangen_door"), "vervangt": o.get("vervangt", [])}


async def _opvolging(conn, werkgebied_id: str) -> dict[str, dict]:
    """Per begrip `vervangen_door` en `vervangt` ({begrip_id, naam, reden}) uit de opvolgingsrelaties."""
    r, b = db.begrip_relaties, db.begrippen
    rows = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.type == "opvolging",
                                               r.c.verwijderd.is_(None)))).all()
    if not rows:
        return {}
    namen = {x.id: x.inhoud.get("naam", "") for x in (await conn.execute(select(b.c.id, b.c.inhoud).where(
        b.c.id.in_({x.van_begrip for x in rows} | {x.naar_begrip for x in rows})))).all()}
    uit: dict[str, dict] = {}
    for x in rows:
        uit.setdefault(x.van_begrip, {})["vervangen_door"] = {"begrip_id": x.naar_begrip,
                                                               "naam": namen.get(x.naar_begrip, ""),
                                                               "reden": x.toelichting}
        uit.setdefault(x.naar_begrip, {}).setdefault("vervangt", []).append(
            {"begrip_id": x.van_begrip, "naam": namen.get(x.van_begrip, ""), "reden": x.toelichting})
    return uit


async def _werkgebied_bestaat(conn, werkgebied_id: str, slot: bool = False):
    t = db.werkgebieden
    q = select(t).where(t.c.id == werkgebied_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None or row.gearchiveerd is not None:
        raise await niet_gevonden(werkgebied_id)
    return row


async def definitie_onderbouwing(conn, begrip_id: str, inhoud: dict) -> dict | None:
    """Waarop de huidige definitie rust (spoor M), afgeleid en alleen gelezen: het voorstel achter de
    revisie die deze definitie zette (`begrip_revisies.detail.voorstel_id`), met zijn fragmenten, de
    vindplaats van een brondefinitie, de duiding en het onderzoek van de run. Komt de definitie uit een
    groep van de keten (overnemen of akkoord), dan staat de onderbouwing bevroren in het revisiedetail
    (`onderbouwing`). `inhoud` blijft slank. None als de definitie niet (ongewijzigd) uit een voorstel
    of groep komt: met de hand geschreven of aangepast bij het overnemen."""
    definitie = (inhoud.get("definitie") or "").strip()
    if not definitie:
        return None
    r, v, k = db.begrip_revisies, db.begrip_voorstellen, db.begrip_kaartruns
    revisies = (await conn.execute(select(r.c.detail, r.c.inhoud).where(r.c.begrip_id == begrip_id)
                                   .order_by(r.c.revisie.desc()))).all()
    for x in revisies:
        if (x.inhoud or {}).get("definitie", "").strip() != definitie:
            break                                       # vóór deze revisie was het een andere definitie
        d = x.detail or {}
        if d.get("onderbouwing"):
            o = d["onderbouwing"]
            return {**o, "fragmenten": [{**f, "rol": "ondersteunend"} for f in o.get("fragmenten") or []]}
        if d.get("voorstel_id") and d.get("veld") == "definitie":
            if d.get("aangepast"):
                return None
            vrow = (await conn.execute(select(v.c.id, v.c.run_id, v.c.actie, v.c.waarde)
                                       .where(v.c.id == d["voorstel_id"]))).first()
            if vrow is None:
                return None
            krow = (await conn.execute(select(k.c.invoer).where(k.c.id == vrow.run_id))).first()
            w = vrow.waarde or {}
            return {"voorstel_id": vrow.id, "actie": vrow.actie, "herkomst": w.get("herkomst", ""),
                    "definitie_bron_iri": w.get("definitie_bron_iri", ""),
                    "definitie_vindplaats": w.get("definitie_vindplaats", ""),
                    "fragmenten": [{"bron_iri": f["bron_iri"], "start": f["start"], "eind": f["eind"],
                                    "tekst": f["tekst"], "rol": "ondersteunend"} for f in w.get("fragmenten") or []],
                    "duiding": w.get("duiding"),
                    "onderzoek_id": ((krow.invoer if krow else {}) or {}).get("onderzoek_id", "")}
    return None


async def haal(werkgebied_id: str, begrip_id: str) -> dict:
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                                  b.c.verwijderd.is_(None)))).first()
        if row is None:
            raise await niet_gevonden(werkgebied_id, begrip_id)
        uit = _begrip(row, await _koppelingen_van(conn, werkgebied_id, begrip_id), await _opvolging(conn, werkgebied_id))
        uit["definitie_onderbouwing"] = await definitie_onderbouwing(conn, begrip_id, row.inhoud)
        return uit


async def lijst(werkgebied_id: str) -> list[dict]:
    """De begrippen van het werkgebied, zonder de koppelingen zelf (wel tellingen en aandacht)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        rows = (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.verwijderd.is_(None))
                                   .order_by(b.c.aangemaakt, b.c.id))).all()
        alle = await _koppelingen_van(conn, werkgebied_id)
        opvolging = await _opvolging(conn, werkgebied_id)
    uit = []
    for row in rows:
        ks = [k for k in alle if k["begrip_id"] == row.id]
        volledig = _begrip(row, ks, opvolging)
        uit.append({**{k: v for k, v in volledig.items() if k != "koppelingen"},
                    "aantal_koppelingen": len(ks),
                    "element_ids": sorted({k["element_id"] for k in ks})})
    return uit


async def samenhang(werkgebied_id: str) -> dict:
    """Begrippen en hun koppelingen, zonder bewijs: wat de samenhangsgraaf tekent (fase F3)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id)
        rows = (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id, b.c.verwijderd.is_(None))
                                   .order_by(b.c.aangemaakt, b.c.id))).all()
        koppelingen = await _koppelingen_van(conn, werkgebied_id)
    return {"begrippen": [{"id": r.id, "iri": begrip_iri(r.id), "naam": r.inhoud.get("naam", ""), "status": r.status,
                           "definitie": r.inhoud.get("definitie", "")} for r in rows],
            "koppelingen": [{"begrip_id": k["begrip_id"], "element_id": k["element_id"], "rol": k["rol"],
                             "beoordeling": k["beoordeling"], "actualiteit": k["actualiteit"]} for k in koppelingen]}


async def primaire_duidingen(werkgebied_id: str) -> dict[str, dict]:
    """Per element het begrip dat het primair aanduidt – voor de inventaris in de werkplek."""
    k, b = db.begrip_koppelingen, db.begrippen
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(k.c.element_id, b.c.id, b.c.inhoud).join_from(k, b, k.c.begrip_id == b.c.id)
                                   .where(k.c.werkgebied_id == werkgebied_id, k.c.rol == "duiding",
                                          k.c.verwijderd.is_(None), b.c.verwijderd.is_(None),
                                          b.c.status != "vervangen"))).all()
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
async def _gewijzigd(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str, actie: str, detail: dict,
                     mag_vervangen: bool = False):
    """Werkgebiedslot, begripslot, revisietoets; daarna revisie +1, revisiekopie en audit.

    De aanroeper muteert via `stand`: `inhoud` en `status` en extra kolommen in `waarden`. Zet hij
    `geen_wijziging`, dan gebeurt er niets (idempotent). `detail` wordt pas ná het blok gelezen, dus
    de aanroeper mag het daarin nog aanvullen."""
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, actie, detail,
                                 mag_vervangen) as uit:
            yield uit


@asynccontextmanager
async def _gewijzigd_in(conn, werkgebied_id: str, begrip_id: str, verwacht: int, actor: str, actie: str,
                        detail: dict, mag_vervangen: bool = False):
    """`_gewijzigd` binnen een transactie van de aanroeper: zo kan een besluit over een voorstel (fase D)
    begrip, koppelingen, accorderen en groepsbesluit samen vastleggen of samen laten mislukken."""
    b = db.begrippen
    await _werkgebied_bestaat(conn, werkgebied_id, slot=True)
    row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                              b.c.verwijderd.is_(None)).with_for_update())).first()
    if row is None:
        raise HTTPException(404, "Begrip bestaat niet.")
    if row.status == "vervangen" and not mag_vervangen:
        raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger en "
                                  "is alleen nog te lezen. Verwijder de opvolger om het terug te zetten."})
    if row.revisie != verwacht:
        raise HTTPException(412, {"fout": "revisie_conflict", "revisie": row.revisie,
                                  "melding": "Iemand anders wijzigde dit begrip intussen; laad het opnieuw."})
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
                  motivatie: str, actor: str, beoordeling: str = "open") -> list[str]:
    """Voegt de koppelingen toe die er nog niet zijn; geeft de nieuwe element-id's terug. Draait onder
    het werkgebiedslot: daarop rust de regel van één primaire duiding per element.

    `beoordeling: akkoord` alleen als de jurist de passages zelf zag en goedkeurde: het akkoord op een
    voorstel van Lex (fase D) – dan staat de beoordelaar er meteen bij."""
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
            motivatie=motivatie, bewijs=bewijs[eid], beoordeling=beoordeling, toegevoegd_door=actor, toegevoegd=nu,
            **({"beoordeeld_door": actor, "beoordeeld_op": nu} if beoordeling != "open" else {})))
    return nieuw


#: Wat een begrip vóór spoor I1 nog meer droeg; het valt bij het lezen weg (er staat geen te behouden
#: data op Azure, dus geen migratie).
VERVALLEN = ("jas_klasse", "jas_subtype", "begripstype", "geldigheid", "eigenschappen", "onderbouwing",
             "open_vragen")


def slank(inhoud: dict) -> dict:
    """De inhoud zonder de velden die vervielen, en voorbeelden zonder toelichting."""
    uit = {k: v for k, v in (inhoud or {}).items() if k not in VERVALLEN}
    if "voorbeelden" in uit:
        uit["voorbeelden"] = [{k: v for k, v in x.items() if k != "toelichting"} for x in uit["voorbeelden"] or []]
    return uit


def met_afgeleid(oud: dict | None, nieuw: dict) -> dict:
    """Herkomst en `definitie_door` rekent de api, nooit de client (spoor I1: geen keuzerondjes meer).
    Een ongewijzigde definitie houdt haar herkomst en wie ze voorstelde; een nieuwe of andere tekst is
    door de analist geformuleerd; geen definitie = geen herkomst. Letterlijk wordt een definitie alleen
    door een overgenomen brondefinitie (`begrip_voorstel_store`, het akkoord in `begrippen_run_store`)."""
    tekst = (nieuw.get("definitie") or "").strip()
    if not tekst:
        herkomst, door = None, ""
    elif oud is not None and (oud.get("definitie") or "").strip() == tekst and oud.get("definitie_herkomst"):
        herkomst, door = oud["definitie_herkomst"], oud.get("definitie_door") or ""
    else:
        herkomst, door = "geformuleerd", "analist"
    return {**nieuw, "definitie_herkomst": herkomst, "definitie_door": door}


async def maak(werkgebied: dict, invoer: BegripInvoer, actor: str, resolve: Resolver) -> dict:
    bewijs = await bewijzen(werkgebied, invoer.element_ids, resolve) if invoer.element_ids else {}
    async with db.get_engine().begin() as conn:
        bid = await maak_in(conn, werkgebied["id"], met_afgeleid(None, invoer.inhoud.model_dump(mode="json")), bewijs,
                            invoer.rol.value, actor)
    return await haal(werkgebied["id"], bid)


async def maak_in(conn, werkgebied_id: str, inhoud: dict, bewijs: dict[str, dict], rol: str, actor: str,
                  beoordeling: str = "open", onderbouwing: dict | None = None) -> str:
    """Een nieuw begrip (revisie 1, concept) binnen de transactie van de aanroeper; geeft het id.
    `onderbouwing` (een groep van de keten) gaat in het revisiedetail, waar `definitie_onderbouwing` haar leest."""
    bid, nu = str(uuid.uuid4()), db.utcnow()
    await _werkgebied_bestaat(conn, werkgebied_id, slot=True)
    await conn.execute(insert(db.begrippen).values(
        id=bid, werkgebied_id=werkgebied_id, status="concept", revisie=1, inhoud=inhoud,
        aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
    nieuw = await _koppel(conn, werkgebied_id, bid, bewijs, rol, "", actor, beoordeling)
    detail = {"naam": inhoud["naam"], "element_ids": nieuw, "rol": rol,
              **({"beoordeling": beoordeling} if beoordeling != "open" else {})}
    await _revisieregel(conn, bid, 1, "begrip-aangemaakt",
                        {**detail, **({"onderbouwing": onderbouwing} if onderbouwing else {})}, "concept", inhoud,
                        actor, nu)
    await werkgebied_audit(conn, werkgebied_id, actor, "begrip-aangemaakt",
                           {**detail, "begrip_id": bid, "begrip_revisie": 1})
    return bid


async def wijzig(werkgebied_id: str, begrip_id: str, w: BegripWijziging, actor: str) -> dict:
    nieuw = w.inhoud.model_dump(mode="json")
    # `_gewijzigd` leest `detail` pas na het blok: de velden zijn pas onder het slot bekend.
    detail: dict = {}
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "begrip-gewijzigd",
                          detail) as (_, row, stand):
        oud = slank(row.inhoud)
        nieuw = met_afgeleid(oud, nieuw)
        # Herkomst en `definitie_door` volgen uit de definitie en zijn dus geen eigen wijziging (een
        # begrip van vóór fase E mist het veld; opslaan zonder wijziging mag daar geen revisie van maken).
        detail["velden"] = sorted(k for k in nieuw if k not in ("definitie_door", "definitie_herkomst")
                                  and nieuw.get(k) != oud.get(k))
        stand["inhoud"] = nieuw
        stand["geen_wijziging"] = not detail["velden"]
    return await haal(werkgebied_id, begrip_id)


async def verwijder(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    """Echt wissen, net als een annotatie: het begrip met zijn revisies, koppelingen, relaties,
    voorstellen en kaartruns, en zijn plek bij de deelvragen. De annotaties blijven onaangeroerd; de
    auditregel blijft als bewijs. Was het de opvolger van een vervangen begrip, dan krijgt dat zijn
    vorige status terug. Een vervangen begrip zelf gaat niet weg: verwijder dan de opvolger."""
    b = db.begrippen
    async with db.get_engine().begin() as conn:
        await _werkgebied_bestaat(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                                  b.c.verwijderd.is_(None)).with_for_update())).first()
        if row is None:
            raise await niet_gevonden(werkgebied_id, begrip_id)
        if row.status == "vervangen":
            raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger. "
                                      "Verwijder de opvolger om het terug te zetten."})
        if row.revisie != verwacht:
            raise HTTPException(412, {"fout": "revisie_conflict", "revisie": row.revisie,
                                      "melding": "Iemand anders wijzigde dit begrip intussen; laad het opnieuw."})
        hersteld = await _herstel_voorgangers(conn, werkgebied_id, begrip_id, actor, db.utcnow())
        await wis_begrippen(conn, [begrip_id])
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-verwijderd",
                               {"begrip_id": begrip_id, "naam": (row.inhoud or {}).get("naam", ""),
                                "begrip_revisie": row.revisie, "hersteld": hersteld})
    return {"verwijderd": begrip_id, "hersteld": hersteld}


#: Elke tabel met een `begrip_id`: wat `wis_begrippen` opruimt (de relaties via `van_begrip`/`naar_begrip`,
#: de groepen houden hun uitkomst en verliezen alleen de verwijzing). `tests/test_werkgebied_verwijderen.py`
#: bewaakt dat een nieuwe tabel met die kolom hier staat.
BEGRIP_TABELLEN = ("begrip_revisies", "begrip_koppelingen", "begrip_voorstellen", "begrip_kaartruns", "betekenisgroepen")


async def wis_begrippen(conn, ids: list[str]) -> None:
    t = db.metadata.tables
    r, k = db.begrip_relaties, db.werkgebied_deelvraag_koppelingen
    await conn.execute(delete(r).where(r.c.van_begrip.in_(ids) | r.c.naar_begrip.in_(ids)))
    await conn.execute(delete(k).where(k.c.soort == "begrip", k.c.doel_id.in_(ids)))
    for naam in BEGRIP_TABELLEN:
        if naam == "betekenisgroepen":
            await conn.execute(update(t[naam]).where(t[naam].c.begrip_id.in_(ids)).values(begrip_id=None))
        else:
            await conn.execute(delete(t[naam]).where(t[naam].c.begrip_id.in_(ids)))
    await conn.execute(delete(db.begrippen).where(db.begrippen.c.id.in_(ids)))


async def _herstel_voorgangers(conn, werkgebied_id: str, begrip_id: str, actor: str, nu) -> list[str]:
    """Een verwijderd begrip neemt zijn relaties mee; was het de opvolger van een vervangen begrip (fase
    F2), dan krijgt dat zijn vorige status terug – met een eigen revisie, zodat de historie het zegt."""
    r, b = db.begrip_relaties, db.begrippen
    rels = (await conn.execute(select(r).where(
        r.c.werkgebied_id == werkgebied_id, r.c.verwijderd.is_(None),
        (r.c.van_begrip == begrip_id) | (r.c.naar_begrip == begrip_id)))).all()
    hersteld = []
    for x in rels:
        await conn.execute(update(r).where(r.c.id == x.id).values(verwijderd=nu))
        if x.type != "opvolging" or x.naar_begrip != begrip_id:
            continue
        oud = (await conn.execute(select(b).where(b.c.id == x.van_begrip, b.c.verwijderd.is_(None))
                                  .with_for_update())).first()
        if oud is None or oud.status != "vervangen":
            continue
        status = x.bewijs.get("vorige_status") or "concept"
        await conn.execute(update(b).where(b.c.id == oud.id).values(status=status, revisie=oud.revisie + 1, gewijzigd=nu))
        await _revisieregel(conn, oud.id, oud.revisie + 1, "begrip-hersteld", {"opvolger": begrip_id}, status,
                            oud.inhoud, actor, nu)
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-hersteld",
                               {"begrip_id": oud.id, "begrip_revisie": oud.revisie + 1, "opvolger": begrip_id})
        hersteld.append(oud.id)
    return hersteld


async def koppel(werkgebied: dict, begrip_id: str, invoer: KoppelInvoer, actor: str, resolve: Resolver) -> dict:
    bewijs = await bewijzen(werkgebied, invoer.element_ids, resolve)
    async with db.get_engine().begin() as conn:
        await koppel_in(conn, werkgebied["id"], begrip_id, invoer.verwachte_revisie, bewijs, invoer.rol.value,
                        invoer.motivatie, actor)
    return await haal(werkgebied["id"], begrip_id)


async def koppel_in(conn, werkgebied_id: str, begrip_id: str, verwacht: int, bewijs: dict[str, dict], rol: str,
                    motivatie: str, actor: str, beoordeling: str = "open") -> list[str]:
    detail = {"rol": rol, **({"beoordeling": beoordeling} if beoordeling != "open" else {})}
    async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, "begrip-gekoppeld",
                             detail) as (_, __, stand):
        nieuw = await _koppel(conn, werkgebied_id, begrip_id, bewijs, rol, motivatie, actor, beoordeling)
        detail["element_ids"] = nieuw
        stand["geen_wijziging"] = not nieuw
    return nieuw


async def wijzig_koppeling(werkgebied_id: str, begrip_id: str, koppeling_id: str, w: KoppelWijziging,
                           actor: str) -> dict:
    k = db.begrip_koppelingen
    gevraagd = {f: (v.value if hasattr(v, "value") else v) for f in ("rol", "motivatie", "beoordeling")
                if (v := getattr(w, f)) is not None}
    # `_gewijzigd` leest `detail` pas na het blok: wat er echt verandert is pas onder het slot bekend.
    detail: dict = {"koppeling": koppeling_id}
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "koppeling-gewijzigd",
                          detail) as (conn, _, stand):
        row = (await conn.execute(select(k).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                                  k.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Koppeling bestaat niet.")
        velden = {f: v for f, v in gevraagd.items() if getattr(row, f) != v}
        detail["velden"] = sorted(velden)
        if "beoordeling" in velden:
            detail["beoordeling"] = velden["beoordeling"]
        if "rol" in velden:
            # Dezelfde regels als bij koppelen: per begrip één koppeling per element en rol, en
            # hooguit één primaire duiding per element.
            dubbel = (await conn.execute(select(k.c.id).where(
                k.c.begrip_id == begrip_id, k.c.element_id == row.element_id, k.c.rol == velden["rol"],
                k.c.verwijderd.is_(None)))).first()
            if dubbel is not None:
                raise HTTPException(409, {"fout": "al_gekoppeld", "melding": "Deze passage staat al met die rol "
                                                                            "bij dit begrip."})
            if velden["rol"] == "duiding":
                await _toets_primair(conn, werkgebied_id, begrip_id, [row.element_id])
        if not velden:
            stand["geen_wijziging"] = True
        else:
            if "beoordeling" in velden:
                velden.update(beoordeeld_door=actor, beoordeeld_op=db.utcnow())
            await conn.execute(update(k).where(k.c.id == koppeling_id).values(**velden))
    return await haal(werkgebied_id, begrip_id)


async def _toets_primair(conn, werkgebied_id: str, begrip_id: str, element_ids: list[str]) -> None:
    """Hooguit één primaire duiding per element per werkgebied. Draait onder het werkgebiedslot."""
    k, b = db.begrip_koppelingen, db.begrippen
    elders = (await conn.execute(select(k.c.element_id, b.c.id, b.c.inhoud).join_from(k, b, k.c.begrip_id == b.c.id)
                                 .where(k.c.werkgebied_id == werkgebied_id, k.c.rol == "duiding",
                                        k.c.verwijderd.is_(None), k.c.begrip_id != begrip_id,
                                        b.c.status != "vervangen",       # een vervangen begrip houdt niets vast
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
    async with db.get_engine().begin() as conn:
        p = await accordeer_in(conn, werkgebied_id, begrip_id, verwacht, actor)
    if not p["mag"]:
        raise HTTPException(409, {"fout": "poort", "redenen": p["redenen"],
                                  "melding": "Nog niet te accorderen: " + " ".join(p["redenen"])})
    return await haal(werkgebied_id, begrip_id)


async def accordeer_in(conn, werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    """Accorderen als de poort het toelaat, binnen de transactie van de aanroeper. Mag het niet, dan
    verandert er niets en komen de redenen terug: de aanroeper beslist of dat een fout is."""
    async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, "begrip-geaccordeerd",
                             {}) as (_, row, stand):
        p = poort(row.inhoud, await _koppelingen_van(conn, werkgebied_id, begrip_id))
        if not p["mag"]:
            stand["geen_wijziging"] = True
        else:
            stand["status"] = "geaccordeerd"
            stand["waarden"] = {"geaccordeerd_door": actor, "geaccordeerd_op": db.utcnow(),
                                "geaccordeerd_revisie": row.revisie + 1}
    return p


async def heropen(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "begrip-heropend", {}) as (_, row, stand):
        if row.status != "geaccordeerd":
            raise HTTPException(409, "Het begrip is niet geaccordeerd.")
        stand["status"] = "concept"
    return await haal(werkgebied_id, begrip_id)


# --- export ------------------------------------------------------------------------------------

EXPORT_SCHEMA = "begrippen-export-v1"
# Nieuwe kolommen komen achteraan, zodat wie de export al inleest niet breekt.
_KOLOMMEN = ["begrip_iri", "begrip", "status", "revisie", "definitie", "definitie_herkomst", "context",
             "alternatieve_termen", "rol", "beoordeling", "actualiteit", "annotatie_beoordeeld",
             "passage", "klasse_passage", "vindplaats", "bron_iri", "element_id", "motivatie", "definitie_door"]


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
               i.get("definitie_herkomst") or "", i.get("context", ""),
               "; ".join(i.get("alternatieve_termen", []))]
        door = i.get("definitie_door") or ""
        if not b["koppelingen"]:
            w.writerow([_cel(v) for v in kop] + [""] * (len(_KOLOMMEN) - len(kop) - 1) + [_cel(door)])
        for k in b["koppelingen"]:
            bron = k["bewijs"].get("ankers", [{}])[0].get("bron_iri", "") if k["bewijs"].get("ankers") \
                else k["bewijs"].get("eigenaar_iri", "")
            w.writerow([_cel(v) for v in kop + [
                k["rol"], k["beoordeling"], k["actualiteit"], "ja" if k["annotatie_beoordeeld"] else "nee",
                k["bewijs"].get("tekst", ""), k["bewijs"].get("klasse", ""), k["bewijs"].get("vindplaats", ""),
                bron, k["element_id"], k["motivatie"], door]])
    return tekst.getvalue().encode("utf-8-sig")
