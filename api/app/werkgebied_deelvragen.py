"""Deelvragen bij een werkgebied, en de dekkingscheck ertegen (vervolg op spoor D fase F).

Open keuze 4 is besloten op *optioneel*: een werkgebied zonder deelvragen werkt zoals altijd. Met
deelvragen meet de dekkingscheck per vraag of er een bron en een geaccordeerd begrip bij hoort.

- **Een actieve deelvraag hoort bij de scope**, dus elke mutatie loopt door
  `werkgebied_store._gewijzigd` (rij-slot, revisie, audit). De bronnenrun neemt de actieve deelvragen
  mee in zijn invoer (`bronnen_run_store.invoer_van`).
- **Een voorstel van Lex** (`stel_voor`, graph-qa) draagt geen revisie: het raakt de scope pas als de
  analist het overneemt. Lex stelt niets opnieuw voor wat er al staat, wat is afgewezen of wat de
  analist weghaalde – vergeleken op de genormaliseerde tekst.
- **Een verbetering vervangt.** Een voorstel van Lex kan een actieve deelvraag verbeteren
  (`vervangt`: herformuleren of splitsen). Overnemen zet die deelvraag op `vervangen`; de opvolger krijgt
  haar plek en haar koppelingen, en een kandidaat die bij de oude gevonden was, landt bij de opvolger.
  Bij een splitsing erft elk overgenomen deel; de eerste overname vervangt.
- **Koppelingen zijn een set** per deelvraag (bronselecties en begrippen van dit werkgebied), zonder
  foreign key. Een weggehaalde selectie of een verwijderd begrip valt bij het lezen weg.
"""
from __future__ import annotations

import re
import unicodedata
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, insert, select, update

from . import db
from .werkgebied_contracts import (
    DeelvraagInvoer, DeelvraagKoppelingen, DeelvraagStatus, DeelvraagVoorstellen, DeelvraagWijziging,
)
from .werkgebied_store import _audit, _gewijzigd

STANDEN = ("geen_bron", "geen_begrip", "gedekt")


def normaliseer(vraag: str) -> str:
    """Zonder hoofdletters, diakrieten en leestekens: "Wanneer is een aanslag invorderbaar?" en
    "wanneer is een aanslag invorderbaar" zijn dezelfde vraag."""
    t = unicodedata.normalize("NFKD", vraag.casefold())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def _deelvraag(row, bronnen: list[str], begrippen: list[str]) -> dict:
    return {"id": row.id, "vraag": row.vraag, "volgorde": row.volgorde, "status": row.status,
            "herkomst": row.herkomst, "reden": row.reden, "vervangt": row.vervangt or "",
            "aangemaakt_door": row.aangemaakt_door,
            "aangemaakt": db.aware(row.aangemaakt).isoformat(), "bronnen": bronnen, "begrippen": begrippen}


async def _actieve_doelen(conn, werkgebied_id: str) -> tuple[set[str], dict[str, dict]]:
    """De bronselecties en begrippen die nu bestaan: een koppeling naar iets anders telt niet."""
    s, b = db.werkgebied_bronselecties, db.begrippen
    selecties = set((await conn.execute(select(s.c.id).where(
        s.c.werkgebied_id == werkgebied_id, s.c.verwijderd.is_(None)))).scalars())
    begrippen = {r.id: {"id": r.id, "naam": (r.inhoud or {}).get("naam", ""), "status": r.status}
                 for r in (await conn.execute(select(b.c.id, b.c.inhoud, b.c.status).where(
                     b.c.werkgebied_id == werkgebied_id, b.c.verwijderd.is_(None)))).all()}
    return selecties, begrippen


