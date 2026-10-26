"""Werkgebieden-API (spoor D, levering 1). Gedeeld tussen analisten; elke route vraagt een actieve
gebruiker, die als actor in de audit komt."""
from __future__ import annotations

import httpx
from bronmodel import BronFout
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import annotatie_v2_store, werkgebied_deelvragen as deelvragen, werkgebied_store as store
from .auth import require_client
from .bron_resolver import resolve_bron as _resolve_bron
from .routers.auth import actieve_userid
from .werkgebied_contracts import (
    BronselectieInvoer, BronselectieWijziging, DeelvraagInvoer, DeelvraagKoppelingen, DeelvraagVoorstellen,
    DeelvraagWijziging, WerkgebiedInvoer, WerkgebiedWijziging,
)
from .werkgebied_inventaris import inventaris
from .werkgebied_werkvoorraad import selecties_in_bereik, werkvoorraad

router = APIRouter(prefix="/werkgebieden", tags=["werkgebieden"],
                   dependencies=[Depends(require_client)])


async def resolve_bron(doel: dict) -> dict:
    """Zelfde foutvertaling als de annotatie-API: ongeldige bron 422, graaf weg 503."""
    try:
        return await _resolve_bron(doel)
    except BronFout as exc:
        raise HTTPException(422, str(exc)) from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar.") from exc


@router.get("")
async def get_lijst(mijn: bool = False, bron_iri: str | None = Query(None, max_length=2000),
                    actor: str = Depends(actieve_userid)):
    return {"werkgebieden": await store.lijst(actor if mijn else None, bron_iri)}


@router.post("", status_code=201)
async def post_werkgebied(req: WerkgebiedInvoer, actor: str = Depends(actieve_userid)):
    return await store.maak(req, actor)


@router.get("/{werkgebied_id}")
async def get_werkgebied(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id)


@router.patch("/{werkgebied_id}")
async def patch_werkgebied(werkgebied_id: str, req: WerkgebiedWijziging,
                           actor: str = Depends(actieve_userid)):
    return await store.wijzig(werkgebied_id, req, actor)


@router.delete("/{werkgebied_id}")
async def delete_werkgebied(werkgebied_id: str, verwachte_revisie: int = Query(ge=1),
                            actor: str = Depends(actieve_userid)):
    return await store.verwijder(werkgebied_id, verwachte_revisie, actor)


@router.post("/{werkgebied_id}/bronnen")
async def post_bron(werkgebied_id: str, req: BronselectieInvoer, response: Response,
                    actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id)                     # 404 vóór de graaf wordt gevraagd
    snapshot = await resolve_bron({"bron_iri": req.bron_iri, "bwb_id": req.bwb_id,
                                   "artikel": req.artikel, "lid": req.lid})
    doel = snapshot["doel"]
    node = annotatie_v2_store.nodes_van(snapshot).get(doel["bron_iri"], {})
    bron = {"bron_iri": doel["bron_iri"], "label": doel.get("label") or node.get("label", ""),
            "bwb_id": doel.get("bwb_id") or node.get("bwb_id", ""),
            "snapshot_id": snapshot.get("snapshot_id", ""), "bron_hash": node.get("bron_hash", "")}
    selectie, nieuw = await store.voeg_bron_toe(werkgebied_id, req, bron, actor)
    response.status_code = 201 if nieuw else 200
    return {"selectie": selectie, "werkgebied": await store.haal(werkgebied_id)}


@router.patch("/{werkgebied_id}/bronnen/{selectie_id}")
async def patch_bron(werkgebied_id: str, selectie_id: str, req: BronselectieWijziging,
                     actor: str = Depends(actieve_userid)):
    return await store.wijzig_bron(werkgebied_id, selectie_id, req, actor)


@router.delete("/{werkgebied_id}/bronnen/{selectie_id}")
async def delete_bron(werkgebied_id: str, selectie_id: str, verwachte_revisie: int = Query(ge=1),
                      actor: str = Depends(actieve_userid)):
    return await store.verwijder_bron(werkgebied_id, selectie_id, verwachte_revisie, actor)


# --- Deelvragen (optioneel; open keuze 4) -----------------------------------------------------------
# Elke wijziging draagt de revisie van het werkgebied en geeft het werkgebied terug, zoals de bronnen.
# `voorstellen` is voor graph-qa: geen revisie, het raakt de scope pas na overnemen.

@router.post("/{werkgebied_id}/deelvragen", status_code=201)
async def post_deelvraag(werkgebied_id: str, req: DeelvraagInvoer, actor: str = Depends(actieve_userid)):
    return await deelvragen.maak(werkgebied_id, req, actor)


