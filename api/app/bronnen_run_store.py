"""Bronnen vinden met Lex: runs van de ontdekmethoden en de kandidaatbepalingen (spoor D, fase A).

- **De api legt de invoer vast, graph-qa zoekt.** `start` legt de selectie van het werkgebied vast
  (kern = rol *analyseren*, plus de contextbronnen en de analysevraag); graph-qa haalt de run op, past
  de methoden toe en zet de kandidaten terug (`zet_uitkomst`).
- **Idempotent op (werkgebied, invoer).** Dezelfde selectie en analysevraag geven dezelfde run, zolang het
  de nieuwste is: na een tussenstand (A → B → A) zoekt Lex opnieuw, anders klopte `run_id` op de kandidaten
  niet meer met de run die er nu ligt. Een run die blijft hangen (`runs.VERLOPEN`) mag opnieuw.
- **Wat telt, is de laatste klare run.** Een open voorstel dat die run niet vond, is *vervallen*: het
  dossier of de selectie veranderde en de nieuwe zoekopdracht vond het niet meer. De bronselectie laat het
  weg; een besluit (opgenomen, uitgesloten) blijft staan. De uitkomst van een run die intussen is ingehaald,
  wordt vastgelegd maar raakt de kandidaten niet.
- **Eén kandidaat per bepaling.** Vinden meer methoden dezelfde bepaling – in één run of over runs
  heen – dan is dat één rij met meer bewijs, en de sterkste rol wint.
- **Een besluit hoort bij de kandidaat, niet bij de run.** Een latere run werkt het bewijs bij, maar
  laat *uitgesloten* staan: een uitgesloten kandidaat stelt Lex niet opnieuw voor. Besluiten neemt de
  analist per deelvraag (`bronselectie.besluit`); de werkgebiedbrede stand is `voorgesteld`, `opgenomen`
  of `uitgesloten`.
  *Opgenomen* blijft staan zolang de bron in de selectie zit; haalt de analist hem eruit, dan maakt
  `werkgebied_store.verwijder_bron` er in dezelfde transactie weer een voorstel van.
- **Opnemen** maakt in dezelfde transactie een bronselectie (`werkgebied_store.voeg_bron_toe`) en
  draagt daarom de revisie van het werkgebied.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import db, runs, werkgebied_deelvragen, werkgebied_store
from .bronnen_run_contracts import ROL_VOLGORDE, BronnenUitkomst, Opnemen
from .werkgebied_contracts import Bereik, BronselectieInvoer, Rol
from .werkgebied_store import _audit as werkgebied_audit, werkgebied_rij

#: Na zoveel stilte telt een run die niet klaar is als vastgelopen; dan mag hij opnieuw.


def kandidaat_id(bron_iri: str) -> str:
    """Dezelfde bepaling, dezelfde kandidaat – ook over runs heen."""
    return "K" + hashlib.sha256(bron_iri.encode()).hexdigest()[:16]


DOSSIER = ("aanleiding", "context", "doel", "praktijkvoorbeeld", "afbakening", "gebeurtenis")


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
    # Het zoekbereik dat de analist koos; alleen als het er is (dezelfde reden).
    regelingen = [r["bwb_id"] for r in werkgebied.get("regelingen") or [] if r.get("bwb_id")]
    if regelingen:
        invoer["regelingen"] = regelingen
    return invoer


def invoer_id(invoer: dict) -> str:
    return "I" + hashlib.sha256(json.dumps(invoer, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _run(row, met_invoer: bool = False) -> dict:
    uit = {"id": row.id, "werkgebied_id": row.werkgebied_id, "invoer_id": row.invoer_id,
           "status": runs.status(row), "reden": row.reden, "meting": row.meting,
           "aantal_kern": len(row.invoer.get("kern", [])), "zoekversie": row.invoer.get("zoekversie", ""),
           "gestart_door": row.gestart_door, "gestart": db.aware(row.gestart).isoformat(),
           "gewijzigd": db.aware(row.gewijzigd).isoformat()}
    if met_invoer:
        uit["invoer"] = row.invoer
    return uit


def _kandidaat(row) -> dict:
    return {"id": row.id, "bron_iri": row.bron_iri, "label": row.label, "bwb_id": row.bwb_id, "rol": row.rol,
            "bewijs": row.bewijs, "status": row.status, "reden": row.reden, "run_id": row.run_id,
            "besloten_door": row.besloten_door,
            "besloten_op": db.aware(row.besloten_op).isoformat() if row.besloten_op else None,
            "voorgesteld": db.aware(row.voorgesteld).isoformat(), "gewijzigd": db.aware(row.gewijzigd).isoformat()}


# --- runs ------------------------------------------------------------------------------------

async def start(werkgebied: dict, actor: str, zoekversie: str = "") -> tuple[dict, bool]:
    """De run op de huidige selectie: de bestaande als die er al is, anders een nieuwe. (run, nieuw).

    `zoekversie` is de versie van de zoekcode van graph-qa (een hash van haar modules). Ze hoort bij de invoer en dus
    bij de identiteit van de run: met nieuwe zoekcode zoekt Lex opnieuw, ook als het werkgebied niet veranderde.
    Zonder bleef bij Rekeningafspraken (4 nov 2026) de uitkomst van de oude code staan, ook na *Verder onderzoeken*."""
    invoer = invoer_van(werkgebied)
    if zoekversie:
        invoer = {**invoer, "zoekversie": zoekversie}
    if not invoer["kern"] and not invoer["analysevraag"].strip() and not invoer.get("deelvragen"):
        raise HTTPException(409, {"fout": "geen_vertrekpunt",
                                  "melding": "Geef het werkgebied een analysevraag of neem minstens één bepaling op "
                                             "om te analyseren; daar zoekt Lex vanuit."})
    iid = invoer_id(invoer)
    r = db.bronnen_runs
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied["id"], slot=True)
        bestaand = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied["id"], r.c.invoer_id == iid)
                                       .order_by(r.c.gestart.desc()).limit(1))).first()
        nieuwste = await _laatste_row(conn, werkgebied["id"])
        if bestaand is not None and (runs.status(bestaand) in runs.LOPEND
                                     or (runs.status(bestaand) == "klaar" and bestaand.id == nieuwste.id)):
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
        await werkgebied_rij(conn, werkgebied_id)
        row = (await conn.execute(select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id))).first()
    if row is None:
        raise HTTPException(404, "Run bestaat niet.")
    return _run(row, met_invoer)


async def _laatste_row(conn, werkgebied_id: str):
    r = db.bronnen_runs
    return (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id)
                               .order_by(r.c.gestart.desc()).limit(1))).first()


async def basis_run_id(conn, werkgebied_id: str) -> str | None:
    """De laatste klare run: wat die vond, zijn de open voorstellen. Loopt er een nieuwere of mislukte die,
    dan blijft de vorige staan tot er een nieuwe uitkomst is."""
    r = db.bronnen_runs
    return (await conn.execute(select(r.c.id).where(r.c.werkgebied_id == werkgebied_id, r.c.status == "klaar")
                               .order_by(r.c.gestart.desc()).limit(1))).scalar()


def genoemd(bewijs: list[dict] | None) -> bool:
    """Door de analist zelf genoemd (`bronselectie.noem`): een voorstel dat geen run nodig heeft om te blijven staan."""
    return any(b.get("methode") == "genoemd" for b in bewijs or [])


def vervallen(status: str, run_id: str | None, basis: str | None, bewijs: list[dict] | None = None) -> bool:
    """Een open voorstel dat de laatste klare run niet vond. Een besluit vervalt nooit, en een zelf genoemd voorstel
    ook niet: dat hangt niet van een zoekopdracht af."""
    return status == "voorgesteld" and basis is not None and run_id != basis and not genoemd(bewijs)


async def laatste(werkgebied: dict) -> dict | None:
    """De laatste run, met `verouderd` als de selectie of de analysevraag intussen veranderde."""
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied["id"])
        row = await _laatste_row(conn, werkgebied["id"])
    if row is None:
        return None
    # Verouderd zegt dat het werkgebied veranderde, niet de zoekcode: de versie van de run telt mee als gelijk.
    nu = invoer_van(werkgebied)
    if row.invoer.get("zoekversie"):
        nu = {**nu, "zoekversie": row.invoer["zoekversie"]}
    return {**_run(row), "verouderd": row.invoer_id != invoer_id(nu)}


async def loopt(werkgebied_id: str, run_id: str) -> dict:
    await haal(werkgebied_id, run_id)                           # 404 als de run hier niet hoort
    await runs.zet_loopt(db.bronnen_runs, run_id)
    return await haal(werkgebied_id, run_id)


async def mislukt(werkgebied_id: str, run_id: str, reden: str) -> dict:
    await haal(werkgebied_id, run_id)
    await runs.zet_mislukt(db.bronnen_runs, run_id, reden)
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
    r = db.bronnen_runs
    h = _uitkomst_hash(invoer)
    async with db.get_engine().begin() as conn:
        await werkgebied_rij(conn, werkgebied_id, slot=True)
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
        nu = db.utcnow()
        # Is intussen een nieuwere run gestart (het dossier of de selectie veranderde), dan hoort deze uitkomst bij
        # een oude stand: vastgelegd, maar ze overschrijft de voorstellen van nu niet.
        ingehaald = (await _laatste_row(conn, werkgebied_id)).id != run_id
        aantal, nieuw = (0, 0) if ingehaald else await _leg_kandidaten_vast(conn, werkgebied_id, run_id, invoer, nu)
        await conn.execute(update(r).where(r.c.id == run_id).values(
            status="klaar", meting={m: x.model_dump() for m, x in invoer.meting.items()}, uitkomst_hash=h,
            gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "bronnen-voorgesteld",
                               {"run": run_id, "kandidaten": aantal, "nieuw": nieuw,
                                **({"ingehaald": True} if ingehaald else {})})
    return await haal(werkgebied_id, run_id)


async def _leg_kandidaten_vast(conn, werkgebied_id: str, run_id: str, invoer: BronnenUitkomst, nu) -> tuple[int, int]:
    """De kandidaten van deze run: nieuw erbij, bestaande met het bewijs van nu. (aantal, nieuw)."""
    k = db.bron_kandidaten
    # Wat nú in de selectie staat, wordt geen nieuwe kandidaat (de selectie kan sinds de start veranderd zijn);
    # een bestaande kandidaat krijgt wel het bewijs en de run van nu, zodat hij na loskoppelen klopt.
    in_selectie = await werkgebied_store.actieve_bron_iris(conn, werkgebied_id)
    bestaande = {x.bron_iri: x for x in (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id))).all()}
    gevonden = {iri: v for iri, v in _samengevoegd(invoer.kandidaten).items()
                if iri not in in_selectie or iri in bestaande}
    for iri, v in gevonden.items():
        oud = bestaande.get(iri)
        if oud is None:
            await conn.execute(insert(k).values(werkgebied_id=werkgebied_id, id=kandidaat_id(iri), bron_iri=iri,
                                                status="voorgesteld", reden="", run_id=run_id,
                                                voorgesteld=nu, gewijzigd=nu, **v))
            continue
        # Het bewijs wordt bijgewerkt; het besluit blijft staan, en wat de analist zelf noemde ook.
        zelf = [b for b in oud.bewijs or [] if b.get("methode") == "genoemd" and b not in v["bewijs"]]
        await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == oud.id)
                           .values(run_id=run_id, gewijzigd=nu, **{**v, "bewijs": v["bewijs"] + zelf}))
    return len(gevonden), sum(1 for iri in gevonden if iri not in bestaande)


# --- kandidaten ------------------------------------------------------------------------------

async def kandidaten(werkgebied_id: str) -> dict:
    """Alle kandidaten, sterkste rol eerst; met de laatste run, zodat de werkplek weet wat er nu speelt."""
    k = db.bron_kandidaten
    async with db.get_engine().connect() as conn:
        await werkgebied_rij(conn, werkgebied_id)
        run = await _laatste_row(conn, werkgebied_id)
        rows = (await conn.execute(select(k).where(k.c.werkgebied_id == werkgebied_id))).all()
        in_selectie = await werkgebied_store.actieve_bron_iris(conn, werkgebied_id)
        basis = await basis_run_id(conn, werkgebied_id)
    # `in_selectie`: intussen met de hand opgenomen. Dan is het geen open voorstel meer.
    lijst = sorted(({**_kandidaat(x), "in_selectie": x.bron_iri in in_selectie,
                     "vervallen": x.bron_iri not in in_selectie and vervallen(x.status, x.run_id, basis, x.bewijs)} for x in rows),
                   key=lambda x: (ROL_VOLGORDE[x["rol"]], -len(x["bewijs"]), x["label"], x["bron_iri"]))
    return {"run": _run(run) if run is not None else None, "kandidaten": lijst}


async def bron_iri_van(werkgebied_id: str, kid: str) -> str:
    """De bepaling van één kandidaat; leeg als hij er niet is."""
    k = db.bron_kandidaten
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(k.c.bron_iri).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid))).scalar() or ""


async def _haal_kandidaat(conn, werkgebied_id: str, kid: str, slot: bool = False):
    k = db.bron_kandidaten
    q = select(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None:
        raise HTTPException(404, "Kandidaat bestaat niet.")
    return row


async def opnemen(werkgebied_id: str, kid: str, req: Opnemen, bron: dict, actor: str, *,
                  deelvraag_ids: list[str], koppel_rol: str = "", binnen=None, bron_iri: str = "") -> dict:
    """De kandidaat wordt een bronselectie; beide in één transactie. `bron` komt uit de resolver, net als bij
    zelf opnemen. De bronselectie per deelvraag (`bronselectie.besluit`) geeft de deelvraag mee (leeg zonder
    deelvragen), met `koppel_rol` als de rol bij die deelvraag, en `binnen` om in dezelfde transactie het besluit
    bij die deelvraag op te ruimen. Geeft {kandidaat, selectie}."""
    k = db.bron_kandidaten
    async with db.get_engine().connect() as conn:
        row = await _haal_kandidaat(conn, werkgebied_id, kid)
    # Al opgenomen mag ook: een ander lid, of het geheel na een lid (per lid opnemen); de selectie is idempotent.
    if row.status not in ("voorgesteld", "opgenomen"):
        raise HTTPException(409, {"fout": "status", "status": row.status,
                                  "melding": "Alleen een open voorstel kun je opnemen."})
    rol = req.rol or ("analyseren" if row.rol == "kern" else "context")
    # `bron_iri`: een lid of onderdeel van de kandidaat in plaats van het geheel (de bronselectie per deelvraag toetst dat).
    doel = bron_iri or row.bron_iri
    invoer = BronselectieInvoer(verwachte_revisie=req.verwachte_revisie, bron_iri=doel,
                                bereik=Bereik.onderliggend, rol=Rol(rol),
                                reden=req.reden.strip())
    # Wie de bepaling voorstelde volgt uit het bewijs: zelf genoemd is van de analist, de rest vond Lex. Een
    # standaardzin als reden ("Voorgesteld door Lex") schreef de keuze van de jurist eerder aan Lex toe.
    voorgesteld_door = "analist" if genoemd(row.bewijs) else "lex"

    async def markeer(conn) -> None:
        nu = db.utcnow()
        await conn.execute(update(k).where(k.c.werkgebied_id == werkgebied_id, k.c.id == kid).values(
            status="opgenomen", reden="", besloten_door=actor, besloten_op=nu, gewijzigd=nu))
        await werkgebied_audit(conn, werkgebied_id, actor, "kandidaat-opgenomen",
                               {"kandidaat": kid, "bron_iri": doel, "rol": rol})
        s = db.werkgebied_bronselecties
        sid = (await conn.execute(select(s.c.id).where(s.c.werkgebied_id == werkgebied_id, s.c.bron_iri == doel,
                                                       s.c.verwijderd.is_(None)))).scalar()
        if sid:
            await werkgebied_deelvragen.koppel_bron_in(conn, werkgebied_id, sid, deelvraag_ids, actor, rol=koppel_rol,
                                                       reden=req.reden.strip())
        if binnen is not None:
            await binnen(conn)

    selectie, nieuw = await werkgebied_store.voeg_bron_toe(werkgebied_id, invoer, bron, actor, binnen=markeer,
                                                           voorgesteld_door=voorgesteld_door)
    if not nieuw:
        # Stond al in de selectie (met dezelfde rol): dan alleen de kandidaat bijwerken.
        async with db.get_engine().begin() as conn:
            await markeer(conn)
    async with db.get_engine().connect() as conn:
        row = await _haal_kandidaat(conn, werkgebied_id, kid)
    return {"kandidaat": _kandidaat(row), "selectie": selectie}