async def lijst_in(conn, werkgebied_id: str) -> list[dict]:
    """Actieve deelvragen en open voorstellen, in volgorde; met hun geldige koppelingen."""
    d, k = db.werkgebied_deelvragen, db.werkgebied_deelvraag_koppelingen
    rows = (await conn.execute(select(d).where(
        d.c.werkgebied_id == werkgebied_id, d.c.verwijderd.is_(None),
        d.c.status.in_((DeelvraagStatus.actief.value, DeelvraagStatus.voorgesteld.value)))
        .order_by(d.c.volgorde, d.c.aangemaakt, d.c.id))).all()
    if not rows:
        return []
    selecties, begrippen = await _actieve_doelen(conn, werkgebied_id)
    kopp = (await conn.execute(select(k).where(k.c.deelvraag_id.in_([r.id for r in rows]))
                               .order_by(k.c.gekoppeld, k.c.doel_id))).all()
    per: dict[str, dict[str, list[str]]] = {r.id: {"bron": [], "begrip": []} for r in rows}
    for x in kopp:
        geldig = x.doel_id in selecties if x.soort == "bron" else x.doel_id in begrippen
        if geldig:
            per[x.deelvraag_id][x.soort].append(x.doel_id)
    return [_deelvraag(r, per[r.id]["bron"], per[r.id]["begrip"]) for r in rows]


async def lijst(werkgebied_id: str) -> list[dict]:
    async with db.get_engine().connect() as conn:
        return await lijst_in(conn, werkgebied_id)


async def _onder_slot(conn, werkgebied_id: str, deelvraag_id: str):
    d = db.werkgebied_deelvragen
    row = (await conn.execute(select(d).where(d.c.id == deelvraag_id, d.c.werkgebied_id == werkgebied_id,
                                              d.c.verwijderd.is_(None)))).first()
    if row is None:
        raise HTTPException(404, "Deelvraag bestaat niet.")
    return row


async def _bestaande(conn, werkgebied_id: str) -> dict[str, str]:
    """Genormaliseerde tekst → status, over alles wat er ooit stond (ook afgewezen en weggehaald)."""
    d = db.werkgebied_deelvragen
    rows = (await conn.execute(select(d.c.vraag, d.c.status, d.c.verwijderd).where(
        d.c.werkgebied_id == werkgebied_id))).all()
    return {normaliseer(r.vraag): ("weggehaald" if r.verwijderd else r.status) for r in rows}


async def _volgende_plek(conn, werkgebied_id: str) -> int:
    d = db.werkgebied_deelvragen
    hoogste = (await conn.execute(select(func.max(d.c.volgorde)).where(
        d.c.werkgebied_id == werkgebied_id, d.c.verwijderd.is_(None)))).scalar()
    return 0 if hoogste is None else hoogste + 1


async def maak(werkgebied_id: str, invoer: DeelvraagInvoer, actor: str) -> dict:
    did = str(uuid.uuid4())
    async with _gewijzigd(werkgebied_id, invoer.verwachte_revisie, actor, "deelvraag-toegevoegd",
                          {"deelvraag": did, "vraag": invoer.vraag}) as (conn, _):
        actief = {n for n, s in (await _bestaande(conn, werkgebied_id)).items()
                  if s in (DeelvraagStatus.actief.value, DeelvraagStatus.voorgesteld.value)}
        if normaliseer(invoer.vraag) in actief:
            raise HTTPException(409, {"fout": "al_gesteld", "melding": "Deze deelvraag staat er al."})
        nu = db.utcnow()
        await conn.execute(insert(db.werkgebied_deelvragen).values(
            id=did, werkgebied_id=werkgebied_id, vraag=invoer.vraag, volgorde=await _volgende_plek(conn, werkgebied_id),
            status=DeelvraagStatus.actief.value, herkomst="analist", reden="", aangemaakt_door=actor,
            aangemaakt=nu, gewijzigd=nu))
    return await _werkgebied(werkgebied_id)


