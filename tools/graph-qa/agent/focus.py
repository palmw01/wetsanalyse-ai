"""Waar het gesprek over gaat: de focus, als expliciete toestand naast de berichten.

De checkpointer bewaart de berichten wél, maar daaruit moest elke volgende beurt zelf raden waar
"dat", "die markering" of "lid 2" naar verwijst. De supervisor zag de historie bovendien helemaal
niet, en na een annotatie stond er in de historie één regel zonder regeling, bronnode of element-id.
Een vervolgvraag op een markering kon zo nergens heen.

De focus is klein en gestructureerd, en wordt door de beurt zelf bijgewerkt: na een annotatie de
bepaling met haar markeringen, na een antwoord de geraadpleegde bronnen, bij een adviesvraag het
aangewezen element. `als_context` maakt er het GESPREKSCONTEXT-blok van dat de supervisor én elke
specialist meekrijgen.

**De focus is context, geen filter.** Ze stuurt nooit zelf een zoekopdracht of een doel: "welke
rechtssubjecten ken je nog meer uit andere annotaties" gaat juist over iets anders dan de focus.
Het model leest haar om een verwijzing op te lossen; wat het daarna ophaalt, haalt het zelf op.
"""
from __future__ import annotations

from typing import Any

from .agent_common import truncate
from .tools.annotatie_tools import vindplaats_label

MAX_ELEMENTEN = 30
MAX_BRONNEN = 6


def _element(e: dict[str, Any]) -> dict[str, str]:
    uit = {k: str(e.get(k) or "") for k in ("id", "klasse", "tekst")}
    uit["tekst"] = truncate(uit["tekst"], 160)
    if e.get("aandacht"):
        uit["aandacht"] = str(e["aandacht"])
    return {k: v for k, v in uit.items() if v}


def na_annotatie(snapshot: dict[str, Any], plek: str, citeertitel: str,
                 elementen: list[dict[str, Any]], *, hergebruikt: bool = False) -> dict[str, Any]:
    """Een nieuwe annotatie verschuift het onderwerp: de vorige focus vervalt."""
    doel = (snapshot or {}).get("doel") or {}
    bron_iri = str(doel.get("bron_iri") or "")
    return {
        "laatste_route": "annotatie",
        "bron_iri": bron_iri,
        "bwb_id": str(doel.get("bwb_id") or ""),
        "label": " ".join(x for x in (plek, citeertitel or doel.get("citeertitel") or "") if x),
        "elementen": [_element(e) for e in elementen[:MAX_ELEMENTEN] if isinstance(e, dict)],
        "aantal": len(elementen),
        "hergebruikt": hergebruikt,
    }


def na_antwoord(oud: dict[str, Any] | None, specialist: str, bronnen: list[str]) -> dict[str, Any]:
    """Een antwoord vóegt toe: de bepaling en markeringen van een eerdere annotatie blijven het
    onderwerp, want "en waarom die klasse?" na een uitleg gaat nog steeds daarover."""
    focus = dict(oud or {})
    focus["laatste_route"] = specialist or "antwoord"
    if bronnen:
        focus["bronnen"] = bronnen[:MAX_BRONNEN]
    return focus


def bij_advies(oud: dict[str, Any] | None, context: dict[str, Any] | None) -> dict[str, Any]:
    """De jurist wees één markering aan. Die blijft het onderwerp tot er een ander komt."""
    c = context or {}
    focus = dict(oud or {})
    focus["laatste_route"] = "advies"
    element = {"id": c.get("element_id"), "klasse": c.get("klasse"), "tekst": c.get("fragment")}
    element = {k: truncate(str(v), 160) for k, v in element.items() if v}
    if element:
        focus["element"] = element
    if c.get("bron_iri"):
        focus["bron_iri"] = str(c["bron_iri"])
        focus.setdefault("label", vindplaats_label(str(c["bron_iri"])))
    return focus


def als_context(focus: dict[str, Any] | None, gezien: list[str] | None,
                open_elementen: list[dict[str, Any]] | None = None) -> str:
    """Het GESPREKSCONTEXT-blok voor de systeemprompt; leeg als er nog niets is.

    `open_elementen` zijn de markeringen in de bepaling die de jurist nu open heeft
    (`context.bestaande_elementen`). Die stuurt de werkplek bij elke vraag mee; ze werden alleen bij
    een adviesvraag gelezen en bij een gewone vraag stil weggegooid."""
    f = focus or {}
    regels: list[str] = []
    if f.get("bron_iri"):
        wat = "Geannoteerd (hergebruikt uit de laag)" if f.get("hergebruikt") else "Onderwerp"
        regels.append(f"{wat}: {f.get('label') or vindplaats_label(f['bron_iri'])} – bronnode {f['bron_iri']}")
    if f.get("elementen"):
        meer = f" (eerste {len(f['elementen'])} van {f['aantal']})" if f.get("aantal", 0) > len(f["elementen"]) else ""
        regels.append(f"Markeringen daarin{meer}, als id · klasse · tekst:")
        regels += [f"- {e.get('id', '?')} · {e.get('klasse', '')} · \"{e.get('tekst', '')}\""
                   + (f" ({e['aandacht']})" if e.get("aandacht") else "") for e in f["elementen"]]
    if f.get("element"):
        e = f["element"]
        regels.append(f"Aangewezen markering: {e.get('id', '?')} · {e.get('klasse', '')} · \"{e.get('tekst', '')}\"")
    open_ = [_element(e) for e in (open_elementen or [])[:20] if isinstance(e, dict)]
    if open_:
        regels.append("Markeringen in de bepaling die de jurist nu open heeft:")
        regels += [f"- {e.get('klasse', '')} · \"{e.get('tekst', '')}\"" for e in open_ if e.get("tekst")]
    if f.get("laatste_route"):
        regels.append(f"Vorige beurt: {f['laatste_route']}")
    seen = list(dict.fromkeys(f.get("bronnen") or [])) + [u for u in dict.fromkeys(gezien or [])
                                                           if u not in (f.get("bronnen") or [])]
    if seen:
        regels.append("Eerder geraadpleegde bepalingen: " + ", ".join(seen[-12:]))
    if not regels:
        return ""
    return (
        "\n\nGESPREKSCONTEXT – waar dit gesprek tot nu toe over ging. Gebruik het om verwijzingen als "
        "'dat artikel', 'die markering' of 'lid 2' op te lossen; de details van een markering haal je "
        "op met get_annotatie(id). Feiten over de wettekst verifieer je via de tools.\n"
        + "\n".join(regels)
    )
