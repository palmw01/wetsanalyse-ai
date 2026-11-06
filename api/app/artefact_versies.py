"""Momentopnamen van artefacten: de versiekiezer zoals bij Claude (deel 2 van de artefacten, 4 nov 2026).

Een artefact van Lex is een levend object (werkgebied, begrip, annotatie, …): wat de chip opent, is de stand van nu.
Claude toont bij een artefact de versie die bij die beurt hoort, met ‹ versie n van m ›. Daarvoor legt de api bij het
bewaren van een assistentbericht met een artefact de stand van dat moment vast (`leg_vast`), met zijn eigen
leesfuncties – één schrijfpad, dat niemand kan overslaan. Het id komt in `artefact.ref.versie`; een bericht verandert
daarna niet meer, dus "de stand na beurt n" ligt vast.

- **Een versie is de stand direct na een beurt van Lex** die het artefact opleverde of bijwerkte (besluit gebruiker).
  Handmatige wijzigingen ertussen zijn geen eigen versie; die zie je op *Nu*.
- **Per object tellen, over gesprekken heen** (`sleutel`): een werkgebied of annotatie is gedeeld.
- **Een mislukte opname laat het bericht landen**, zonder `versie`: de versie is een gemak, geen voorwaarde.
- **Idempotent** op (run, sleutel): een herhaalde beurt (dezelfde `run_id`) maakt geen tweede versie.
- Een verwijderd werkgebied neemt zijn versies mee (`werkgebied_store.WERKGEBIED_TABELLEN`); een verwijderde annotatie
  ook (`annotatie_v2_store.verwijder_weergave`).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, insert, select

from . import db
from .auth import require_client
from .routers.auth import actieve_userid

logger = logging.getLogger("wetsanalyse.artefact_versies")
POGINGEN = 3  # de eerste lezing en hoogstens twee keer opnieuw

#: De soorten met een momentopname; `regels` is gereserveerd, `bronnen` bestaat niet meer (een bronselectie).
SOORTEN = ("werkgebied", "deelvraag", "bronselectie", "begrip", "begrippen", "annotatie")


def sleutel_van(soort: str, ref: dict[str, Any]) -> str | None:
    """Welk object: één sleutel per object, zodat de versies ervan bij elkaar horen."""
    wid = str(ref.get("werkgebied_id") or "")
    if soort == "annotatie":
        return f"annotatie:{ref['bron_iri']}" if ref.get("bron_iri") else None
    if not wid:
        return None
    return {"werkgebied": f"werkgebied:{wid}", "bronselectie": f"bronselectie:{wid}", "begrippen": f"begrippen:{wid}",
            "deelvraag": f"deelvraag:{wid}:{ref.get('deelvraag_id', '')}" if ref.get("deelvraag_id") else None,
            "begrip": f"begrip:{wid}:{ref.get('begrip_id', '')}" if ref.get("begrip_id") else None}.get(soort)


async def _inhoud(soort: str, ref: dict[str, Any]) -> dict[str, Any]:
    """De stand van nu, met dezelfde leesfuncties als de routes die het paneel gebruikt."""
    from . import begrip_relatie_store, begrip_store, begrippen_run_store, bronselectie, werkgebied_store

    wid = str(ref.get("werkgebied_id") or "")
    if soort == "werkgebied":
        return {"werkgebied": await werkgebied_store.haal(wid), "bronselectie": await bronselectie.overzicht(wid)}
    if soort == "bronselectie":
        return {"bronselectie": await bronselectie.overzicht(wid)}
    if soort == "deelvraag":
        wg = await werkgebied_store.haal(wid)
        d = next((x for x in wg.get("deelvragen") or [] if x["id"] == ref["deelvraag_id"]), None)
        return {"werkgebied": wg, "deelvraag": d, "bronselectie": await bronselectie.overzicht(wid)}
    if soort == "begrip":
        bid = str(ref["begrip_id"])
        return {"begrip": await begrip_store.haal(wid, bid), "relaties": await begrip_relatie_store.lijst(wid, bid)}
    if soort == "begrippen":
        return {"groepen": await begrippen_run_store.groepen(wid)}
    if soort == "annotatie":
        from .annotatie_v2 import resolve_bron
        from . import annotatie_v2_store
        doel = {"bron_iri": ref["bron_iri"], "bwb_id": "", "artikel": "", "lid": ""}
        return {"weergave": annotatie_v2_store.compacte_weergave(await annotatie_v2_store.weergave(await resolve_bron(doel)))}
    raise ValueError(soort)


async def _revisie(soort: str, ref: dict[str, Any]) -> int | None:
    """De revisie die de soorten dragen die hun stand uit meer dan één leesactie opbouwen; de rest leest één keer.
    De stand van een bronselectie heeft een eigen revisie en valt hierbuiten."""
    if soort in ("werkgebied", "deelvraag"):
        t, sleutel = db.werkgebieden, ref.get("werkgebied_id")
    elif soort == "begrip":
        t, sleutel = db.begrippen, ref.get("begrip_id")
    else:
        return None
    async with db.get_engine().connect() as conn:
        return (await conn.execute(select(t.c.revisie).where(t.c.id == str(sleutel or "")))).scalar()


async def _een_stand(soort: str, ref: dict[str, Any]) -> dict[str, Any]:
    """`_inhoud` met de revisie ervoor en erna gelijk: wijzigde iemand het object tijdens het lezen, dan opnieuw,
    hoogstens twee keer. Daarna telt de opname toch, met `consistent: false`: het bericht mag er niet op wachten."""
    for _ in range(POGINGEN):
        voor = await _revisie(soort, ref)
        inhoud = await _inhoud(soort, ref)
        if voor == await _revisie(soort, ref):
            return inhoud
    logger.warning("artefact: momentopname over een wijziging heen", extra={"categorie": "technisch", "soort": soort})
    return {**inhoud, "consistent": False}


async def leg_vast(gesprek_id: str, run_id: str, artefact: dict[str, Any]) -> str | None:
    """Leg de stand van het artefact van deze beurt vast; geeft het versie-id, of None (geen soort met versies, geen
    run, of het lukte niet – dat logt en blokkeert niets)."""
    soort, ref = artefact.get("soort", ""), dict(artefact.get("ref") or {})
    if soort not in SOORTEN or not run_id or not (sleutel := sleutel_van(soort, ref)):
        return None
    t = db.artefact_versies
    async with db.get_engine().connect() as conn:
        al = (await conn.execute(select(t.c.id).where(t.c.run_id == run_id, t.c.sleutel == sleutel))).scalar()
    if al:
        return al
    try:
        inhoud = await _een_stand(soort, ref)
    except Exception:  # noqa: BLE001 – een versie is een gemak; het bericht moet landen
        logger.warning("artefact: geen momentopname", extra={"categorie": "technisch", "soort": soort}, exc_info=True)
        return None
    vid = uuid.uuid4().hex
    try:
        async with db.get_engine().begin() as conn:
            await conn.execute(insert(t).values(id=vid, soort=soort, sleutel=sleutel, werkgebied_id=str(ref.get("werkgebied_id") or ""),
                                                gesprek_id=gesprek_id, run_id=run_id, inhoud=_json(inhoud), gemaakt=db.utcnow()))
    except Exception:  # noqa: BLE001 – een gelijktijdige opname van dezelfde run: neem die
        async with db.get_engine().connect() as conn:
            al = (await conn.execute(select(t.c.id).where(t.c.run_id == run_id, t.c.sleutel == sleutel))).scalar()
        return al
    return vid


def _json(x: Any) -> Any:
    """Wat de leesfuncties geven, als JSON (datums als tekst)."""
    import json
    return json.loads(json.dumps(x, default=str))


async def haal(versie_id: str) -> dict[str, Any]:
    """Eén versie met haar plek tussen de andere van hetzelfde object: `{id, soort, sleutel, inhoud, gemaakt, nr,
    totaal, vorige, volgende}`. 404 als ze er niet (meer) is."""
    t = db.artefact_versies
    async with db.get_engine().connect() as conn:
        row = (await conn.execute(select(t).where(t.c.id == versie_id))).mappings().first()
        if row is None:
            raise HTTPException(404, "Deze versie bestaat niet (meer).")
        ids = [r for r, in (await conn.execute(select(t.c.id).where(t.c.sleutel == row["sleutel"])
                                                .order_by(t.c.gemaakt, t.c.id))).all()]
    i = ids.index(row["id"])
    return {"id": row["id"], "soort": row["soort"], "sleutel": row["sleutel"], "inhoud": row["inhoud"],
            "gemaakt": db.aware(row["gemaakt"]).isoformat(), "nr": i + 1, "totaal": len(ids),
            "vorige": ids[i - 1] if i else None, "volgende": ids[i + 1] if i + 1 < len(ids) else None}


async def lijst(sleutel: str) -> list[dict[str, Any]]:
    """De versies van één object, oud → nieuw (zonder inhoud)."""
    t = db.artefact_versies
    async with db.get_engine().connect() as conn:
        rows = (await conn.execute(select(t.c.id, t.c.gemaakt, t.c.gesprek_id).where(t.c.sleutel == sleutel)
                                   .order_by(t.c.gemaakt, t.c.id))).all()
    return [{"id": r.id, "nr": n, "gemaakt": db.aware(r.gemaakt).isoformat(), "gesprek_id": r.gesprek_id}
            for n, r in enumerate(rows, start=1)]


async def wis_sleutel(conn, sleutel: str) -> None:
    await conn.execute(delete(db.artefact_versies).where(db.artefact_versies.c.sleutel == sleutel))


# Routes. Toegang zoals het object: werkgebieden en annotaties zijn gedeeld, dus elke actieve gebruiker.
router = APIRouter(prefix="/artefact-versies", tags=["artefacten"], dependencies=[Depends(require_client)])


@router.get("")
async def get_lijst(sleutel: str = Query(..., min_length=1, max_length=600), actor: str = Depends(actieve_userid)):
    return {"sleutel": sleutel, "versies": await lijst(sleutel)}


@router.get("/{versie_id}")
async def get_versie(versie_id: str, actor: str = Depends(actieve_userid)):
    return await haal(versie_id)