async def wijzig(werkgebied_id: str, deelvraag_id: str, w: DeelvraagWijziging, actor: str) -> dict:
    velden: dict = {}
    if w.vraag is not None:
        velden["vraag"] = w.vraag
    if w.volgorde is not None:
        velden["volgorde"] = w.volgorde
    if w.status is not None:
        velden["status"] = w.status.value
        velden["reden"] = w.reden.strip() if w.status == DeelvraagStatus.afgewezen else ""
    actie = {"actief": "deelvraag-overgenomen", "afgewezen": "deelvraag-afgewezen"}.get(
        velden.get("status", ""), "deelvraag-gewijzigd")
    async with _gewijzigd(werkgebied_id, w.verwachte_revisie, actor, actie,
                          {"deelvraag": deelvraag_id, "velden": sorted(velden)}) as (conn, _):
        row = await _onder_slot(conn, werkgebied_id, deelvraag_id)
        if w.status == DeelvraagStatus.voorgesteld and row.status != DeelvraagStatus.voorgesteld.value:
            raise HTTPException(422, "Een deelvraag wordt alleen door Lex voorgesteld.")
        if row.status == DeelvraagStatus.vervangen.value:
            raise HTTPException(409, {"fout": "vervangen", "melding": "Deze deelvraag is vervangen."})
        if (w.status == DeelvraagStatus.actief and row.status == DeelvraagStatus.voorgesteld.value
                and row.vervangt):
            velden.update(await _vervang(conn, werkgebied_id, row, actor))
        if velden:
            await conn.execute(update(db.werkgebied_deelvragen).where(db.werkgebied_deelvragen.c.id == deelvraag_id)
                               .values(**velden, gewijzigd=db.utcnow()))
    return await _werkgebied(werkgebied_id)


async def _vervang(conn, werkgebied_id: str, voorstel, actor: str) -> dict:
    """Een verbetering overnemen: de oude deelvraag wordt `vervangen` (als ze nog actief is), de opvolger
    krijgt haar plek, en de geldige koppelingen van de oude gaan mee. Geeft de velden voor de opvolger."""
    d, k = db.werkgebied_deelvragen, db.werkgebied_deelvraag_koppelingen
    oud = (await conn.execute(select(d).where(d.c.id == voorstel.vervangt, d.c.werkgebied_id == werkgebied_id,
                                              d.c.verwijderd.is_(None)))).first()
    if oud is None:
        return {}   # weggehaald intussen: het voorstel wordt een gewone deelvraag
    if oud.status == DeelvraagStatus.actief.value:
        await conn.execute(update(d).where(d.c.id == oud.id).values(
            status=DeelvraagStatus.vervangen.value, gewijzigd=db.utcnow()))
        await _audit(conn, werkgebied_id, actor, "deelvraag-vervangen", {"deelvraag": oud.id, "door": voorstel.id})
    elif oud.status != DeelvraagStatus.vervangen.value:
        return {}
    selecties, begrippen = await _actieve_doelen(conn, werkgebied_id)
    al = {(x.soort, x.doel_id) for x in (await conn.execute(select(k).where(k.c.deelvraag_id == voorstel.id))).all()}
    for x in (await conn.execute(select(k).where(k.c.deelvraag_id == oud.id))).all():
        geldig = x.doel_id in selecties if x.soort == "bron" else x.doel_id in begrippen
        if geldig and (x.soort, x.doel_id) not in al:
            await conn.execute(insert(k).values(deelvraag_id=voorstel.id, soort=x.soort, doel_id=x.doel_id,
                                                gekoppeld_door=actor, gekoppeld=db.utcnow()))
    await _op_de_plek_van(conn, werkgebied_id, oud, voorstel.id)
    return {}


