"""Begrippen over werkgebieden heen (spoor D, fase F4), onder `/v1/begrippen`.

Drie ingangen, alle drie alleen lezend en uit Postgres:

- `GET /v1/begrippen` – het overzicht in de webapp: zoeken op naam, alternatieve term en definitie,
  met filters op status en werkgebied. De webapp praat niet met GraphDB.
- `POST /v1/begrippen/verifieer` – voor Lex. Lex zoekt met SPARQL in de NL-SBB-projectie (fase F3) en
  laat zijn kandidaten hier bevestigen: bestaat het begrip nog, wat is de status nu, en loopt de
  projectie van het werkgebied achter (`projectie_hash` naast de hash die de graaf droeg)? Zo blijft
  Postgres de waarheid, zoals bij `search_annotaties`.
- `GET /v1/begrippen/{id}` – één begrip met zijn werkgebied en relaties, zonder dat de vrager het
  werkgebied hoeft te kennen.

Een begrip in een gearchiveerd werkgebied, of een verwijderd begrip, bestaat hier niet: doorklikken
naar de kaart zou anders een 404 geven. Begrippen zijn analyse-uitkomsten, geen wettelijke definities.

Een generiek begrip (ADR-006) heeft geen werkgebied: het staat hier één keer, met waar het gebruikt wordt, en zijn inhoud
wijzig je hier (`PATCH`, `accorderen`, `heropenen`, `DELETE`).
"""
from __future__ import annotations

import unicodedata

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select

from . import begrip_projectie, begrip_relatie_store, begrip_store, bestandsnaam, db
from .begrip_relatie_contracts import NieuweBetekenis
from .auth import require_client
from .begrip_contracts import Accordering, BegripStatus, BegripVerificatie, BegripWijziging, BegripZoekvraag, Revisie
from .routers.auth import actieve_userid

router = APIRouter(prefix="/begrippen", tags=["begrippen"], dependencies=[Depends(require_client)])

STATUS_VOLGORDE = {"geaccordeerd": 0, "concept": 1, "vervangen": 2}


def normaal(tekst: str) -> str:
    """Hoofdletters en diakrieten tellen niet: "Belastingschuldige" vindt "belastingschuldigé"."""
    t = unicodedata.normalize("NFKD", tekst or "")
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).casefold().split())


def treffer(q: str, naam: str, termen: list[str], definitie: str) -> int | None:
    """Hoe goed een begrip bij de zoekterm past – lager is beter, None is geen treffer.
    0 exacte naam, 1 exacte alternatieve term, 2 in de naam, 3 in een term, 4 in de definitie,
    5 alle woorden ergens."""
    q = normaal(q)
    if not q:
        return 0
    naam_n, termen_n, def_n = normaal(naam), [normaal(t) for t in termen], normaal(definitie)
    if naam_n == q:
        return 0
    if q in termen_n:
        return 1
    if q in naam_n:
        return 2
    if any(q in t for t in termen_n):
        return 3
    if q in def_n:
        return 4
    hooiberg = " ".join([naam_n, *termen_n, def_n])
    return 5 if all(w in hooiberg for w in q.split()) else None


