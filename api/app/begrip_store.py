"""Begrippen: opslag, koppelingen, actualiteit, de accorderingspoort en de export (spoor D, levering 2).

Een begrip hoort bij één werkgebied, met een impliciet begrippenkader (`urn:wa:kader:<werkgebied>`), of is generiek
(ADR-006): `werkgebied_id` is dan leeg, het staat in `urn:wa:kader:generiek` en werkgebieden gebruiken het zonder kopie
(`werkgebied_begrippen`). De inhoud staat op één plek; de passages horen bij het werkgebied dat ze koppelde.

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
- **Een generiek begrip** wijzig je alleen met `werkgebied_id=None` (`/v1/begrippen/{id}`), niet vanuit een werkgebied
  (409 `generiek`), zodat niemand ongemerkt andere analyses wijzigt. Een passage in een werkgebied heropent het niet:
  anders zet één analyse het begrip voor iedereen terug.
"""
from __future__ import annotations

import csv
import io
import json
import re
import uuid
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import delete, func, insert, or_, select, update

from . import annotatie_v2_store as annotaties, db
from .annotatie_export import cel
from .annotatie_v2_contracts import BEOORDEELD
from .begrip_contracts import (
    BegripInvoer, BegripWijziging, KoppelBeoordelingen, KoppelInvoer, KoppelWijziging,
)
from .werkgebied_inventaris import inventaris
from .werkgebied_store import _audit as werkgebied_audit, niet_gevonden, toets_revisie, werkgebied_rij

Resolver = Callable[[dict], Awaitable[dict]]

DRAGEND = {"duiding", "definitie"}


GENERIEK = "generiek"


def kader_iri(werkgebied_id: str | None) -> str:
    return f"urn:wa:kader:{werkgebied_id or GENERIEK}"


def in_werkgebied(werkgebied_id: str):
    """De begrippen in beeld bij een werkgebied: zijn eigen, en de generieke die het gebruikt."""
    b, g = db.begrippen, db.werkgebied_begrippen
    return or_(b.c.werkgebied_id == werkgebied_id,
               b.c.id.in_(select(g.c.begrip_id).where(g.c.werkgebied_id == werkgebied_id, g.c.verwijderd.is_(None))))


def begrip_iri(begrip_id: str) -> str:
    return f"urn:wa:begrip:{begrip_id}"


def element_hash(el: dict) -> str:
    """Wat een passage inhoudelijk is: tekst, klasse, subtype en ankers. Een oordeel van een jurist
    (de lifecycle) hoort er niet bij – een akkoord maakt een passage niet "gewijzigd"."""
    ankers = [{k: a.get(k) for k in ("bron_iri", "start", "eind", "tekst", "bron_hash")} for a in el.get("ankers", [])]
    return annotaties.digest({"tekst": el.get("tekst", ""), "klasse": el.get("klasse", ""),
                              "jas_subtype": el.get("jas_subtype", ""), "ankers": ankers})


# --- lezen ------------------------------------------------------------------------------------

def bevestigde_stand(bewijs: dict, bevestigingen: list[dict] | None) -> dict:
    """Het bewijs zoals de analist het voor het laatst bevestigde: wat een lezer en de export moeten zien. Een
    bevestiging legt een nieuwe tekst vast; zonder deze stap toonde `wa:passage` de tekst van vóór de wijziging (N2).
    De rij verandert niet: de stand bij het koppelen blijft `bewijs_bij_koppelen`."""
    if not bevestigingen:
        return bewijs
    laatste = bevestigingen[-1]
    return {**bewijs, **{k: laatste[k] for k in ("element_hash", "ankers", "tekst", "klasse") if laatste.get(k)}}