async def _op_de_plek_van(conn, werkgebied_id: str, oud, nieuw_id: str) -> None:
    """Zet de opvolger op de plek van de oude deelvraag, ná een eerder overgenomen deel van dezelfde
    splitsing, en nummer de actieve deelvragen opnieuw – twee delen op één `volgorde` hadden geen vaste
    volgorde."""
    d = db.werkgebied_deelvragen
    rows = (await conn.execute(select(d.c.id, d.c.vervangt).where(
        d.c.werkgebied_id == werkgebied_id, d.c.verwijderd.is_(None), d.c.id != nieuw_id,
        (d.c.status == DeelvraagStatus.actief.value) | (d.c.id == oud.id))
        .order_by(d.c.volgorde, d.c.aangemaakt, d.c.id))).all()
    ids = [r.id for r in rows]
    plek = ids.index(oud.id) + 1
    while plek < len(rows) and rows[plek].vervangt == oud.id:
        plek += 1
    ids.insert(plek, nieuw_id)
    for i, did in enumerate(ids):
        await conn.execute(update(d).where(d.c.id == did).values(volgorde=i))


async def opvolgers_in(conn, werkgebied_id: str, deelvraag_ids: list[str]) -> dict[str, list[str]]:
    """Per vervangen deelvraag de actieve deelvragen die haar plek innamen."""
    d = db.werkgebied_deelvragen
    rows = (await conn.execute(select(d.c.id, d.c.vervangt).where(
        d.c.werkgebied_id == werkgebied_id, d.c.vervangt.in_(deelvraag_ids), d.c.verwijderd.is_(None),
        d.c.status == DeelvraagStatus.actief.value).order_by(d.c.volgorde, d.c.aangemaakt, d.c.id))).all()
    uit: dict[str, list[str]] = {}
    for r in rows:
        uit.setdefault(r.vervangt, []).append(r.id)
    return uit


async def haal(werkgebied_id: str, deelvraag_id: str) -> dict:
    """Eén deelvraag in elke stand (ook vervangen of afgewezen), met haar opvolgers en de open voorstellen
    die haar zouden vervangen – voor het paneel van één deelvraag."""
    d, k = db.werkgebied_deelvragen, db.werkgebied_deelvraag_koppelingen
    async with db.get_engine().connect() as conn:
        t = db.werkgebieden
        wg = (await conn.execute(select(t.c.id, t.c.gearchiveerd).where(t.c.id == werkgebied_id))).first()
        if wg is None or wg.gearchiveerd is not None:
            raise HTTPException(404, "Werkgebied bestaat niet.")
        row = await _onder_slot(conn, werkgebied_id, deelvraag_id)
        selecties, begrippen = await _actieve_doelen(conn, werkgebied_id)
        per: dict[str, list[str]] = {"bron": [], "begrip": []}
        for x in (await conn.execute(select(k).where(k.c.deelvraag_id == deelvraag_id)
                                     .order_by(k.c.gekoppeld, k.c.doel_id))).all():
            if x.doel_id in (selecties if x.soort == "bron" else begrippen):
                per[x.soort].append(x.doel_id)
        verwant = (await conn.execute(select(d).where(
            d.c.werkgebied_id == werkgebied_id, d.c.vervangt == deelvraag_id, d.c.verwijderd.is_(None),
            d.c.status.in_((DeelvraagStatus.actief.value, DeelvraagStatus.voorgesteld.value)))
            .order_by(d.c.volgorde, d.c.aangemaakt, d.c.id))).all()
    uit = _deelvraag(row, per["bron"], per["begrip"])
    uit["opvolgers"] = [{"id": r.id, "vraag": r.vraag} for r in verwant if r.status == DeelvraagStatus.actief.value]
    uit["voorstellen"] = [_deelvraag(r, [], []) for r in verwant if r.status == DeelvraagStatus.voorgesteld.value]
    return uit


async def verwijder(werkgebied_id: str, deelvraag_id: str, verwacht: int, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, verwacht, actor, "deelvraag-verwijderd",
                          {"deelvraag": deelvraag_id}) as (conn, _):
        await _onder_slot(conn, werkgebied_id, deelvraag_id)
        await conn.execute(update(db.werkgebied_deelvragen).where(db.werkgebied_deelvragen.c.id == deelvraag_id)
                           .values(verwijderd=db.utcnow()))
    return await _werkgebied(werkgebied_id)


