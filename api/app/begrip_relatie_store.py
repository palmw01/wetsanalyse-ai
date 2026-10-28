"""Begripsrelaties en opvolging (spoor D, fase F2).

- **Een relatie is een eigen object met type, richting en bewijs.** De typen van de keten
  (kwalificatie, inclusie, uitsluiting, hiërarchie) houden hun juridische betekenis; `verwant` is de
  enige zwakke en vraagt een toelichting. Niets wordt platgeslagen tot "verwant" (ADR-003).
- **Voorstellen worden afgeleid, besluiten opgeslagen.** Een relatie tussen twee elementen uit de laatste
  klare begrippenrun, die elk primair een ander begrip aanduiden, is een voorgestelde begripsrelatie
  (`voorstellen`). Lezen schrijft niets; akkoord en afwijzen schrijven een rij, en een afgewezen voorstel
  (zelfde van, naar en type) komt niet terug.
- **Doorwerking**: een vastgelegde relatie bewaart de stand (definitie + context) van beide kanten. Wijkt
  die af, dan staat de relatie bij het begrip aan de andere kant in de herbeoordeling (`doorwerking`);
  *bevestigen* legt de stand van nu vast.
- **Opvolging** (`nieuwe_betekenis`, `combineer`): het oude begrip wordt `vervangen` (alleen-lezen, houdt
  geen primaire duiding vast), met een relatie `opvolging` naar de opvolger die zijn vorige status
  draagt. Verwijder je de opvolger, dan zet `begrip_store.verwijder` hem terug.
- Sloten: altijd eerst het werkgebied (ook via `begrip_store._gewijzigd_in`), dan de begrippen.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import begrip_store, begrippen_run_store, db
from .begrip_relatie_contracts import Combineren, NieuweBetekenis, RelatieInvoer
from .werkgebied_store import _audit as werkgebied_audit


def stand(inhoud: dict) -> str:
    """Wat een relatie over een begrip aanneemt: zijn definitie en context."""
    return hashlib.sha256(json.dumps([inhoud.get("definitie", ""), inhoud.get("context", "")]).encode()).hexdigest()[:32]


def voorstel_id(van: str, naar: str, type_: str) -> str:
    return "R" + hashlib.sha256(f"{van}\x1f{naar}\x1f{type_}".encode()).hexdigest()[:16]


def _relatie(row, namen: dict[str, str]) -> dict:
    return {"id": row.id, "van_begrip": row.van_begrip, "naar_begrip": row.naar_begrip, "type": row.type,
            "van_naam": namen.get(row.van_begrip, ""), "naar_naam": namen.get(row.naar_begrip, ""),
            "herkomst": row.herkomst, "bewijs": row.bewijs, "toelichting": row.toelichting,
            "beoordeling": row.beoordeling, "door": row.door, "op": db.aware(row.op).isoformat()}


async def _begrippen(conn, werkgebied_id: str) -> dict[str, object]:
    b = db.begrippen
    return {r.id: r for r in (await conn.execute(select(b).where(b.c.werkgebied_id == werkgebied_id,
                                                                 b.c.verwijderd.is_(None)))).all()}


async def _rijen(conn, werkgebied_id: str):
    r = db.begrip_relaties
    return (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.verwijderd.is_(None))
                               .order_by(r.c.op, r.c.id))).all()


async def _voorstellen(conn, werkgebied_id: str, begrippen: dict, rijen) -> list[dict]:
    """De relaties van de laatste klare run, op begrippen gezet. Alleen tussen twee verschillende, niet
    vervangen begrippen, en niet wat er al ligt (vastgelegd of afgewezen)."""
    run = await begrippen_run_store._laatste_klare(conn, werkgebied_id)
    if run is None or not run.uitkomst.get("relaties"):
        return []
    primair = await begrip_store.primaire_duidingen(werkgebied_id)
    passages = {f["element_id"]: f for f in run.manifest.get("formuleringen", [])}
    labels = {x["bron_iri"]: x["label"] for x in run.manifest.get("bronnen", [])}
    bekend = {(x.van_begrip, x.naar_begrip, x.type) for x in rijen}
    uit, gezien = [], set()
    for rel in run.uitkomst["relaties"]:
        van, naar = primair.get(rel["van"]), primair.get(rel["naar"])
        if not van or not naar or van["begrip_id"] == naar["begrip_id"]:
            continue
        sleutel = (van["begrip_id"], naar["begrip_id"], rel["hypothese"])
        if sleutel in bekend or sleutel in gezien or any(
                begrippen.get(i) is None or begrippen[i].status == "vervangen" for i in sleutel[:2]):
            continue
        gezien.add(sleutel)
        uit.append({"id": voorstel_id(*sleutel), "van_begrip": sleutel[0], "naar_begrip": sleutel[1],
                    "type": sleutel[2], "van_naam": van["naam"], "naar_naam": naar["naam"], "herkomst": "lex",
                    "beoordeling": "voorgesteld", "toelichting": "",
                    "bewijs": {"run_id": run.id, "kandidaat_id": rel["kandidaat_id"], "aandacht": rel["aandacht"],
                               "uitleg": rel.get("uitleg", []),
                               "van": begrippen_run_store._passage(passages[rel["van"]], labels) if rel["van"] in passages else None,
                               "naar": begrippen_run_store._passage(passages[rel["naar"]], labels) if rel["naar"] in passages else None}})
    return uit


def doorwerking(rijen, begrippen: dict) -> dict[str, list[dict]]:
    """Per begrip de vastgelegde relaties waarvan de andere kant veranderde sinds het vastleggen."""
    uit: dict[str, list[dict]] = {}
    for x in rijen:
        if x.beoordeling != "akkoord" or x.type == "opvolging":
            continue
        van, naar = begrippen.get(x.van_begrip), begrippen.get(x.naar_begrip)
        if van is None or naar is None:
            continue
        for wie, ander, opgeslagen in ((x.naar_begrip, van, x.stand_van), (x.van_begrip, naar, x.stand_naar)):
            if stand(ander.inhoud) != opgeslagen and begrippen[wie].status != "vervangen":
                uit.setdefault(wie, []).append({
                    "relatie_id": x.id, "type": x.type, "ander": {"begrip_id": ander.id, "naam": ander.inhoud.get("naam", "")},
                    "reden": f"De definitie of context van “{ander.inhoud.get('naam', '')}” veranderde nadat deze "
                             f"relatie werd vastgelegd."})
    return uit


async def lijst(werkgebied_id: str, begrip_id: str | None = None) -> dict:
    async with db.get_engine().connect() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id)
        begrippen = await _begrippen(conn, werkgebied_id)
        rijen = await _rijen(conn, werkgebied_id)
        voorstellen = await _voorstellen(conn, werkgebied_id, begrippen, rijen)
    namen = {i: r.inhoud.get("naam", "") for i, r in begrippen.items()}
    raakt = (lambda x: begrip_id in (x["van_begrip"], x["naar_begrip"])) if begrip_id else (lambda x: True)
    door = doorwerking(rijen, begrippen)
    veranderd = {d["relatie_id"] for ds in door.values() for d in ds}
    relaties = [{**_relatie(x, namen), "veranderd": x.id in veranderd} for x in rijen]
    return {"relaties": [x for x in relaties if raakt(x)], "voorstellen": [x for x in voorstellen if raakt(x)]}


def _niet_vervangen(begrippen: dict, *ids: str) -> None:
    for i in ids:
        if i not in begrippen:
            raise HTTPException(404, "Begrip bestaat niet.")
        if begrippen[i].status == "vervangen":
            raise HTTPException(409, {"fout": "vervangen", "melding": f"“{begrippen[i].inhoud.get('naam', '')}” is "
                                      "vervangen; leg de relatie bij de opvolger."})


async def maak(werkgebied_id: str, inv: RelatieInvoer, actor: str) -> dict:
    r = db.begrip_relaties
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id, slot=True)
        begrippen = await _begrippen(conn, werkgebied_id)
        rijen = await _rijen(conn, werkgebied_id)
        if inv.voorstel_id:
            voorstel = next((v for v in await _voorstellen(conn, werkgebied_id, begrippen, rijen)
                             if v["id"] == inv.voorstel_id), None)
            if voorstel is None:
                raise HTTPException(409, {"fout": "voorstel_weg", "melding": "Dit voorstel staat er niet meer; "
                                          "laad de relaties opnieuw."})
            van, naar, type_, herkomst, bewijs = (voorstel["van_begrip"], voorstel["naar_begrip"], voorstel["type"],
                                                  "lex", voorstel["bewijs"])
        else:
            van, naar, type_, herkomst, bewijs = inv.van_begrip, inv.naar_begrip, inv.type, "analist", {}
        if van == naar:
            raise HTTPException(422, {"fout": "zelfde_begrip", "melding": "Een relatie gaat tussen twee begrippen."})
        _niet_vervangen(begrippen, van, naar)
        if any((x.van_begrip, x.naar_begrip, x.type) == (van, naar, type_) and x.beoordeling == "akkoord" for x in rijen):
            raise HTTPException(409, {"fout": "al_vastgelegd", "melding": "Deze relatie is al vastgelegd."})
        # Een eerder afwijzen wordt door een eigen besluit van de analist vervangen, niet naast gezet.
        for x in rijen:
            if (x.van_begrip, x.naar_begrip, x.type) == (van, naar, type_):
                await conn.execute(update(r).where(r.c.id == x.id).values(verwijderd=db.utcnow()))
        rid = str(uuid.uuid4())
        await conn.execute(insert(r).values(
            id=rid, werkgebied_id=werkgebied_id, van_begrip=van, naar_begrip=naar, type=type_, herkomst=herkomst,
            bewijs=bewijs, toelichting=inv.toelichting.strip(), beoordeling="akkoord",
            stand_van=stand(begrippen[van].inhoud), stand_naar=stand(begrippen[naar].inhoud), door=actor, op=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "relatie-vastgelegd",
                               {"relatie_id": rid, "type": type_, "van": van, "naar": naar, "herkomst": herkomst})
    return await lijst(werkgebied_id)


async def wijs_af(werkgebied_id: str, vid: str, reden: str, actor: str) -> dict:
    r = db.begrip_relaties
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id, slot=True)
        begrippen = await _begrippen(conn, werkgebied_id)
        voorstel = next((v for v in await _voorstellen(conn, werkgebied_id, begrippen, await _rijen(conn, werkgebied_id))
                         if v["id"] == vid), None)
        if voorstel is None:
            raise HTTPException(409, {"fout": "voorstel_weg", "melding": "Dit voorstel staat er niet meer."})
        rid = str(uuid.uuid4())
        await conn.execute(insert(r).values(
            id=rid, werkgebied_id=werkgebied_id, van_begrip=voorstel["van_begrip"], naar_begrip=voorstel["naar_begrip"],
            type=voorstel["type"], herkomst="lex", bewijs=voorstel["bewijs"], toelichting=reden, beoordeling="afgewezen",
            door=actor, op=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "relatie-afgewezen",
                               {"relatie_id": rid, "type": voorstel["type"], "reden": reden})
    return await lijst(werkgebied_id)


async def _rij(conn, werkgebied_id: str, rid: str):
    r = db.begrip_relaties
    x = (await conn.execute(select(r).where(r.c.id == rid, r.c.werkgebied_id == werkgebied_id,
                                            r.c.verwijderd.is_(None)))).first()
    if x is None:
        raise HTTPException(404, "Relatie bestaat niet.")
    return x


async def verwijder(werkgebied_id: str, rid: str, actor: str) -> dict:
    r = db.begrip_relaties
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id, slot=True)
        x = await _rij(conn, werkgebied_id, rid)
        if x.type == "opvolging":
            raise HTTPException(409, {"fout": "opvolging", "melding": "Een opvolging haal je weg door de opvolger "
                                      "te verwijderen; dan krijgt het oude begrip zijn status terug."})
        await conn.execute(update(r).where(r.c.id == rid).values(verwijderd=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "relatie-verwijderd", {"relatie_id": rid, "type": x.type})
    return await lijst(werkgebied_id)


async def bevestig(werkgebied_id: str, rid: str, actor: str) -> dict:
    """De relatie klopt nog na een wijziging aan één kant: de stand van nu wordt de nieuwe basis."""
    r = db.begrip_relaties
    async with db.get_engine().begin() as conn:
        await begrip_store._werkgebied_bestaat(conn, werkgebied_id, slot=True)
        x = await _rij(conn, werkgebied_id, rid)
        if x.beoordeling != "akkoord" or x.type == "opvolging":
            raise HTTPException(409, {"fout": "niet_te_bevestigen", "melding": "Alleen een vastgelegde relatie bevestig je."})
        begrippen = await _begrippen(conn, werkgebied_id)
        await conn.execute(update(r).where(r.c.id == rid).values(
            stand_van=stand(begrippen[x.van_begrip].inhoud), stand_naar=stand(begrippen[x.naar_begrip].inhoud),
            door=actor, op=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "relatie-bevestigd", {"relatie_id": rid, "type": x.type})
    return await lijst(werkgebied_id)


# --- opvolging -------------------------------------------------------------------------------------

async def _kopieer_koppelingen(conn, werkgebied_id: str, van: str, naar: str, actor: str) -> list[str]:
    """De niet-afgewezen koppelingen van `van` bij `naar`, met hun bewaarde bewijsstand en opnieuw open
    ter beoordeling. Wat `naar` al met dezelfde rol heeft, slaat hij over."""
    k = db.begrip_koppelingen
    bron = (await conn.execute(select(k).where(k.c.begrip_id == van, k.c.verwijderd.is_(None),
                                               k.c.beoordeling != "afgewezen"))).all()
    al = {(x.element_id, x.rol) for x in (await conn.execute(select(k).where(
        k.c.begrip_id == naar, k.c.verwijderd.is_(None)))).all()}
    nu, nieuw = db.utcnow(), []
    for x in bron:
        if (x.element_id, x.rol) in al:
            continue
        await conn.execute(insert(k).values(
            id=str(uuid.uuid4()), begrip_id=naar, werkgebied_id=werkgebied_id, element_id=x.element_id, rol=x.rol,
            motivatie=x.motivatie, bewijs=x.bewijs, bevestigingen=x.bevestigingen, beoordeling="open",
            toegevoegd_door=actor, toegevoegd=nu))
        nieuw.append(x.element_id)
    return nieuw


async def _opvolging(conn, werkgebied_id: str, oud, nieuw_id: str, reden: str, soort: str, actor: str) -> None:
    await conn.execute(insert(db.begrip_relaties).values(
        id=str(uuid.uuid4()), werkgebied_id=werkgebied_id, van_begrip=oud.id, naar_begrip=nieuw_id, type="opvolging",
        herkomst="systeem", bewijs={"soort": soort, "vorige_status": oud.status}, toelichting=reden,
        beoordeling="akkoord", door=actor, op=db.utcnow()))


async def nieuwe_betekenis(werkgebied_id: str, begrip_id: str, nb: NieuweBetekenis, actor: str) -> dict:
    """Eén transactie: het oude begrip wordt vervangen, de opvolger krijgt inhoud en passages (open)."""
    detail: dict = {"reden": nb.reden}
    async with db.get_engine().begin() as conn:
        async with begrip_store._gewijzigd_in(conn, werkgebied_id, begrip_id, nb.verwachte_revisie, actor,
                                              "begrip-vervangen", detail) as (_, oud, stand_):
            stand_["status"] = "vervangen"
        # Pas nu is het oude begrip vervangen en zijn de primaire duidingen vrij.
        nieuw_id = await begrip_store.maak_in(conn, werkgebied_id, {**oud.inhoud, "definitie_door": oud.inhoud.get(
            "definitie_door", "")}, {}, "duiding", actor)
        gekopieerd = await _kopieer_koppelingen(conn, werkgebied_id, begrip_id, nieuw_id, actor)
        await _opvolging(conn, werkgebied_id, oud, nieuw_id, nb.reden, "nieuwe_betekenis", actor)
        await werkgebied_audit(conn, werkgebied_id, actor, "begrip-opgevolgd",
                               {"begrip_id": nieuw_id, "vervangt": begrip_id, "element_ids": gekopieerd, "reden": nb.reden})
    return await begrip_store.haal(werkgebied_id, nieuw_id)


async def combineer(werkgebied_id: str, begrip_id: str, c: Combineren, actor: str) -> dict:
    """Eén transactie: `ander_begrip_id` wordt vervangen door `begrip_id`, dat zijn passages (open) en zijn
    naam als alternatieve term meekrijgt."""
    if c.ander_begrip_id == begrip_id:
        raise HTTPException(422, {"fout": "zelfde_begrip", "melding": "Kies een ander begrip om mee te combineren."})
    detail_ander: dict = {"reden": c.reden, "opvolger": begrip_id}
    detail: dict = {"reden": c.reden, "vervangt": c.ander_begrip_id}
    async with db.get_engine().begin() as conn:
        async with begrip_store._gewijzigd_in(conn, werkgebied_id, c.ander_begrip_id, c.ander_revisie, actor,
                                              "begrip-vervangen", detail_ander) as (_, ander, stand_):
            stand_["status"] = "vervangen"
        async with begrip_store._gewijzigd_in(conn, werkgebied_id, begrip_id, c.verwachte_revisie, actor,
                                              "begrip-gecombineerd", detail) as (_, row, stand_):
            inhoud = dict(row.inhoud)
            naam = ander.inhoud.get("naam", "")
            termen = list(inhoud.get("alternatieve_termen", []))
            for t in [naam, *ander.inhoud.get("alternatieve_termen", [])]:
                if t and t != inhoud.get("naam") and t not in termen:
                    termen.append(t)
            inhoud["alternatieve_termen"] = termen
            stand_["inhoud"] = inhoud
            detail["element_ids"] = await _kopieer_koppelingen(conn, werkgebied_id, c.ander_begrip_id, begrip_id, actor)
        await _opvolging(conn, werkgebied_id, ander, begrip_id, c.reden, "combineren", actor)
    return await begrip_store.haal(werkgebied_id, begrip_id)
