"""Wat elke leestool van een bronconnector deelt over de tekst van een stuk (ADR-013): de inhoud met offsets voor de
eerste pagina. Eén plek, zodat een tweede connector haar niet kopieert en het bronvenster overal dezelfde inhoud ziet."""
from __future__ import annotations

import json
from typing import Any

from ..resultaat import BUDGET

#: Zo veel koppen staan hoogstens in `inhoud` op de eerste pagina; meer en alleen de bovenste twee niveaus.
MAX_INHOUD = 40


def inhoud(rijen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """De koppen van het stuk met de offset waar ze beginnen, voor de eerste pagina, en of dat alle koppen zijn. Zo springt
    Lex naar het deel dat de vraag raakt in plaats van het stuk pagina voor pagina te lezen (acceptatie 8 nov 2026: twee
    pagina's gelezen, de artikelsgewijze toelichting niet). Het diepste niveau dat helemaal past (hoogstens `MAX_INHOUD`
    koppen en een kwart van de begroting: de inhoud wijst de weg, de alinea's zijn de inhoud); past zelfs het bovenste
    niveau niet, dan het begin ervan, en dat zegt het resultaat (`inhoud_ingekort`). Leeg bij één kop."""
    def koppen(diepte: int | None) -> list[dict[str, Any]]:
        uit: list[dict[str, Any]] = []
        for i, r in enumerate(rijen):
            delen = r.get("kop", "").split(" › ")
            kop = " › ".join(delen[:diepte] if diepte else delen)
            if kop and all(u["kop"] != kop for u in uit):
                uit.append({"kop": kop, "offset": i})
        return uit

    def past(lijst: list[dict[str, Any]]) -> bool:
        return len(lijst) <= MAX_INHOUD and len(json.dumps(lijst, ensure_ascii=False)) <= BUDGET // 4

    for diepte in (None, 2, 1):
        if past(lijst := koppen(diepte)):
            return (lijst, True) if len(lijst) > 1 else ([], True)
    lijst = koppen(1)
    while lijst and not past(lijst):
        lijst = lijst[:-1]
    return lijst, False
