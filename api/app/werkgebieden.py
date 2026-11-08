"""Werkgebieden-API (spoor D, levering 1). Gedeeld tussen analisten; elke route vraagt een actieve
gebruiker, die als actor in de audit komt."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Literal

import httpx
from bronmodel import BronFout, BronKeuze
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from . import annotatie_v2_store, bepaling_graaf, pdf_opmaak, werkgebied_deelvragen as deelvragen, werkgebied_export, werkgebied_store as store
from .auth import require_client
from .bron_resolver import resolve_bron as _resolve_bron
from .graaf_client import sparql_select
from .graaf_projectie_v2 import verklaringen
from .graaf import lees_bron as _lees_bron
from .routers.auth import actieve_userid
from .werkgebied_contracts import (
    BronselectieInvoer, BronselectieWijziging, DeelvragenSamen, DeelvraagVoorstellen, DeelvraagWijziging,
    WerkgebiedInvoer, WerkgebiedWijziging,
)
from .werkgebied_inventaris import inventaris
from .werkgebied_werkvoorraad import selecties_in_bereik, werkvoorraad

logger = logging.getLogger("wetsanalyse.werkgebieden")

router = APIRouter(prefix="/werkgebieden", tags=["werkgebieden"],
                   dependencies=[Depends(require_client)])


async def _met_foutvertaling(resolve, doel: dict) -> dict:
    try:
        return await resolve(doel)
    except BronKeuze as exc:
        # Een dubbelzinnig nummer of een lid dat niet bestaat: de graaf kent wel de opties. Die gaan mee,
        # zodat de werkplek kan laten kiezen in plaats van alleen "niet gevonden" te zeggen.
        raise HTTPException(422, {"melding": str(exc), "opties": exc.opties}) from exc
    except BronFout as exc:
        raise HTTPException(422, str(exc)) from exc
    except (httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(503, "De brongraaf is tijdelijk niet beschikbaar.") from exc


async def resolve_bron(doel: dict) -> dict:
    """Zelfde foutvertaling als de annotatie-API: ongeldige bron 422, graaf weg 503."""
    return await _met_foutvertaling(_resolve_bron, doel)


async def geverifieerde_bron(doel: dict) -> dict:
    """Een bepaling zoals een werkgebied haar opneemt, geverifieerd in de graaf (`resolve_bron`: 422 als ze niet
    bestaat): de canonieke IRI, het label, de regeling, de snapshot en de teksthash. Eén plek voor zelf opnemen, een
    kandidaat opnemen en een genoemde bepaling."""
    snapshot = await resolve_bron(doel)
    gevonden = snapshot["doel"]
    node = annotatie_v2_store.nodes_van(snapshot).get(gevonden["bron_iri"], {})
    return {"bron_iri": gevonden["bron_iri"], "label": gevonden.get("label") or node.get("label", ""),
            "bwb_id": gevonden.get("bwb_id") or node.get("bwb_id", ""),
            "snapshot_id": snapshot.get("snapshot_id", ""), "bron_hash": node.get("bron_hash", "")}


async def lees_bron(doel: dict) -> dict:
    """De bronboom voor een route die alleen leest, uit de cache (`graaf.lees_bron`); wat iets vastlegt, neemt
    `resolve_bron`."""
    return await _met_foutvertaling(_lees_bron, doel)


@router.get("")
async def get_lijst(mijn: bool = False, bron_iri: str | None = Query(None, max_length=2000),
                    actor: str = Depends(actieve_userid)):
    return {"werkgebieden": await store.lijst(actor if mijn else None, bron_iri)}


@router.post("", status_code=201)
async def post_werkgebied(req: WerkgebiedInvoer, actor: str = Depends(actieve_userid)):
    return await store.maak(req, actor)


@router.get("/export-schema")
async def get_export_schema(actor: str = Depends(actieve_userid)):
    """Vóór `/{werkgebied_id}`, anders vangt die route hem af. Het JSON-schema van het werkgebiedrapport (`formaat=json`), zodat een ontvanger het document kan toetsen."""
    from . import werkgebied_rapport
    return werkgebied_rapport.json_schema()


@router.get("/{werkgebied_id}")
async def get_werkgebied(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await store.haal(werkgebied_id)


@router.get("/{werkgebied_id}/thema-voorstel")
async def get_thema_voorstel(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    """Spoor I6: de thema's (tooitop) die passen bij de WTI-rechtsgebieden van de regelingen van de bronnen,
    zonder model. Best-effort: zonder graaf een lege lijst."""
    from . import tooi

    wg = await store.haal(werkgebied_id)
    regelingen = sorted(f"urn:bwb:{b}" for b in store.regelingen_van(wg))
    gebieden: list[str] = []
    if regelingen:
        waarden = " ".join(f"<{r}>" for r in regelingen)
        q = f"""PREFIX dct: <http://purl.org/dc/terms/> PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?r ?l WHERE {{ VALUES ?r {{ {waarden} }} ?r dct:subject ?b . ?b skos:prefLabel ?l }}"""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                gebieden = [x["l"] for x in await sparql_select(client, q)]
        except (httpx.HTTPError, ConnectionError, ValueError):
            gebieden = []
    voorstel = tooi.thema_voorstel(gebieden)
    return {"rechtsgebieden": sorted(set(gebieden)),
            "voorstel": [{"thema": u, "label": tooi.thema_label(u)} for u in voorstel]}


