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
- **Akkoord is één transactie** (fase D): begrip, koppelingen als beoordeeld, accorderen als de poort
  het toelaat, groepsbesluit en eventueel de twijfelvraag – samen vastgelegd of samen niet. Overnemen
  en koppelen gaan langs hetzelfde pad, zonder het akkoord.
- **Splitsen laat de rest staan.** Worden niet alle leden van een groep een begrip, dan blijft de groep
  open met de overige leden (`afgehandeld`); pas als alle leden zijn afgehandeld is hij overgenomen.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import timedelta
from typing import Awaitable, Callable

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import insert, select, update

from . import begrip_onderzoek, begrip_store, db
from .begrip_contracts import BegripInhoud
from .begrippen_run_contracts import Aanpassing, Akkoord, GroepKoppeling, Overname, UitkomstInvoer
from .werkgebied_store import _audit as werkgebied_audit

Resolver = Callable[[dict], Awaitable[dict]]

#: Na zoveel stilte telt een run die niet klaar is als vastgelopen; dan mag hij opnieuw.
VERLOPEN = timedelta(minutes=5)


def _run(row, met_manifest: bool = False) -> dict:
    uit = {"id": row.id, "werkgebied_id": row.werkgebied_id, "manifest_id": row.manifest_id,
           "onderzoek_id": row.onderzoek_id or "", "onderzoek_samenvatting": onderzoek_samenvatting(row.onderzoek),
           "status": _status(row), "reden": row.reden, "overgeslagen": row.overgeslagen,
           "aantal_formuleringen": len(row.manifest.get("formuleringen", [])),
           "uitkomst": row.uitkomst, "vragen_besluiten": row.vragen_besluiten,
           "gestart_door": row.gestart_door, "gestart": db.aware(row.gestart).isoformat(),
           "gewijzigd": db.aware(row.gewijzigd).isoformat()}
    if met_manifest:
        uit["manifest"] = row.manifest
        uit["onderzoek"] = row.onderzoek
    return uit


