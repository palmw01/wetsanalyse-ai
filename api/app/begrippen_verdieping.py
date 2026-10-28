"""De verdieping van de voorstellen: het model op twijfelparen en kaarten (spoor D, fase C).

Bovenop de laatste klare begrippenrun (levering 3a, `begrippen_run_store`). graph-qa rekent
(`agent/begrippen_verdieping.py`), de api bewaart en toetst:

- **Per afgeronde batch** (`zet_batch`): een herstart doet alleen de batches die hier ontbreken. De
  batch-id is inhoudelijk (graph-qa `verdieping.batch_id`); dezelfde batch nog eens is idempotent,
  een andere inhoud onder dezelfde id een conflict.
- **De garanties toetst de api zelf**, tegen het eigen manifest: elk element-, kandidaat- en
  groep-id bestaat, elk fragment staat letterlijk op zijn offsets en draagt het id dat daaruit volgt,
  een letterlijke definitie staat in haar bron, een samengestelde is precies haar fragmenten. Faalt
  er één, dan 422 en wordt er niets bewaard – nooit half.
- **De werkvoorraad** (`werkvoorraad`) is wat het model nog moet doen: de twijfelvragen (behalve die
  de wet al als relatie noemt) en de groepen zonder definitie, min wat in een klare batch zit. Een
  bevestiging noemt dat aantal; graph-qa start alleen als het nog klopt.
- **De uitkomst** (`zet_verdieping`): de groepen na hergroeperen (ook nieuwe, `door: model`), een
  kaart per groep en de oordelen. Besluiten blijven op groep-id staan, zoals bij de run.
"""
from __future__ import annotations

import hashlib
import json
from statistics import median

from fastapi import HTTPException
from sqlalchemy import insert, select, update

from . import db, verbruik
from .begrippen_run_contracts import BatchInvoer, Kaart, VerdiepingInvoer
from .begrippen_run_store import _run, _werkgebied
from .werkgebied_store import _audit as werkgebied_audit

#: Een paar dat de wet al als relatie noemt, gaat niet naar het model (graph-qa `verdieping.te_vergelijken`).
RELATIE_GAAT_VOOR = "Z-RELATIE-GAAT-VOOR"
SCHATTING_BASIS = 20
SCHEIDING = " … "                       # graph-qa `toetsen.scheiding`


def fragment_id(bron_iri: str, start: int, eind: int) -> str:
    """Zelfde rekenwijze als graph-qa `model.fragment_id`."""
    return "F" + hashlib.sha256("\x1f".join((bron_iri, str(start), str(eind))).encode()).hexdigest()[:10]


def fragmentruimte(manifest: dict, onderzoek: dict | None) -> dict:
    """Waar een fragment uit mag komen: het manifest plus de contextbronnen van het onderzoek (spoor M).
    Een fragment-id volgt uit bron en offsets, dus de ids van het manifest veranderen niet."""
    if not onderzoek:
        return manifest
    return {**manifest, "bronnen": [*manifest["bronnen"], *onderzoek.get("bronnen", [])]}


def fragment_fouten(manifest: dict, fragmenten) -> list[str]:
    """Elk fragment bestaat in het manifest (id uit bron en offsets) en staat letterlijk op zijn plek."""
    bronnen = {b["bron_iri"]: b["tekst"] for b in manifest["bronnen"]}
    fouten: list[str] = []
    for f in fragmenten:
        tekst = bronnen.get(f.bron_iri)
        if tekst is None or f.id != fragment_id(f.bron_iri, f.start, f.eind):
            fouten.append("FRAGMENT_ONBEKEND")
        elif tekst[f.start:f.eind] != f.tekst:
            fouten.append("FRAGMENT_NIET_LETTERLIJK")
    return fouten