def _koppeling(row) -> dict:
    return {"id": row.id, "begrip_id": row.begrip_id, "werkgebied_id": row.werkgebied_id, "element_id": row.element_id,
            "rol": row.rol, "motivatie": row.motivatie, "bewijs": bevestigde_stand(row.bewijs, row.bevestigingen),
            "bewijs_bij_koppelen": row.bewijs, "beoordeling": row.beoordeling,
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


# De zin die `begrippen_run_store.context_uit` en graph-qa `kaart._context` maken. Een punt binnen een vindplaats staat
# tegen het volgende teken ("Artikel 79.5a"); een punt met een spatie erachter is het eind van de zin, dus wie er een
# eigen tekst achter zet, valt hier niet onder.
_NIET_EINDE = r"(?:[^.]|\.(?=\S))+"
_VINDPLAATSREGEL = re.compile(rf"Komt voor in {_NIET_EINDE}\.(?: Wettelijke definitie in {_NIET_EINDE}\.)?")


def eigen_toelichting(context: str) -> bool:
    """Staat er een toelichting? De gegenereerde vindplaatsregel is er geen: die zegt waar de term staat, niet wat er
    afgebakend wordt (S6)."""
    tekst = (context or "").strip()
    return bool(tekst) and _VINDPLAATSREGEL.fullmatch(tekst) is None


def poort(inhoud: dict, koppelingen: list[dict]) -> dict:
    """Mag dit begrip geaccordeerd worden, en zo nee, waarom niet. `koppelingen` met actualiteit."""
    redenen = []
    if not inhoud.get("definitie", "").strip():
        redenen.append("Er is nog geen definitie.")
    if not eigen_toelichting(inhoud.get("context", "")):
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


async def _koppelingen_van(conn, werkgebied_id: str | None, begrip_id: str | None = None) -> list[dict]:
    """De koppelingen van een werkgebied; met `None` die van alle werkgebieden (een generiek begrip)."""
    k = db.begrip_koppelingen
    q = select(k).where(k.c.verwijderd.is_(None))
    if werkgebied_id is not None:
        q = q.where(k.c.werkgebied_id == werkgebied_id)
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
            "kader": GENERIEK if row.werkgebied_id is None else "werkgebied", "ontstaan_in": row.ontstaan_in,
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


#: Wat een besluit over een koppeling kan veranderen. De kaart en het bewijs blijven staan.
_KOPPELSTAND = ("id", "element_id", "rol", "motivatie", "beoordeling", "beoordeeld_door", "beoordeeld_op", "actualiteit",
                "lifecycle_nu", "annotatie_beoordeeld")
_BEGRIPSTAND = ("id", "status", "revisie", "gewijzigd", "geaccordeerd_door", "geaccordeerd_op", "geaccordeerd_revisie",
                "accorderen", "aandachtspunten")


def koppelstand(begrip: dict) -> dict:
    """Het antwoord op een besluit over koppelingen. Niet de hele kaart: die groeit met het aantal passages, en de
    jurist neemt ze één voor één door, dus een reeks besluiten werd kwadratisch. De werkplek legt dit over wat ze heeft."""
    return {**{k: begrip[k] for k in _BEGRIPSTAND}, "koppelingen": [
        {k: x[k] for k in _KOPPELSTAND} | {"bevestigingen": len(x.get("bevestigingen") or [])} for x in begrip["koppelingen"]]}


async def _opvolging(conn, werkgebied_id: str | None) -> dict[str, dict]:
    """Per begrip `vervangen_door` en `vervangt` ({begrip_id, naam, reden}) uit de opvolgingsrelaties. De opvolging van
    een generiek begrip heeft geen werkgebied en geldt overal."""
    r, b = db.begrip_relaties, db.begrippen
    plek = r.c.werkgebied_id.is_(None) if werkgebied_id is None else or_(r.c.werkgebied_id == werkgebied_id,
                                                                          r.c.werkgebied_id.is_(None))
    rows = (await conn.execute(select(r).where(plek, r.c.type == "opvolging", r.c.verwijderd.is_(None)))).all()
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


async def definitie_onderbouwing(conn, begrip_id: str, inhoud: dict) -> dict | None:
    """Waarop de huidige definitie rust (spoor M), afgeleid en alleen gelezen: het voorstel achter de
    revisie die deze definitie zette (`begrip_revisies.detail.voorstel_id`), met zijn fragmenten, de
    vindplaats van een brondefinitie, de duiding en het onderzoek van de run. Komt de definitie uit een
    groep van de keten (overnemen of akkoord), dan staat de onderbouwing bevroren in het revisiedetail
    (`onderbouwing`). `inhoud` blijft slank. Paste de analist de definitie aan, bij het overnemen of later, dan blijft
    de onderbouwing staan met `aangepast: true` (S8): de bronnen zijn nog steeds waar hij mee begon, maar de tekst is
    niet meer wat ze dragen. None als er nooit een voorstel of groep achter zat."""
    definitie = (inhoud.get("definitie") or "").strip()
    if not definitie:
        return None
    r, v, k = db.begrip_revisies, db.begrip_voorstellen, db.begrip_kaartruns
    revisies = (await conn.execute(select(r.c.detail, r.c.inhoud).where(r.c.begrip_id == begrip_id)
                                   .order_by(r.c.revisie.desc()))).all()
    aangepast = False
    for x in revisies:
        if (x.inhoud or {}).get("definitie", "").strip() != definitie:
            aangepast = True                            # de definitie van nu is hierna geschreven
        d = x.detail or {}
        if d.get("onderbouwing"):
            o = d["onderbouwing"]
            return {**o, "aangepast": aangepast or bool(o.get("aangepast")),
                    "fragmenten": [{**f, "rol": "ondersteunend"} for f in o.get("fragmenten") or []]}
        if d.get("voorstel_id") and d.get("veld") == "definitie":
            aangepast = aangepast or bool(d.get("aangepast"))
            vrow = (await conn.execute(select(v.c.id, v.c.run_id, v.c.actie, v.c.waarde)
                                       .where(v.c.id == d["voorstel_id"]))).first()
            if vrow is None:
                return None
            krow = (await conn.execute(select(k.c.invoer).where(k.c.id == vrow.run_id))).first()
            w = vrow.waarde or {}
            return {"voorstel_id": vrow.id, "actie": vrow.actie, "herkomst": w.get("herkomst", ""), "aangepast": aangepast,
                    "definitie_bron_iri": w.get("definitie_bron_iri", ""),
                    "definitie_vindplaats": w.get("definitie_vindplaats", ""),
                    "fragmenten": [{"bron_iri": f["bron_iri"], "start": f["start"], "eind": f["eind"],
                                    "tekst": f["tekst"], "rol": "ondersteunend"} for f in w.get("fragmenten") or []],
                    "duiding": w.get("duiding"),
                    "onderzoek_id": ((krow.invoer if krow else {}) or {}).get("onderzoek_id", "")}
    return None


async def haal(werkgebied_id: str | None, begrip_id: str) -> dict:
    """Eén begrip zoals een werkgebied het ziet: met zijn eigen passages. Met `None` een generiek begrip met de passages
    van alle werkgebieden en waar het gebruikt wordt."""
    if werkgebied_id is None:
        return await haal_generiek(begrip_id)
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, in_werkgebied(werkgebied_id)))).first()
        if row is None:
            raise await niet_gevonden(werkgebied_id, begrip_id)
        uit = _begrip(row, await _koppelingen_van(conn, werkgebied_id, begrip_id), await _opvolging(conn, werkgebied_id))
        uit["definitie_onderbouwing"] = await definitie_onderbouwing(conn, begrip_id, row.inhoud)
        return uit


