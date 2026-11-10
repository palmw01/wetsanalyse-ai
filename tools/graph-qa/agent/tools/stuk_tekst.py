"""Wat elke leestool van een bronconnector deelt over de tekst van een stuk (ADR-013): de inhoud met offsets voor de
eerste pagina, de kop alleen waar hij verandert, en de pagina zelf (`tekstpagina`). Eén plek, zodat een tweede connector
haar niet kopieert en het bronvenster overal dezelfde vorm ziet."""
from __future__ import annotations

import json
from typing import Any, Sequence

from ..resultaat import BUDGET, per_eenheid

#: Zo veel koppen staan hoogstens in `inhoud` op de eerste pagina; meer en alleen de bovenste twee niveaus.
MAX_INHOUD = 40

#: Velden die een rij alleen draagt als ze anders zijn dan op de rij ervoor op dezelfde pagina. De kop staat anders op
#: elke alinea van een sectie: bij ECLI:NL:HR:2022:50 ~900 van de ~8500 tekens, en dan past de uitspraak niet op één
#: pagina en haalt het model het vervolg op (derde meting 10 nov 2026: 72k tokens in plaats van 47k).
HERHAALD = ("kop",)


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


def _zonder_gaten(rijen: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """De velden uit `HERHAALD` die na hun eerste voorkomen op elke rij staan. Alleen die mogen wegvallen bij een
    herhaling: een rij zonder kop midden in het stuk zou bij het aanvullen anders de kop van de rij ervoor krijgen."""
    uit = []
    for veld in HERHAALD:
        gezien = False
        for r in rijen:
            if r.get(veld):
                gezien = True
            elif gezien:
                break
        else:
            uit.append(veld)
    return tuple(uit)


def aangevuld(data: dict[str, Any]) -> list[dict[str, Any]]:
    """De rijen van één pagina met elk veld dat de pagina bij een herhaling weglaat (`zonder_herhaling`) weer op elke
    rij: de lezer van een pagina (het blok `extern`) krijgt de kop van een passage ook als die alinea midden in een
    sectie staat."""
    rijen = [r for r in data.get("resultaten") or [] if isinstance(r, dict)]
    velden = [v for v in data.get("zonder_herhaling") or [] if isinstance(v, str)]
    uit: list[dict[str, Any]] = []
    vorige: dict[str, Any] = {}
    for r in rijen:
        r = dict(r)
        for veld in velden:
            if r.get(veld):
                vorige[veld] = r[veld]
            elif veld in vorige:
                r[veld] = vorige[veld]
        uit.append(r)
    return uit


def tekstpagina(rijen: list[dict[str, Any]], *, tool: str, args: dict[str, Any], offset: int, stuk: dict[str, Any],
                extra: dict[str, Any] | None = None, toelichting: str = "") -> str:
    """Een pagina van de tekst van een stuk, voor elke leestool dezelfde vorm.

    - De kop alleen waar hij verandert (`HERHAALD`); de eerste rij van een pagina draagt hem altijd.
    - Op de eerste pagina `inhoud`, behalve als het hele stuk zonder past en met niet: dan staan de koppen al in de rijen,
      en één pagina scheelt het model een ronde.
    - Een stuk zonder tekst zegt `leesbaar: false` in `stuk`, zoals een stuk dat de bron niet als tekst heeft."""
    if not rijen:
        stuk = {**stuk, "leesbaar": False}
    velden = _zonder_gaten(rijen)
    # De pagina zegt welke velden bij een herhaling wegvallen, zodat een lezer alleen dan aanvult (een tabelpagina doet
    # het niet: haar rijen hebben geen kop).
    basis = {"stuk": stuk, **(extra or {}), "totaal": len(rijen), **({"zonder_herhaling": list(velden)} if velden else {})}

    def maak(met: dict[str, Any]) -> str:
        return per_eenheid(rijen, tool=tool, args=args, offset=offset, extra=met, toelichting=toelichting,
                           zonder_herhaling=velden)

    if offset != 0:
        return maak(basis)
    inh, alle = inhoud(rijen)
    met = {**basis, **({"inhoud": inh} if inh else {}), **({} if alle else {"inhoud_ingekort": True})}
    tekst = maak(met)
    if inh and not json.loads(tekst).get("volledig"):
        zonder = maak(basis)
        if json.loads(zonder).get("volledig"):
            return zonder
    return tekst