def definitie_fouten(manifest: dict, definitie: str, herkomst: str | None, bron_iri: str, fragmenten,
                     brontekst: str | None = None) -> list[str]:
    """De garanties op één definitie. `brontekst` is de tekst van de bron als die buiten het manifest
    ligt (een brondefinitie elders in de graaf, fase E); anders komt hij uit het manifest."""
    fouten = fragment_fouten(manifest, fragmenten)
    if brontekst is None:
        brontekst = next((b["tekst"] for b in manifest["bronnen"] if b["bron_iri"] == bron_iri), "")
    if herkomst == "letterlijk" and definitie not in brontekst:
        fouten.append("LETTERLIJK_NIET_IN_BRON")
    if herkomst == "samengesteld" and definitie != SCHEIDING.join(f.tekst for f in fragmenten):
        fouten.append("SAMENGESTELD_NIET_UIT_FRAGMENTEN")
    return list(dict.fromkeys(fouten))


def garanties(manifest: dict, kaart: Kaart) -> list[str]:
    """De codes van graph-qa `toetsen.garanties`, hier opnieuw getoetst tegen het bewaarde manifest."""
    return definitie_fouten(manifest, kaart.definitie, kaart.herkomst, kaart.definitie_bron_iri, kaart.fragmenten)


def _toets_kaarten(manifest: dict, kaarten: list[Kaart], groep_ids: set[str]) -> None:
    fout = {k.groep_id: c for k in kaarten if (c := garanties(manifest, k))}
    if fout:
        raise HTTPException(422, {"fout": "garantie", "kaarten": fout,
                                  "melding": "Een kaart noemt tekst die niet zo in de bron staat."})
    vreemd = sorted({k.groep_id for k in kaarten} - groep_ids)
    if vreemd:
        raise HTTPException(422, {"fout": "onbekende_groep", "groep_ids": vreemd,
                                  "melding": "Een kaart hoort bij een groep die er niet is."})


def _hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def _run_rij(conn, werkgebied_id: str, run_id: str, slot: bool = False):
    r = db.begrippen_runs
    q = select(r).where(r.c.id == run_id, r.c.werkgebied_id == werkgebied_id)
    row = (await conn.execute(q.with_for_update() if slot else q)).first()
    if row is None:
        raise HTTPException(404, "Run bestaat niet.")
    if row.status != "klaar" or not row.uitkomst:
        raise HTTPException(409, {"fout": "run_niet_klaar", "melding": "Er zijn nog geen voorstellen om te verdiepen."})
    return row


def _te_vergelijken(row) -> list[str]:
    return [v["kandidaat_id"] for v in row.uitkomst.get("vragen", []) if v.get("regel") != RELATIE_GAAT_VOOR]


async def _batches(conn, run_id: str) -> list:
    b = db.begrippen_batches
    return (await conn.execute(select(b).where(b.c.run_id == run_id).order_by(b.c.gemaakt))).all()


def _batch(row) -> dict:
    return {"id": row.id, "soort": row.soort, "ids": row.ids, "resultaat": row.resultaat, "model": row.model,
            "promptversie": row.promptversie, "tokens": row.tokens}


async def schatting(userid: str) -> dict | None:
    """Mediaan van het verbruik per item (paar of kaart) over de laatste batches van deze gebruiker."""
    b = db.begrippen_batches.c
    async with db.get_engine().connect() as conn:
        rijen = (await conn.execute(select(b.tokens, b.ids).where(
            b.gemaakt_door == (userid or "").strip().lower(), b.tokens > 0)
            .order_by(b.gemaakt.desc()).limit(SCHATTING_BASIS))).all()
    per_item = [t / max(1, len(ids)) for t, ids in rijen]
    return {"per_item": int(median(per_item)), "basis": len(per_item)} if per_item else None


