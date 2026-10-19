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
"""
from __future__ import annotations

import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from . import begrip_projectie, begrip_relatie_store, begrip_store, db
from .auth import require_client
from .begrip_contracts import BegripStatus, BegripVerificatie, BegripZoekvraag
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


async def _rijen(conn, ids: list[str] | None = None, werkgebied_id: str | None = None) -> list[dict]:
    """De begrippen van alle actieve werkgebieden (of de gevraagde), als lichte rij."""
    b, w, k, r = db.begrippen, db.werkgebieden, db.begrip_koppelingen, db.begrip_relaties
    q = (select(b, w.c.naam.label("wg_naam")).join_from(b, w, b.c.werkgebied_id == w.c.id)
         .where(b.c.verwijderd.is_(None), w.c.gearchiveerd.is_(None)))
    if ids is not None:
        q = q.where(b.c.id.in_(ids))
    if werkgebied_id:
        q = q.where(b.c.werkgebied_id == werkgebied_id)
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
    for wid in sorted({x.werkgebied_id for x in rows if x.status == "geaccordeerd"}):
        for kp in await begrip_store._koppelingen_van(conn, wid):
            if (kp["begrip_id"] in bids and kp["rol"] in begrip_store.DRAGEND and kp["beoordeling"] != "afgewezen"
                    and kp["actualiteit"] != "actueel"):
                herbeoordelen[kp["begrip_id"]] = herbeoordelen.get(kp["begrip_id"], 0) + 1
    return [{"id": x.id, "iri": begrip_store.begrip_iri(x.id), "werkgebied_id": x.werkgebied_id,
             "werkgebied_naam": x.wg_naam, "naam": x.inhoud.get("naam", ""),
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
        if vraag.werkgebied_id and x["werkgebied_id"] != vraag.werkgebied_id:
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
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        actor: str = Depends(actieve_userid)):
    vraag = BegripZoekvraag(q=q, status=status, werkgebied_id=werkgebied_id, eerst=eerst)
    async with db.get_engine().connect() as conn:
        gevonden = zoek(await _rijen(conn, werkgebied_id=werkgebied_id), vraag)
    pagina = gevonden[offset:offset + limit]
    volgende = offset + limit if offset + limit < len(gevonden) else None
    return {"resultaten": pagina, "totaal": len(gevonden), "volgende_offset": volgende}


@router.post("/verifieer")
async def post_verifieer(req: BegripVerificatie, actor: str = Depends(actieve_userid)):
    """Per gevraagd id de rij van nu, of `null` als het begrip er niet (meer) is. `werkgebieden` geeft per
    werkgebied van een gevonden begrip de projectiehash van nu: wijkt die af van wat de graaf droeg, dan
    loopt de projectie achter en kan Lex begrippen missen."""
    async with db.get_engine().connect() as conn:
        rijen = {x["id"]: x for x in await _rijen(conn, ids=list(dict.fromkeys(req.ids)))}
        werkgebieden = {}
        for wid in sorted({x["werkgebied_id"] for x in rijen.values()} | set(req.werkgebieden)):
            inv = await begrip_projectie.invoer(conn, wid)
            werkgebieden[wid] = {"projectie_hash": begrip_projectie.invoer_hash(inv) if inv is not None else None}
    return {"begrippen": {i: rijen.get(i) for i in req.ids}, "werkgebieden": werkgebieden}


@router.get("/{begrip_id}")
async def get_begrip(begrip_id: str, actor: str = Depends(actieve_userid)):
    async with db.get_engine().connect() as conn:
        rij = await _rijen(conn, ids=[begrip_id])
    if not rij:
        raise HTTPException(404, "Begrip bestaat niet.")
    wid = rij[0]["werkgebied_id"]
    rel = await begrip_relatie_store.lijst(wid, begrip_id)
    return {"werkgebied": {"id": wid, "naam": rij[0]["werkgebied_naam"]},
            "begrip": await begrip_store.haal(wid, begrip_id),
            "relaties": [x for x in rel["relaties"] if x["beoordeling"] == "akkoord"]}