async def _zet_koppelingen(conn, deelvraag_id: str, soort: str, ids: list[str], actor: str) -> None:
    k = db.werkgebied_deelvraag_koppelingen
    await conn.execute(delete(k).where(k.c.deelvraag_id == deelvraag_id, k.c.soort == soort))
    nu = db.utcnow()
    for doel in dict.fromkeys(ids):
        await conn.execute(insert(k).values(deelvraag_id=deelvraag_id, soort=soort, doel_id=doel,
                                            gekoppeld_door=actor, gekoppeld=nu))


async def koppel(werkgebied_id: str, deelvraag_id: str, w: DeelvraagKoppelingen, actor: str) -> dict:
    async with _gewijzigd(werkgebied_id, w.verwachte_revisie, actor, "deelvraag-gekoppeld",
                          {"deelvraag": deelvraag_id, "bronnen": len(set(w.bronnen)),
                           "begrippen": len(set(w.begrippen))}) as (conn, _):
        row = await _onder_slot(conn, werkgebied_id, deelvraag_id)
        if row.status != DeelvraagStatus.actief.value:
            raise HTTPException(409, {"fout": "niet_actief", "melding": "Neem de deelvraag eerst over."})
        selecties, begrippen = await _actieve_doelen(conn, werkgebied_id)
        vreemd = [x for x in w.bronnen if x not in selecties] + [x for x in w.begrippen if x not in begrippen]
        if vreemd:
            raise HTTPException(422, {"fout": "buiten_werkgebied", "ids": vreemd,
                                      "melding": "Koppel alleen bronnen en begrippen van dit werkgebied."})
        await _zet_koppelingen(conn, deelvraag_id, "bron", w.bronnen, actor)
        await _zet_koppelingen(conn, deelvraag_id, "begrip", w.begrippen, actor)
    return await _werkgebied(werkgebied_id)


async def koppel_bron_in(conn, werkgebied_id: str, selectie_id: str, deelvraag_ids: list[str], actor: str) -> None:
    """Binnen een lopende transactie (opnemen van een kandidaat): de nieuwe selectie hoort bij de
    deelvragen waarvoor Lex haar vond. Alleen actieve deelvragen van dit werkgebied."""
    if not deelvraag_ids:
        return
    d, k = db.werkgebied_deelvragen, db.werkgebied_deelvraag_koppelingen
    actief = set((await conn.execute(select(d.c.id).where(
        d.c.werkgebied_id == werkgebied_id, d.c.id.in_(deelvraag_ids), d.c.verwijderd.is_(None),
        d.c.status == DeelvraagStatus.actief.value))).scalars())
    # Gevonden bij een deelvraag die intussen vervangen is: dan hoort de bron bij haar opvolger(s).
    for ids in (await opvolgers_in(conn, werkgebied_id, [x for x in deelvraag_ids if x not in actief])).values():
        actief.update(ids)
    for did in sorted(actief):
        bestaat = (await conn.execute(select(k.c.doel_id).where(
            k.c.deelvraag_id == did, k.c.soort == "bron", k.c.doel_id == selectie_id))).first()
        if bestaat is None:
            await conn.execute(insert(k).values(deelvraag_id=did, soort="bron", doel_id=selectie_id,
                                                gekoppeld_door=actor, gekoppeld=db.utcnow()))