async def werkvoorraad(werkgebied_id: str, userid: str) -> dict:
    """Wat het model voor de laatste klare run nog moet doen, met schatting en budget."""
    r, g = db.begrippen_runs, db.betekenisgroepen
    async with db.get_engine().connect() as conn:
        await _werkgebied(conn, werkgebied_id)
        row = (await conn.execute(select(r).where(r.c.werkgebied_id == werkgebied_id, r.c.status == "klaar")
                                  .order_by(r.c.gestart.desc()).limit(1))).first()
        if row is None:
            return {"run": None, "aantal": 0, "vragen": [], "kaarten": [], "batches": [], "verdiept": False,
                    "schatting": None, "budget": None}
        batches = await _batches(conn, row.id)
        ids = row.uitkomst.get("groep_ids", [])
        groepen = (await conn.execute(select(g.c.id, g.c.voorstel).where(
            g.c.werkgebied_id == werkgebied_id, g.c.id.in_(ids)))).all() if ids else []
    gedaan = {soort: {i for x in batches if x.soort == soort for i in x.ids} for soort in ("vraag", "kaart")}
    verdiept = row.verdieping is not None
    vragen = [] if verdiept else [k for k in _te_vergelijken(row) if k not in gedaan["vraag"]]
    kaarten = [] if verdiept else sorted(x.id for x in groepen
                                         if not (x.voorstel or {}).get("definitie") and x.id not in gedaan["kaart"])
    aantal = len(vragen) + len(kaarten)
    schat = await schatting(userid)
    stand = await verbruik.stand(userid)
    return {
        "run": _run(row), "verdiept": verdiept, "aantal": aantal, "vragen": vragen, "kaarten": kaarten,
        "batches": [_batch(x) for x in batches],
        "schatting": {**schat, "totaal": schat["per_item"] * aantal} if schat else None,
        "schatting_toelichting": (f"Mediaan per twijfelpunt of kaart over je laatste {schat['basis']} batches, "
                                  "keer het aantal." if schat else
                                  "Nog geen verdieping van jou om een schatting op te baseren."),
        "budget": {"resterend": stand.resterend, "budget": stand.budget, "actief": stand.actief,
                   "geblokkeerd": stand.geblokkeerd},
    }


async def zet_batch(werkgebied_id: str, run_id: str, batch_id: str, invoer: BatchInvoer, actor: str) -> dict:
    b = db.begrippen_batches
    resultaat = {"oordelen": [o.model_dump() for o in invoer.oordelen]} if invoer.soort == "vraag" \
        else {"kaarten": [k.model_dump() for k in invoer.kaarten]}
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = await _run_rij(conn, werkgebied_id, run_id, slot=True)
        bestaand = (await conn.execute(select(b).where(b.c.run_id == run_id, b.c.id == batch_id))).first()
        if bestaand is not None:
            if _hash(bestaand.resultaat) == _hash(resultaat) and bestaand.ids == invoer.ids:
                return _batch(bestaand)                                # dezelfde batch nog eens
            raise HTTPException(409, "Deze batch staat er al, met een andere uitkomst.")
        if row.verdieping is not None:
            raise HTTPException(409, "Deze run is al verdiept.")
        if invoer.soort == "vraag":
            vreemd = sorted(set(invoer.ids) - set(_te_vergelijken(row)))
            if vreemd:
                raise HTTPException(422, {"fout": "onbekende_vraag", "kandidaat_ids": vreemd,
                                          "melding": "De batch noemt paren die geen twijfelvraag van deze run zijn."})
        else:
            # Een kaart kan ook bij een groep horen die pas na het hergroeperen bestaat; de leden toetst
            # `zet_verdieping`. Hier: de tekst.
            _toets_kaarten(fragmentruimte(row.manifest, row.onderzoek), invoer.kaarten, {k.groep_id for k in invoer.kaarten})
        await conn.execute(insert(b).values(
            run_id=run_id, id=batch_id, werkgebied_id=werkgebied_id, soort=invoer.soort, ids=invoer.ids,
            resultaat=resultaat, model=invoer.model, promptversie=invoer.promptversie, tokens=invoer.tokens,
            gemaakt_door=actor, gemaakt=db.utcnow()))
        # De stilteklok van de run: graph-qa leeft nog.
        await conn.execute(update(db.begrippen_runs).where(db.begrippen_runs.c.id == run_id)
                           .values(gewijzigd=db.utcnow()))
        nieuw = (await conn.execute(select(b).where(b.c.run_id == run_id, b.c.id == batch_id))).first()
    return _batch(nieuw)


