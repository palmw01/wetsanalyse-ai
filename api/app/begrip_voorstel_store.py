"""Lex naast de kaart: kaartruns en kaartvoorstellen (spoor D, fase E).

Bovenop een begrip (`begrip_store`) en het manifest van zijn werkgebied (`begrip_manifest`). graph-qa
rekent (`agent/begrip_kaart.py`), de api legt de invoer vast, toetst en bewaart:

- **Een voorstel is geen wijziging.** Lex schrijft nooit in het begrip. Pas `overnemen` door de
  analist raakt het, via het schrijfpad van `begrip_store` (`_gewijzigd_in`: revisie, revisiekopie,
  audit) – in dezelfde transactie als het besluit over het voorstel.
- **Niets stil overschreven.** Een definitievoorstel bewaart de definitie waarop het rust (`basis`).
  Staat er intussen een andere, dan weigert overnemen met 409 `voorstel_verouderd` en de drie waarden
  (toen, nu, voorstel). Uitleg, toelichting en voorbeelden worden toegevoegd, nooit vervangen.
- **Herkomst gaat mee.** Overnemen zet `definitie_herkomst` en `definitie_door` (`lex`, of `analist`
  bij een aanpassing); de revisieregel noemt het voorstel, de actie en het model. Alleen een
  overgenomen brondefinitie is letterlijk.
- **De garanties toetst de api zelf** (`begrippen_verdieping.definitie_fouten`): fragmenten letterlijk
  in het manifest, een samengestelde definitie precies haar fragmenten, een letterlijke definitie in
  haar bron – en ligt die bron buiten het werkgebied, dan vraagt de api de tekst aan de graaf.
- **Idempotent op invoer.** Dezelfde actie op dezelfde revisie van het begrip (en het manifest) geeft
  de lopende run terug, of de klare zolang er nog open voorstellen aan hangen.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from statistics import median
from typing import Awaitable, Callable

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import insert, select, update

from . import begrip_onderzoek, begrip_store, db, verbruik
from .begrip_contracts import BegripInhoud
from .begrip_voorstel_contracts import (
    MODEL_ACTIES, VELDEN, KaartRunStart, KaartUitkomst, VoorstelInvoer, VoorstelOvername,
)
from .begrippen_run_store import VERLOPEN, _werkgebied
from .begrippen_verdieping import definitie_fouten, fragment_fouten, fragmentruimte
from .werkgebied_inventaris import nodes_met_titel
from .werkgebied_store import _audit as werkgebied_audit

Resolver = Callable[[dict], Awaitable[dict]]

SCHATTING_BASIS = 20


def _hash(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _status(row) -> str:
    if row.status in ("wacht", "loopt") and db.utcnow() - db.aware(row.gewijzigd) > VERLOPEN:
        return "mislukt"
    return row.status


def _run(row, met_invoer: bool = False) -> dict:
    uit = {"id": row.id, "werkgebied_id": row.werkgebied_id, "begrip_id": row.begrip_id, "actie": row.actie,
           "invoer_id": row.invoer_id, "status": _status(row), "melding": row.melding, "reden": row.reden,
           "basis_revisie": row.invoer["begrip"]["revisie"],
           "ander_begrip_id": (row.invoer.get("ander") or {}).get("id"),
           "gestart_door": row.gestart_door, "gestart": db.aware(row.gestart).isoformat(),
           "gewijzigd": db.aware(row.gewijzigd).isoformat()}
    if met_invoer:
        uit["invoer"] = row.invoer
    return uit


def _voorstel(row, huidig: dict | None = None) -> dict:
    uit = {"id": row.id, "begrip_id": row.begrip_id, "run_id": row.run_id, "actie": row.actie, "veld": row.veld,
           "volgorde": row.volgorde, "basis": row.basis, "waarde": row.waarde, "motivatie": row.motivatie,
           "aandacht": row.aandacht, "aandachtspunten": row.aandachtspunten, "door": row.door,
           "status": row.status, "reden": row.reden, "besloten_door": row.besloten_door,
           "besloten_op": db.aware(row.besloten_op).isoformat() if row.besloten_op else None,
           "begrip_revisie": row.begrip_revisie, "gemaakt": db.aware(row.gemaakt).isoformat()}
    if row.veld == "definitie" and row.status == "open" and huidig is not None:
        nu = _definitie_stand(huidig)
        uit["verouderd"] = nu != _definitie_stand(row.basis)
        uit["nu"] = nu
    return uit


def _definitie_stand(inhoud: dict) -> dict:
    return {"definitie": inhoud.get("definitie") or "", "definitie_herkomst": inhoud.get("definitie_herkomst") or None}


def _leden(begrip: dict, manifest: dict) -> list[str]:
    """De dragende passages van het begrip die in het manifest staan: daarop rust een voorstel."""
    in_manifest = {f["element_id"] for f in manifest["formuleringen"]}
    return list(dict.fromkeys(k["element_id"] for k in begrip["koppelingen"]
                              if k["rol"] in begrip_store.DRAGEND and k["beoordeling"] != "afgewezen"
                              and k["actualiteit"] == "actueel" and k["element_id"] in in_manifest))


def _invoer_id(invoer: dict) -> str:
    sleutel = {"actie": invoer["actie"], "begrip": [invoer["begrip"]["id"], invoer["begrip"]["revisie"]],
               "ander": [invoer["ander"]["id"], invoer["ander"]["revisie"]] if invoer.get("ander") else None,
               "manifest_id": invoer["manifest_id"]}
    if invoer.get("onderzoek_id"):          # spoor M; een invoer van daarvoor houdt zijn id
        sleutel["onderzoek_id"] = invoer["onderzoek_id"]
    return _hash(sleutel)[:32]


# --- starten -----------------------------------------------------------------------------------

async def start(werkgebied: dict, begrip_id: str, s: KaartRunStart, actor: str, resolve: Resolver) -> tuple[dict, bool]:
    """Legt de invoer vast en geeft de run erop. Geeft (run, nieuw)."""
    wid = werkgebied["id"]
    begrip = await begrip_store.haal(wid, begrip_id)
    ander = None
    if s.ander_begrip_id:
        if s.ander_begrip_id == begrip_id:
            raise HTTPException(422, "Vergelijk met een ander begrip.")
        ander = await begrip_store.haal(wid, s.ander_begrip_id)
    if s.actie in ("voorbeelden", "uitleg") and not (begrip["inhoud"].get("definitie") or "").strip():
        wat = "Voorbeelden toetsen" if s.actie == "voorbeelden" else "Een uitleg legt"
        raise HTTPException(409, {"fout": "geen_definitie",
                                  "melding": f"{wat} een definitie; geef het begrip eerst een definitie."})
    m = await begrip_onderzoek.manifest_en_onderzoek(werkgebied, resolve)
    if not m["volledig"]:
        raise HTTPException(409, {"fout": "inventaris_onvolledig",
                                  "melding": "Niet elke bron van het werkgebied kon worden opgehaald; probeer het zo opnieuw."})
    leden = _leden(begrip, m["manifest"])
    if s.actie in ("scherper", "betekenisverschil") and not leden:
        raise HTTPException(409, {"fout": "geen_passages",
                                  "melding": "Dit begrip heeft nog geen actuele dragende passage; daar kan Lex niets op baseren."})
    invoer = {
        "actie": s.actie,
        "werkgebied": {"id": wid, "naam": werkgebied.get("naam", ""), "analysevraag": werkgebied.get("analysevraag", "")},
        "begrip": {"id": begrip["id"], "revisie": begrip["revisie"], "inhoud": begrip["inhoud"]},
        "leden": leden,
        "ander": {"id": ander["id"], "revisie": ander["revisie"], "inhoud": ander["inhoud"],
                  "leden": _leden(ander, m["manifest"])} if ander else None,
        "selecties": [{"bron_iri": x["bron_iri"], "rol": x["rol"], "bwb_id": x.get("bwb_id", ""),
                       "label": x.get("label", "")} for x in werkgebied["bronnen"]],
        "manifest": m["manifest"], "manifest_id": m["manifest_id"],
        "onderzoek": m["onderzoek"], "onderzoek_id": m["onderzoek_id"],
    }
    invoer["invoer_id"] = iid = _invoer_id(invoer)
    r, v = db.begrip_kaartruns, db.begrip_voorstellen
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, wid, slot=True)
        bestaand = (await conn.execute(select(r).where(r.c.begrip_id == begrip_id, r.c.actie == s.actie,
                                                       r.c.invoer_id == iid).order_by(r.c.gestart.desc()).limit(1))).first()
        if bestaand is not None:
            stand = _status(bestaand)
            open_ = (await conn.execute(select(v.c.id).where(v.c.run_id == bestaand.id, v.c.status == "open")
                                        .limit(1))).first() is not None
            if stand in ("wacht", "loopt") or (stand == "klaar" and open_):
                return _run(bestaand), False
        nu, rid = db.utcnow(), str(uuid.uuid4())
        await conn.execute(insert(r).values(
            id=rid, werkgebied_id=wid, begrip_id=begrip_id, actie=s.actie, invoer_id=iid, invoer=invoer,
            status="wacht", melding="", reden="", gestart_door=actor, gestart=nu, gewijzigd=nu))
        await werkgebied_audit(conn, wid, actor, "kaartrun-gestart",
                               {"run": rid, "begrip_id": begrip_id, "actie": s.actie,
                                "begrip_revisie": begrip["revisie"], **({"ander_begrip_id": ander["id"]} if ander else {})})
        row = (await conn.execute(select(r).where(r.c.id == rid))).first()
    return _run(row), True


async def _run_rij(conn, werkgebied_id: str, begrip_id: str, run_id: str, slot: bool = False):
    r = db.begrip_kaartruns
    q = select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id, r.c.begrip_id == begrip_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None:
        raise HTTPException(404, "Run bestaat niet.")
    return row


async def haal_run(werkgebied_id: str, begrip_id: str, run_id: str, met_invoer: bool = False) -> dict:
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        return _run(await _run_rij(conn, werkgebied_id, begrip_id, run_id), met_invoer)


async def loopt(werkgebied_id: str, begrip_id: str, run_id: str) -> dict:
    """graph-qa begint (of leeft nog): de stilteklok begint opnieuw."""
    r = db.begrip_kaartruns
    async with db.get_engine().begin() as conn:
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id, slot=True)
        if row.status != "klaar":
            await conn.execute(update(r).where(r.c.id == run_id).values(status="loopt", gewijzigd=db.utcnow()))
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id)
    return _run(row)


async def mislukt(werkgebied_id: str, begrip_id: str, run_id: str, reden: str) -> dict:
    r = db.begrip_kaartruns
    async with db.get_engine().begin() as conn:
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id, slot=True)
        if row.status == "klaar":
            raise HTTPException(409, "Deze run is al klaar.")
        await conn.execute(update(r).where(r.c.id == run_id).values(status="mislukt", reden=reden[:2000],
                                                                    gewijzigd=db.utcnow()))
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id)
    return _run(row)


# --- de uitkomst van graph-qa --------------------------------------------------------------------

async def _toets(invoer: dict, v: VoorstelInvoer, resolve: Resolver) -> list[str]:
    """De garanties op één voorstel; een lege lijst = in orde."""
    if v.veld not in VELDEN[invoer["actie"]]:
        return ["VELD_HOORT_NIET_BIJ_ACTIE"]
    manifest = fragmentruimte(invoer["manifest"], invoer.get("onderzoek"))
    fouten = fragment_fouten(manifest, v.fragmenten)
    d = v.definitie
    if d is None:
        return list(dict.fromkeys(fouten))
    brontekst = None
    in_manifest = any(b["bron_iri"] == d.definitie_bron_iri for b in manifest["bronnen"])
    if d.herkomst == "letterlijk" and not in_manifest:
        # Een brondefinitie buiten het werkgebied: de tekst komt uit de graaf, niet van graph-qa.
        try:
            node = nodes_met_titel(await resolve({"bron_iri": d.definitie_bron_iri})).get(d.definitie_bron_iri)
        except HTTPException as e:
            if e.status_code == 503:
                raise
            node = None
        brontekst = (node or {}).get("tekst") or ""
    return list(dict.fromkeys(fouten + definitie_fouten(manifest, d.definitie, d.herkomst, d.definitie_bron_iri,
                                                        d.fragmenten, brontekst)))


def _waarde(v: VoorstelInvoer) -> dict:
    if v.definitie is not None:
        uit = v.definitie.model_dump(mode="json")
        if v.duiding is not None:                     # spoor M: bij het voorstel, niet in het begrip
            uit["duiding"] = v.duiding.model_dump(mode="json")
        return uit
    uit = {"tekst": v.tekst.strip(), "fragmenten": [f.model_dump() for f in v.fragmenten]}
    if v.veld == "voorbeelden":
        uit["oordeel"] = v.oordeel.value
        uit.update({k: x for k, x in (("soort_voorbeeld", v.soort_voorbeeld), ("toetst", v.toetst),
                                      ("kenmerk", v.kenmerk)) if x})
    if v.vergelijking:
        uit["vergelijking"] = v.vergelijking
    return uit


async def zet_uitkomst(werkgebied_id: str, begrip_id: str, run_id: str, u: KaartUitkomst, actor: str,
                       resolve: Resolver) -> dict:
    """De voorstellen van graph-qa, getoetst en bewaard; daarmee is de run klaar."""
    async with db.get_engine().connect() as conn:
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id)
    if u.invoer_id != row.invoer_id:
        raise HTTPException(422, "De uitkomst hoort bij een andere invoer dan deze run.")
    h = _hash(u.model_dump(mode="json", exclude={"meting", "tokens"}))
    if row.status == "klaar":
        if row.uitkomst_hash == h:
            return await voorstellen(werkgebied_id, begrip_id)
        raise HTTPException(409, "Deze run is al klaar, met een andere uitkomst.")
    fout = {i: c for i, v in enumerate(u.voorstellen) if (c := await _toets(row.invoer, v, resolve))}
    if fout:
        raise HTTPException(422, {"fout": "garantie", "voorstellen": fout,
                                  "melding": "Een voorstel noemt tekst die niet zo in de bron staat."})
    basis = {"revisie": row.invoer["begrip"]["revisie"], **_definitie_stand(row.invoer["begrip"]["inhoud"])}
    door = {"bron": "model" if row.actie in MODEL_ACTIES else "graaf", "model": u.model, "promptversie": u.promptversie}
    r, t = db.begrip_kaartruns, db.begrip_voorstellen
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = await _run_rij(conn, werkgebied_id, begrip_id, run_id, slot=True)
        if row.status == "klaar":                                     # tegelijk binnengekomen
            if row.uitkomst_hash == h:
                return await _voorstellen_in(conn, werkgebied_id, begrip_id)
            raise HTTPException(409, "Deze run is al klaar, met een andere uitkomst.")
        nu = db.utcnow()
        for i, v in enumerate(u.voorstellen):
            await conn.execute(insert(t).values(
                id=str(uuid.uuid4()), werkgebied_id=werkgebied_id, begrip_id=begrip_id, run_id=run_id,
                actie=row.actie, veld=v.veld, volgorde=i, basis=basis, waarde=_waarde(v),
                motivatie=" ".join(v.motivatie.split()), aandacht=v.aandacht, aandachtspunten=v.aandachtspunten,
                door=door, status="open", reden="", gemaakt=nu))
        await conn.execute(update(r).where(r.c.id == run_id).values(
            status="klaar", melding=u.melding, uitkomst_hash=h, gewijzigd=nu,
            meting={**u.meting, "model": u.model, "promptversie": u.promptversie, "tokens": u.tokens}))
        await werkgebied_audit(conn, werkgebied_id, actor, "kaartvoorstellen",
                               {"run": run_id, "begrip_id": begrip_id, "actie": row.actie,
                                "voorstellen": len(u.voorstellen), "model": u.model})
        return await _voorstellen_in(conn, werkgebied_id, begrip_id)


# --- lezen ------------------------------------------------------------------------------------

async def _voorstellen_in(conn, werkgebied_id: str, begrip_id: str) -> dict:
    t, r, b = db.begrip_voorstellen, db.begrip_kaartruns, db.begrippen
    inhoud = (await conn.execute(select(b.c.inhoud).where(b.c.id == begrip_id, b.c.werkgebied_id == werkgebied_id,
                                                         b.c.verwijderd.is_(None)))).scalar()
    if inhoud is None:
        raise HTTPException(404, "Begrip bestaat niet.")
    rows = (await conn.execute(select(t).where(t.c.begrip_id == begrip_id, t.c.werkgebied_id == werkgebied_id)
                               .order_by(t.c.gemaakt.desc(), t.c.volgorde))).all()
    runs = (await conn.execute(select(r).where(r.c.begrip_id == begrip_id, r.c.werkgebied_id == werkgebied_id)
                               .order_by(r.c.gestart.desc()))).all()
    laatste: dict[str, dict] = {}
    for x in runs:
        laatste.setdefault(x.actie, _run(x))
    return {"voorstellen": [_voorstel(x, inhoud) for x in rows], "runs": laatste}


async def voorstellen(werkgebied_id: str, begrip_id: str) -> dict:
    """De voorstellen van Lex bij dit begrip (open en besloten, nieuwste eerst) en per actie de laatste run."""
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        return await _voorstellen_in(conn, werkgebied_id, begrip_id)


async def schatting(userid: str) -> dict[str, dict]:
    """Per model-actie de mediaan van het verbruik over de laatste klare runs van deze gebruiker."""
    r = db.begrip_kaartruns.c
    uit: dict[str, dict] = {}
    async with db.get_engine().connect() as conn:
        for actie in sorted(MODEL_ACTIES):
            rijen = (await conn.execute(select(r.meting).where(
                r.gestart_door == (userid or "").strip().lower(), r.actie == actie, r.status == "klaar")
                .order_by(r.gestart.desc()).limit(SCHATTING_BASIS))).scalars().all()
            tokens = [int((m or {}).get("tokens") or 0) for m in rijen]
            tokens = [x for x in tokens if x > 0]
            if tokens:
                uit[actie] = {"tokens": int(median(tokens)), "basis": len(tokens)}
    return uit


async def budget(userid: str) -> dict:
    stand = await verbruik.stand(userid)
    return {"resterend": stand.resterend, "budget": stand.budget, "actief": stand.actief,
            "geblokkeerd": stand.geblokkeerd}


# --- besluiten ----------------------------------------------------------------------------------

async def _voorstel_rij(conn, werkgebied_id: str, begrip_id: str, voorstel_id: str):
    t = db.begrip_voorstellen
    row = (await conn.execute(select(t).where(t.c.id == voorstel_id, t.c.werkgebied_id == werkgebied_id,
                                              t.c.begrip_id == begrip_id).with_for_update())).first()
    if row is None:
        raise HTTPException(404, "Voorstel bestaat niet.")
    if row.status != "open":
        raise HTTPException(409, {"fout": "al_besloten", "status": row.status, "begrip_revisie": row.begrip_revisie,
                                  "melding": "Over dit voorstel is al besloten."})
    return row


def _neem_veld_over(inhoud: dict, row, o: VoorstelOvername) -> tuple[dict, bool]:
    """De inhoud na overnemen, en of de analist het voorstel aanpaste."""
    w = row.waarde
    uit = dict(inhoud)
    if row.veld == "definitie":
        gezien = o.nu_gezien is not None and o.nu_gezien == (inhoud.get("definitie") or "")
        if _definitie_stand(inhoud) != _definitie_stand(row.basis) and not gezien:
            raise HTTPException(409, {
                "fout": "voorstel_verouderd", "toen": _definitie_stand(row.basis), "nu": _definitie_stand(inhoud),
                "voorstel": {"definitie": w["definitie"], "definitie_herkomst": w["herkomst"]},
                "melding": "De definitie veranderde nadat Lex dit voorstelde; vergelijk voordat je iets overneemt."})
        tekst = (o.aanpassing or "").strip()
        aangepast = bool(tekst) and tekst != w["definitie"]
        if aangepast:
            uit.update(definitie=tekst, definitie_herkomst="geformuleerd", definitie_door="analist")
        else:
            uit.update(definitie=w["definitie"], definitie_herkomst=w["herkomst"], definitie_door="lex")
        return uit, aangepast
    tekst = (o.aanpassing or "").strip() or w["tekst"]
    aangepast = tekst != w["tekst"] or (o.oordeel is not None and o.oordeel.value != w.get("oordeel"))
    if row.veld in ("uitleg", "context"):
        oud = (inhoud.get(row.veld) or "").strip()
        uit[row.veld] = tekst if not oud else (oud if tekst in oud else f"{oud}\n\n{tekst}")
    else:
        vbs = list(inhoud.get("voorbeelden") or [])
        if not any(x.get("tekst") == tekst for x in vbs):
            vbs.append({"tekst": tekst, "oordeel": (o.oordeel.value if o.oordeel else w["oordeel"])})
        uit["voorbeelden"] = vbs
    return uit, aangepast


async def overnemen(werkgebied_id: str, begrip_id: str, voorstel_id: str, o: VoorstelOvername, actor: str) -> dict:
    """Het voorstel in het begrip, in één transactie met het besluit erover. Geeft het begrip."""
    t = db.begrip_voorstellen
    detail: dict = {}
    async with db.get_engine().begin() as conn:
        async with begrip_store._gewijzigd_in(conn, werkgebied_id, begrip_id, o.verwachte_revisie, actor,
                                              "voorstel-overgenomen", detail) as (_, brow, stand):
            row = await _voorstel_rij(conn, werkgebied_id, begrip_id, voorstel_id)
            nieuw, aangepast = _neem_veld_over(brow.inhoud, row, o)
            try:
                nieuw = BegripInhoud(**nieuw).model_dump(mode="json")
            except ValidationError as e:
                raise HTTPException(422, {"fout": "inhoud", "melding": "; ".join(
                    f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())}) from e
            detail.update(voorstel_id=voorstel_id, actie=row.actie, veld=row.veld, door=row.door, aangepast=aangepast)
            stand["inhoud"] = nieuw
            stand["geen_wijziging"] = nieuw == brow.inhoud
            revisie = brow.revisie if stand["geen_wijziging"] else brow.revisie + 1
        await conn.execute(update(t).where(t.c.id == voorstel_id).values(
            status="aangepast" if aangepast else "overgenomen", besloten_door=actor, besloten_op=db.utcnow(),
            begrip_revisie=revisie))
        if stand["geen_wijziging"]:
            # Het begrip draagt dit al (dezelfde vraag, hetzelfde voorbeeld): geen revisie, wel het besluit.
            await werkgebied_audit(conn, werkgebied_id, actor, "voorstel-overgenomen",
                                   {**detail, "begrip_id": begrip_id, "begrip_revisie": revisie, "geen_wijziging": True})
    return await begrip_store.haal(werkgebied_id, begrip_id)


async def afwijzen(werkgebied_id: str, begrip_id: str, voorstel_id: str, reden: str, actor: str) -> dict:
    """Het voorstel blijft bewaard, met wie het afwees en waarom; het begrip verandert niet."""
    t = db.begrip_voorstellen
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = await _voorstel_rij(conn, werkgebied_id, begrip_id, voorstel_id)
        await conn.execute(update(t).where(t.c.id == voorstel_id).values(
            status="afgewezen", reden=reden.strip(), besloten_door=actor, besloten_op=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "voorstel-afgewezen",
                               {"voorstel_id": voorstel_id, "begrip_id": begrip_id, "actie": row.actie,
                                "veld": row.veld, "reden": reden.strip()})
        return await _voorstellen_in(conn, werkgebied_id, begrip_id)