def toestanden_query(bwb_ids: list[str]) -> str:
    """Per regeling de toestand in de graaf: wanneer de tekst ging gelden (`bwb:geldigVanaf`) en tot wanneer.
    De BWB-id's komen uit Postgres, maar gaan alleen in de vorm `BWBR…`/`BWBV…` de query in."""
    waarden = " ".join(f"<urn:bwb:{b}>" for b in bwb_ids if re.fullmatch(r"BWB[RV]\d+", b))
    return f"""PREFIX bwb: <urn:bwb-ns:>
SELECT ?r ?citeertitel ?vanaf ?tot WHERE {{ VALUES ?r {{ {waarden} }}
  OPTIONAL {{ ?r bwb:citeertitel ?citeertitel }} OPTIONAL {{ ?r bwb:geldigVanaf ?vanaf }} OPTIONAL {{ ?r bwb:geldigTot ?tot }}
}}"""


async def toestanden_van(wg: dict) -> dict:
    """De peildatum naast de toestand van elke regeling van het werkgebied (`regelingen_van`). De graaf bevat per regeling alleen de
    nieuwste toestand: ging die pas ná de peildatum gelden, dan kan de tekst afwijken van wat op de peildatum
    gold (`na_peildatum`). Best-effort: een haperende graaf geeft `volledig: false`, nooit een stille leegte."""
    bwbs = store.regelingen_van(wg)
    uit = {"peildatum": wg["peildatum"], "peildatum_standaard": wg["peildatum_standaard"], "regelingen": [],
           "volledig": True}
    if not bwbs:
        return uit
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            rijen = await sparql_select(client, toestanden_query(bwbs))
    except (httpx.HTTPError, ConnectionError, ValueError):
        return {**uit, "volledig": False}
    per = {(r.get("r") or "").removeprefix("urn:bwb:"): r for r in rijen}
    for b in bwbs:
        r = per.get(b, {})
        vanaf = (r.get("vanaf") or "")[:10]
        uit["regelingen"].append({"bwb_id": b, "citeertitel": r.get("citeertitel") or b, "geldig_vanaf": vanaf or None,
                                  "geldig_tot": (r.get("tot") or "")[:10] or None,
                                  "na_peildatum": bool(vanaf) and vanaf > wg["peildatum"]})
    return uit


