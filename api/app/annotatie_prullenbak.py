"""De prullenbak van de annotaties: verwijderen is terug te draaien, tot een beheerder hem leegt.

Een verwijderde bepaling (`annotatie_v2_store.verwijder_weergave`) verdwijnt uit de actuele tabellen en uit de graaf,
maar haar rijen gaan eerst hierheen (`bewaar`): de lagen, de elementen, de relaties en impliciete partijen die met haar
weggingen, de dekkingsrijen van haar bronnodes en de artefactversies. Zo lezen alle andere paden de actuele tabellen
zoals altijd; niets hoeft een `verwijderd`-vlag te kennen.

- **Terugzetten** (`zet_terug`) zet de rijen terug met hun eigen id's, geeft elke laag een revisie en projecteert ze
  opnieuw. Dat kan alleen zolang er op geen van haar bronnodes een nieuwe laag staat: twee lagen op één bronnode bestaan
  niet (`bron_iri` is uniek). Anders 409 `nieuwe_laag`, met wat er nu ligt; de werkplek biedt dan een vergelijking.
- **Een relatie met een drager buiten de bepaling** komt alleen terug als die laag en de andere kant er nog zijn; de
  dragerlaag krijgt dan een revisie. Een dekkingsrij van een ruimere bepaling die bij het verwijderen haar bereik
  inkromp, blijft zoals hij is: hij is alleen niet meer `voltooid`, en dat kost hoogstens een controle door Lex.
- **Bewaartermijn**: minstens `ANNOTATIE_PRULLENBAK_DAGEN` (30). Vanzelf gaat er niets weg; legen is een beheeractie
  (`POST /v1/admin/annotatie/prullenbak/legen`), standaard alleen wat ouder is dan de termijn.
- **De audit**: `laag-verwijderd` noemt `prullenbak_id`, terugzetten schrijft `laag-teruggezet` per laag, legen
  `prullenbak-geleegd`. Wat naar een verwijderd element verwijst (een begripkoppeling, een drager van een regel), leest
  daaruit `bron_verwijderd` (`bron_verwijderd`), ook na legen, en ook voor wat vóór de prullenbak hard verdween.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, insert, select

from . import db
from .annotatie_v2_contracts import AFGEHANDELD, is_vervangen
from .config import get_settings


def _iso(t) -> str | None:
    return db.aware(t).isoformat() if t else None


def _dt(s):
    return datetime.fromisoformat(s) if isinstance(s, str) else s


def bewaartermijn() -> timedelta:
    return timedelta(days=get_settings().annotatie_prullenbak_dagen)


def telling(elementen: list[dict]) -> dict:
    """Wat een jurist kwijt is: de actuele markeringen, en hoeveel daarvan een oordeel hebben (akkoord, aangepast of
    verworpen). Verouderde en vervangen markeringen zijn historie en tellen apart."""
    actueel = [e for e in elementen if not e.get("verouderd") and not is_vervangen(e)]
    return {"markeringen": len(actueel), "beoordeeld": sum(e.get("lifecycle") in AFGEHANDELD for e in actueel),
            "historie": len(elementen) - len(actueel)}


async def verwijzers(conn, element_ids: set[str]) -> dict:
    """De begrippen en afleidingsregels die naar deze elementen verwijzen (een koppeling of een drager die er nog
    staat), met hun naam: zij lezen daarna "bron verwijderd"."""
    if not element_ids:
        return {"begrippen": [], "regels": []}
    ids = sorted(element_ids)
    k, d, b, r = db.begrip_koppelingen, db.regel_dragers, db.begrippen, db.regels
    begrip_ids = sorted({x for x in (await conn.execute(select(k.c.begrip_id).where(
        k.c.element_id.in_(ids), k.c.verwijderd.is_(None)))).scalars().all()})
    regel_rijen = (await conn.execute(select(r.c.id, r.c.werkgebied_id, r.c.inhoud).where(r.c.id.in_(
        select(d.c.regel_id).where(d.c.element_id.in_(ids), d.c.verwijderd.is_(None)))))).all()
    namen_nodig = set(begrip_ids) | {(x.inhoud or {}).get("regelbegrip_id", "") for x in regel_rijen}
    namen = {x.id: ((x.inhoud or {}).get("naam") or x.id, x.werkgebied_id) for x in (await conn.execute(
        select(b.c.id, b.c.werkgebied_id, b.c.inhoud).where(b.c.id.in_(sorted(namen_nodig - {""}))))).all()}
    return {"begrippen": [{"id": i, "naam": namen.get(i, (i, None))[0], "werkgebied_id": namen.get(i, (i, None))[1]}
                          for i in begrip_ids],
            "regels": sorted(({"id": x.id, "werkgebied_id": x.werkgebied_id,
                               "naam": namen.get((x.inhoud or {}).get("regelbegrip_id", ""), (x.id, None))[0]}
                              for x in regel_rijen), key=lambda x: x["id"])}


async def bewaar(conn, actor: str, weergave_iri: str, doelen: dict, elementen: list, relaties: list,
                 impliciet: list, dekking: list, versies: list) -> dict:
    """In de transactie van `verwijder_weergave`, vóór het wissen: de rijen die weggaan, in de prullenbak. Geeft de
    samenvatting (met het id) terug."""
    prullenbak_id = uuid.uuid4().hex
    lagen = [{**{k: v for k, v in l.items() if k != "updated"}, "updated": _iso(l["updated"])} for l in doelen.values()]
    samenvatting = {"id": prullenbak_id, **telling([e["inhoud"] for e in elementen]), "lagen": len(lagen),
                    "relaties": len(relaties)}
    await conn.execute(insert(db.annotatie_v2_prullenbak).values(
        id=prullenbak_id, weergave_iri=weergave_iri, bron_iris=sorted(doelen), verwijderd_door=actor,
        verwijderd_op=db.utcnow(), samenvatting=samenvatting,
        inhoud={"lagen": lagen, "elementen": elementen, "relaties": relaties, "impliciet": impliciet,
                "dekking": dekking, "versies": [{**v, "gemaakt": _iso(v["gemaakt"])} for v in versies]}))
    return samenvatting


def _publiek(row) -> dict:
    op = db.aware(row.verwijderd_op)
    return {"id": row.id, "weergave_iri": row.weergave_iri, "bron_iris": list(row.bron_iris), "door": row.verwijderd_door,
            "op": op.isoformat(), "bewaard_tot": (op + bewaartermijn()).isoformat(), **{
                k: v for k, v in (row.samenvatting or {}).items() if k != "id"}}


_LICHT = (db.annotatie_v2_prullenbak.c.id, db.annotatie_v2_prullenbak.c.weergave_iri,
          db.annotatie_v2_prullenbak.c.bron_iris, db.annotatie_v2_prullenbak.c.verwijderd_door,
          db.annotatie_v2_prullenbak.c.verwijderd_op, db.annotatie_v2_prullenbak.c.samenvatting)


async def bij_weergave(conn, scope: set[str], lagen: dict) -> dict | None:
    """Het nieuwste item in de prullenbak dat deze bepaling raakt, voor de weergave: met `terugzetbaar` en, als er al een
    nieuwe laag ligt, welke bronnodes bezet zijn. `lagen` zijn de lagen van nu (per bron-IRI)."""
    p = db.annotatie_v2_prullenbak
    for row in (await conn.execute(select(*_LICHT).order_by(p.c.verwijderd_op.desc(), p.c.id))).all():
        iris = set(row.bron_iris) | {row.weergave_iri}
        if iris & scope:
            bezet = sorted(i for i in row.bron_iris if i in lagen)
            return {**_publiek(row), "terugzetbaar": not bezet, "bezet": bezet}
    return None


async def lees(prullenbak_id: str) -> dict:
    """Eén item met zijn markeringen (compact), voor de vergelijking met wat er nu ligt."""
    from .annotatie_v2_store import compact_element
    p = db.annotatie_v2_prullenbak
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(p).where(p.c.id == prullenbak_id))).first()
    if row is None:
        raise HTTPException(404, {"fout": "niet_in_prullenbak", "id": prullenbak_id})
    elementen = [compact_element(dict(e["inhoud"])) for e in row.inhoud.get("elementen", [])]
    return {**_publiek(row), "lagen_toen": row.inhoud.get("lagen", []), "elementen": elementen}


async def lijst() -> list[dict]:
    p = db.annotatie_v2_prullenbak
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(*_LICHT).order_by(p.c.verwijderd_op.desc(), p.c.id))).all()
    grens = db.utcnow() - bewaartermijn()
    return [{**_publiek(r), "over_termijn": db.aware(r.verwijderd_op) <= grens} for r in rows]


async def _bestaat(conn, tabel, rij_id: str) -> bool:
    return (await conn.execute(select(tabel.c.id).where(tabel.c.id == rij_id))).first() is not None


async def _weiger_bij_bezet(conn, row, layers: dict) -> None:
    """409 als er op een van de bronnodes intussen een laag staat, met per bronnode wat er nu ligt; of als een markering
    uit de prullenbak weer bestaat (dan zou terugzetten haar dubbel maken)."""
    e = db.annotatie_v2_elementen
    bezet = sorted(i for i in row.bron_iris if i in layers)
    if bezet:
        nu = {layers[i]["id"]: i for i in bezet}
        per_iri: dict[str, list] = {}
        for laag_id, inh in (await conn.execute(select(e.c.laag_id, e.c.inhoud).where(
                e.c.laag_id.in_(sorted(nu))))).all():
            per_iri.setdefault(nu[laag_id], []).append(inh)
        raise HTTPException(409, {"fout": "nieuwe_laag", "bezet": bezet,
                                  "nu": {i: telling(per_iri.get(i, [])) for i in bezet},
                                  "melding": "Er staat intussen een nieuwe annotatie op deze bepaling. Vergelijk ze; "
                                             "terugzetten kan pas als de nieuwe annotatie is verwijderd."})
    ids = [x["id"] for x in row.inhoud["elementen"]]
    if ids and (await conn.execute(select(e.c.id).where(e.c.id.in_(ids)))).first():
        raise HTTPException(409, {"fout": "element_bestaat", "melding": "Een markering uit de prullenbak bestaat "
                                  "intussen weer; terugzetten zou haar dubbel maken."})


async def _kanten_bestaan(conn, relatie: dict, terug: dict[str, set]) -> bool:
    """Bestaan beide eindpunten (teruggezet of nog aanwezig)? Een bron (een bronnode als eindpunt) bestaat altijd."""
    tabellen = {"element": db.annotatie_v2_elementen, "impliciet": db.annotatie_v2_impliciet}
    for kant in (relatie["van"], relatie["naar"]):
        soort = kant["soort"]
        if soort in tabellen and kant["id"] not in terug[soort] and not await _bestaat(conn, tabellen[soort], kant["id"]):
            return False
    return True


async def _zet_relaties_terug(conn, inhoud: dict, per_id: dict, eigen: set[str]) -> tuple[int, set[str]]:
    """Een relatie komt terug als haar dragerlaag er is en beide kanten bestaan. Geeft het aantal en de dragerlagen
    buiten de teruggezette lagen (die krijgen een revisie)."""
    rel = db.annotatie_v2_relaties
    terug = {"element": {x["id"] for x in inhoud["elementen"]}, "impliciet": {x["id"] for x in inhoud["impliciet"]}}
    aantal, geraakt = 0, set()
    for x in inhoud["relaties"]:
        if x["laag_id"] not in per_id or await _bestaat(conn, rel, x["id"]) \
                or not await _kanten_bestaan(conn, x["inhoud"], terug):
            continue
        await conn.execute(insert(rel).values(**x))
        aantal += 1
        if x["laag_id"] not in eigen:
            geraakt.add(x["laag_id"])
    return aantal, geraakt


async def _zet_rest_terug(conn, inhoud: dict) -> None:
    """Impliciete partijen, dekkingsrijen en artefactversies: alleen wat er niet (opnieuw) staat."""
    for x in inhoud["impliciet"]:
        if not await _bestaat(conn, db.annotatie_v2_impliciet, x["id"]):
            await conn.execute(insert(db.annotatie_v2_impliciet).values(**x))
    for x in inhoud["dekking"]:
        if not await _bestaat(conn, db.annotatie_v2_dekking, x["id"]):
            await conn.execute(insert(db.annotatie_v2_dekking).values(**x))
    ver = db.artefact_versies
    for x in inhoud["versies"]:
        if not (await conn.execute(select(ver.c.id).where(
                (ver.c.id == x["id"]) | ((ver.c.run_id == x["run_id"]) & (ver.c.sleutel == x["sleutel"]))))).first():
            await conn.execute(insert(ver).values(**{**x, "gemaakt": _dt(x["gemaakt"])}))


async def zet_terug(prullenbak_id: str, actor: str) -> dict:
    from .annotatie_v2_store import _audit, _lagen, _raak, schrijftransactie
    p = db.annotatie_v2_prullenbak
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(p).where(p.c.id == prullenbak_id).with_for_update())).first()
        if row is None:
            raise HTTPException(404, {"fout": "niet_in_prullenbak", "id": prullenbak_id})
        inhoud = row.inhoud
        await _weiger_bij_bezet(conn, row, await _lagen(conn))
        lagen = [{**l, "updated": _dt(l["updated"]), "geprojecteerd_revisie": 0} for l in inhoud["lagen"]]
        for layer in lagen:
            await conn.execute(insert(db.annotatie_v2_lagen).values(**layer))
        for x in inhoud["elementen"]:
            await conn.execute(insert(db.annotatie_v2_elementen).values(**x))
        await _zet_rest_terug(conn, inhoud)
        per_id = {l["id"]: l for l in (await _lagen(conn)).values()}
        relaties, geraakt = await _zet_relaties_terug(conn, inhoud, per_id, {l["id"] for l in lagen})
        for layer in lagen:
            await _raak(conn, layer, layer["snapshot_id"])
            await _audit(conn, actor, "laag-teruggezet", {
                "bron_iri": layer["bron_iri"], "laag_id": layer["id"], "prullenbak_id": prullenbak_id,
                "weergave": row.weergave_iri, "elementen": sorted(
                    x["id"] for x in inhoud["elementen"] if x["laag_id"] == layer["id"])}, laag_id=layer["id"])
        for laag_id in sorted(geraakt):
            await _raak(conn, per_id[laag_id], per_id[laag_id]["snapshot_id"])
        await conn.execute(delete(p).where(p.c.id == prullenbak_id))
    return {"teruggezet": {"lagen": len(lagen), "elementen": len(inhoud["elementen"]), "relaties": relaties,
                           "impliciet": len(inhoud["impliciet"])}, "weergave_iri": row.weergave_iri}


async def legen(actor: str, prullenbak_id: str | None = None, alles: bool = False) -> dict:
    """Definitief: een beheeractie. Zonder id alleen wat langer dan de bewaartermijn in de prullenbak ligt; met een id
    dat ene item, ook binnen de termijn (de beheerder kiest dat bewust). `alles` leegt alles."""
    from .annotatie_v2_store import _audit, schrijftransactie
    p = db.annotatie_v2_prullenbak
    grens = db.utcnow() - bewaartermijn()
    async with schrijftransactie() as conn:
        q = select(*_LICHT)
        if prullenbak_id:
            q = q.where(p.c.id == prullenbak_id)
        elif not alles:
            q = q.where(p.c.verwijderd_op <= grens)
        rows = (await conn.execute(q)).all()
        if prullenbak_id and not rows:
            raise HTTPException(404, {"fout": "niet_in_prullenbak", "id": prullenbak_id})
        for row in rows:
            await _audit(conn, actor, "prullenbak-geleegd", {
                "prullenbak_id": row.id, "weergave": row.weergave_iri, "bron_iris": list(row.bron_iris),
                "verwijderd_door": row.verwijderd_door, "verwijderd_op": _iso(row.verwijderd_op)})
        if rows:
            await conn.execute(delete(p).where(p.c.id.in_([r.id for r in rows])))
    return {"geleegd": len(rows), "bewaartermijn_dagen": get_settings().annotatie_prullenbak_dagen}


async def bron_verwijderd(conn, element_ids: set[str]) -> dict[str, dict]:
    """Per element dat niet meer bestaat: wanneer en door wie het verwijderd werd, bij welke bepaling, en of het nog in
    de prullenbak ligt (`prullenbak_id`, anders `None`: definitief weg). Uit de audit, dus ook voor wat verdween
    vóór er een prullenbak was. Een element zonder auditregel ontbreekt (onbekend waarom)."""
    if not element_ids:
        return {}
    a = db.annotatie_v2_audit
    uit: dict[str, dict] = {}
    rows = (await conn.execute(select(a.c.actie, a.c.detail, a.c.actor, a.c.tijdstip).where(
        a.c.actie.in_(("laag-verwijderd", "element-verwijderd"))).order_by(a.c.id.desc()))).all()
    for actie, detail, actor, tijdstip in rows:
        detail = detail or {}
        ids = (detail.get("elementen") or []) if actie == "laag-verwijderd" else [
            (detail.get("element") or {}).get("id")]
        for i in ids:
            if i in element_ids and i not in uit:
                uit[i] = {"op": _iso(tijdstip), "door": actor,
                          "weergave": detail.get("weergave") or (detail.get("element") or {}).get("eigenaar_iri", ""),
                          "prullenbak_id": detail.get("prullenbak_id")}
        if len(uit) == len(element_ids):
            break
    nog = {x for x in (await conn.execute(select(db.annotatie_v2_prullenbak.c.id).where(
        db.annotatie_v2_prullenbak.c.id.in_(sorted({v["prullenbak_id"] for v in uit.values() if v["prullenbak_id"]})))))
        .scalars().all()}
    for v in uit.values():
        if v["prullenbak_id"] not in nog:
            v["prullenbak_id"] = None
    return uit


async def met_bron_verwijderd(conn, items: list[dict]) -> list[dict]:
    """Zet `bron_verwijderd` op elk item (koppeling of drager, met `actualiteit`) waarvan het element verdween."""
    weg = {k["element_id"] for k in items if k.get("actualiteit") == "verdwenen"}
    if not weg:
        return items
    info = await bron_verwijderd(conn, weg)
    for k in items:
        if k.get("actualiteit") == "verdwenen" and k["element_id"] in info:
            k["bron_verwijderd"] = info[k["element_id"]]
    return items
