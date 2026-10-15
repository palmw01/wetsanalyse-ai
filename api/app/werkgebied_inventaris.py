"""De inventaris van een werkgebied: welke geannoteerde elementen vallen binnen de selecties.

- Per regeling één bronboom (`_resolve_bron` levert altijd de hele regeling); de scope van een
  selectie is de bronnode zelf (`node`) of de node met alles eronder (`onderliggend`, via
  `annotatie_v2_store.bereik_van`).
- Elementen uit `annotatie_v2_store.actuele_elementen`, met de eigenaar binnen de scope. Elk
  element staat één keer in de inventaris, ook als selecties overlappen.
- Rol: `analyseren` als een analyse-selectie het element dekt, anders `context`.
- Een element met een anker buiten de samengevoegde scope krijgt `deels_buiten`; het wordt niet
  stil verbreed.
- Afgewezen elementen worden geteld, niet getoond.
- Per selectie: `bron_gewijzigd` als de huidige hash van de bronnode afwijkt van de bewaarde (een
  signaal, geen ongeldigverklaring), en `onbereikbaar` als de bronboom niet op te halen is. De rest
  van de inventaris komt dan gewoon: een niet-beschikbare bron is een open punt.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import HTTPException

from . import annotatie_v2_store as store

Resolver = Callable[[dict], Awaitable[dict]]

_VELDEN = ("id", "klasse", "tekst", "lifecycle", "aandacht", "jas_subtype", "eigenaar_iri",
           "laag_id", "ankers", "verouderd", "toelichting")


async def inventaris(selecties: list[dict], resolve: Resolver) -> dict:
    per_bwb: dict[str, dict] = {}
    fouten: dict[str, str] = {}
    for sel in selecties:
        bwb = sel["bwb_id"] or sel["bron_iri"].split(":")[2]
        if bwb in per_bwb or bwb in fouten:
            continue
        try:
            per_bwb[bwb] = await resolve({"bron_iri": sel["bron_iri"]})
        except HTTPException as exc:
            fouten[bwb] = str(exc.detail)

    alle_nodes: dict[str, dict] = {}
    volgorde: dict[str, int] = {}
    scopes: dict[str, set[str]] = {}
    samenvatting = []
    for sel in selecties:
        bwb = sel["bwb_id"] or sel["bron_iri"].split(":")[2]
        regel = {"id": sel["id"], "bron_iri": sel["bron_iri"], "label": sel["label"], "rol": sel["rol"],
                 "bereik": sel["bereik"], "aantal": 0, "afgewezen": 0, "bron_gewijzigd": False,
                 "onbereikbaar": None}
        samenvatting.append(regel)
        snapshot = per_bwb.get(bwb)
        if snapshot is None:
            regel["onbereikbaar"] = fouten.get(bwb, "Bron niet beschikbaar.")
            continue
        nodes = store.nodes_van(snapshot)
        if sel["bron_iri"] not in nodes:
            regel["onbereikbaar"] = "De bepaling staat niet (meer) in de actuele bronstand."
            continue
        scope = store.bereik_van(snapshot, sel["bron_iri"]) if sel["bereik"] == "onderliggend" \
            else {sel["bron_iri"]}
        scopes[sel["id"]] = scope
        for iri in scope:
            alle_nodes[iri] = nodes[iri]
        for i, n in enumerate(snapshot["nodes"] if isinstance(snapshot["nodes"], list) else nodes.values()):
            volgorde.setdefault(n["bron_iri"], n.get("volgorde", i))
        regel["bron_gewijzigd"] = bool(sel["bron_hash"]) and nodes[sel["bron_iri"]].get("bron_hash") != sel["bron_hash"]

    elementen = await store.actuele_elementen(alle_nodes) if alle_nodes else []
    alle_scope = set(alle_nodes)
    per_id = {r["id"]: r for r in samenvatting}
    uit = []
    for el in elementen:
        dekkend = [sid for sid, scope in scopes.items() if el["eigenaar_iri"] in scope]
        if not dekkend:
            continue
        if el.get("lifecycle") == "rejected":
            for sid in dekkend:
                per_id[sid]["afgewezen"] += 1
            continue
        for sid in dekkend:
            per_id[sid]["aantal"] += 1
        analyse = any(per_id[sid]["rol"] == "analyseren" for sid in dekkend)
        uit.append({**{k: el.get(k) for k in _VELDEN if k in el},
                    "rol": "analyseren" if analyse else "context",
                    "selecties": sorted(dekkend),
                    "deels_buiten": any(a["bron_iri"] not in alle_scope for a in el.get("ankers", []))})

    def sleutel(e: dict):
        eerste = min(e.get("ankers") or [{"bron_iri": e["eigenaar_iri"], "start": 0}],
                     key=lambda a: (volgorde.get(a["bron_iri"], 1 << 30), a.get("start", 0)))
        return (volgorde.get(eerste["bron_iri"], 1 << 30), eerste.get("start", 0), e["id"])

    uit.sort(key=sleutel)
    return {"selecties": samenvatting, "elementen": uit,
            "volledig": not any(r["onbereikbaar"] for r in samenvatting)}
