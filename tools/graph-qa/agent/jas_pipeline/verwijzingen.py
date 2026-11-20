"""De verwijzingen van een bepaling met hun doel, uit de graaf (M-1-1, voor de relatievoorstellen van ADR-011).

De keten herkent "In afwijking van het eerste lid" en "vindt het eerste lid toepassing" in de tekst, maar het doel van
de verwijzing staat in de graaf: de importer legde per bronnode `bwb:heeftVerwijzing` met het anker en `bwb:naar`. Die
lijst gaat mee naar `relaties.stel_voor`, die er een relatie `uitzondering_op` of `toepassing` naar een hele bepaling
van maakt. Zonder graaf of bij een fout een lege lijst: dan komen die relaties niet, de rest wel.
"""
from __future__ import annotations

import logging
from typing import Any

from ..bepaling_namen import rijen
from ..graph.queries import NS, PREFIXES

logger = logging.getLogger(__name__)

#: Hoeveel verwijzingen per beurt: een bepaling heeft er zelden meer dan tien.
MAX_VERWIJZINGEN = 200


def q_verwijzingen(bron_iris: list[str]) -> str:
    waarden = " ".join(f"<{i}>" for i in sorted(set(bron_iris)) if i.startswith(NS) and ">" not in i and " " not in i)
    return PREFIXES + f"""SELECT DISTINCT ?bron ?anker ?naar WHERE {{
  VALUES ?bron {{ {waarden} }}
  ?bron bwb:heeftVerwijzing ?v .
  ?v bwb:naar ?naar ; bwb:ankerTekst ?anker .
  FILTER(STRSTARTS(STR(?naar), "{NS}"))
}} ORDER BY ?bron ?anker LIMIT {MAX_VERWIJZINGEN}"""


def verwijzingen_van(graph: Any, bron_iris: list[str]) -> dict[str, list[dict[str, str]]]:
    """Per bronnode de verwijzingen als `{anker, naar}`; leeg zonder graaf of bronnodes."""
    if graph is None or not bron_iris:
        return {}
    try:
        gevonden = rijen(graph, q_verwijzingen(bron_iris))
    except Exception:  # noqa: BLE001 – geen graaf: geen relaties naar een bepaling, de annotatie gaat door
        logger.warning("verwijzingen: de graaf antwoordde niet", exc_info=True)
        return {}
    uit: dict[str, list[dict[str, str]]] = {}
    for r in gevonden:
        if r.get("anker") and r.get("naar"):
            uit.setdefault(r["bron"], []).append({"anker": r["anker"], "naar": r["naar"]})
    return uit
