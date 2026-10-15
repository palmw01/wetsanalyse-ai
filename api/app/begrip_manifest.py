"""Het manifest van de begrippenketen (spoor D, levering 3; ADR-004): de vaste invoer van één run.

De api materialiseert het uit Postgres en de bronboom (PLAN D, verwerking stap 1), via dezelfde
inventaris als de tab Elementen: actuele, niet-verworpen elementen binnen de selecties, contextbronnen
inbegrepen – een definitie buiten de analyseselectie hoort juist als contextbron in het manifest.

De vorm volgt `tools/graph-qa/agent/begrippen_pipeline/model.py` (`Bron`, `Formulering`,
`Manifest`). Importeren kan niet (twee diensten); `manifest_id` rekent daarom hier op dezelfde manier,
en `manifest-id.vectoren.json` bij de referentiesets bewaakt aan beide kanten dat dat zo blijft.

Wat niet past, gaat er niet stil uit maar staat in `overgeslagen` met een reden:
- een element met meer dan één anker – een `Formulering` kent er één;
- een element dat verouderd is, of waarvan het anker niet meer letterlijk op de brontekst staat.
"""
from __future__ import annotations

import hashlib
from typing import Awaitable, Callable

from .werkgebied_inventaris import inventaris_met_bronbomen, nodes_met_titel

Resolver = Callable[[dict], Awaitable[dict]]


def manifest_id(bronnen: list[dict], formuleringen: list[dict]) -> str:
    """Zelfde rekenwijze als `Manifest.id` in de keten: inhoud, geen moment."""
    delen = sorted(f"{b['bron_iri']}@{b['bron_hash']}" for b in bronnen)
    delen += sorted(f["element_id"] for f in formuleringen)
    return "M" + hashlib.sha256("\x1f".join(delen).encode()).hexdigest()[:16]


def _vindplaats(nodes: dict[str, dict], iri: str) -> str:
    """"Artikel 9 · Lid 1 – Invorderingswet 1990": van het artikel omlaag, met de regeling erachter."""
    keten, iri_nu = [], iri
    while iri_nu in nodes:
        keten.append(nodes[iri_nu])
        iri_nu = nodes[iri_nu].get("parent_iri") or ""
    keten.reverse()
    regeling = keten[0].get("label", "") if keten else ""
    vanaf = next((i for i, n in enumerate(keten) if n.get("type") == "Artikel"), len(keten) - 1)
    pad = " · ".join(n.get("label", "") for n in keten[vanaf:] if n.get("label"))
    return f"{pad} – {regeling}" if regeling and pad != regeling else pad


async def bouw(werkgebied: dict, resolve: Resolver) -> dict:
    """`{manifest: {bronnen, formuleringen}, manifest_id, overgeslagen, volledig}`."""
    inv, per_bwb = await inventaris_met_bronbomen(werkgebied["bronnen"], resolve)
    nodes: dict[str, dict] = {}
    for snap in per_bwb.values():
        nodes.update(nodes_met_titel(snap))

    bronnen: dict[str, dict] = {}
    formuleringen: list[dict] = []
    overgeslagen: list[dict] = []
    for el in inv["elementen"]:
        ankers = el.get("ankers") or []
        if len(ankers) != 1:
            overgeslagen.append({"element_id": el["id"], "tekst": el.get("tekst", ""),
                                 "reden": "Dit element heeft meer dan één anker; de keten werkt per passage."})
            continue
        a = ankers[0]
        node = nodes.get(a["bron_iri"])
        tekst = (node or {}).get("tekst") or ""
        if el.get("verouderd") or node is None or tekst[a["start"]:a["eind"]] != a.get("tekst", el.get("tekst")):
            overgeslagen.append({"element_id": el["id"], "tekst": el.get("tekst", ""),
                                 "reden": "De brontekst veranderde sinds deze markering; beoordeel haar eerst opnieuw."})
            continue
        if a["bron_iri"] not in bronnen:
            ouder = nodes.get(node.get("parent_iri") or "", {})
            bronnen[a["bron_iri"]] = {
                "bron_iri": a["bron_iri"], "tekst": tekst, "bron_hash": node["bron_hash"],
                "label": _vindplaats(nodes, a["bron_iri"]),
                # De aanhef van de houder bepaalt het bereik van een definitie ("Deze wet verstaat onder:").
                "aanhef": ouder.get("tekst") or "",
                "regeling": node.get("bwb_id") or a["bron_iri"].split(":")[2],
            }
        formuleringen.append({"element_id": el["id"], "bron_iri": a["bron_iri"], "start": a["start"],
                              "eind": a["eind"], "tekst": tekst[a["start"]:a["eind"]],
                              "jas_klasse": el.get("klasse") or "", "jas_subtype": el.get("jas_subtype") or "",
                              "review_status": el.get("lifecycle") or "voorgesteld"})

    lijst = sorted(bronnen.values(), key=lambda b: b["bron_iri"])
    formuleringen.sort(key=lambda f: (f["bron_iri"], f["start"], f["element_id"]))
    return {"manifest": {"bronnen": lijst, "formuleringen": formuleringen},
            "manifest_id": manifest_id(lijst, formuleringen), "overgeslagen": overgeslagen,
            "volledig": inv["volledig"]}