async def zet_verdieping(werkgebied_id: str, run_id: str, invoer: VerdiepingInvoer, actor: str) -> dict:
    r, g = db.begrippen_runs, db.betekenisgroepen
    verdieping = {"groep_ids": [x.id for x in invoer.groepen],
                  "oordelen": {o.kandidaat_id: o.model_dump() for o in invoer.oordelen},
                  "vragen": invoer.vragen, "model": invoer.model}
    h = _hash({**verdieping, "groepen": [x.model_dump() for x in invoer.groepen],
               "kaarten": [k.model_dump() for k in invoer.kaarten]})
    async with db.get_engine().begin() as conn:
        await _werkgebied(conn, werkgebied_id, slot=True)
        row = await _run_rij(conn, werkgebied_id, run_id, slot=True)
        if row.verdieping is not None:
            if row.verdieping.get("hash") == h:
                return _run(row)
            raise HTTPException(409, "Deze run is al verdiept, met een andere uitkomst.")
        if invoer.manifest_id != row.manifest_id:
            raise HTTPException(422, "De verdieping hoort bij een ander manifest dan deze run.")
        bekend = {f["element_id"] for f in row.manifest["formuleringen"]}
        vreemd = sorted({e for x in invoer.groepen for e in x.leden} - bekend)
        if vreemd:
            raise HTTPException(422, {"fout": "onbekend_element", "element_ids": vreemd,
                                      "melding": "De verdieping noemt elementen die niet in het manifest staan."})
        vragen = {v["kandidaat_id"] for v in row.uitkomst.get("vragen", [])}
        if set(invoer.vragen) - vragen or {o.kandidaat_id for o in invoer.oordelen} - vragen:
            raise HTTPException(422, "De verdieping noemt paren die geen twijfelvraag van deze run zijn.")
        _toets_kaarten(fragmentruimte(row.manifest, row.onderzoek), invoer.kaarten, {x.id for x in invoer.groepen})
        kaarten = {k.groep_id: k.model_dump() for k in invoer.kaarten}
        bestaande = {x.id for x in (await conn.execute(select(g.c.id).where(g.c.werkgebied_id == werkgebied_id))).all()}
        for groep in invoer.groepen:
            waarden = {"run_id": run_id, "leden": groep.leden, "aandacht": groep.aandacht,
                       "voorstel": groep.voorstel.model_dump(), "uitleg": groep.uitleg,
                       "conflicten": groep.conflicten, "door": groep.door, "kaart": kaarten.get(groep.id)}
            if groep.id in bestaande:                         # zelfde groep: het besluit blijft staan
                await conn.execute(update(g).where(g.c.werkgebied_id == werkgebied_id, g.c.id == groep.id)
                                   .values(**waarden))
            else:
                await conn.execute(insert(g).values(werkgebied_id=werkgebied_id, id=groep.id, besluit="open",
                                                    reden="", **waarden))
        await conn.execute(update(r).where(r.c.id == run_id).values(
            verdieping={**verdieping, "hash": h, "meting": invoer.meting, "door": actor,
                        "op": db.utcnow().isoformat()}, gewijzigd=db.utcnow()))
        await werkgebied_audit(conn, werkgebied_id, actor, "begrippen-verdiept",
                               {"run": run_id, "groepen": len(invoer.groepen), "kaarten": len(invoer.kaarten),
                                "oordelen": len(invoer.oordelen), "model": invoer.model})
        row = (await conn.execute(select(r).where(r.c.id == run_id))).first()
    return _run(row)
