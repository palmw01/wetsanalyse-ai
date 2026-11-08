"""Relaties tussen markeringen en impliciete partijen (ADR-011, deelactiviteit 2c).

Een relatie verbindt twee eindpunten: een markering (element, ook in een andere laag) of een impliciete partij. Ze hoort
bij de laag van de **drager**, de kant die de catalogus aanwijst (`jas_relaties.drager_kant`). Een mutatie raakt die
laag, dus alles loopt door het schrijfslot van `annotatie_v2_store`: revisie, 412, de auditregels en de projectie.

- Het type en de klassen toetst de api zelf tegen de catalogus; juridische juistheid niet.
- Het id volgt uit de inhoud (van, naar, type, volgorde): dezelfde relatie twee keer leggen is een 409.
- Bij het vastleggen bewaart de relatie de stand van beide eindpunten (`begrip_store.element_hash`). Wijkt een kant daar
  later van af, of is ze verworpen, verouderd of vervangen, dan is de relatie `veranderd` en vraagt ze een oordeel.
- Een gewist element of een gewiste impliciete partij neemt haar relaties mee (`wis_bij`), met een auditregel.
- Een impliciete partij is alleen een rechtssubject en alleen van de jurist. Ze is geen markering: geen ankers, geen
  dekking, en ze telt niet in de inventaris.
- Een voorstel van de keten komt mee in de batch (`leg_voorstellen`, binnen de transactie van `annotatie_v2_store.batch`):
  eindpunten als ankers, omgezet naar de elementen die de batch net opsloeg. Wat niet op te lossen is, wordt gemeld en
  nooit geraden. Een ronde `opnieuw` zet oude voorstellen zonder oordeel die ze niet meer maakte op `vervangen`.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, insert, select, update

from . import db
from . import jas_relaties
from .annotatie_v2_contracts import (AFGEHANDELD, NIET_ACTUEEL, Eindpunt, ImplicietInvoer, Lifecycle, RelatieBeslissing,
                                      RelatieInvoer, RelatieVoorstel, is_vervangen)
from .annotatie_v2_store import _audit, _laag, _lagen, _raak, leestransactie, publiek_laag, schrijftransactie, zonder_meting
from .begrip_store import element_hash


def relatie_id(van: dict, naar: dict, type_: str, volgorde: int | None) -> str:
    """`R` + hash van wat de relatie is. Dezelfde relatie is dus hetzelfde id, ook als een agent haar later voorstelt."""
    sleutel = json.dumps([van["soort"], van["id"], naar["soort"], naar["id"], type_, volgorde], ensure_ascii=False)
    return "R" + hashlib.sha256(sleutel.encode()).hexdigest()[:16]


def _impliciet_stand(i: dict) -> str:
    return hashlib.sha256(json.dumps([i["klasse"], i["label"]], ensure_ascii=False).encode()).hexdigest()[:32]


async def _alle(conn, tabel) -> dict[str, dict]:
    return {r["id"]: dict(r["inhoud"]) for r in (await conn.execute(select(tabel))).mappings().all()}


def _info(ep: dict, elementen: dict, impliciet: dict) -> dict | None:
    """Wat een eindpunt nu is: klasse, subtype, laag, een korte tekst en de stand. None als het niet (meer) bestaat."""
    if ep["soort"] == "element":
        e = elementen.get(ep["id"])
        if e is None:
            return None
        actueel = not e.get("verouderd") and not is_vervangen(e) and e.get("lifecycle") != Lifecycle.rejected.value
        return {"klasse": e["klasse"], "subtype": e.get("jas_subtype", ""), "laag_id": e["laag_id"],
                "tekst": e["tekst"], "actueel": actueel, "stand": element_hash(e)}
    i = impliciet.get(ep["id"])
    if i is None:
        return None
    return {"klasse": i["klasse"], "subtype": "", "laag_id": i["laag_id"], "tekst": i["label"], "actueel": True,
            "impliciet": True, "stand": _impliciet_stand(i)}


def _layers_per_id(layers: dict) -> dict[str, dict]:
    return {layer["id"]: layer for layer in layers.values()}


async def _dragerlaag(conn, layers: dict, laag_id: str, verwachte_revisies: dict) -> dict:
    """De laag van de drager, getoetst op revisie (412) en status (409, heropen eerst) zoals een element."""
    layer = _layers_per_id(layers).get(laag_id)
    if layer is None:
        raise HTTPException(404, "De laag van de drager bestaat niet meer.")
    return await _laag(conn, layers, layer["bron_iri"], layer["snapshot_id"], verwachte_revisies)


def _beslissing(type_: str, actor: str, comment: str = "") -> dict:
    return {"type": type_, "actor": actor, "tijd": db.utcnow().isoformat(), "comment": comment}


async def leg(req: RelatieInvoer, actor: str) -> dict:
    """Een relatie van de jurist: meteen vastgesteld (`human_approved`), zoals een eigen markering."""
    t = jas_relaties.type_van(req.type)
    if t is None:
        raise HTTPException(422, {"fout": "onbekend_type", "melding": f"Het relatietype {req.type!r} bestaat niet."})
    van, naar = req.van.model_dump(), req.naar.model_dump()
    if van == naar:
        raise HTTPException(422, {"fout": "naar_zichzelf", "melding": "Een relatie verbindt twee verschillende eindpunten."})
    if req.volgorde is not None and not t["volgorde"]:
        raise HTTPException(422, {"fout": "geen_volgorde", "melding": f"Een relatie {req.type} heeft geen volgorde."})
    async with schrijftransactie() as conn:
        elementen = await _alle(conn, db.annotatie_v2_elementen)
        impliciet = await _alle(conn, db.annotatie_v2_impliciet)
        info_van, info_naar = _info(van, elementen, impliciet), _info(naar, elementen, impliciet)
        for kant, info in (("van", info_van), ("naar", info_naar)):
            if info is None:
                raise HTTPException(404, {"fout": "eindpunt_onbekend", "melding": f"Het eindpunt aan de kant {kant} bestaat niet."})
            if not info["actueel"]:
                raise HTTPException(422, {"fout": "eindpunt_niet_actueel",
                                          "melding": f"Het eindpunt aan de kant {kant} is verworpen, verouderd of vervangen."})
        if not jas_relaties.toegestaan(req.type, info_van["klasse"], info_naar["klasse"],
                                       info_van["subtype"], info_naar["subtype"]):
            raise HTTPException(422, {"fout": "klassen_passen_niet", "melding":
                                      f"Een relatie {req.type} ({t['leesvorm']}) past niet tussen "
                                      f"{info_van['klasse']} en {info_naar['klasse']}."})
        rid = relatie_id(van, naar, req.type, req.volgorde)
        if (await conn.execute(select(db.annotatie_v2_relaties.c.id).where(db.annotatie_v2_relaties.c.id == rid))).first():
            raise HTTPException(409, {"fout": "al_vastgelegd", "melding": "Deze relatie staat er al.", "id": rid})
        if req.volgorde is not None:
            # Uniek per regel of operator: twee operanden op plek 1 zeggen niets over de volgorde.
            for r in (await _alle(conn, db.annotatie_v2_relaties)).values():
                if r["type"] == req.type and r["naar"] == naar and r.get("volgorde") == req.volgorde:
                    raise HTTPException(409, {"fout": "volgorde_bezet",
                                              "melding": f"Plek {req.volgorde} is bij dit eindpunt al bezet."})
        layers = await _lagen(conn)
        drager = info_van if jas_relaties.drager_kant(req.type) == "van" else info_naar
        layer = await _dragerlaag(conn, layers, drager["laag_id"], req.verwachte_revisies)
        relatie = {"id": rid, "type": req.type, "van": van, "naar": naar, "volgorde": req.volgorde,
                   "toelichting": req.toelichting, "herkomst": "mens", "aangemaakt_door": actor,
                   "lifecycle": Lifecycle.human_approved.value, "aandacht": None, "laag_id": layer["id"],
                   "stand_van": info_van["stand"], "stand_naar": info_naar["stand"],
                   "beslissingen": [_beslissing("markering", actor)]}
        await conn.execute(insert(db.annotatie_v2_relaties).values(id=rid, laag_id=layer["id"], inhoud=relatie))
        await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "relatie-gelegd", {"relatie": relatie}, None, layer["id"])
        return {"relatie": beschrijf(relatie, elementen, impliciet), "laag": publiek_laag(layer)}


def _ankersleutel(ankers: list[dict]) -> tuple:
    return tuple((a["bron_iri"], a["start"], a["eind"], a["bron_hash"]) for a in ankers)


def _los_op(r: RelatieVoorstel, per_anker: dict[tuple, list[dict]], elementen: dict, impliciet: dict
            ) -> tuple[dict, dict, dict, dict] | str:
    """De eindpunten van één voorstel: het element in de batch met precies die ankers, aan elke kant. Staan er twee
    markeringen op dezelfde ankers (twee klassen), dan beslist de catalogus, maar alleen als er precies één paar past.
    Geeft (van, naar, info_van, info_naar), of de reden waarom het niet kan."""
    t = jas_relaties.type_van(r.type)
    if t is None:
        return "onbekend_type"
    if r.volgorde is not None and not t["volgorde"]:
        return "geen_volgorde"
    kanten = []
    for kant, ankers in (("van", r.van_ankers), ("naar", r.naar_ankers)):
        kandidaten = per_anker.get(_ankersleutel([a.model_dump() for a in ankers]), [])
        if not kandidaten:
            return f"eindpunt_onbekend:{kant}"
        kanten.append(kandidaten)
    paren = []
    for a in kanten[0]:
        for b in kanten[1]:
            van, naar = {"soort": "element", "id": a["id"]}, {"soort": "element", "id": b["id"]}
            info_van, info_naar = _info(van, elementen, impliciet), _info(naar, elementen, impliciet)
            if van != naar and info_van and info_naar and jas_relaties.toegestaan(
                    r.type, info_van["klasse"], info_naar["klasse"], info_van["subtype"], info_naar["subtype"]):
                paren.append((van, naar, info_van, info_naar))
    if not paren:
        return "naar_zichzelf" if kanten[0] == kanten[1] and len(kanten[0]) == 1 else "klassen_passen_niet"
    if len(paren) > 1:
        return "dubbelzinnig"
    van, naar, info_van, info_naar = paren[0]
    if not (info_van["actueel"] and info_naar["actueel"]):
        return "eindpunt_niet_actueel"
    return paren[0]


async def leg_voorstellen(conn, req, saved: list[dict], layers: dict, touched: dict, scope: set[str], actor: str,
                          *, opnieuw: bool) -> dict:
    """In de lopende schrijftransactie van een batch (`annotatie_v2_store.batch`), ná de elementen: de
    relatievoorstellen van de keten (ADR-011).

    - Een eindpunt is het element in `saved` met precies die ankers; wat niet op te lossen is, staat in
      `overgeslagen` met een reden, nooit geraden.
    - De catalogus toetst klassen, richting en subtype (`toegestaan`), zoals bij `leg`.
    - Vastgelegd als `herkomst: "agent"`, `lifecycle: "voorgesteld"`, `aandacht: "groen"`, met het spoor van de keten.
      Het id volgt uit de inhoud: een gelijk voorstel blijft gelijk, een afgewezen voorstel komt niet terug, en een
      vervangen voorstel leeft weer op.
    - `opnieuw` (een ronde opnieuw met voltooide dekking): een oud voorstel van Lex in het bereik, zonder oordeel en niet
      opnieuw voorgesteld, wordt `vervangen`. Een relatie van de jurist blijft altijd staan.

    De dragerlaag gaat in `touched`; de batch raakt haar daarna één keer (`_raak`)."""
    elementen = await _alle(conn, db.annotatie_v2_elementen)
    impliciet = await _alle(conn, db.annotatie_v2_impliciet)
    bestaand = await _alle(conn, db.annotatie_v2_relaties)
    per_laag = _layers_per_id(layers)
    per_anker: dict[tuple, list[dict]] = {}
    for e in saved:
        huidig = elementen.get(e["id"], e)
        lijst = per_anker.setdefault(_ankersleutel(huidig["ankers"]), [])
        if all(x["id"] != huidig["id"] for x in lijst):
            lijst.append(huidig)

    nieuw: dict[str, tuple[dict, RelatieVoorstel]] = {}
    overgeslagen = []
    for i, r in enumerate(req.relaties):
        opgelost = _los_op(r, per_anker, elementen, impliciet)
        if isinstance(opgelost, str):
            overgeslagen.append({"index": i, "type": r.type, "reden": opgelost})
            continue
        van, naar, info_van, info_naar = opgelost
        drager = info_van if jas_relaties.drager_kant(r.type) == "van" else info_naar
        layer = per_laag.get(drager["laag_id"])
        if layer is None or layer["status"] != "in_review":
            overgeslagen.append({"index": i, "type": r.type, "reden": "laag_afgerond"})
            continue
        rid = relatie_id(van, naar, r.type, r.volgorde)
        nieuw.setdefault(rid, ({"id": rid, "type": r.type, "van": van, "naar": naar, "volgorde": r.volgorde,
                                "toelichting": "", "herkomst": "agent", "aangemaakt_door": actor,
                                "lifecycle": Lifecycle.voorgesteld.value, "aandacht": "groen", "laag_id": layer["id"],
                                "stand_van": info_van["stand"], "stand_naar": info_naar["stand"],
                                "spoor": r.spoor, "geproduceerd_door": zonder_meting(req.run),
                                "beslissingen": []}, r))

    async def raak(laag_id: str) -> None:
        layer = per_laag[laag_id]
        if layer["bron_iri"] not in touched:
            touched[layer["bron_iri"]] = await _laag(conn, layers, layer["bron_iri"], req.snapshot_id,
                                                     req.verwachte_revisies)

    vervangen = []
    if opnieuw:
        for r in sorted(bestaand.values(), key=lambda r: r["id"]):
            layer = per_laag.get(r["laag_id"])
            if (r["id"] in nieuw or r.get("herkomst") != "agent" or r.get("lifecycle") != Lifecycle.voorgesteld.value
                    or r.get("beslissingen") or layer is None or layer["bron_iri"] not in scope
                    or layer["status"] != "in_review"):
                continue
            await raak(r["laag_id"])
            r = {**r, "lifecycle": Lifecycle.vervangen.value,
                 "vervangen_in": {"batch_id": req.batch_id, "tijd": db.utcnow().isoformat()}}
            await conn.execute(update(db.annotatie_v2_relaties).where(
                db.annotatie_v2_relaties.c.id == r["id"]).values(inhoud=r))
            await _audit(conn, actor, "relatie-vervangen", {"relatie": r["id"], "batch_id": req.batch_id}, None,
                         r["laag_id"])
            bestaand[r["id"]] = r
            vervangen.append(r["id"])

    gelegd = []
    for rid, (relatie, r) in nieuw.items():
        oud = bestaand.get(rid)
        if oud is not None and oud.get("lifecycle") not in NIET_ACTUEEL:
            gelegd.append(rid)                     # gelijk voorstel blijft gelijk; een oordeel erover ook
            continue
        if relatie["volgorde"] is not None and any(
                x["id"] != rid and x["type"] == relatie["type"] and x["naar"] == relatie["naar"]
                and x.get("volgorde") == relatie["volgorde"]
                and x.get("lifecycle") not in (*NIET_ACTUEEL, Lifecycle.rejected.value) for x in bestaand.values()):
            overgeslagen.append({"index": req.relaties.index(r), "type": r.type, "reden": "volgorde_bezet"})
            continue
        await raak(relatie["laag_id"])
        if oud is not None:                        # een vervangen voorstel dat terugkomt, leeft op
            relatie = {**{k: v for k, v in oud.items() if k != "vervangen_in"}, **relatie,
                       "beslissingen": oud.get("beslissingen", [])}
            await conn.execute(update(db.annotatie_v2_relaties).where(
                db.annotatie_v2_relaties.c.id == rid).values(laag_id=relatie["laag_id"], inhoud=relatie))
            await _audit(conn, actor, "relatie-hersteld", {"relatie": rid, "batch_id": req.batch_id}, None,
                         relatie["laag_id"])
        else:
            await conn.execute(insert(db.annotatie_v2_relaties).values(id=rid, laag_id=relatie["laag_id"],
                                                                      inhoud=relatie))
            await _audit(conn, actor, "relatie-voorgesteld", {"relatie": relatie, "batch_id": req.batch_id}, None,
                         relatie["laag_id"])
        bestaand[rid] = relatie
        gelegd.append(rid)
    return {"relaties": gelegd, "overgeslagen": sorted(overgeslagen, key=lambda x: x["index"]), "vervangen": vervangen}


async def beslis(relatie_id_: str, req: RelatieBeslissing, actor: str) -> dict:
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(db.annotatie_v2_relaties).where(
            db.annotatie_v2_relaties.c.id == relatie_id_))).mappings().first()
        if row is None:
            raise HTTPException(404, "Relatie niet gevonden.")
        relatie = dict(row["inhoud"])
        afgewezen = relatie["lifecycle"] == Lifecycle.rejected.value
        if afgewezen and req.type not in ("heropen", "comment"):
            raise HTTPException(409, {"fout": "heropen_nodig", "melding": "Heropen de relatie voordat je erover beslist."})
        if req.type == "heropen" and relatie["lifecycle"] not in AFGEHANDELD:
            raise HTTPException(409, {"fout": "niet_afgehandeld", "melding": "Er is niets te heropenen."})
        layers = await _lagen(conn)
        layer = await _dragerlaag(conn, layers, row["laag_id"], req.verwachte_revisies)
        elementen = await _alle(conn, db.annotatie_v2_elementen)
        impliciet = await _alle(conn, db.annotatie_v2_impliciet)
        if req.type == "approve":
            info_van, info_naar = _info(relatie["van"], elementen, impliciet), _info(relatie["naar"], elementen, impliciet)
            if not (info_van and info_naar and info_van["actueel"] and info_naar["actueel"]):
                raise HTTPException(422, {"fout": "eindpunt_niet_actueel",
                                          "melding": "Een eindpunt is verworpen, verouderd of weg; goedkeuren kan niet."})
            if not jas_relaties.toegestaan(relatie["type"], info_van["klasse"], info_naar["klasse"],
                                           info_van["subtype"], info_naar["subtype"]):
                raise HTTPException(422, {"fout": "klassen_passen_niet", "melding":
                                          "Een eindpunt wisselde van klasse; deze relatie past daar niet meer bij."})
            relatie.update(lifecycle=Lifecycle.human_approved.value, stand_van=info_van["stand"], stand_naar=info_naar["stand"])
        elif req.type == "reject":
            relatie["lifecycle"] = Lifecycle.rejected.value
        elif req.type == "heropen":
            relatie["lifecycle"] = Lifecycle.voorgesteld.value
        relatie["beslissingen"] = [*relatie.get("beslissingen", []), _beslissing(req.type, actor, req.comment)]
        await conn.execute(update(db.annotatie_v2_relaties).where(
            db.annotatie_v2_relaties.c.id == relatie_id_).values(inhoud=relatie))
        await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "relatie-beoordeeld", {"type": req.type, "comment": req.comment}, None, layer["id"])
        return {"relatie": beschrijf(relatie, elementen, impliciet), "laag": publiek_laag(layer)}


async def wis(relatie_id_: str, verwachte_revisies: dict, actor: str) -> dict:
    """Alleen een eigen relatie; een voorstel van Lex wijs je af, dan blijft het als historie staan."""
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(db.annotatie_v2_relaties).where(
            db.annotatie_v2_relaties.c.id == relatie_id_))).mappings().first()
        if row is None:
            raise HTTPException(404, "Relatie niet gevonden.")
        relatie = row["inhoud"]
        if relatie.get("herkomst") != "mens" or relatie.get("aangemaakt_door") != actor:
            raise HTTPException(409, {"fout": "niet_eigen", "melding": "Alleen een eigen relatie kun je wissen; wijs een voorstel af."})
        layer = await _dragerlaag(conn, await _lagen(conn), row["laag_id"], verwachte_revisies)
        await conn.execute(delete(db.annotatie_v2_relaties).where(db.annotatie_v2_relaties.c.id == relatie_id_))
        await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "relatie-gewist", {"relatie": relatie}, None, layer["id"])
        return {"gewist": relatie_id_, "laag": publiek_laag(layer)}


async def maak_impliciet(req: ImplicietInvoer, snapshot: dict, actor: str) -> dict:
    if req.snapshot_id != snapshot["snapshot_id"]:
        raise HTTPException(409, "Bronstand gewijzigd; laad het bereik opnieuw.")
    if req.klasse not in jas_relaties.IMPLICIET_TOEGESTAAN:
        raise HTTPException(422, {"fout": "klasse_niet_impliciet", "melding": "Een impliciete partij is een rechtssubject."})
    async with schrijftransactie() as conn:
        if req.zelfde_als:
            el = (await _alle(conn, db.annotatie_v2_elementen)).get(req.zelfde_als)
            if el is None or el["klasse"] != req.klasse:
                raise HTTPException(422, {"fout": "zelfde_als_onbekend",
                                          "melding": "`zelfde_als` moet een markering met dezelfde klasse zijn."})
        layers = await _lagen(conn)
        iri = snapshot["doel"]["bron_iri"]
        layer = await _laag(conn, layers, iri, snapshot["snapshot_id"], req.verwachte_revisies)
        partij = {"id": "I" + uuid.uuid4().hex[:16], "klasse": req.klasse, "label": req.label.strip(),
                  "toelichting": req.toelichting.strip(), "vindplaats": req.vindplaats, "zelfde_als": req.zelfde_als,
                  "herkomst": "mens", "aangemaakt_door": actor, "laag_id": layer["id"], "op": db.utcnow().isoformat()}
        await conn.execute(insert(db.annotatie_v2_impliciet).values(id=partij["id"], laag_id=layer["id"], inhoud=partij))
        await _raak(conn, layer, snapshot["snapshot_id"])
        await _audit(conn, actor, "impliciet-gemaakt", {"impliciet": partij}, None, layer["id"])
        return {"impliciet": partij, "laag": publiek_laag(layer)}


async def wis_impliciet(impliciet_id: str, verwachte_revisies: dict, actor: str) -> dict:
    async with schrijftransactie() as conn:
        row = (await conn.execute(select(db.annotatie_v2_impliciet).where(
            db.annotatie_v2_impliciet.c.id == impliciet_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Impliciete partij niet gevonden.")
        if row["inhoud"].get("aangemaakt_door") != actor:
            raise HTTPException(409, {"fout": "niet_eigen", "melding": "Alleen wie de partij maakte, kan haar wissen."})
        layers = await _lagen(conn)
        layer = await _dragerlaag(conn, layers, row["laag_id"], verwachte_revisies)
        gewist = await wis_bij(conn, actor, layers, impliciet_ids={impliciet_id})
        await conn.execute(delete(db.annotatie_v2_impliciet).where(db.annotatie_v2_impliciet.c.id == impliciet_id))
        if layer["id"] not in gewist["geraakt"]:
            await _raak(conn, layer, layer["snapshot_id"])
        await _audit(conn, actor, "impliciet-gewist", {"impliciet": row["inhoud"]}, None, layer["id"])
        return {"gewist": impliciet_id, "relaties": gewist["relaties"], "laag": publiek_laag(layer)}


async def wis_bij(conn, actor: str, layers: dict, *, element_ids: set[str] = frozenset(),
                  impliciet_ids: set[str] = frozenset(), laag_ids: set[str] = frozenset()) -> dict:
    """In een lopende schrijftransactie: wis de relaties met een eindpunt dat weggaat, of in een laag die weggaat, en
    de impliciete partijen van die lagen. Een dragerlaag die blijft, krijgt een revisie. Geeft de gewiste relaties en
    de geraakte lagen."""
    impliciet = await _alle(conn, db.annotatie_v2_impliciet)
    weg_impliciet = set(impliciet_ids) | {i for i, p in impliciet.items() if p["laag_id"] in laag_ids}
    weg = {("element", e) for e in element_ids} | {("impliciet", i) for i in weg_impliciet}
    per_id = _layers_per_id(layers)
    geraakt: set[str] = set()
    gewist = []
    for r in (await _alle(conn, db.annotatie_v2_relaties)).values():
        kanten = {(r["van"]["soort"], r["van"]["id"]), (r["naar"]["soort"], r["naar"]["id"])}
        if r["laag_id"] not in laag_ids and not kanten & weg:
            continue
        await conn.execute(delete(db.annotatie_v2_relaties).where(db.annotatie_v2_relaties.c.id == r["id"]))
        await _audit(conn, actor, "relatie-gewist", {"relatie": r, "reden": "eindpunt of laag gewist"}, None,
                     r["laag_id"] if r["laag_id"] in per_id else None)
        gewist.append(r["id"])
        layer = per_id.get(r["laag_id"])
        if layer and r["laag_id"] not in laag_ids and r["laag_id"] not in geraakt:
            await _raak(conn, layer, layer["snapshot_id"])
            geraakt.add(r["laag_id"])
    rest = weg_impliciet - set(impliciet_ids)
    if rest:
        await conn.execute(delete(db.annotatie_v2_impliciet).where(db.annotatie_v2_impliciet.c.id.in_(sorted(rest))))
    return {"relaties": gewist, "geraakt": geraakt, "impliciet": sorted(rest)}


def beschrijf(relatie: dict, elementen: dict, impliciet: dict) -> dict:
    """Een relatie zoals een lezer haar ziet: met de leesvorm, wat de eindpunten nu zijn, en `veranderd`."""
    t = jas_relaties.type_van(relatie["type"]) or {}
    info_van, info_naar = _info(relatie["van"], elementen, impliciet), _info(relatie["naar"], elementen, impliciet)

    def kant(ep, info):
        if info is None:
            return {**ep, "bestaat": False}
        return {**ep, "bestaat": True, "klasse": info["klasse"], "tekst": info["tekst"], "laag_id": info["laag_id"],
                "actueel": info["actueel"]}
    veranderd = not (info_van and info_naar and info_van["actueel"] and info_naar["actueel"]
                     and info_van["stand"] == relatie.get("stand_van") and info_naar["stand"] == relatie.get("stand_naar"))
    return {**{k: v for k, v in relatie.items() if k not in ("van", "naar")}, "leesvorm": t.get("leesvorm", ""),
            "van": kant(relatie["van"], info_van), "naar": kant(relatie["naar"], info_naar), "veranderd": veranderd}


async def bij_weergave(conn, element_ids: set[str], laag_ids: set[str], elementen: dict) -> tuple[list[dict], list[dict]]:
    """De relaties en impliciete partijen die bij een weergave horen: een eindpunt in beeld, of de drager in een van
    de lagen. Impliciete partijen: die in de lagen, en die waar een getoonde relatie naar wijst."""
    impliciet = await _alle(conn, db.annotatie_v2_impliciet)
    relaties = []
    for r in sorted((await _alle(conn, db.annotatie_v2_relaties)).values(), key=lambda r: r["id"]):
        if r.get("lifecycle") in NIET_ACTUEEL:
            continue                               # net als een vervangen element: historie, niet in beeld
        eind = {k["id"] for k in (r["van"], r["naar"]) if k["soort"] == "element"}
        if r["laag_id"] in laag_ids or eind & element_ids:
            relaties.append(beschrijf(r, elementen, impliciet))
    genoemd = {k["id"] for r in relaties for k in (r["van"], r["naar"]) if k["soort"] == "impliciet"}
    partijen = [p for i, p in sorted(impliciet.items()) if p["laag_id"] in laag_ids or i in genoemd]
    return relaties, partijen


async def alle_relaties() -> tuple[list[dict], list[dict]]:
    """Alle relaties (beschreven, zoals in een weergave) en alle impliciete partijen in één leestransactie, voor de
    complete graaf (`graaf.py`). Een partij draagt `bron_iri`: de bronnode van haar laag, zodat de graaf haar kan
    toetsen tegen de regelingen in beeld."""
    async with leestransactie() as conn:
        elementen = await _alle(conn, db.annotatie_v2_elementen)
        impliciet = await _alle(conn, db.annotatie_v2_impliciet)
        relaties = await _alle(conn, db.annotatie_v2_relaties)
        per_id = _layers_per_id(await _lagen(conn))
    beschreven = [beschrijf(r, elementen, impliciet) for _, r in sorted(relaties.items())]
    partijen = [{**p, "bron_iri": (per_id.get(p["laag_id"]) or {}).get("bron_iri", "")} for _, p in sorted(impliciet.items())]
    return beschreven, partijen


async def bij_elementen(element_ids: set[str]) -> list[dict]:
    """De relaties met een eindpunt onder deze markeringen, beschreven zoals de weergave ze toont, voor het werkgebiedrapport.
    Daarbij de operanden en waarden van een operator of parameter die eraan hangt, ook als die elders staat: zonder die
    stap is het regelskelet van een afleidingsregel niet compleet. Een element-eindpunt draagt ook zijn `eigenaar_iri`, zodat
    de lezer weet bij welke bepaling het hoort. Afgewezen relaties komen mee; de lezer kiest wat hij toont."""
    async with leestransactie() as conn:
        elementen = await _alle(conn, db.annotatie_v2_elementen)
        impliciet = await _alle(conn, db.annotatie_v2_impliciet)
        alle = await _alle(conn, db.annotatie_v2_relaties)

    def eindpunten(r: dict) -> set[str]:
        return {k["id"] for k in (r["van"], r["naar"]) if k["soort"] == "element"}
    gekozen = {i: r for i, r in alle.items() if eindpunten(r) & element_ids}
    verder = {e for r in gekozen.values() for e in eindpunten(r)} - set(element_ids)
    gekozen |= {i: r for i, r in alle.items() if r["type"] in ("operand", "waarde")
                and r["naar"]["soort"] == "element" and r["naar"]["id"] in verder}
    uit = []
    for _i, r in sorted(gekozen.items()):
        b = beschrijf(r, elementen, impliciet)
        for kant in ("van", "naar"):
            e = elementen.get(b[kant]["id"]) if b[kant]["soort"] == "element" else None
            b[kant] = {**b[kant], "eigenaar_iri": e["eigenaar_iri"] if e else ""}
        uit.append(b)
    return uit