async def _rijen(conn, ids: list[str] | None = None, werkgebied_id: str | None = None,
                 door: str | None = None) -> list[dict]:
    """De begrippen van alle actieve werkgebieden en de generieke (of de gevraagde), als lichte rij. Met `werkgebied_id`
    ook de generieke die dat werkgebied gebruikt. Met `door` alleen de begrippen waarvan deze gebruiker een revisie
    maakte (*Door mij bewerkt*)."""
    b, w, k, r, g = db.begrippen, db.werkgebieden, db.begrip_koppelingen, db.begrip_relaties, db.werkgebied_begrippen
    q = (select(b, w.c.naam.label("wg_naam")).join_from(b, w, b.c.werkgebied_id == w.c.id, isouter=True)
         .where(b.c.verwijderd.is_(None), or_(b.c.werkgebied_id.is_(None), w.c.gearchiveerd.is_(None))))
    if ids is not None:
        q = q.where(b.c.id.in_(ids))
    if werkgebied_id:
        q = q.where(begrip_store.in_werkgebied(werkgebied_id))
    if door:
        rev = db.begrip_revisies
        q = q.where(b.c.id.in_(select(rev.c.begrip_id).where(rev.c.actor == door)))
    rows = (await conn.execute(q.order_by(b.c.aangemaakt, b.c.id))).all()
    if not rows:
        return []
    bids = [x.id for x in rows]
    dragend = dict((await conn.execute(
        select(k.c.begrip_id, func.count()).where(k.c.begrip_id.in_(bids), k.c.verwijderd.is_(None),
                                                  k.c.rol.in_(sorted(begrip_store.DRAGEND)),
                                                  k.c.beoordeling != "afgewezen")
        .group_by(k.c.begrip_id))).all())
    opvolgers = (await conn.execute(select(r.c.van_begrip, r.c.naar_begrip).where(
        r.c.van_begrip.in_(bids), r.c.type == "opvolging", r.c.verwijderd.is_(None)))).all()
    namen = {x.id: x.inhoud.get("naam", "") for x in (await conn.execute(select(b.c.id, b.c.inhoud).where(
        b.c.id.in_({o.naar_begrip for o in opvolgers})))).all()} if opvolgers else {}
    door = {o.van_begrip: {"begrip_id": o.naar_begrip, "naam": namen.get(o.naar_begrip, "")} for o in opvolgers}
    # Een geaccordeerd begrip waarvan een dragende passage veranderde (de aandachtspunten van de kaart,
    # uit Postgres): Lex en het overzicht noemen het. Een nieuwe wettekst zonder herannotatie ziet alleen
    # `GET …/herbeoordelingen` (die vraagt de bronboom); dit is de lichte stand.
    herbeoordelen: dict[str, int] = {}
    for wid in sorted({x.werkgebied_id for x in rows if x.status == "geaccordeerd" and x.werkgebied_id}):
        for kp in await begrip_store._koppelingen_van(conn, wid):
            if (kp["begrip_id"] in bids and kp["rol"] in begrip_store.DRAGEND and kp["beoordeling"] != "afgewezen"
                    and kp["actualiteit"] != "actueel"):
                herbeoordelen[kp["begrip_id"]] = herbeoordelen.get(kp["begrip_id"], 0) + 1
    # Een generiek begrip: de werkgebieden die het gebruiken (voor het overzicht), en zijn passages uit alle werkgebieden.
    generiek = [x.id for x in rows if x.werkgebied_id is None]
    gebruikt_in = dict((await conn.execute(select(g.c.begrip_id, func.count()).where(
        g.c.begrip_id.in_(generiek), g.c.verwijderd.is_(None)).group_by(g.c.begrip_id))).all()) if generiek else {}
    for x in rows:
        if x.werkgebied_id is None and x.status == "geaccordeerd":
            for kp in await begrip_store._koppelingen_van(conn, None, x.id):
                if (kp["rol"] in begrip_store.DRAGEND and kp["beoordeling"] != "afgewezen"
                        and kp["actualiteit"] != "actueel"):
                    herbeoordelen[x.id] = herbeoordelen.get(x.id, 0) + 1
    return [{"id": x.id, "iri": begrip_store.begrip_iri(x.id), "werkgebied_id": x.werkgebied_id,
             "kader": begrip_store.GENERIEK if x.werkgebied_id is None else "werkgebied",
             "gebruikt_in": gebruikt_in.get(x.id, 0),
             "werkgebied_naam": x.wg_naam or "", "naam": x.inhoud.get("naam", ""),
             "alternatieve_termen": x.inhoud.get("alternatieve_termen") or [], "status": x.status,
             "revisie": x.revisie, "definitie": x.inhoud.get("definitie", ""),
             "definitie_herkomst": x.inhoud.get("definitie_herkomst"),
             "vervangen_door": door.get(x.id), "aantal_dragend": dragend.get(x.id, 0),
             "herbeoordelen": herbeoordelen.get(x.id, 0) if x.status == "geaccordeerd" else 0,
             "geaccordeerd_op": db.aware(x.geaccordeerd_op).isoformat() if x.geaccordeerd_op else None,
             "gewijzigd": db.aware(x.gewijzigd).isoformat()} for x in rows]


def zoek(rijen: list[dict], vraag: BegripZoekvraag) -> list[dict]:
    """Filteren en ordenen: beste treffer, dan het werkgebied van de vrager, dan geaccordeerd vóór
    concept vóór vervangen, dan naam."""
    status = {s.value for s in vraag.status}
    uit = []
    for x in rijen:
        if status and x["status"] not in status:
            continue
        # Een generiek begrip staat al alleen in de rijen als dit werkgebied het gebruikt.
        if vraag.werkgebied_id and x["werkgebied_id"] not in (vraag.werkgebied_id, None):
            continue
        if vraag.kader and x["kader"] != vraag.kader:
            continue
        t = treffer(vraag.q, x["naam"], x["alternatieve_termen"], x["definitie"])
        if t is not None:
            uit.append((t, x["werkgebied_id"] != vraag.eerst if vraag.eerst else False,
                        STATUS_VOLGORDE.get(x["status"], 9), normaal(x["naam"]), x["id"], x))
    return [x for *_, x in sorted(uit, key=lambda t: t[:5])]


@router.get("")
async def get_begrippen(q: str = Query("", max_length=200), status: list[BegripStatus] = Query(default=[]),
                        werkgebied_id: str | None = Query(None, max_length=64),
                        eerst: str | None = Query(None, max_length=64),
                        kader: Literal["generiek", "werkgebied"] | None = None,
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        mijn: bool = False, actor: str = Depends(actieve_userid)):
    vraag = BegripZoekvraag(q=q, status=status, werkgebied_id=werkgebied_id, eerst=eerst, kader=kader)
    async with db.get_engine().connect() as conn:
        rijen = await _rijen(conn, werkgebied_id=werkgebied_id, door=actor if mijn else None)
    gevonden = zoek(rijen, vraag)
    # De tellers bij de statusknoppen: dezelfde filters, zonder het statusfilter – zo klopt een teller
    # met wat je krijgt als je op die knop drukt.
    per_status: dict[str, int] = {}
    for x in zoek(rijen, vraag.model_copy(update={"status": []})):
        per_status[x["status"]] = per_status.get(x["status"], 0) + 1
    pagina = gevonden[offset:offset + limit]
    volgende = offset + limit if offset + limit < len(gevonden) else None
    return {"resultaten": pagina, "totaal": len(gevonden), "volgende_offset": volgende, "per_status": per_status}


