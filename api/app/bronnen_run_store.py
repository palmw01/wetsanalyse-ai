"""Bronnen vinden met Lex: runs van de ontdekmethoden en de kandidaatbepalingen (spoor D, fase A).

- **De api legt de invoer vast, graph-qa zoekt.** `start` legt de selectie van het werkgebied vast
  (kern = rol *analyseren*, plus de contextbronnen en de analysevraag); graph-qa haalt de run op, past
  de methoden toe en zet de kandidaten terug (`zet_uitkomst`).
- **Idempotent op (werkgebied, invoer).** Dezelfde selectie en analysevraag geven dezelfde run. Een
  run die blijft hangen (`VERLOPEN`) mag opnieuw.
- **Eén kandidaat per bepaling.** Vinden meer methoden dezelfde bepaling – in één run of over runs
  heen – dan is dat één rij met meer bewijs, en de sterkste rol wint.
- **Een besluit hoort bij de kandidaat, niet bij de run.** Een latere run werkt het bewijs bij, maar
  laat *later* en *uitgesloten* staan: een uitgesloten kandidaat stelt Lex niet opnieuw voor.
  *Opgenomen* blijft staan zolang de bron in de selectie zit; haalt de analist hem eruit, dan maakt
  `werkgebied_store.verwijder_bron` er in dezelfde transactie weer een voorstel van.
- **Opnemen** maakt in dezelfde transactie een bronselectie (`werkgebied_store.voeg_bron_toe`) en
  draagt daarom de revisie van het werkgebied. De andere besluiten wijzigen de scope niet en dragen
  geen revisie, zoals de besluiten over betekenisgroepen.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import db, werkgebied_deelvragen, werkgebied_store
from .bronnen_run_contracts import ROL_VOLGORDE, BronnenUitkomst, Opnemen
from .werkgebied_contracts import Bereik, BronselectieInvoer, Rol
from .werkgebied_store import _audit as werkgebied_audit

#: Na zoveel stilte telt een run die niet klaar is als vastgelopen; dan mag hij opnieuw.
VERLOPEN = timedelta(minutes=5)
STATUSSEN = ("voorgesteld", "opgenomen", "later", "uitgesloten")


def kandidaat_id(bron_iri: str) -> str:
    """Dezelfde bepaling, dezelfde kandidaat – ook over runs heen."""
    return "K" + hashlib.sha256(bron_iri.encode()).hexdigest()[:16]


DOSSIER = ("aanleiding", "context", "doel", "praktijkvoorbeeld", "afbakening")


def invoer_van(werkgebied: dict) -> dict:
    """Wat graph-qa nodig heeft, en niets uit de graaf: de selectie zoals hij nu is."""
    def bron(s: dict) -> dict:
        return {"bron_iri": s["bron_iri"], "label": s["label"], "bwb_id": s["bwb_id"], "bereik": s["bereik"]}
    sel = sorted(werkgebied["bronnen"], key=lambda s: s["bron_iri"])
    invoer = {"naam": werkgebied["naam"], "analysevraag": werkgebied.get("analysevraag", ""),
              "kern": [bron(s) for s in sel if s["rol"] == "analyseren"],
              "context": [bron(s) for s in sel if s["rol"] != "analyseren"]}
    # Alleen met actieve deelvragen een sleutel: zo blijft de invoer (en dus `invoer_id`) van een
    # werkgebied zonder deelvragen wat hij was.
    deelvragen = [{"id": d["id"], "vraag": d["vraag"]} for d in werkgebied.get("deelvragen", [])
                  if d["status"] == "actief"]
    if deelvragen:
        invoer["deelvragen"] = deelvragen
    # Het dossier van het werkgebied (startactiviteit a, praktijkvoorbeeld, afbakening) scherpt het
    # zoeken aan; ook alleen als er iets staat, om dezelfde reden.
    dossier = {k: werkgebied[k].strip() for k in DOSSIER if (werkgebied.get(k) or "").strip()}
    if dossier:
        invoer["dossier"] = dossier
    return invoer


def invoer_id(invoer: dict) -> str:
    return "I" + hashlib.sha256(json.dumps(invoer, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _status(row) -> str:
    if row.status in ("wacht", "loopt") and db.utcnow() - db.aware(row.gewijzigd) > VERLOPEN:
        return "mislukt"
    return row.status


def _run(row, met_invoer: bool = False) -> dict:
    uit = {"id": row.id, "werkgebied_id": row.werkgebied_id, "invoer_id": row.invoer_id,
           "status": _status(row), "reden": row.reden, "meting": row.meting,
           "aantal_kern": len(row.invoer.get("kern", [])),
           "gestart_door": row.gestart_door, "gestart": db.aware(row.gestart).isoformat(),
           "gewijzigd": db.aware(row.gewijzigd).isoformat()}
    if met_invoer:
        uit["invoer"] = row.invoer
    return uit


def _kandidaat(row, laatste_run: str | None = None) -> dict:
    return {"id": row.id, "bron_iri": row.bron_iri, "label": row.label, "bwb_id": row.bwb_id, "rol": row.rol,
            "bewijs": row.bewijs, "status": row.status, "reden": row.reden, "run_id": row.run_id,
            "in_laatste_run": laatste_run is not None and row.run_id == laatste_run,
            "besloten_door": row.besloten_door,
            "besloten_op": db.aware(row.besloten_op).isoformat() if row.besloten_op else None,
            "voorgesteld": db.aware(row.voorgesteld).isoformat(), "gewijzigd": db.aware(row.gewijzigd).isoformat()}


async def _werkgebied(conn, werkgebied_id: str, slot: bool = False):
    t = db.werkgebieden
    q = select(t).where(t.c.id == werkgebied_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None or row.gearchiveerd is not None:
        raise HTTPException(404, "Werkgebied bestaat niet.")
    return row


# --- runs ------------------------------------------------------------------------------------

async def start(werkgebied: dict, actor: str) -> tuple[dict, bool]:
    """De run op de huidige selectie: de bestaande als die er al is, anders een nieuwe. (run, nieuw)."""
    invoer = invoer_van(werkgebied)
    if not invoer["kern"] and not invoer["analysevraag"].strip() and not invoer.get("deelvragen"):
        raise HTTPException(409, {"fout": "geen_vertrekpunt",
                                  "melding": "Geef het werkgebied een analysevraag of neem minstens één bepaling op "
                                             "om te analyseren; daar zoekt Lex vanuit."})
    iid = invoer_id(invoer)
    r = db.bronnen_runs
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied["id"], slot=True)
        bestaand = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied["id"], r.c.invoer_id == iid)
                                       .order_by(r.c.gestart.desc()).limit(1))).first()
        if bestaand is not None and _status(bestaand) in ("wacht", "loopt", "klaar"):
            return _run(bestaand), False
        nu, rid = db.utcnow(), str(uuid.uuid4())
        await conn.execute(insert(r).values(id=rid, werkgebied_id=werkgebied["id"], invoer_id=iid, invoer=invoer,
                                            status="wacht", reden="", gestart_door=actor, gestart=nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied["id"], actor, "bronnen-run-gestart",
                               {"run": rid, "invoer_id": iid, "kern": len(invoer["kern"])})
        row = (await conn.execute(select(r).where(r.c.id == rid))).first()
    return _run(row), True


async def haal(werkgebied_id: str, run_id: str, met_invoer: bool = False) -> dict:
    r = db.bronnen_runs
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        row = (await conn.execute(select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id))).first()
    if row is None:
        raise HTTPException(404, "Run bestaat niet.")
    return _run(row, met_invoer)


async def _laatste_row(conn, werkgebied_id: str):
    r = db.bronnen_runs
    return (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id)
                               .order_by(r.c.gestart.desc()).limit(1))).first()


async def laatste(werkgebied: dict) -> dict | None:
    """De laatste run, met `verouderd` als de selectie of de analysevraag intussen veranderde."""
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied["id"])
        row = await _laatste_row(conn, werkgebied["id"])
    if row is None:
        return None
    return {**_run(row), "verouderd": row.invoer_id != invoer_id(invoer_van(werkgebied))}


async def _zet(run_id: str, **waarden) -> None:
    async with db.get_engine().begin() as conn:
        await conn.execute(update(db.bronnen_runs).where(db.bronnen_runs.c.id == run_id)
                           .values(gewijzigd=db.utcnow(), **waarden))


async def loopt(werkgebied_id: str, run_id: str) -> dict:
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


def _samengevoegd(kandidaten) -> dict[str, dict]:
    """Per bron_iri één kandidaat: het bewijs bij elkaar, de sterkste rol."""
    uit: dict[str, dict] = {}
    for k in kandidaten:
        bewijs = [b.model_dump() for b in k.bewijs]
        if k.bron_iri not in uit:
            uit[k.bron_iri] = {"label": k.label, "bwb_id": k.bwb_id, "rol": k.rol, "bewijs": bewijs}
            continue
        v = uit[k.bron_iri]
        v["bewijs"] += [b for b in bewijs if b not in v["bewijs"]]
        if ROL_VOLGORDE[k.rol] < ROL_VOLGORDE[v["rol"]]:
            v["rol"] = k.rol
        v["label"] = v["label"] or k.label
        v["bwb_id"] = v["bwb_id"] or k.bwb_id
    return uit


def _uitkomst_hash(invoer: BronnenUitkomst) -> str:
    data = invoer.model_dump(mode="json", exclude={"meting"})
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def zet_uitkomst(werkgebied_id: str, run_id: str, invoer: BronnenUitkomst, actor: str) -> dict:
    r, k, s = db.bronnen_runs, db.bron_kandidaten, db.werkgebied_bronselecties
    h = _uitkomst_hash(invoer)
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
        if invoer.invoer_id != row.invoer_id:
            raise HTTPException(422, "De uitkomst hoort bij een andere invoer dan deze run.")
        # Wat nú in de selectie staat, is geen kandidaat (de selectie kan sinds de start veranderd zijn).
        in_selectie = set((await conn.execute(select(s.c.bron_iri).where(
            s.c.werkgebied_id == werkgebied_id, s.c.verwijderd.is_(None)))).scalars())
        nieuw = {iri: v for iri, v in _samengevoegd(invoer.kandidaten).items() if iri not in in_selectie}
        bestaande = {x.bron_iri: x for x in (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id))).all()}
        nu = db.utcnow()
        for iri, v in nieuw.items():
            oud = bestaande.get(iri)
            if oud is None:
                await conn.execute(insert(k).values(werkgebied_id=werkgebied_id, id=kandidaat_id(iri), bron_iri=iri,
                                                    status="voorgesteld", reden="", run_id=run_id,
                                                    voorgesteld=nu, gewijzigd=nu, **v))
                continue
            # Het bewijs wordt bijgewerkt; het besluit blijft staan.
            await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == oud.id)
                               .values(run_id=run_id, gewijzigd=nu, **v))
        await conn.execute(update(r).where(r.c.id == run_id).values(
            status="klaar", meting={m: x.model_dump() for m, x in invoer.meting.items()}, uitkomst_hash=h,
            gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "bronnen-voorgesteld",
                               {"run": run_id, "kandidaten": len(nieuw),
                                "nieuw": sum(1 for iri in nieuw if iri not in bestaande)})
    return await haal(werkgebied_id, run_id)


# --- kandidaten ------------------------------------------------------------------------------

async def kandidaten(werkgebied_id: str) -> dict:
    """Alle kandidaten, sterkste rol eerst; met de laatste run, zodat de werkplek weet wat er nu speelt."""
    k, s = db.bron_kandidaten, db.werkgebied_bronselecties
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        run = await _laatste_row(conn, werkgebied_id)
        rows = (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id))).all()
        in_selectie = set((await conn.execute(select(s.c.bron_iri).where(
            s.c.werkgebied_id == werkgebied_id, s.c.verwijderd.is_(None)))).scalars())
    laatste_id = run.id if run is not None and _status(run) == "klaar" else None
    # `in_selectie`: intussen met de hand opgenomen. Dan is het geen open voorstel meer.
    lijst = sorted(({**_kandidaat(x, laatste_id), "in_selectie": x.bron_iri in in_selectie} for x in rows),
                   key=lambda x: (ROL_VOLGORDE[x["rol"]], -len(x["bewijs"]), x["label"], x["bron_iri"]))
    return {"run": _run(run) if run is not None else None, "kandidaten": lijst}


async def _haal_kandidaat(conn, werkgebied_id: str, kid: str, slot: bool = False):
    k = db.bron_kandidaten
    q = select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None:
        raise HTTPException(404, "Kandidaat bestaat niet.")
    return row


async def _besluit(werkgebied_id: str, kid: str, actor: str, *, van: tuple[str, ...], naar: str,
                   reden: str = "") -> dict:
    """Later, uitsluiten of heropenen: het slot op het werkgebied (geen revisie), dan de kandidaat."""
    k = db.bron_kandidaten
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = await _haal_kandidaat(conn, werkgebied_id, kid, slot=True)
        if row.status not in van:
            meldingen = {"opgenomen": "Deze bepaling is al opgenomen; haal haar op de tab Bronnen uit de selectie."}
            raise HTTPException(409, {"fout": "status", "status": row.status,
                                      "melding": meldingen.get(row.status, "Dit besluit past niet bij de stand van deze kandidaat.")})
        nu = db.utcnow()
        await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid).values(
            status=naar, reden=reden, besloten_door=None if naar == "voorgesteld" else actor,
            besloten_op=None if naar == "voorgesteld" else nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, f"kandidaat-{naar}",
                               {"kandidaat": kid, "bron_iri": row.bron_iri, **({"reden": reden} if reden else {})})
        row = await _haal_kandidaat(conn, werkgebied_id, kid)
    return _kandidaat(row)


async def later(werkgebied_id: str, kid: str, actor: str) -> dict:
    return await _besluit(werkgebied_id, kid, actor, van=("voorgesteld",), naar="later")


async def uitsluiten(werkgebied_id: str, kid: str, reden: str, actor: str) -> dict:
    return await _besluit(werkgebied_id, kid, actor, van=("voorgesteld", "later"), naar="uitgesloten",
                          reden=reden.strip())


async def heropenen(werkgebied_id: str, kid: str, actor: str) -> dict:
    return await _besluit(werkgebied_id, kid, actor, van=("later", "uitgesloten"), naar="voorgesteld")


async def opnemen(werkgebied_id: str, kid: str, req: Opnemen, bron: dict, actor: str, *,
                  deelvraag_ids: list[str] | None = None, koppel_rol: str = "", binnen=None) -> dict:
    """De kandidaat wordt een bronselectie; beide in één transactie. `bron` komt uit de resolver,
    net als bij zelf opnemen. Geeft {kandidaat, selectie}.

    Zonder `deelvraag_ids` hoort de selectie bij de deelvragen waarvoor Lex haar vond; de bronselectie per
    deelvraag (spoor J) geeft er precies één mee, met `koppel_rol` als de rol bij die deelvraag, en `binnen`
    om in dezelfde transactie het besluit bij die deelvraag op te ruimen."""
    k = db.bron_kandidaten
    async with db.get_engine().connect() as conn:
        row = await _haal_kandidaat(conn, werkgebied_id, kid)
    if row.status not in ("voorgesteld", "later"):
        raise HTTPException(409, {"fout": "status", "status": row.status,
                                  "melding": "Alleen een open voorstel (of een voor later) kun je opnemen."})
    rol = req.rol or ("analyseren" if row.rol == "kern" else "context")
    invoer = BronselectieInvoer(verwachte_revisie=req.verwachte_revisie, bron_iri=row.bron_iri,
                                bereik=Bereik.onderliggend, rol=Rol(rol),
                                reden=req.reden or f"Voorgesteld door Lex ({row.rol}).")

    # Vond Lex de bepaling bij een deelvraag, dan hoort de nieuwe selectie bij die deelvraag.
    if deelvraag_ids is None:
        deelvraag_ids = sorted({str((b.get("detail") or {}).get("deelvraag_id", "")) for b in row.bewijs
                                if b.get("methode") == "deelvraag"} - {""})

    async def markeer(conn) -> None:
        nu = db.utcnow()
        await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid).values(
            status="opgenomen", reden="", besloten_door=actor, besloten_op=nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "kandidaat-opgenomen",
                               {"kandidaat": kid, "bron_iri": row.bron_iri, "rol": rol})
        s = db.werkgebied_bronselecties
        sid = (await conn.execute(select(s.c.id).where(s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == row.bron_iri,
                                                       s.c.verwijderd.is_(None)))).scalar()
        if sid:
            await werkgebied_deelvragen.koppel_bron_in(conn, werkgebied_id, sid, deelvraag_ids, actor, rol=koppel_rol)
        if binnen is not None:
            await binnen(conn)

    selectie, nieuw = await werkgebied_store.voeg_bron_toe(werkgebied_id, invoer, bron, actor, binnen=markeer)
    if not nieuw:
        # Stond al in de selectie (met dezelfde rol): dan alleen de kandidaat bijwerken.
        async with db.get_engine().begin() as conn:
            await markeer(conn)
    async with db.get_engine().connect() as conn:
        row = await _haal_kandidaat(conn, werkgebied_id, kid)
    return {"kandidaat": _kandidaat(row), "selectie": selectie}