async def stel_voor(werkgebied_id: str, v: DeelvraagVoorstellen, actor: str) -> dict:
    """De voorstellen van Lex: alleen wat nieuw is. Geeft `{nieuw, overgeslagen, deelvragen}`."""
    t = db.werkgebieden
    nieuw: list[str] = []
    overgeslagen: list[dict] = []
    async with db.get_engine().begin() as conn:
        row = (await conn.execute(select(t).where(t.c.id == werkgebied_id).with_for_update())).first()
        if row is None or row.gearchiveerd is not None:
            raise HTTPException(404, "Werkgebied bestaat niet.")
        if v.vervangt:
            d = db.werkgebied_deelvragen
            oud = (await conn.execute(select(d.c.status).where(
                d.c.id == v.vervangt, d.c.werkgebied_id == werkgebied_id, d.c.verwijderd.is_(None)))).first()
            if oud is None or oud.status != DeelvraagStatus.actief.value:
                raise HTTPException(422, {"fout": "vervangt_onbekend",
                                          "melding": "Een verbetering hoort bij een actieve deelvraag van dit werkgebied."})
        bestaand = await _bestaande(conn, werkgebied_id)
        plek = await _volgende_plek(conn, werkgebied_id)
        nu = db.utcnow()
        for vraag in v.vragen:
            n = normaliseer(vraag)
            if n in bestaand:
                overgeslagen.append({"vraag": vraag, "reden": bestaand[n]})
                continue
            bestaand[n] = DeelvraagStatus.voorgesteld.value
            did = str(uuid.uuid4())
            await conn.execute(insert(db.werkgebied_deelvragen).values(
                id=did, werkgebied_id=werkgebied_id, vraag=vraag, volgorde=plek, status=DeelvraagStatus.voorgesteld.value,
                herkomst="lex", reden="", vervangt=v.vervangt, aangemaakt_door=actor, aangemaakt=nu, gewijzigd=nu))
            plek += 1
            nieuw.append(did)
        await _audit(conn, werkgebied_id, actor, "deelvragen-voorgesteld",
                     {"nieuw": nieuw, "overgeslagen": len(overgeslagen), "model": v.model,
                      **({"vervangt": v.vervangt} if v.vervangt else {})})
    return {"nieuw": nieuw, "overgeslagen": overgeslagen, "deelvragen": await lijst(werkgebied_id)}


async def dekking(werkgebied_id: str) -> dict:
    """Per actieve deelvraag: `geen_bron` (niets gekoppeld), `geen_begrip` (bronnen, maar geen
    geaccordeerd begrip) of `gedekt`. Een vervangen begrip dekt niets meer; zijn opvolger wel, als die
    gekoppeld is. Uit Postgres, zonder graaf."""
    async with db.get_engine().connect() as conn:
        t = db.werkgebieden
        row = (await conn.execute(select(t.c.id, t.c.gearchiveerd).where(t.c.id == werkgebied_id))).first()
        if row is None or row.gearchiveerd is not None:
            raise HTTPException(404, "Werkgebied bestaat niet.")
        vragen = [d for d in await lijst_in(conn, werkgebied_id) if d["status"] == DeelvraagStatus.actief.value]
        _, begrippen = await _actieve_doelen(conn, werkgebied_id)
        s = db.werkgebied_bronselecties
        labels = {r.id: r.label for r in (await conn.execute(select(s.c.id, s.c.label).where(
            s.c.werkgebied_id == werkgebied_id, s.c.verwijderd.is_(None)))).all()}
    uit = []
    for d in vragen:
        bs = [begrippen[b] for b in d["begrippen"]]
        stand = ("gedekt" if any(b["status"] == "geaccordeerd" for b in bs)
                 else "geen_begrip" if d["bronnen"] or bs else "geen_bron")
        uit.append({"id": d["id"], "vraag": d["vraag"], "stand": stand,
                    "bronnen": [{"id": x, "label": labels.get(x, "")} for x in d["bronnen"]],
                    "begrippen": bs})
    telling = {st: sum(1 for x in uit if x["stand"] == st) for st in STANDEN}
    return {"deelvragen": uit, "telling": telling, "totaal": len(uit)}


async def _werkgebied(werkgebied_id: str) -> dict:
    from . import werkgebied_store
    return await werkgebied_store.haal(werkgebied_id)
