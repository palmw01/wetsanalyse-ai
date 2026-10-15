"""Voorstellen van Lex: runs van de begrippenketen en de betekenisgroepen (spoor D, levering 3).

- **De api bouwt het manifest, graph-qa rekent.** `start` legt het manifest vast; graph-qa haalt de
  run op, draait de keten en zet de uitkomst terug (`zet_uitkomst`). De api toetst die uitkomst:
  hetzelfde manifest, en elk element-id komt uit dat manifest (PLAN D, stap 5).
- **Idempotent op (werkgebied, manifest).** Dezelfde invoer geeft dezelfde groepen, dus een tweede
  start op hetzelfde manifest rekent niet opnieuw. Een run die blijft hangen (`wacht`/`loopt` zonder
  teken van leven, `VERLOPEN`) mag opnieuw.
- **Een besluit hoort bij de groep, niet bij de run.** Een groep-id is de inhoudshash van de keten;
  komt dezelfde groep in een latere run terug, dan blijft een afwijzing of overname staan.
- **Een besluit wijzigt nooit annotaties.** Overnemen maakt een begrip (concept) via `begrip_store`,
  met dezelfde regels als zelf maken: inventaris, bewijsstand, primaire duiding.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import timedelta
from typing import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import begrip_manifest, begrip_store, db
from .begrip_contracts import BegripInhoud, BegripInvoer, KoppelInvoer, KoppelRol
from .begrippen_run_contracts import GroepKoppeling, Overname, UitkomstInvoer
from .werkgebied_store import _audit as werkgebied_audit

Resolver = Callable[[dict], Awaitable[dict]]

#: Na zoveel stilte telt een run die niet klaar is als vastgelopen; dan mag hij opnieuw.
VERLOPEN = timedelta(minutes=5)


def _run(row, met_manifest: bool = False) -> dict:
    uit = {"id": row.id, "werkgebied_id": row.werkgebied_id, "manifest_id": row.manifest_id,
           "status": _status(row), "reden": row.reden, "overgeslagen": row.overgeslagen,
           "aantal_formuleringen": len(row.manifest.get("formuleringen", [])),
           "uitkomst": row.uitkomst, "vragen_besluiten": row.vragen_besluiten,
           "gestart_door": row.gestart_door, "gestart": db.aware(row.gestart).isoformat(),
           "gewijzigd": db.aware(row.gewijzigd).isoformat()}
    if met_manifest:
        uit["manifest"] = row.manifest
    return uit


def _status(row) -> str:
    if row.status in ("wacht", "loopt") and db.utcnow() - db.aware(row.gewijzigd) > VERLOPEN:
        return "mislukt"
    return row.status


async def _werkgebied(conn, werkgebied_id: str, slot: bool = False):
    t = db.werkgebieden
    q = select(t).where(t.c.id == werkgebied_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None or row.gearchiveerd is not None:
        raise HTTPException(404, "Werkgebied bestaat niet.")
    return row


async def start(werkgebied: dict, actor: str, resolve: Resolver) -> tuple[dict, bool]:
    """Bouwt het manifest en geeft de run erop: de bestaande als die er al is, anders een nieuwe.
    Geeft (run, nieuw)."""
    m = await begrip_manifest.bouw(werkgebied, resolve)
    if not m["volledig"]:
        raise HTTPException(409, {"fout": "inventaris_onvolledig",
                                  "melding": "Niet elke bron van het werkgebied kon worden opgehaald. Een voorstel op een "
                                             "onvolledige inventaris zou passages missen; probeer het zo opnieuw."})
    if len(m["manifest"]["formuleringen"]) < 2:
        raise HTTPException(409, {"fout": "te_weinig_passages",
                                  "melding": "Er zijn minder dan twee bruikbare passages; daar valt niets te groeperen."})
    r = db.begrippen_runs
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied["id"], slot=True)
        bestaand = (await conn.execute(select(r).where(
            r.c.werkgebied_id == werkgebied["id"], r.c.manifest_id == m["manifest_id"])
            .order_by(r.c.gestart.desc()).limit(1))).first()
        if bestaand is not None and _status(bestaand) in ("wacht", "loopt", "klaar"):
            return _run(bestaand), False
        nu, rid = db.utcnow(), str(uuid.uuid4())
        await conn.execute(insert(r).values(
            id=rid, werkgebied_id=werkgebied["id"], manifest_id=m["manifest_id"], manifest=m["manifest"],
            overgeslagen=m["overgeslagen"], status="wacht", vragen_besluiten={}, reden="", gestart_door=actor,
            gestart=nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied["id"], actor, "begrippen-run-gestart",
                               {"run": rid, "manifest_id": m["manifest_id"],
                                "formuleringen": len(m["manifest"]["formuleringen"])})
        row = (await conn.execute(select(r).where(r.c.id == rid))).first()
    return _run(row), True


async def haal(werkgebied_id: str, run_id: str, met_manifest: bool = False) -> dict:
    r = db.begrippen_runs
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        row = (await conn.execute(select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id))).first()
    if row is None:
        raise HTTPException(404, "Run bestaat niet.")
    return _run(row, met_manifest)


async def laatste(werkgebied: dict, resolve: Resolver) -> dict | None:
    """De laatste run, met `verouderd` als het werkgebied intussen een ander manifest geeft (een nieuwe
    annotatie, een bron erbij). Is de graaf weg, dan is dat onbekend (`None`), geen "actueel"."""
    r = db.begrippen_runs
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied["id"])
        row = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied["id"])
                                  .order_by(r.c.gestart.desc()).limit(1))).first()
    if row is None:
        return None
    try:
        huidig = (await begrip_manifest.bouw(werkgebied, resolve))["manifest_id"]
        verouderd: bool | None = huidig != row.manifest_id
    except HTTPException:
        verouderd = None
    return {**_run(row), "verouderd": verouderd}


async def _zet(run_id: str, **waarden) -> None:
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.begrippen_runs).where(db.begrippen_runs.c.id == run_id)
                           .values(gewijzigd=db.utcnow(), **waarden))


async def loopt(werkgebied_id: str, run_id: str) -> dict:
    """graph-qa begint (of leeft nog): de stilteklok begint opnieuw."""
    run = await haal(werkgebied_id, run_id)
    if run["status"] == "klaar":
        return run
    await _zet(run_id, status="loopt")
    return await haal(werkgebied_id, run_id)


async def mislukt(werkgebied_id: str, run_id: str, reden: str) -> dict:
    run = await haal(werkgebied_id, run_id)
    if run["status"] == "klaar":
        raise HTTPException(409, "De run is al klaar.")
    await _zet(run_id, status="mislukt", reden=reden)
    return await haal(werkgebied_id, run_id)


def _payload_hash(invoer: UitkomstInvoer) -> str:
    data = invoer.model_dump(mode="json", exclude={"meting"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def zet_uitkomst(werkgebied_id: str, run_id: str, invoer: UitkomstInvoer, actor: str) -> dict:
    r, g = db.begrippen_runs, db.betekenisgroepen
    h = _payload_hash(invoer)
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id)
                                  .with_for_update())).first()
        if row is None:
            raise HTTPException(404, "Run bestaat niet.")
        if row.status == "klaar":
            if row.uitkomst_hash == h:
                return _run(row)                              # dezelfde uitkomst nog eens: idempotent
            raise HTTPException(409, "Deze run heeft al een andere uitkomst.")
        if invoer.manifest_id != row.manifest_id:
            raise HTTPException(422, "De uitkomst hoort bij een ander manifest dan deze run.")
        bekend = {f["element_id"] for f in row.manifest["formuleringen"]}
        genoemd = {e for x in invoer.groepen for e in x.leden} | {e for x in invoer.relaties for e in (x.van, x.naar)} \
            | {e for x in invoer.vragen for e in (x.van, x.naar)}
        if genoemd - bekend:
            raise HTTPException(422, {"fout": "onbekend_element", "element_ids": sorted(genoemd - bekend),
                                      "melding": "De uitkomst noemt elementen die niet in het manifest staan."})
        bestaande = {x.id: x for x in (await conn.execute(select(g).where(g.c.werkgebied_id == werkgebied_id))).all()}
        for groep in invoer.groepen:
            waarden = {"run_id": run_id, "leden": groep.leden, "aandacht": groep.aandacht,
                       "voorstel": groep.voorstel.model_dump(), "uitleg": groep.uitleg, "conflicten": groep.conflicten}
            if groep.id in bestaande:                        # zelfde groep: het besluit blijft staan
                await conn.execute(update(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id == groep.id).values(**waarden))
            else:
                await conn.execute(insert(g).values(werkgebied_id=werkgebied_id, id=groep.id, besluit="open",
                                                    reden="", **waarden))
        uitkomst = invoer.model_dump(mode="json", exclude={"groepen"})
        uitkomst["groep_ids"] = [x.id for x in invoer.groepen]
        await conn.execute(update(r).where(r.c.id == run_id).values(
            status="klaar", uitkomst=uitkomst, uitkomst_hash=h, gewijzigd=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "begrippen-voorgesteld",
                               {"run": run_id, "groepen": len(invoer.groepen), "relaties": len(invoer.relaties),
                                "vragen": len(invoer.vragen)})
    return await haal(werkgebied_id, run_id)


# --- groepen ---------------------------------------------------------------------------------

_LIDWOORD = re.compile(r"^(de|het|een)\s+")


def _norm(s: str) -> str:
    return _LIDWOORD.sub("", s.strip().lower())


async def groepen(werkgebied_id: str) -> dict:
    """De groepen van de laatste klare run, met hun passages, besluit en de bestaande begrippen die
    erop lijken (deelt een passage, of draagt dezelfde naam als term)."""
    r, g = db.begrippen_runs, db.betekenisgroepen
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        run = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.status == "klaar")
                                  .order_by(r.c.gestart.desc()).limit(1))).first()
        if run is None:
            return {"run": None, "groepen": [], "passages": {}}
        ids = run.uitkomst.get("groep_ids", [])
        rows = {x.id: x for x in (await conn.execute(select(g).where(
            g.c.werkgebied_id == werkgebied_id, g.c.id.in_(ids)))).all()} if ids else {}
    passages = {f["element_id"]: f for f in run.manifest["formuleringen"]}
    labels = {b["bron_iri"]: b["label"] for b in run.manifest["bronnen"]}
    begrippen = await begrip_store.lijst(werkgebied_id)
    uit = []
    for gid in ids:
        x = rows.get(gid)
        if x is None:
            continue
        leden = set(x.leden)
        lijkt = [{"begrip_id": b["id"], "naam": b["inhoud"]["naam"],
                  "gedeeld": sorted(leden & set(b["element_ids"]))}
                 for b in begrippen
                 if leden & set(b["element_ids"]) or _norm(x.voorstel["naam"]) in
                 {_norm(b["inhoud"]["naam"]), *(_norm(t) for t in b["inhoud"].get("alternatieve_termen", []))}]
        uit.append({"id": x.id, "aandacht": x.aandacht, "voorstel": x.voorstel, "uitleg": x.uitleg,
                    "conflicten": x.conflicten, "besluit": x.besluit, "reden": x.reden, "begrip_id": x.begrip_id,
                    "besloten_door": x.besloten_door,
                    "leden": [_passage(passages[e], labels) for e in x.leden if e in passages],
                    "lijkt_op": lijkt})
    # Twijfelvragen en relaties noemen ook elementen buiten een groep; de werkplek toont ze letterlijk.
    genoemd = {e for x in (*run.uitkomst.get("vragen", []), *run.uitkomst.get("relaties", []))
               for e in (x["van"], x["naar"])}
    return {"run": _run(run), "groepen": uit,
            "passages": {e: _passage(passages[e], labels) for e in sorted(genoemd) if e in passages}}


def _passage(f: dict, labels: dict[str, str]) -> dict:
    return {"element_id": f["element_id"], "tekst": f["tekst"], "jas_klasse": f["jas_klasse"],
            "review_status": f["review_status"], "bron_iri": f["bron_iri"],
            "vindplaats": labels.get(f["bron_iri"], "")}


async def _groepen_rij(conn, werkgebied_id: str, groep_ids: list[str]):
    g = db.betekenisgroepen
    rows = (await conn.execute(select(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id.in_(groep_ids)))).all()
    if len(rows) != len(set(groep_ids)):
        raise HTTPException(404, "Niet elke groep bestaat.")
    return rows


async def _besluit(werkgebied_id: str, groep_ids: list[str], besluit: str, actor: str, reden: str = "",
                   begrip_id: str | None = None) -> None:
    g = db.betekenisgroepen
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        await _groepen_rij(conn, werkgebied_id, groep_ids)
        await conn.execute(update(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id.in_(groep_ids)).values(
            besluit=besluit, reden=reden, begrip_id=begrip_id, besloten_door=actor, besloten_op=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, f"groep-{besluit}",
                               {"groepen": groep_ids, "reden": reden, **({"begrip_id": begrip_id} if begrip_id else {})})


async def overnemen(werkgebied: dict, o: Overname, actor: str, resolve: Resolver) -> dict:
    """Eén begrip uit de gekozen groepen; de gekozen leden duiden het aan."""
    async with db.get_engine().connect() as conn:
        rows = await _groepen_rij(conn, werkgebied["id"], o.groep_ids)
    afgehandeld = [x.id for x in rows if x.besluit in ("overgenomen", "gekoppeld")]
    if afgehandeld:
        raise HTTPException(409, {"fout": "al_besloten", "groepen": afgehandeld,
                                  "melding": "Een van deze groepen is al overgenomen of gekoppeld."})
    alle = [e for x in rows for e in x.leden]
    leden = list(dict.fromkeys(o.element_ids if o.element_ids is not None else alle))
    buiten = set(leden) - set(alle)
    if buiten:
        # Een passage buiten de gekozen groepen ("samen" bij een twijfelvraag) mag, als ze in de
        # voorstellen staat die de jurist in beeld heeft: het manifest van de laatste klare run.
        r = db.begrippen_runs
        async with db.get_engine().connect() as conn:
            run = (await conn.execute(select(r.c.manifest).where(r.c.werkgebied_id == werkgebied["id"], r.c.status == "klaar")
                                      .order_by(r.c.gestart.desc()).limit(1))).first()
        in_manifest = {f["element_id"] for f in run.manifest["formuleringen"]} if run else set()
        if buiten - in_manifest:
            raise HTTPException(422, "Kies passages uit de voorstellen van dit werkgebied.")
    if not leden:
        raise HTTPException(422, "Kies minstens één passage.")
    if rows and not set(leden) & set(alle):
        # Een groep overnemen zonder één van haar eigen passages is geen overname van die groep.
        raise HTTPException(422, "Kies minstens één passage uit de gekozen groepen.")
    inhoud: dict = {"naam": o.naam}
    # De letterlijke brondefinitie gaat alleen mee als er precies één is: bij combineren kiest de
    # analist zelf.
    definities = {(x.voorstel.get("definitie") or "", x.voorstel.get("definitie_vindplaats") or "")
                  for x in rows if x.voorstel.get("definitie")}
    if o.met_definitie and len(definities) == 1:
        definitie, vindplaats = definities.pop()
        inhoud.update(definitie=definitie, definitie_herkomst="letterlijk",
                      onderbouwing=f"Letterlijk uit {vindplaats}." if vindplaats else "")
    begrip = await begrip_store.maak(werkgebied, BegripInvoer(inhoud=BegripInhoud(**inhoud), element_ids=leden,
                                                              rol=KoppelRol.duiding), actor, resolve)
    if o.groep_ids:
        await _besluit(werkgebied["id"], o.groep_ids, "overgenomen", actor, begrip_id=begrip["id"])
    return begrip


async def koppelen(werkgebied: dict, groep_id: str, k: GroepKoppeling, actor: str, resolve: Resolver) -> dict:
    async with db.get_engine().connect() as conn:
        [row] = await _groepen_rij(conn, werkgebied["id"], [groep_id])
    leden = k.element_ids if k.element_ids is not None else list(row.leden)
    if not leden or set(leden) - set(row.leden):
        raise HTTPException(422, "Kies passages uit deze groep.")
    huidig = await begrip_store.haal(werkgebied["id"], k.begrip_id)
    begrip = await begrip_store.koppel(werkgebied, k.begrip_id, KoppelInvoer(
        verwachte_revisie=huidig["revisie"], element_ids=leden), actor, resolve)
    await _besluit(werkgebied["id"], [groep_id], "gekoppeld", actor, begrip_id=k.begrip_id)
    return begrip


async def besluit(werkgebied_id: str, groep_id: str, soort: str, reden: str, actor: str) -> None:
    await _besluit(werkgebied_id, [groep_id], soort, actor, reden=reden)


async def vraag(werkgebied_id: str, run_id: str, kandidaat_id: str, antwoord: str, actor: str) -> dict:
    """Een twijfelvraag beantwoorden. "Samen" maakt nog niets: de werkplek biedt daarna de overname
    van beide aan. Het antwoord ligt vast, met wie en wanneer."""
    r = db.begrippen_runs
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = (await conn.execute(select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id)
                                  .with_for_update())).first()
        if row is None or not row.uitkomst:
            raise HTTPException(404, "Run bestaat niet of heeft nog geen uitkomst.")
        if kandidaat_id not in {v["kandidaat_id"] for v in row.uitkomst.get("vragen", [])}:
            raise HTTPException(404, "Deze vraag staat niet in de run.")
        besluiten = {**row.vragen_besluiten, kandidaat_id: {"antwoord": antwoord, "door": actor,
                                                            "op": db.utcnow().isoformat()}}
        await conn.execute(update(r).where(r.c.id == run_id).values(vragen_besluiten=besluiten))
        await werkgebied_audit(conn, werkgebied_id, actor, "vraag-beantwoord",
                               {"run": run_id, "kandidaat": kandidaat_id, "antwoord": antwoord})
    return await haal(werkgebied_id, run_id)


async def heropen_groep(werkgebied_id: str, groep_id: str, actor: str) -> None:
    g = db.betekenisgroepen
    async with db.get_engine().connect() as conn:
        [row] = await _groepen_rij(conn, werkgebied_id, [groep_id])
    if row.besluit in ("overgenomen", "gekoppeld"):
        raise HTTPException(409, {"fout": "al_besloten",
                                  "melding": "Deze groep is een begrip geworden; wijzig het begrip zelf."})
    await _besluit(werkgebied_id, [groep_id], "open", actor)