@router.post("/verifieer")
async def post_verifieer(req: BegripVerificatie, actor: str = Depends(actieve_userid)):
    """Per gevraagd id de rij van nu, of `null` als het begrip er niet (meer) is. `werkgebieden` geeft per
    werkgebied van een gevonden begrip de projectiehash van nu: wijkt die af van wat de graaf droeg, dan
    loopt de projectie achter en kan Lex begrippen missen."""
    async with db.get_engine().connect() as conn:
        rijen = {x["id"]: x for x in await _rijen(conn, ids=list(dict.fromkeys(req.ids)))}
        werkgebieden = {}
        # Een generiek begrip staat in zijn eigen graph: ook daarvan de hash van nu.
        for wid in sorted({x["werkgebied_id"] or begrip_projectie.GENERIEK for x in rijen.values()} | set(req.werkgebieden)):
            inv = await begrip_projectie.invoer(conn, wid)
            werkgebieden[wid] = {"projectie_hash": begrip_projectie.invoer_hash(inv) if inv is not None else None}
    return {"begrippen": {i: rijen.get(i) for i in req.ids}, "werkgebieden": werkgebieden}


# Vóór `/{begrip_id}`, anders leest de router "export" als een begrip-id.
@router.get("/export")
async def get_export(inclusief: Literal["geaccordeerd", "alle"] = "geaccordeerd", actor: str = Depends(actieve_userid)):
    """Het generieke begrippenkader als Turtle (NL-SBB)."""
    body = await begrip_projectie.export_turtle(begrip_projectie.GENERIEK, alles=inclusief == "alle")
    return Response(body, media_type="text/turtle; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{bestandsnaam.met_tijd("generieke-begrippen", "ttl")}"'})


@router.get("/conformiteit")
async def get_conformiteit(actor: str = Depends(actieve_userid)):
    """Per generiek begrip: NL-SBB-conform ja/nee met de meldingen (diagnostisch)."""
    return await begrip_projectie.conformiteit_van(begrip_projectie.GENERIEK)


@router.get("/{begrip_id}")
async def get_begrip(begrip_id: str, actor: str = Depends(actieve_userid)):
    async with db.get_engine().connect() as conn:
        rij = await _rijen(conn, ids=[begrip_id])
    if not rij:
        raise HTTPException(404, "Begrip bestaat niet.")
    wid = rij[0]["werkgebied_id"]
    if wid is None:
        return {"werkgebied": None, "begrip": await begrip_store.haal_generiek(begrip_id),
                "relaties": await begrip_relatie_store.van_begrip(begrip_id)}
    rel = await begrip_relatie_store.lijst(wid, begrip_id)
    return {"werkgebied": {"id": wid, "naam": rij[0]["werkgebied_naam"]},
            "begrip": await begrip_store.haal(wid, begrip_id),
            "relaties": [x for x in rel["relaties"] if x["beoordeling"] == "akkoord"]}


# --- de inhoud van een generiek begrip (ADR-006): alleen hier, niet vanuit een werkgebied --------------------

@router.patch("/{begrip_id}")
async def patch_generiek(begrip_id: str, req: BegripWijziging, actor: str = Depends(actieve_userid)):
    return await begrip_store.wijzig(None, begrip_id, req, actor)


@router.delete("/{begrip_id}")
async def delete_generiek(begrip_id: str, verwachte_revisie: int = Query(ge=1), actor: str = Depends(actieve_userid)):
    return await begrip_store.verwijder_generiek(begrip_id, verwachte_revisie, actor)


@router.post("/{begrip_id}/accorderen")
async def post_accorderen(begrip_id: str, req: Accordering, actor: str = Depends(actieve_userid)):
    return await begrip_store.accordeer(None, begrip_id, req.verwachte_revisie, req.reden, actor)


@router.post("/{begrip_id}/heropenen")
async def post_heropenen(begrip_id: str, req: Revisie, actor: str = Depends(actieve_userid)):
    return await begrip_store.heropen(None, begrip_id, req.verwachte_revisie, actor)


@router.post("/{begrip_id}/nieuwe-betekenis", status_code=201)
async def post_nieuwe_betekenis(begrip_id: str, req: NieuweBetekenis, actor: str = Depends(actieve_userid)):
    return await begrip_relatie_store.nieuwe_betekenis_generiek(begrip_id, req, actor)


@router.get("/{begrip_id}/revisies")
async def get_revisies(begrip_id: str, limit: int = Query(100, ge=1, le=500), actor: str = Depends(actieve_userid)):
    await begrip_store.haal_generiek(begrip_id)
    return {"revisies": await begrip_store.revisies_van(begrip_id, limit)}