async def haal_generiek(begrip_id: str) -> dict:
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Begrip bestaat niet.")
        uit = _begrip(row, await _koppelingen_van(conn, None, begrip_id), await _opvolging(conn, None))
        uit["definitie_onderbouwing"] = await definitie_onderbouwing(conn, begrip_id, row.inhoud)
        uit["gebruik"] = await gebruik_van(conn, begrip_id)
        return uit


async def maak_generiek_in(conn, inhoud: dict, ontstaan_in: str | None, actor: str) -> str:
    """De opvolger van een generiek begrip: een nieuw concept in het generieke kader, zonder passages. Elk werkgebied
    neemt hem zelf over."""
    bid, nu = str(uuid.uuid4()), db.utcnow()
    await conn.execute(insert(db.begrippen).values(
        id=bid, werkgebied_id=None, ontstaan_in=ontstaan_in, status="concept", revisie=1, inhoud=inhoud,
        aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
    await _revisieregel(conn, bid, 1, "begrip-aangemaakt", {"naam": inhoud["naam"], "element_ids": [], "rol": "duiding"},
                        "concept", inhoud, actor, nu)
    return bid


async def gebruik_van(conn, begrip_id: str) -> list[dict]:
    """Welke werkgebieden dit generieke begrip gebruiken, met hun aantal passages."""
    g, w, k = db.werkgebied_begrippen, db.werkgebieden, db.begrip_koppelingen
    rows = (await conn.execute(select(g.c.werkgebied_id, g.c.gezien_revisie, w.c.naam)
                               .join_from(g, w, g.c.werkgebied_id == w.c.id)
                               .where(g.c.begrip_id == begrip_id, g.c.verwijderd.is_(None))
                               .order_by(w.c.naam, g.c.werkgebied_id))).all()
    tellingen = dict((await conn.execute(select(k.c.werkgebied_id, func.count()).where(
        k.c.begrip_id == begrip_id, k.c.verwijderd.is_(None)).group_by(k.c.werkgebied_id))).all())
    return [{"werkgebied_id": x.werkgebied_id, "naam": x.naam, "gezien_revisie": x.gezien_revisie,
             "passages": tellingen.get(x.werkgebied_id, 0)} for x in rows]


async def lijst(werkgebied_id: str) -> list[dict]:
    """De begrippen in beeld bij het werkgebied, zonder de koppelingen zelf (wel tellingen en aandacht)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        rows = (await conn.execute(select(b).where(in_werkgebied(werkgebied_id))
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


async def generieke_buiten(werkgebied_id: str) -> list[dict]:
    """De generieke begrippen die dit werkgebied (nog) niet gebruikt, in de vorm die `lijkt_op` leest."""
    b, g = db.begrippen, db.werkgebied_begrippen
    gebruikt = select(g.c.begrip_id).where(g.c.werkgebied_id == werkgebied_id, g.c.verwijderd.is_(None))
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(b).where(b.c.werkgebied_id.is_(None),
                                                   b.c.status != "vervangen", b.c.id.not_in(gebruikt))
                                   .order_by(b.c.aangemaakt, b.c.id))).all()
    return [{"id": r.id, "kader": GENERIEK, "status": r.status, "inhoud": slank(r.inhoud), "element_ids": []} for r in rows]


async def samenhang(werkgebied_id: str) -> dict:
    """Begrippen en hun koppelingen, zonder bewijs: wat de samenhangsgraaf tekent (fase F3)."""
    b = db.begrippen
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        rows = (await conn.execute(select(b).where(in_werkgebied(werkgebied_id))
                                   .order_by(b.c.aangemaakt, b.c.id))).all()
        koppelingen = await _koppelingen_van(conn, werkgebied_id)
    return {"begrippen": [{"id": r.id, "iri": begrip_iri(r.id), "naam": r.inhoud.get("naam", ""), "status": r.status,
                           "definitie": r.inhoud.get("definitie", "")} for r in rows],
            "koppelingen": [{"begrip_id": k["begrip_id"], "element_id": k["element_id"], "rol": k["rol"],
                             "beoordeling": k["beoordeling"], "actualiteit": k["actualiteit"]} for k in koppelingen]}


async def generiek_bij_elementen(element_ids: set[str]) -> list[dict]:
    """Geaccordeerde generieke begrippen met een niet-afgewezen koppeling op deze elementen, voor een los gesprek."""
    k, b = db.begrip_koppelingen, db.begrippen
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(b.c.id, b.c.status, b.c.inhoud, k.c.element_id, k.c.rol)
                                   .join_from(k, b, k.c.begrip_id == b.c.id)
                                   .where(k.c.element_id.in_(element_ids), k.c.verwijderd.is_(None),
                                          k.c.beoordeling != "afgewezen", b.c.werkgebied_id.is_(None),
                                          b.c.status == "geaccordeerd"))).all()
    return [{"id": r.id, "status": r.status, "naam": r.inhoud.get("naam", ""), "definitie": r.inhoud.get("definitie", ""),
             "element_id": r.element_id, "rol": r.rol} for r in rows]


async def primaire_duidingen(werkgebied_id: str) -> dict[str, dict]:
    """Per element het begrip dat het primair aanduidt – voor de inventaris in de werkplek."""
    k, b = db.begrip_koppelingen, db.begrippen
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(k.c.element_id, b.c.id, b.c.inhoud).join_from(k, b, k.c.begrip_id == b.c.id)
                                   .where(k.c.werkgebied_id == werkgebied_id, k.c.rol == "duiding",
                                          k.c.verwijderd.is_(None),
                                          b.c.status != "vervangen"))).all()
    return {r.element_id: {"begrip_id": r.id, "naam": r.inhoud.get("naam", "")} for r in rows}


async def revisies(werkgebied_id: str, begrip_id: str, limit: int = 100) -> list[dict]:
    await haal(werkgebied_id, begrip_id)
    return await revisies_van(begrip_id, limit)


async def revisies_van(begrip_id: str, limit: int = 100) -> list[dict]:
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
    details = await annotaties.details(element_ids)
    for eid in dict.fromkeys(element_ids):
        detail, inv_el = details[eid], per_id[eid]
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
async def _gewijzigd(werkgebied_id: str | None, begrip_id: str, verwacht: int, actor: str, actie: str, detail: dict,
                     mag_vervangen: bool = False, passage: bool = False):
    """Werkgebiedslot, begripslot, revisietoets; daarna revisie +1, revisiekopie en audit.

    De aanroeper muteert via `stand`: `inhoud` en `status` en extra kolommen in `waarden`. Zet hij
    `geen_wijziging`, dan gebeurt er niets (idempotent). `detail` wordt pas ná het blok gelezen, dus
    de aanroeper mag het daarin nog aanvullen."""
    async with db.get_engine().begin() as conn:
        async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, actie, detail,
                                 mag_vervangen, passage) as uit:
            yield uit


@asynccontextmanager
async def _gewijzigd_in(conn, werkgebied_id: str | None, begrip_id: str, verwacht: int, actor: str, actie: str,
                        detail: dict, mag_vervangen: bool = False, passage: bool = False):
    """`_gewijzigd` binnen een transactie van de aanroeper: zo kan een besluit over een voorstel (fase D)
    begrip, koppelingen, accorderen en groepsbesluit samen vastleggen of samen laten mislukken.

    `werkgebied_id=None` is een generiek begrip op zijn eigen route: geen werkgebiedslot, en de auditregel gaat naar elk
    werkgebied dat het gebruikt. `passage`: de mutatie gaat over een koppeling in dit werkgebied. Alleen die mag vanuit
    een werkgebied op een generiek begrip, en ze laat de status staan."""
    b = db.begrippen
    if werkgebied_id is None:
        waar = b.c.werkgebied_id.is_(None)
    else:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        waar = in_werkgebied(werkgebied_id)
    row = (await conn.execute(select(b).where(b.c.id == begrip_id, waar)
                              .with_for_update())).first()
    if row is None:
        raise HTTPException(404, "Begrip bestaat niet.")
    generiek = row.werkgebied_id is None
    if generiek and werkgebied_id is not None and not passage:
        raise HTTPException(409, {"fout": "generiek", "melding": "Dit is een generiek begrip: het geldt voor meer "
                                  "werkgebieden. Je wijzigt het op zijn eigen pagina."})
    if row.status == "vervangen" and not mag_vervangen:
        raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger en "
                                  "is alleen nog te lezen. Verwijder de opvolger om het terug te zetten."})
    toets_revisie(row.revisie, verwacht, "dit begrip")
    stand = {"inhoud": row.inhoud, "status": None, "waarden": {}, "geen_wijziging": False}
    yield conn, row, stand
    if stand["geen_wijziging"]:
        return
    status = stand["status"] or (row.status if generiek and passage
                                 else "concept" if row.status == "geaccordeerd" else row.status)
    nieuw, nu = row.revisie + 1, db.utcnow()
    await conn.execute(update(b).where(b.c.id == begrip_id).values(
        revisie=nieuw, gewijzigd=nu, status=status, inhoud=stand["inhoud"], **stand["waarden"]))
    await _revisieregel(conn, begrip_id, nieuw, actie, detail, status, stand["inhoud"], actor, nu)
    audit = {**detail, "begrip_id": begrip_id, "begrip_revisie": nieuw}
    for wid in ([werkgebied_id] if werkgebied_id is not None else await _gebruikers(conn, begrip_id)):
        await werkgebied_audit(conn, wid, actor, actie, audit)


async def _gebruikers(conn, begrip_id: str) -> list[str]:
    g = db.werkgebied_begrippen
    return list((await conn.execute(select(g.c.werkgebied_id).where(
        g.c.begrip_id == begrip_id, g.c.verwijderd.is_(None)).order_by(g.c.werkgebied_id))).scalars().all())


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
    await werkgebied_rij(conn, werkgebied_id, slot=True)
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


async def wijzig(werkgebied_id: str | None, begrip_id: str, w: BegripWijziging, actor: str) -> dict:
    nieuw = w.inhoud.model_dump(mode="json")
    # `_gewijzigd` leest `detail` pas na het blok: de velden zijn pas onder het slot bekend.
    detail: dict = {}
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "begrip-gewijzigd",
                          detail) as (conn, row, stand):
        oud = slank(row.inhoud)
        nieuw = met_afgeleid(oud, nieuw)
        # Een generiek begrip heet één keer zo, ook na een nieuwe naam (`generiek_maken` toetst hetzelfde).
        if werkgebied_id is None and _term(nieuw.get("naam", "")) != _term(oud.get("naam", "")):
            await _toets_term(conn, nieuw.get("naam", ""), begrip_id)
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
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id)
                                   .with_for_update())).first()
        if row is None:
            raise await niet_gevonden(werkgebied_id, begrip_id)
        if row.status == "vervangen":
            raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger. "
                                      "Verwijder de opvolger om het terug te zetten."})
        toets_revisie(row.revisie, verwacht, "dit begrip")
        hersteld = await _herstel_voorgangers(conn, werkgebied_id, begrip_id, actor, db.utcnow())
        await wis_begrippen(conn, [begrip_id])
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-verwijderd",
                               {"begrip_id": begrip_id, "naam": (row.inhoud or {}).get("naam", ""),
                                "begrip_revisie": row.revisie, "hersteld": hersteld})
    return {"verwijderd": begrip_id, "hersteld": hersteld}


#: Elke tabel met een `begrip_id`: wat `wis_begrippen` opruimt (de relaties via `van_begrip`/`naar_begrip`,
#: de groepen houden hun uitkomst en verliezen alleen de verwijzing). `tests/test_werkgebied_verwijderen.py`
#: bewaakt dat een nieuwe tabel met die kolom hier staat.
BEGRIP_TABELLEN = ("begrip_revisies", "begrip_koppelingen", "begrip_voorstellen", "begrip_kaartruns", "betekenisgroepen",
                   "werkgebied_begrippen")


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


async def _herstel_voorgangers(conn, werkgebied_id: str | None, begrip_id: str, actor: str, nu) -> list[str]:
    """Een verwijderd begrip neemt zijn relaties mee; was het de opvolger van een vervangen begrip (fase
    F2), dan krijgt dat zijn vorige status terug – met een eigen revisie, zodat de historie het zegt. Met `None` een
    generiek begrip: zijn relaties staan in meer werkgebieden."""
    r, b = db.begrip_relaties, db.begrippen
    q = select(r).where(r.c.verwijderd.is_(None), (r.c.van_begrip == begrip_id) | (r.c.naar_begrip == begrip_id))
    if werkgebied_id is not None:
        q = q.where(r.c.werkgebied_id == werkgebied_id)
    rels = (await conn.execute(q)).all()
    hersteld = []
    for x in rels:
        await conn.execute(update(r).where(r.c.id == x.id).values(verwijderd=nu))
        if x.type != "opvolging" or x.naar_begrip != begrip_id:
            continue
        oud = (await conn.execute(select(b).where(b.c.id == x.van_begrip)
                                  .with_for_update())).first()
        if oud is None or oud.status != "vervangen":
            continue
        status = x.bewijs.get("vorige_status") or "concept"
        await conn.execute(update(b).where(b.c.id == oud.id).values(status=status, revisie=oud.revisie + 1, gewijzigd=nu))
        await _revisieregel(conn, oud.id, oud.revisie + 1, "begrip-hersteld", {"opvolger": begrip_id}, status,
                            oud.inhoud, actor, nu)
        for wid in ([werkgebied_id] if werkgebied_id is not None else [x.werkgebied_id] if x.werkgebied_id
                    else await _gebruikers(conn, oud.id)):
            await werkgebied_audit(conn, wid, actor, "begrip-hersteld",
                                   {"begrip_id": oud.id, "begrip_revisie": oud.revisie + 1, "opvolger": begrip_id})
        hersteld.append(oud.id)
    return hersteld


async def koppel(werkgebied: dict, begrip_id: str, invoer: KoppelInvoer, actor: str, resolve: Resolver) -> dict:
    bewijs = await bewijzen(werkgebied, invoer.element_ids, resolve)
    async with db.get_engine().begin() as conn:
        await koppel_in(conn, werkgebied["id"], begrip_id, invoer.verwachte_revisie, bewijs, invoer.rol.value,
                        invoer.motivatie, actor)
    return koppelstand(await haal(werkgebied["id"], begrip_id))


async def koppel_in(conn, werkgebied_id: str, begrip_id: str, verwacht: int, bewijs: dict[str, dict], rol: str,
                    motivatie: str, actor: str, beoordeling: str = "open") -> list[str]:
    detail = {"rol": rol, **({"beoordeling": beoordeling} if beoordeling != "open" else {})}
    async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, "begrip-gekoppeld",
                             detail, passage=True) as (_, __, stand):
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
                          detail, passage=True) as (conn, _, stand):
        row = (await conn.execute(select(k).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                                  k.c.werkgebied_id == werkgebied_id,
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
    return koppelstand(await haal(werkgebied_id, begrip_id))


async def beoordeel_koppelingen(werkgebied_id: str, begrip_id: str, w: KoppelBeoordelingen, actor: str) -> dict:
    """Dezelfde beoordeling op meer koppelingen, in één revisie. Wat er al zo staat, telt niet mee."""
    k = db.begrip_koppelingen
    beoordeling = w.beoordeling.value
    detail: dict = {"velden": ["beoordeling"], "beoordeling": beoordeling}
    async with _gewijzigd(werkgebied_id, begrip_id, w.verwachte_revisie, actor, "koppeling-gewijzigd",
                          detail, passage=True) as (conn, _, stand):
        rijen = {r.id: r for r in (await conn.execute(select(k).where(
            k.c.id.in_(w.koppeling_ids), k.c.begrip_id == begrip_id, k.c.werkgebied_id == werkgebied_id,
            k.c.verwijderd.is_(None)))).all()}
        if onbekend := [i for i in w.koppeling_ids if i not in rijen]:
            raise HTTPException(404, {"fout": "onbekende_koppeling", "koppeling_ids": onbekend,
                                      "melding": f"{len(onbekend)} koppeling(en) bestaan niet (meer) bij dit begrip."})
        anders = [i for i in w.koppeling_ids if rijen[i].beoordeling != beoordeling]
        detail["koppelingen"] = anders
        stand["geen_wijziging"] = not anders
        if anders:
            await conn.execute(update(k).where(k.c.id.in_(anders)).values(
                beoordeling=beoordeling, beoordeeld_door=actor, beoordeeld_op=db.utcnow()))
    return koppelstand(await haal(werkgebied_id, begrip_id))


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
                          {"koppeling": koppeling_id}, passage=True) as (conn, _, __):
        row = (await conn.execute(select(k.c.id).where(k.c.id == koppeling_id, k.c.begrip_id == begrip_id,
                                                       k.c.werkgebied_id == werkgebied_id,
                                                       k.c.verwijderd.is_(None)))).first()
        if row is None:
            raise HTTPException(404, "Koppeling bestaat niet.")
        await conn.execute(update(k).where(k.c.id == koppeling_id).values(verwijderd=db.utcnow()))
    return koppelstand(await haal(werkgebied_id, begrip_id))


async def accordeer(werkgebied_id: str | None, begrip_id: str, verwacht: int, reden: str, actor: str) -> dict:
    async with db.get_engine().begin() as conn:
        p = await accordeer_in(conn, werkgebied_id, begrip_id, verwacht, reden, actor)
    if not p["mag"]:
        raise HTTPException(409, {"fout": "poort", "redenen": p["redenen"],
                                  "melding": "Nog niet te accorderen: " + " ".join(p["redenen"])})
    return await haal(werkgebied_id, begrip_id)


async def accordeer_in(conn, werkgebied_id: str | None, begrip_id: str, verwacht: int, reden: str, actor: str) -> dict:
    """Accorderen als de poort het toelaat, binnen de transactie van de aanroeper. Mag het niet, dan
    verandert er niets en komen de redenen terug: de aanroeper beslist of dat een fout is. Een akkoord op
    een voorstel zonder reden blijft dus een concept: accorderen zonder reden bestaat niet."""
    reden = reden.strip()
    detail = {"reden": reden}
    async with _gewijzigd_in(conn, werkgebied_id, begrip_id, verwacht, actor, "begrip-geaccordeerd",
                             detail) as (_, row, stand):
        p = poort(row.inhoud, await _koppelingen_van(conn, werkgebied_id, begrip_id))
        if not reden:
            p = {"mag": False, "redenen": [*p["redenen"], "De reden van het accorderen ontbreekt."]}
        if not p["mag"]:
            stand["geen_wijziging"] = True
        else:
            stand["status"] = "geaccordeerd"
            stand["waarden"] = {"geaccordeerd_door": actor, "geaccordeerd_op": db.utcnow(),
                                "geaccordeerd_revisie": row.revisie + 1}
    return p


async def heropen(werkgebied_id: str | None, begrip_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, begrip_id, verwacht, actor, "begrip-heropend", {}) as (_, row, stand):
        if row.status != "geaccordeerd":
            raise HTTPException(409, "Het begrip is niet geaccordeerd.")
        stand["status"] = "concept"
    return await haal(werkgebied_id, begrip_id)


# --- generieke begrippen (ADR-006) ---------------------------------------------------------------

def _term(naam: str) -> str:
    return " ".join((naam or "").casefold().split())


async def _toets_term(conn, naam: str, behalve: str) -> None:
    """Dezelfde voorkeursterm staat één keer in het generieke kader; dan is het combineren, of een andere naam."""
    b = db.begrippen
    rows = (await conn.execute(select(b.c.id, b.c.inhoud).where(
        b.c.werkgebied_id.is_(None), b.c.status != "vervangen", b.c.id != behalve))).all()
    for x in rows:
        andere = x.inhoud.get("naam", "")
        if _term(andere) == _term(naam):
            raise HTTPException(409, {"fout": "al_generiek", "begrip_id": x.id, "begrip_naam": andere,
                                      "melding": f"Er is al een generiek begrip \"{andere}\". Combineer dit begrip "
                                                 "daarmee, of geef het een onderscheidende naam."})


async def generiek_maken(werkgebied_id: str, begrip_id: str, verwacht: int, actor: str) -> dict:
    """Een geaccordeerd begrip gaat naar het generieke kader. Het id, de IRI en de passages blijven; dit werkgebied
    gebruikt het voortaan. Alleen een geaccordeerd begrip: een concept delen met andere analyses is te vroeg."""
    b, g = db.begrippen, db.werkgebied_begrippen
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id)
                                   .with_for_update())).first()
        if row is None:
            raise await niet_gevonden(werkgebied_id, begrip_id)
        toets_revisie(row.revisie, verwacht, "dit begrip")
        if row.status != "geaccordeerd":
            raise HTTPException(409, {"fout": "niet_geaccordeerd",
                                      "melding": "Alleen een geaccordeerd begrip kan generiek worden."})
        await _toets_term(conn, row.inhoud.get("naam", ""), begrip_id)
        nieuw, nu = row.revisie + 1, db.utcnow()
        await conn.execute(update(b).where(b.c.id == begrip_id).values(
            werkgebied_id=None, ontstaan_in=werkgebied_id, revisie=nieuw, gewijzigd=nu))
        await conn.execute(insert(g).values(id=str(uuid.uuid4()), werkgebied_id=werkgebied_id, begrip_id=begrip_id,
                                            gezien_revisie=nieuw, door=actor, op=nu))
        detail = {"werkgebied": werkgebied_id}
        await _revisieregel(conn, begrip_id, nieuw, "begrip-generiek", detail, row.status, row.inhoud, actor, nu)
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-generiek",
                               {**detail, "begrip_id": begrip_id, "begrip_revisie": nieuw})
    return await haal_generiek(begrip_id)


async def gebruik(werkgebied_id: str, begrip_id: str, actor: str) -> dict:
    """Een generiek begrip gebruiken in dit werkgebied. Idempotent; de passages koppel je daarna hier."""
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        await gebruik_in(conn, werkgebied_id, begrip_id, actor)
    return await haal(werkgebied_id, begrip_id)


async def gebruik_in(conn, werkgebied_id: str, begrip_id: str, actor: str) -> None:
    """`gebruik` onder het werkgebiedslot van de aanroeper."""
    b, g = db.begrippen, db.werkgebied_begrippen
    row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id.is_(None)))).first()
    if row is None:
        raise HTTPException(404, "Generiek begrip bestaat niet.")
    if row.status == "vervangen":
        raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger."})
    bestaand = (await conn.execute(select(g.c.id).where(g.c.werkgebied_id == werkgebied_id, g.c.begrip_id == begrip_id,
                                                        g.c.verwijderd.is_(None)))).first()
    if bestaand is not None:
        return
    await conn.execute(insert(g).values(id=str(uuid.uuid4()), werkgebied_id=werkgebied_id, begrip_id=begrip_id,
                                        gezien_revisie=row.revisie, door=actor, op=db.utcnow()))
    await werkgebied_audit(conn, werkgebied_id, actor, "begrip-gebruikt",
                           {"begrip_id": begrip_id, "naam": row.inhoud.get("naam", "")})


async def stop_gebruik(werkgebied_id: str, begrip_id: str, actor: str) -> dict:
    """Dit werkgebied gebruikt het generieke begrip niet meer. De passages van dit werkgebied gaan los; het begrip en
    de annotaties blijven."""
    g, k = db.werkgebied_begrippen, db.begrip_koppelingen
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        rij = (await conn.execute(select(g.c.id).where(g.c.werkgebied_id == werkgebied_id, g.c.begrip_id == begrip_id,
                                                       g.c.verwijderd.is_(None)))).first()
        if rij is None:
            raise HTTPException(404, "Dit werkgebied gebruikt dit begrip niet.")
        nu = db.utcnow()
        await conn.execute(update(g).where(g.c.id == rij.id).values(verwijderd=nu))
        await conn.execute(update(k).where(k.c.begrip_id == begrip_id, k.c.werkgebied_id == werkgebied_id,
                                           k.c.verwijderd.is_(None)).values(verwijderd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-niet-meer-gebruikt", {"begrip_id": begrip_id})
    return {"gestopt": begrip_id}


async def verwijder_generiek(begrip_id: str, verwacht: int, actor: str) -> dict:
    """Echt wissen, maar niet zolang een werkgebied het begrip gebruikt: dat raakt die analyses (409 `in_gebruik`)."""
    b = db.begrippen
    async with db.get_engine().begin() as conn:
        row = (await conn.execute(select(b).where(b.c.id == begrip_id, b.c.werkgebied_id.is_(None))
                                   .with_for_update())).first()
        if row is None:
            raise HTTPException(404, "Begrip bestaat niet.")
        if row.status == "vervangen":
            raise HTTPException(409, {"fout": "vervangen", "melding": "Dit begrip is vervangen door een opvolger."})
        toets_revisie(row.revisie, verwacht, "dit begrip")
        if gebruikers := await _gebruikers(conn, begrip_id):
            plek = "1 werkgebied" if len(gebruikers) == 1 else f"{len(gebruikers)} werkgebieden"
            raise HTTPException(409, {"fout": "in_gebruik", "werkgebieden": gebruikers,
                                      "melding": f"Dit begrip wordt nog in {plek} gebruikt."})
        hersteld = await _herstel_voorgangers(conn, None, begrip_id, actor, db.utcnow())
        await wis_begrippen(conn, [begrip_id])
        if row.ontstaan_in:
            await werkgebied_audit(conn, row.ontstaan_in, actor, "begrip-verwijderd",
                                   {"begrip_id": begrip_id, "naam": (row.inhoud or {}).get("naam", ""),
                                    "begrip_revisie": row.revisie, "hersteld": hersteld})
    return {"verwijderd": begrip_id, "hersteld": hersteld}


#: Wat een werkgebied van een generiek begrip overneemt; een andere status of passage elders is geen wijziging voor hem.
INHOUD_VELDEN = ("naam", "alternatieve_termen", "definitie", "uitleg", "context", "voorbeelden")


async def generiek_veranderd(conn, werkgebied_id: str, begrip_id: str | None = None) -> list[dict]:
    """De generieke begrippen die dit werkgebied gebruikt en die veranderden sinds het ze zag, met toen en nu: de
    inhoud uit `begrip_revisies`, of de opvolger als het begrip vervangen is. Een nieuwe revisie door een passage in een
    ander werkgebied telt niet: de inhoud bleef gelijk."""
    g, b, r, rel = db.werkgebied_begrippen, db.begrippen, db.begrip_revisies, db.begrip_relaties
    q = (select(g.c.gezien_revisie, b).join_from(g, b, g.c.begrip_id == b.c.id)
         .where(g.c.werkgebied_id == werkgebied_id, g.c.verwijderd.is_(None),
                b.c.werkgebied_id.is_(None)).order_by(b.c.aangemaakt, b.c.id))
    if begrip_id:
        q = q.where(b.c.id == begrip_id)
    uit = []
    for x in (await conn.execute(q)).all():
        toen = (await conn.execute(select(r.c.inhoud).where(r.c.begrip_id == x.id, r.c.revisie == x.gezien_revisie))).scalar()
        toen, nu = slank(toen or {}), slank(x.inhoud)
        velden = [v for v in INHOUD_VELDEN if (toen.get(v) or None) != (nu.get(v) or None)]
        opvolger = None
        if x.status == "vervangen":
            o = (await conn.execute(select(rel.c.naar_begrip, rel.c.toelichting).where(
                rel.c.van_begrip == x.id, rel.c.type == "opvolging", rel.c.verwijderd.is_(None),
                rel.c.werkgebied_id.is_(None)))).first()
            if o is not None:
                naam = (await conn.execute(select(b.c.inhoud).where(b.c.id == o.naar_begrip))).scalar() or {}
                opvolger = {"begrip_id": o.naar_begrip, "naam": naam.get("naam", ""), "reden": o.toelichting}
        if velden or opvolger:
            uit.append({"begrip_id": x.id, "naam": nu.get("naam", ""), "revisie": x.revisie, "status": x.status,
                        "gezien_revisie": x.gezien_revisie, "velden": velden, "opvolger": opvolger,
                        "toen": {v: toen.get(v) for v in velden}, "nu": {v: nu.get(v) for v in velden}})
    return uit


async def bevestig_gebruik(werkgebied_id: str, begrip_id: str, actor: str) -> dict:
    """Het begrip klopt nog voor dit werkgebied: de stand van nu is wat het zag."""
    g, b = db.werkgebied_begrippen, db.begrippen
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
        rij = (await conn.execute(select(g.c.id).where(g.c.werkgebied_id == werkgebied_id, g.c.begrip_id == begrip_id,
                                                       g.c.verwijderd.is_(None)))).first()
        if rij is None:
            raise HTTPException(404, "Dit werkgebied gebruikt dit begrip niet.")
        revisie = (await conn.execute(select(b.c.revisie).where(b.c.id == begrip_id))).scalar()
        await conn.execute(update(g).where(g.c.id == rij.id).values(gezien_revisie=revisie))
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-generiek-bevestigd",
                               {"begrip_id": begrip_id, "begrip_revisie": revisie})
    return await haal(werkgebied_id, begrip_id)


# --- export ------------------------------------------------------------------------------------

EXPORT_SCHEMA = "begrippen-export-v1"
# Nieuwe kolommen komen achteraan, zodat wie de export al inleest niet breekt.
_KOLOMMEN = ["begrip_iri", "begrip", "status", "revisie", "definitie", "definitie_herkomst", "context",
             "alternatieve_termen", "rol", "beoordeling", "actualiteit", "annotatie_beoordeeld",
             "passage", "klasse_passage", "vindplaats", "bron_iri", "element_id", "motivatie", "definitie_door"]


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
        return await werkgebied_rij(conn, werkgebied_id)


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
            w.writerow([cel(v) for v in kop] + [""] * (len(_KOLOMMEN) - len(kop) - 1) + [cel(door)])
        for k in b["koppelingen"]:
            bron = k["bewijs"].get("ankers", [{}])[0].get("bron_iri", "") if k["bewijs"].get("ankers") \
                else k["bewijs"].get("eigenaar_iri", "")
            w.writerow([cel(v) for v in kop + [
                k["rol"], k["beoordeling"], k["actualiteit"], "ja" if k["annotatie_beoordeeld"] else "nee",
                k["bewijs"].get("tekst", ""), k["bewijs"].get("klasse", ""), k["bewijs"].get("vindplaats", ""),
                bron, k["element_id"], k["motivatie"], door]])
    return tekst.getvalue().encode("utf-8-sig")