@router.get("/{werkgebied_id}/toestanden")
async def get_toestanden(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    return await toestanden_van(await store.haal(werkgebied_id))


_GRAAF_WEG = "De kennisgraaf is tijdelijk niet bereikbaar."


@router.get("/{werkgebied_id}/bepalingen")
async def get_bepalingen(werkgebied_id: str, bwb_id: str = Query(..., pattern=r"^BWB[RV]\d+$"),
                         q: str = Query("", max_length=200), actor: str = Depends(actieve_userid)):
    """De bepalingen in één regeling die bij een getypte vindplaats passen ("9 lid 2", "21.1", "25.4 onderdeel
    b"), uit de echte bronboom, met het begin van hun tekst. Leeg = niets gevonden, met `gelezen`: hoe de
    invoer gelezen is, zodat de werkplek kan zeggen wat er niet bestaat."""
    from dataclasses import asdict

    from . import bepaling_zoeken as zoeken

    await store.haal(werkgebied_id)
    try:
        nodes = await zoeken.boom(bwb_id)
    except BronFout as exc:
        raise HTTPException(404, "Deze regeling staat niet in de kennisgraaf.") from exc
    except (httpx.HTTPError, ConnectionError, ValueError) as exc:
        raise HTTPException(503, _GRAAF_WEG) from exc
    return {"bwb_id": bwb_id, "gelezen": asdict(zoeken.lees(q)), "treffers": zoeken.zoek(nodes, q)}


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
    bron = await geverifieerde_bron({"bron_iri": req.bron_iri, "bwb_id": req.bwb_id,
                                     "artikel": req.artikel, "lid": req.lid})
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
# Elke wijziging draagt de revisie van het werkgebied en geeft het werkgebied terug, zoals de bronnen. De
# werkplek bewerkt ze samen (`samen`) of één tegelijk (`PATCH`). `voorstellen` is voor graph-qa: geen revisie, het raakt de scope pas na overnemen.

@router.post("/{werkgebied_id}/deelvragen/samen")
async def post_deelvragen_samen(werkgebied_id: str, req: DeelvragenSamen, actor: str = Depends(actieve_userid)):
    return await deelvragen.samen(werkgebied_id, req, actor)


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


@router.get("/{werkgebied_id}/elementen")
async def get_elementen(werkgebied_id: str, actor: str = Depends(actieve_userid)):
    wg = await store.haal(werkgebied_id)
    return {"werkgebied_id": werkgebied_id, "revisie": wg["revisie"],
            **await inventaris(wg["bronnen"], lees_bron)}


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
            **await werkvoorraad(selecties, lees_bron, actor)}


@router.get("/{werkgebied_id}/export")
async def get_export(werkgebied_id: str, formaat: Literal["pdf", "md", "json"] = "pdf",
                     inhoud: Literal["beoordeeld", "alles"] = "beoordeeld", actor: str = Depends(actieve_userid)):
    """Het hele werkgebied als één PDF of Markdown, op de stand van nu en met dezelfde inhoud: dossier, deelvragen en bronnen met hun wettekst, annotaties,
    begrippen en een korte verantwoording. De inhoud staat in `werkgebied_export`. Reportlab is puur Python en de api
    deelt de event loop: het zetten gebeurt in een thread."""
    start = time.monotonic()
    data = await werkgebied_export.verzamel(werkgebied_id, actor, resolve_bron, toestanden_van, bepaling_graaf.lees, inhoud=inhoud)
    maak = {"md": werkgebied_export.markdown_export, "json": werkgebied_export.json_export}.get(formaat, werkgebied_export.pdf_export)
    body = await asyncio.to_thread(maak, data, verklaringen())
    logger.info("werkgebied_export", extra={"werkgebied_id": werkgebied_id, "formaat": formaat, "inhoud": inhoud, "bytes": len(body),
                                            "paginas": pdf_opmaak.aantal_paginas(body) if formaat == "pdf" else None,
                                            "ms": round((time.monotonic() - start) * 1000)})
    soort = {"md": "text/markdown; charset=utf-8", "json": "application/json"}.get(formaat, "application/pdf")
    return Response(body, media_type=soort, headers={
        "Content-Disposition": f'attachment; filename="{werkgebied_export.bestandsnaam(data, formaat)}"'})


@router.get("/{werkgebied_id}/audit")
async def get_audit(werkgebied_id: str, limit: int = Query(100, ge=1, le=500),
                    actor: str = Depends(actieve_userid)):
    await store.haal(werkgebied_id)
    return {"audit": await store.audit(werkgebied_id, limit)}