def onderzoek_samenvatting(onderzoek: dict | None) -> dict | None:
    """Wat de werkplek en het gesprek over het onderzoek zeggen: hoeveel bronnen, en wat ontbreekt."""
    if not onderzoek:
        return None
    per_reden: dict[str, int] = {}
    for b in onderzoek.get("bronnen") or []:
        per_reden[b["reden"]] = per_reden.get(b["reden"], 0) + 1
    ontbrekend: dict[str, int] = {}
    for o in onderzoek.get("ontbrekend") or []:
        ontbrekend[o["reden"]] = ontbrekend.get(o["reden"], 0) + 1
    return {"bronnen": len(onderzoek.get("bronnen") or []), "per_reden": per_reden,
            "begrippen": len(onderzoek.get("begrippen") or []), "ontbrekend": ontbrekend}



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
    Geeft (run, nieuw). De sleutel is (werkgebied, manifest, onderzoek): een nieuwe contextbron of een
    gewijzigde bepaling ernaast is een andere invoer."""
    m = await begrip_onderzoek.manifest_en_onderzoek(werkgebied, resolve)
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
            r.c.werkgebied_id == werkgebied["id"], r.c.manifest_id == m["manifest_id"],
            r.c.onderzoek_id == m["onderzoek_id"])
            .order_by(r.c.gestart.desc()).limit(1))).first()
        if bestaand is not None and _status(bestaand) in ("wacht", "loopt", "klaar"):
            return _run(bestaand), False
        nu, rid = db.utcnow(), str(uuid.uuid4())
        await conn.execute(insert(r).values(
            id=rid, werkgebied_id=werkgebied["id"], manifest_id=m["manifest_id"], manifest=m["manifest"],
            onderzoek_id=m["onderzoek_id"], onderzoek=m["onderzoek"],
            overgeslagen=m["overgeslagen"], status="wacht", vragen_besluiten={}, reden="", gestart_door=actor,
            gestart=nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied["id"], actor, "begrippen-run-gestart",
                               {"run": rid, "manifest_id": m["manifest_id"], "onderzoek_id": m["onderzoek_id"],
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
    """De laatste run, met `verouderd` als het werkgebied intussen een ander manifest of een andere
    onderzoeksstand geeft (een nieuwe annotatie, een bron erbij, een gewijzigd lid ernaast). Is de graaf
    weg, dan is dat onbekend (`None`), geen "actueel"."""
    r = db.begrippen_runs
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied["id"])
        row = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied["id"])
                                  .order_by(r.c.gestart.desc()).limit(1))).first()
    if row is None:
        return None
    try:
        huidig = await begrip_onderzoek.manifest_en_onderzoek(werkgebied, resolve)
        verouderd: bool | None = (huidig["manifest_id"] != row.manifest_id
                                  or huidig["onderzoek_id"] != (row.onderzoek_id or ""))
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


async def _laatste_klare(conn, werkgebied_id: str):
    r = db.begrippen_runs
    return (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.status == "klaar")
                               .order_by(r.c.gestart.desc()).limit(1))).first()


def _rest(x) -> list[str]:
    """De leden van een groep die nog geen begrip werden."""
    weg = set(x.afgehandeld or [])
    return [e for e in x.leden if e not in weg]


async def groepen(werkgebied_id: str) -> dict:
    """De groepen van de laatste klare run, met hun passages, besluit en de bestaande begrippen die
    erop lijken (deelt een passage, of draagt dezelfde naam als term). Per open groep ook wat de poort
    na een akkoord nog zou tegenhouden (`poort_vooraf`, fase D), zodat de werkplek dat vooraf zegt."""
    g = db.betekenisgroepen
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        run = await _laatste_klare(conn, werkgebied_id)
        if run is None:
            return {"run": None, "groepen": [], "passages": {}, "verdieping": None}
        ids = run.uitkomst.get("groep_ids", [])
        verdieping = run.verdieping
        if verdieping:
            # Na de verdieping gelden de groepen na hergroeperen (fase C). Een groep van de keten
            # met een besluit blijft zichtbaar, ook als het model haar in een grotere opnam.
            besloten = [x.id for x in (await conn.execute(select(g.c.id).where(
                g.c.werkgebied_id == werkgebied_id, g.c.id.in_(ids), g.c.besluit != "open"))).all()] if ids else []
            ids = list(dict.fromkeys([*verdieping["groep_ids"], *besloten]))
        rows = {x.id: x for x in (await conn.execute(select(g).where(
            g.c.werkgebied_id == werkgebied_id, g.c.id.in_(ids)))).all()} if ids else {}
        # Twijfelvragen en relaties noemen ook elementen buiten een groep; de werkplek toont ze letterlijk.
        genoemd = {e for x in (*run.uitkomst.get("vragen", []), *run.uitkomst.get("relaties", []))
                   for e in (x["van"], x["naar"])}
        huidig = await begrip_store._huidige_elementen(
            conn, {e for x in rows.values() for e in x.leden} | genoemd)
    passages = {f["element_id"]: f for f in run.manifest["formuleringen"]}
    labels = {b["bron_iri"]: b["label"] for b in run.manifest["bronnen"]}
    begrippen = await begrip_store.lijst(werkgebied_id)
    uit = []
    for gid in ids:
        x = rows.get(gid)
        if x is None:
            continue
        rest = [e for e in _rest(x) if e in passages]
        leden = set(rest)
        termen = {_norm(x.voorstel["naam"]), *(_norm(t) for t in (x.kaart or {}).get("alternatieve_termen", []))}
        lijkt = [{"begrip_id": b["id"], "naam": b["inhoud"]["naam"],
                  "gedeeld": sorted(leden & set(b["element_ids"]))}
                 for b in begrippen if b["status"] != "vervangen"
                 if leden & set(b["element_ids"]) or termen &
                 {_norm(b["inhoud"]["naam"]), *(_norm(t) for t in b["inhoud"].get("alternatieve_termen", []))}]
        vooraf = None
        if x.besluit in ("open", "geparkeerd") and rest:
            inhoud = _inhoud([x], Overname(groep_ids=[x.id], naam=x.voorstel["naam"]), run.manifest, rest)
            vooraf = begrip_store.poort(inhoud, [_als_akkoord(huidig.get(e)) for e in rest])
        uit.append({"id": x.id, "aandacht": x.aandacht, "voorstel": x.voorstel, "uitleg": x.uitleg,
                    "conflicten": x.conflicten, "besluit": x.besluit, "reden": x.reden, "begrip_id": x.begrip_id,
                    "besloten_door": x.besloten_door, "door": x.door or "regel", "kaart": x.kaart,
                    "leden": [_passage(passages[e], labels, huidig.get(e)) for e in rest],
                    "afgehandeld": len(x.afgehandeld or []),
                    "lijkt_op": lijkt, "poort_vooraf": vooraf})
    return {"run": _run(run), "groepen": uit,
            "passages": {e: _passage(passages[e], labels, huidig.get(e)) for e in sorted(genoemd) if e in passages},
            # De oordelen van het model per twijfelvraag, en welke vragen na de verdieping open zijn.
            "verdieping": {"vragen_open": verdieping["vragen"], "oordelen": verdieping["oordelen"],
                           "model": verdieping["model"], "op": verdieping.get("op")} if verdieping else None}


def _als_akkoord(huidig: dict | None) -> dict:
    """Een koppeling zoals een akkoord haar nu zou maken: duiding, beoordeeld, met de bewijsstand van nu."""
    k = {"rol": "duiding", "beoordeling": "akkoord",
         "bewijs": {"element_hash": begrip_store.element_hash(huidig) if huidig else ""}}
    return begrip_store.actualiteit(k, huidig)


def _passage(f: dict, labels: dict[str, str], huidig: dict | None = None) -> dict:
    uit = {"element_id": f["element_id"], "tekst": f["tekst"], "jas_klasse": f["jas_klasse"],
           "review_status": f["review_status"], "bron_iri": f["bron_iri"],
           "vindplaats": labels.get(f["bron_iri"], "")}
    if huidig is not None:
        # De stand van de annotatie nú (het manifest is de stand bij de run): een jurist kan haar
        # intussen hebben beoordeeld, en de poort vraagt dat (fase D: "Annotatie akkoord" ter plekke).
        uit.update(lifecycle=huidig.get("lifecycle", ""),
                   annotatie_beoordeeld=huidig.get("lifecycle") in begrip_store.BEOORDEELD)
    return uit


async def _groepen_rij(conn, werkgebied_id: str, groep_ids: list[str], slot: bool = False):
    g = db.betekenisgroepen
    q = select(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id.in_(groep_ids))
    rows = (await conn.execute(q.with_for_update() if slot else q)).all()
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


# --- een voorstel wordt een begrip: overnemen, akkoord, koppelen ------------------------------------

def _niet_al_besloten(rows) -> None:
    """Een overgenomen of gekoppelde groep kan geen tweede begrip worden. De 409 noemt het begrip,
    zodat de werkplek dat opent in plaats van een fout te tonen (een dubbele klik, een tweede tabblad)."""
    besloten = {x.id: x.begrip_id for x in rows if x.besluit in ("overgenomen", "gekoppeld")}
    if besloten:
        raise HTTPException(409, {"fout": "al_besloten", "groepen": sorted(besloten), "begrippen": besloten,
                                  "melding": "Een van deze groepen is al overgenomen of gekoppeld."})


def _kies_leden(rows, element_ids: list[str] | None, run) -> list[str]:
    """De passages die het begrip aanduiden: standaard de rest van de gekozen groepen."""
    alle = [e for x in rows for e in _rest(x)]
    leden = list(dict.fromkeys(element_ids if element_ids is not None else alle))
    if not leden:
        raise HTTPException(422, "Kies minstens één passage.")
    al = {e for x in rows for e in (x.afgehandeld or [])} & set(leden)
    if al:
        raise HTTPException(409, {"fout": "al_besloten", "element_ids": sorted(al),
                                  "melding": "Een van deze passages werd al een begrip."})
    buiten = set(leden) - set(alle)
    if buiten:
        # Een passage buiten de gekozen groepen ("samen" bij een twijfelvraag) mag, als ze in de
        # voorstellen staat die de jurist in beeld heeft: het manifest van de laatste klare run.
        in_manifest = {f["element_id"] for f in run.manifest["formuleringen"]} if run else set()
        if buiten - in_manifest:
            raise HTTPException(422, "Kies passages uit de voorstellen van dit werkgebied.")
    if any(not set(leden) & set(_rest(x)) for x in rows):
        # Een groep overnemen of combineren zonder één van haar eigen passages is geen besluit over die groep.
        raise HTTPException(422, "Kies uit elke gekozen groep minstens één passage.")
    return leden


def _definitie_vindplaats(x) -> str:
    return (x.kaart or {}).get("definitie_vindplaats") or x.voorstel.get("definitie_vindplaats") or ""


def context_uit(manifest: dict, leden: list[str], definitie_vindplaats: str = "") -> str:
    """De context van een begrip zonder concept-kaart: waar de passages staan. Dezelfde zin als
    graph-qa `begrippen_pipeline/kaart.py:_context` (drift-test in `test_begrippen_akkoord.py`)."""
    bron_van = {f["element_id"]: f["bron_iri"] for f in manifest["formuleringen"]}
    labels = {b["bron_iri"]: b.get("label") or b["bron_iri"] for b in manifest["bronnen"]}
    plekken = list(dict.fromkeys(labels.get(bron_van[e], bron_van[e]) for e in leden if e in bron_van))
    if not plekken:
        return ""
    zin = "Komt voor in " + "; ".join(plekken) + "."
    if definitie_vindplaats:
        zin += f" Wettelijke definitie in {definitie_vindplaats}."
    return zin


def _inhoud(rows, o: Overname, manifest: dict | None, leden: list[str]) -> dict:
    """De inhoud van het begrip zoals het voorstel hem draagt: de kaart van de verdieping (fase C) als
    die er is, anders de letterlijke definitie van de keten, en de context uit de vindplaatsen."""
    inhoud: dict = {"naam": o.naam}
    gekozen = getattr(o, "definitie_van", None)
    bron = next((x for x in rows if x.id == gekozen), None) if gekozen else None
    kaarten = [x.kaart for x in rows if x.kaart]
    # Een definitie of kaart gaat alleen mee als er precies één is, of als de jurist bij combineren koos.
    k = bron.kaart if bron is not None else (kaarten[0] if len(kaarten) == 1 else None)
    if k:
        inhoud.update(alternatieve_termen=[t for t in k.get("alternatieve_termen", []) if t != o.naam],
                      context=k.get("context", ""))
    if bron is not None:
        definitie, vindplaats = _definitie_uit(bron), _definitie_vindplaats(bron)
    else:
        metdef = [x for x in rows if _definitie_uit(x)]
        definities = {_definitie_uit(x) for x in metdef}
        definitie = definities.pop() if len(definities) == 1 else None
        vindplaats = _definitie_vindplaats(metdef[0]) if definitie else ""
    if o.met_definitie and definitie:
        inhoud.update(zip(("definitie", "definitie_herkomst"), definitie))
    else:
        vindplaats = ""
    if not inhoud.get("context") and manifest:
        inhoud["context"] = context_uit(manifest, leden, vindplaats)
    return inhoud


def _pas_aan(inhoud: dict, a: Aanpassing | None) -> tuple[dict, list[str]]:
    """De aanpassing van de jurist over het voorstel heen; geeft ook de gewijzigde velden.

    Een andere definitietekst is niet meer letterlijk of samengesteld, dus `geformuleerd` (spoor I1: de
    api leidt de herkomst af, de jurist kiest haar niet)."""
    if a is None:
        return inhoud, []
    w = {k: v for k, v in a.model_dump(exclude_unset=True).items() if v is not None}
    uit = dict(inhoud)
    for veld in ("context", "alternatieve_termen"):
        if veld in w:
            uit[veld] = w[veld]
    if "definitie" in w:
        oud = inhoud.get("definitie", "")
        nieuw = w["definitie"].strip()
        if not nieuw:
            for veld in ("definitie", "definitie_herkomst"):
                uit.pop(veld, None)
        elif nieuw != oud or not inhoud.get("definitie_herkomst"):
            uit.update(definitie=nieuw, definitie_herkomst="geformuleerd")
    velden = sorted(k for k in set(uit) | set(inhoud) if uit.get(k) != inhoud.get(k))
    return uit, velden


async def _verwerk(conn, werkgebied_id: str, rows, leden: list[str], actor: str, begrip_id: str, besluit: str,
                   actie: str, detail: dict) -> None:
    """Het groepsbesluit na een overname, akkoord of koppeling. Een groep waarvan alle leden een begrip
    werden is `besluit`; anders blijft ze open met de rest (splitsen)."""
    g = db.betekenisgroepen
    gekozen, nu = set(leden), db.utcnow()
    volledig, deels = [], []
    for x in rows:
        klaar = list(dict.fromkeys([*(x.afgehandeld or []), *(e for e in x.leden if e in gekozen)]))
        waarden: dict = {"afgehandeld": klaar}
        if set(x.leden) <= set(klaar):
            waarden.update(besluit=besluit, reden="", begrip_id=begrip_id, besloten_door=actor, besloten_op=nu)
            volledig.append(x.id)
        else:
            deels.append(x.id)
        await conn.execute(update(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id == x.id).values(**waarden))
    await werkgebied_audit(conn, werkgebied_id, actor, actie,
                           {"groepen": volledig, **({"deels": deels} if deels else {}), "begrip_id": begrip_id,
                            "element_ids": leden, **detail})


async def overnemen(werkgebied: dict, o: Overname, actor: str, resolve: Resolver) -> dict:
    """Eén begrip (concept) uit de gekozen groepen; de gekozen leden duiden het aan."""
    return (await _neem_over(werkgebied, o, actor, resolve, akkoord=False))["begrip"]


async def akkoord(werkgebied: dict, a: Akkoord, actor: str, resolve: Resolver) -> dict:
    """Akkoord op een voorstel (fase D): het begrip met beoordeelde koppelingen, en geaccordeerd als de
    poort het toelaat. `{begrip, geaccordeerd, poort}`: de poort noemt wat er nog openstaat."""
    return await _neem_over(werkgebied, a, actor, resolve, akkoord=True)


async def _neem_over(werkgebied: dict, o: Overname, actor: str, resolve: Resolver, akkoord: bool) -> dict:
    wid = werkgebied["id"]
    async with db.get_engine().connect() as conn:
        rows = await _groepen_rij(conn, wid, o.groep_ids) if o.groep_ids else []
        run = await _laatste_klare(conn, wid)
    _niet_al_besloten(rows)
    leden = _kies_leden(rows, o.element_ids, run)
    manifest = run.manifest if run else None
    inhoud = _inhoud(rows, o, manifest, leden)
    velden: list[str] = []
    if akkoord:
        inhoud, velden = _pas_aan(inhoud, o.aanpassing)
        if o.kandidaat_id and (run is None or o.kandidaat_id not in {v["kandidaat_id"] for v in run.uitkomst.get("vragen", [])}):
            raise HTTPException(404, "Deze vraag staat niet in de voorstellen.")
        if o.kandidaat_ids:
            vragen = {v["kandidaat_id"]: v for v in (run.uitkomst.get("vragen", []) if run else [])}
            if any(k not in vragen for k in o.kandidaat_ids):
                raise HTTPException(404, "Een van deze vragen staat niet in de voorstellen.")
            gekozen = set(leden)
            buiten = [k for k in o.kandidaat_ids if not {vragen[k]["van"], vragen[k]["naar"]} <= gekozen]
            if buiten:
                raise HTTPException(422, {"fout": "vraag_buiten_keuze", "vragen": buiten,
                                          "melding": "Een twijfelvraag verbindt een passage die niet in deze keuze zit."})
    if inhoud.get("definitie"):
        # Een definitie uit het voorstel is van Lex; heeft de jurist haar aangepast, dan is ze van hem.
        inhoud["definitie_door"] = "analist" if "definitie" in velden else "lex"
    try:
        inhoud = BegripInhoud(**inhoud).model_dump(mode="json")
    except ValidationError as e:
        raise HTTPException(422, {"fout": "inhoud", "melding": "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}"
                                                                         for x in e.errors())}) from e
    # Het bewijs vraagt de graaf (de inventaris); dat gebeurt vóór de schrijftransactie.
    bewijs = await begrip_store.bewijzen(werkgebied, leden, resolve)
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, wid, slot=True)
        # Opnieuw onder het slot: een tweede akkoord tegelijk ziet het besluit van het eerste.
        rows = await _groepen_rij(conn, wid, o.groep_ids, slot=True) if o.groep_ids else []
        _niet_al_besloten(rows)
        _kies_leden(rows, leden, run)
        bid = await begrip_store.maak_in(conn, wid, inhoud, bewijs, "duiding", actor,
                                         "akkoord" if akkoord else "open",
                                         onderbouwing=None if "definitie" in velden else _onderbouwing(rows, o, inhoud, run))
        p = await begrip_store.accordeer_in(conn, wid, bid, 1, actor) if akkoord else None
        detail = {"geaccordeerd": p["mag"], **({"aangepast": velden} if velden else {})} if akkoord else {}
        await _verwerk(conn, wid, rows, leden, actor, bid, "overgenomen",
                       "groep-akkoord" if akkoord else "groep-overgenomen", detail)
        if akkoord:
            for kid in dict.fromkeys([*([o.kandidaat_id] if o.kandidaat_id else []), *o.kandidaat_ids]):
                await _vraag_in(conn, wid, run.id, kid, "samen", actor)
    begrip = await begrip_store.haal(wid, bid)
    return {"begrip": begrip, "geaccordeerd": begrip["status"] == "geaccordeerd", "poort": begrip["accorderen"]}


def _onderbouwing(rows, o: Overname, inhoud: dict, run) -> dict | None:
    """Waarop de overgenomen definitie rust, bevroren zoals het bewijs van een koppeling (spoor M): de
    kaart van de groep die haar leverde (fragmenten, bron, vindplaats, duiding), of de letterlijke
    definitie van de keten. Een latere verdieping kan de kaart van de groep nog veranderen; dit niet."""
    definitie = inhoud.get("definitie")
    if not definitie:
        return None
    gekozen = getattr(o, "definitie_van", None)
    x = next((x for x in rows if (x.id == gekozen if gekozen else (_definitie_uit(x) or ("",))[0] == definitie)), None)
    if x is None:
        return None
    k = x.kaart or {}
    bron = k if k.get("definitie") == definitie else x.voorstel
    return {"groep_id": x.id, "run_id": run.id if run else "", "herkomst": inhoud.get("definitie_herkomst", ""),
            "definitie_bron_iri": bron.get("definitie_bron_iri", ""), "definitie_vindplaats": _definitie_vindplaats(x),
            "fragmenten": [{f: v[f] for f in ("bron_iri", "start", "eind", "tekst")} for v in bron.get("fragmenten") or []],
            "duiding": bron.get("duiding"), "onderzoek_id": (run.onderzoek_id or "") if run else ""}


def _definitie_uit(x) -> tuple[str, str] | None:
    """(definitie, herkomst) van een groep: uit de kaart als die er is, anders het letterlijke voorstel
    van de keten. De bron draagt het begrip via zijn passages (`dct:source` in de projectie)."""
    k = x.kaart or {}
    if k.get("definitie"):
        return k["definitie"], k["herkomst"]
    if x.voorstel.get("definitie"):
        return x.voorstel["definitie"], "letterlijk"
    return None


async def koppelen(werkgebied: dict, groep_id: str, k: GroepKoppeling, actor: str, resolve: Resolver) -> dict:
    """De passages van een groep aan een bestaand begrip. Met `akkoord` (vanuit de review) zijn de
    koppelingen meteen beoordeeld, en wordt een geaccordeerd begrip opnieuw geaccordeerd als het mag."""
    wid = werkgebied["id"]
    async with db.get_engine().connect() as conn:
        [row] = await _groepen_rij(conn, wid, [groep_id])
    _niet_al_besloten([row])
    leden = _kies_leden([row], k.element_ids, None)
    bewijs = await begrip_store.bewijzen(werkgebied, leden, resolve)
    b = db.begrippen
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, wid, slot=True)
        [row] = await _groepen_rij(conn, wid, [groep_id], slot=True)
        _niet_al_besloten([row])
        _kies_leden([row], leden, None)
        q = select(b.c.revisie, b.c.status).where(b.c.id == k.begrip_id, b.c.werkgebied_id == wid, b.c.verwijderd.is_(None))
        voor = (await conn.execute(q)).first()
        if voor is None:
            raise HTTPException(404, "Begrip bestaat niet.")
        await begrip_store.koppel_in(conn, wid, k.begrip_id, voor.revisie, bewijs, "duiding", "", actor,
                                     "akkoord" if k.akkoord else "open")
        if k.akkoord and voor.status == "geaccordeerd":
            await begrip_store.accordeer_in(conn, wid, k.begrip_id, (await conn.execute(q)).first().revisie, actor)
        await _verwerk(conn, wid, [row], leden, actor, k.begrip_id, "gekoppeld", "groep-gekoppeld",
                       {"akkoord": True} if k.akkoord else {})
    return await begrip_store.haal(wid, k.begrip_id)


async def besluit(werkgebied_id: str, groep_id: str, soort: str, reden: str, actor: str) -> None:
    await _besluit(werkgebied_id, [groep_id], soort, actor, reden=reden)


async def vraag(werkgebied_id: str, run_id: str, kandidaat_id: str, antwoord: str, actor: str) -> dict:
    """Een twijfelvraag beantwoorden. "Samen" maakt nog niets: de werkplek biedt daarna de overname
    van beide aan. Het antwoord ligt vast, met wie en wanneer."""
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        await _vraag_in(conn, werkgebied_id, run_id, kandidaat_id, antwoord, actor)
    return await haal(werkgebied_id, run_id)


async def _vraag_in(conn, werkgebied_id: str, run_id: str, kandidaat_id: str, antwoord: str, actor: str) -> None:
    r = db.begrippen_runs
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


async def heropen_groep(werkgebied_id: str, groep_id: str, actor: str) -> None:
    g = db.betekenisgroepen
    async with db.get_engine().connect() as conn:
        [row] = await _groepen_rij(conn, werkgebied_id, [groep_id])
    if row.besluit in ("overgenomen", "gekoppeld"):
        raise HTTPException(409, {"fout": "al_besloten",
                                  "melding": "Deze groep is een begrip geworden; wijzig het begrip zelf."})
    await _besluit(werkgebied_id, [groep_id], "open", actor)
