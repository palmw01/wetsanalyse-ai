"""Wat de juristen met de voorstellen van de agent deden, over alle annotatielagen heen.

Elke keer dat een jurist zegt "nee, dit is een Rechtsfeit en geen Voorwaarde" is dat evaluatiedata
over de agent. Een beslissing draagt het type, de `review_reason`, de correctie (`wijziging`) en de
oude waarden (`voor`); elk agent-element draagt `geproduceerd_door` met het model en de agentversie.
Dit module telt dat op: de reviewuitkomst per klasse en per model, de klasse-verschuivingen die
juristen aanbrengen, en of het aandacht-oordeel van de keten samenvalt met een correctie.

**Lees de cijfers als tellingen.** Zolang er weinig gereviewd is, zeggen percentages weinig; `lagen`
en de uitkomsten staan er daarom altijd bij. Een klasse-verschuiving zegt iets over de agent én over
de methode: JAS kent interpretatieruimte, dus een verschuiving is niet per se een fout van het model.

Werkt op element-dicts zoals ze in `annotatie_v2_elementen.inhoud` en in de JSON-export staan, zodat
het admin-endpoint en `scripts/statistiek.py` dezelfde aggregatie delen.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from pydantic import BaseModel


class ReviewStatistiek(BaseModel):
    """Het rapport. Alle velden zijn tellingen; percentages laat ik aan de lezer."""

    lagen: int = 0
    elementen: int = 0

    #: Agent-voorstellen naar reviewuitkomst. Een element kan meerdere beslissingen dragen (edit dan
    #: comment); geteld wordt de zwaarste uitkomst, want "is dit voorstel geaccepteerd" is één vraag.
    goedgekeurd: int = 0
    aangepast: int = 0
    afgewezen: int = 0
    open: int = 0

    #: Een eigen markering van de jurist staat meteen op goedgekeurd en zou het beeld optillen zonder
    #: dat er iets beoordeeld is; die telt daarom apart.
    van_agent: int = 0
    van_jurist: int = 0

    per_klasse: dict[str, dict[str, int]] = {}
    per_review_reason: dict[str, int] = {}
    #: "Voorwaarde → Rechtsfeit": 7 – wat juristen feitelijk anders zien dan de agent.
    klasse_verschuivingen: dict[str, int] = {}
    #: Per "model · agentversie", zodat twee versies naast elkaar te leggen zijn.
    per_model: dict[str, dict[str, int]] = {}
    #: Per aandacht-niveau van de keten (groen/geel): hoeveel beoordeelde elementen, en hoeveel
    #: daarvan de jurist wijzigde of afwees.
    per_aandacht: dict[str, dict[str, int]] = {}


# Volgorde van zwaarte: een element dat is afgewezen én becommentarieerd telt als afgewezen.
_ZWAARTE = {"reject": 3, "edit": 2, "approve": 1}
_UITKOMST = {"reject": "afgewezen", "edit": "aangepast", "approve": "goedgekeurd"}


def _uitkomst(el: dict[str, Any]) -> str:
    """De reviewuitkomst van één element: afgewezen | aangepast | goedgekeurd | open."""
    zwaarste = max((b.get("type", "") for b in el.get("beslissingen") or []),
                   key=lambda t: _ZWAARTE.get(t, 0), default="")
    return _UITKOMST.get(zwaarste, "open")


def _bij(doel: dict[str, dict[str, int]], sleutel: str, uitkomst: str) -> None:
    vak = doel.setdefault(sleutel, {"totaal": 0, "goedgekeurd": 0, "aangepast": 0, "afgewezen": 0, "open": 0})
    vak["totaal"] += 1
    vak[uitkomst] += 1


def rapport(elementen: Iterable[dict[str, Any]], lagen: int = 0) -> ReviewStatistiek:
    """Tel de review-uitkomsten over een verzameling elementen. Verouderde elementen tellen niet mee:
    hun brontekst bestaat niet meer, dus hun oordeel gaat niet meer over de wet zoals die nu luidt."""
    st = ReviewStatistiek(lagen=lagen)
    redenen: Counter[str] = Counter()
    verschuivingen: Counter[str] = Counter()

    for el in elementen:
        if el.get("verouderd"):
            continue
        st.elementen += 1
        if el.get("herkomst") == "mens":
            st.van_jurist += 1
            continue
        st.van_agent += 1

        uitkomst = _uitkomst(el)
        setattr(st, uitkomst, getattr(st, uitkomst) + 1)
        _bij(st.per_klasse, el.get("klasse", ""), uitkomst)

        run = el.get("geproduceerd_door") or {}
        sleutel = " · ".join(x for x in (run.get("model"), run.get("agent_versie")) if x)
        _bij(st.per_model, sleutel or "onbekend", uitkomst)

        for b in el.get("beslissingen") or []:
            if b.get("review_reason"):
                redenen[b["review_reason"]] += 1
            voor, na = (b.get("voor") or {}).get("klasse"), (b.get("wijziging") or {}).get("klasse")
            if voor and na and voor != na:
                verschuivingen[f"{voor} → {na}"] += 1

        # Alleen elementen die de jurist ook echt bekeek tellen mee – bij `open` weten we het niet,
        # en dat als "niet gecorrigeerd" boeken zou het aandacht-oordeel kunstmatig goed laten lijken.
        if (aandacht := el.get("aandacht")) and uitkomst != "open":
            vak = st.per_aandacht.setdefault(aandacht, {"beoordeeld": 0, "gecorrigeerd": 0})
            vak["beoordeeld"] += 1
            if uitkomst in ("aangepast", "afgewezen"):
                vak["gecorrigeerd"] += 1

    st.per_review_reason = dict(redenen.most_common())
    st.klasse_verschuivingen = dict(verschuivingen.most_common())
    return st