# Vóór `/deelvragen/{deelvraag_id}`, anders leest de router "dekking" en "voorstellen" als een id.
@router.get("/{werkgebied_id}/deelvragen/dekking")
async def get_deelvragen_dekking(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await deelvragen.dekking(werkgebied_id)


@router.post("/{werkgebied_id}/deelvragen/voorstellen")
async def post_deelvraag_voorstellen(werkgebied_id: str, req: DeelvraagVoorstellen,
                                     actor: str = Depends(actieve_userid)):
    return await deelvragen.stel_voor(werkgebied_id, req, actor)


@router.get("/{werkgebied_id}/deelvragen/{deelvraag_id}")
async def get_deelvraag(werkgebied_id: str, deelvraag_id: str, actor: str = Depends(actieve_userid)):
    """Eén deelvraag, ook als ze vervangen is: met haar opvolgers en de voorstellen die haar vervangen."""
    return await deelvragen.haal(werkgebied_id, deelvraag_id)


@router.patch("/{werkgebied_id}/deelvragen/{deelvraag_id}")
async def patch_deelvraag(werkgebied_id: str, deelvraag_id: str, req: DeelvraagWijziging,
                          actor: str = Depends(actieve_userid)):
    return await deelvragen.wijzig(werkgebied_id, deelvraag_id, req, actor)


@router.put("/{werkgebied_id}/deelvragen/{deelvraag_id}/koppelingen")
async def put_deelvraag_koppelingen(werkgebied_id: str, deelvraag_id: str, req: DeelvraagKoppelingen,
                                    actor: str = Depends(actieve_userid)):
    return await deelvragen.koppel(werkgebied_id, deelvraag_id, req, actor)


@router.delete("/{werkgebied_id}/deelvragen/{deelvraag_id}")
async def delete_deelvraag(werkgebied_id: str, deelvraag_id: str, verwachte_revisie: int = Query(ge=1),
                           actor: str = Depends(actieve_userid)):
    return await deelvragen.verwijder(werkgebied_id, deelvraag_id, verwachte_revisie, actor)


@router.get("/{werkgebied_id}/elementen")
async def get_elementen(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    wg = await store.haal(werkgebied_id)
    return {"werkgebied_id": werkgebied_id, "revisie": wg["revisie"],
            **await inventaris(wg["bronnen"], resolve_bron)}


@router.get("/{werkgebied_id}/annotatie-werkvoorraad")
async def get_annotatie_werkvoorraad(werkgebied_id: str,
                                     bereik: str = Query("werkgebied", pattern="^(werkgebied|deelvragen)$"),
                                     deelvraag_id: str = Query("", pattern=r"^[A-Za-z0-9-]{0,64}$"),
                                     actor: str = Depends(actieve_userid)):
    """Wat Lex in dit werkgebied nog moet annoteren (fase B): de eenheden van de analysebronnen met
    hun stand, de schatting voor deze gebruiker en zijn budget. Alleen lezen.

    `bereik=deelvragen` beperkt het tot de bronnen onder de actieve deelvragen, met `deelvraag_id` tot
    die van één deelvraag."""
    if deelvraag_id and bereik != "deelvragen":
        raise HTTPException(422, "deelvraag_id hoort bij bereik=deelvragen")
    wg = await store.haal(werkgebied_id)
    selecties, extra = wg["bronnen"], {"bereik": bereik}
    if bereik == "deelvragen":
        if deelvraag_id:
            d = await deelvragen.haal(werkgebied_id, deelvraag_id)
            if d["status"] != "actief":
                raise HTTPException(409, {"fout": "niet_actief", "melding":
                                          "Deze deelvraag is niet (meer) actief; annoteer de bronnen van een actieve deelvraag."})
        elif not any(d.get("status") == "actief" for d in wg["deelvragen"]):
            raise HTTPException(409, {"fout": "geen_deelvragen", "melding": "Dit werkgebied heeft nog geen deelvragen."})
        selecties, meegenomen = selecties_in_bereik(wg["bronnen"], wg["deelvragen"], deelvraag_id)
        binnen = {s["id"] for s in selecties}
        extra |= {"deelvragen": meegenomen,
                  "buiten_bereik": sum(1 for s in wg["bronnen"] if s["rol"] == "analyseren" and s["id"] not in binnen)}
    return {"werkgebied_id": werkgebied_id, "revisie": wg["revisie"], "naam": wg["naam"], **extra,
            **await werkvoorraad(selecties, resolve_bron, actor)}


@router.get("/{werkgebied_id}/audit")
async def get_audit(werkgebied_id: str, limit: int = Query(100, ge=1, le=500),
                    actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id, met_gearchiveerd=True)
    return {"audit": await store.audit(werkgebied_id, limit)}
