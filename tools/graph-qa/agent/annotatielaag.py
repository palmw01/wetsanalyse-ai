"""Hergebruik van de gedeelde annotatielaag: is dit artikel al geannoteerd, en welke leden niet meer?

De api projecteert elke laag naar een eigen named graph in de kennisgraaf (`urn:jas:graph:…`). Hier
lezen we die terug – read-only, via dezelfde MCP-client als de rest – om per lid te beslissen:

* **ongewijzigd** – de laag kent dit lid met dezelfde hash als de tekst die we net ophaalden. Dan is
  opnieuw annoteren weggegooid geld: de laatste stand staat er, met de oordelen van de juristen erbij.
* **gewijzigd of nieuw** – anders annoteert de keten het gewoon; de api veroudert dan de oude
  markeringen van dat lid.

**De graaf beslist, de api vangt.** Is de graaf achter (net na een GraphDB-herstart, vóór de
projectie terug is), dan ziet deze module geen laag en annoteert de keten opnieuw. Dat kost tokens,
maar geen reviewstatus: de api negeert voorstellen voor een lid waarvan hij de hash al kent
(`X-Hergebruikt-Leden`), en `beurt._leg_vast` logt dat als `hergebruik_gemist`.

Een mislukte leesactie telt als "geen laag" – nooit als reden om de annotatie te laten mislukken.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .graph import queries
from .graph.results import parse_select
from .ports import GraphPort

logger = logging.getLogger("graph_qa.annotatielaag")

#: Lifecycles waarin een jurist over de markering besliste.
_BEOORDEELD = {"human_approved", "edited"}


@dataclass
class Laagstand:
    slug: str
    status: str = ""
    bijgewerkt: str = ""
    leden: dict[str, str] = field(default_factory=dict)          # lid → hash
    markeringen: list[dict[str, str]] = field(default_factory=list)


def lees_laagstand(graph: GraphPort, bwb_id: str, aanduiding: str) -> Laagstand | None:
    """De laag van dit artikel zoals hij in de graaf staat, of None."""
    try:
        rijen = parse_select(graph.sparql(queries.laagstand(bwb_id, aanduiding)))
    except Exception:  # noqa: BLE001 – geen laag lezen is geen reden om niet te annoteren
        logger.warning("laagstand niet te lezen; er wordt geannoteerd",
                       extra={"bwb_id": bwb_id, "aanduiding": aanduiding}, exc_info=True)
        return None
    if not rijen or not rijen[0].get("slug"):
        return None
    eerste = rijen[0]
    stand = Laagstand(
        slug=str(eerste.get("slug", "")),
        status=str(eerste.get("status") or "").rsplit("status-", 1)[-1],
        bijgewerkt=str(eerste.get("bijgewerkt") or ""),
        leden={str(r.get("lid") or ""): str(r["hash"]) for r in rijen if r.get("hash")},
    )
    try:
        stand.markeringen = [
            {k: str(r.get(k) or "") for k in ("id", "klasse", "tekst", "lid", "lifecycle")}
            for r in parse_select(graph.sparql(queries.laag_markeringen(bwb_id, aanduiding)))
        ]
    except Exception:  # noqa: BLE001 – de samenvatting is bijzaak; de lidstand is gelezen
        logger.warning("markeringen van de laag niet te lezen",
                       extra={"bwb_id": bwb_id, "aanduiding": aanduiding}, exc_info=True)
    return stand


def deel_leden_in(
    lidstand: list[dict[str, str]], laag: Laagstand | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(ongewijzigd, te annoteren) – op basis van de hash per lid.

    Alleen een exact gelijke hash telt als ongewijzigd. Een lid dat de laag niet kent, of met een
    andere hash, wordt geannoteerd.
    """
    if laag is None:
        return [], list(lidstand)
    ongewijzigd = [ld for ld in lidstand if laag.leden.get(ld["lid"]) == ld["hash"]]
    rest = [ld for ld in lidstand if laag.leden.get(ld["lid"]) != ld["hash"]]
    return ongewijzigd, rest


def telling(markeringen: list[dict[str, str]]) -> dict[str, int]:
    """Hoeveel markeringen er liggen, en hoe ver de review is."""
    uit = {"markeringen": len(markeringen), "beoordeeld": 0, "afgewezen": 0, "te_beoordelen": 0}
    for m in markeringen:
        lc = m.get("lifecycle", "")
        if lc in _BEOORDEELD:
            uit["beoordeeld"] += 1
        elif lc == "rejected":
            uit["afgewezen"] += 1
        else:
            uit["te_beoordelen"] += 1
    return uit
