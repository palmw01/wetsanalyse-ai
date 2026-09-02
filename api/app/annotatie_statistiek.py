"""Wat de juristen met de voorstellen van de agent deden, over documenten heen.

**Waarom dit bestaat.** Elke keer dat een jurist zegt "nee, dit is een Rechtsfeit en geen Voorwaarde"
is dat evaluatiedata over de agent — en die data wordt al vastgelegd: `Beslissing` draagt het type,
de diff en de `review_reason` (die de server zélf uit de diff afleidt, `routers/annotatie._reden_uit_diff`,
dus hij is toetsbaar en niet aangenomen), en elk element draagt `geproduceerd_door` met het model en
de agentversie die het voorstel maakten. Er was alleen nooit een consument.

Dit is geen tweede telling naast `annotatie_export.tel_elementen`, maar een aanvulling erop. Die
functie is expliciet "één waarheid" voor de export én de werkvoorraadlijst; hij telt per klasse, per
status, per aandacht en agent-vs-jurist. Wat hier bij komt is wat je niet uit één document afleest:
de **reviewuitkomst per klasse**, de **verschuivingen** die juristen aanbrengen, en of de **Critic**
ergens goed voor is.

**Lees de cijfers als wat ze zijn.** Zolang er weinig gereviewd is, zijn dit tellingen en geen
percentages met betekenis; `documenten` en `beslist` staan er daarom altijd bij. En de
klasse-verschuivingen zeggen iets over de agent én over de methode: JAS kent interpretatieruimte, dus
een verschuiving is niet per se een fout van het model.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel

from .annotatie_contracts import AnnotatieDocument, AnnotatieElement, BeslissingType


class ReviewStatistiek(BaseModel):
    """Het rapport. Alle velden zijn tellingen; percentages laat ik aan de lezer."""

    documenten: int = 0
    elementen: int = 0

    #: Elementen waar een mens een oordeel over gaf, uitgesplitst naar wat dat oordeel was. Een
    #: element kan meerdere beslissingen dragen (edit dan comment); geteld wordt de zwaarste
    #: uitkomst, want "is dit voorstel geaccepteerd" is één vraag per element.
    goedgekeurd: int = 0
    aangepast: int = 0
    afgewezen: int = 0
    open: int = 0

    #: Alleen elementen die de AGENT voorstelde. Een eigen markering van de jurist staat meteen op
    #: goedgekeurd en zou het beeld optillen zonder dat er iets beoordeeld is.
    van_agent: int = 0
    van_jurist: int = 0

    per_klasse: dict[str, dict[str, int]] = {}
    per_review_reason: dict[str, int] = {}
    #: "Voorwaarde → Rechtsfeit": 7 – wat juristen feitelijk anders zien dan de agent.
    klasse_verschuivingen: dict[str, int] = {}
    #: Per "model · agentversie", zodat twee versies naast elkaar te leggen zijn.
    per_model: dict[str, dict[str, int]] = {}
    #: Viel het oordeel van de Critic samen met een correctie van de jurist? Per aandacht-niveau
    #: het aantal beoordeelde elementen en hoeveel daarvan de jurist wijzigde of afwees.
    critic: dict[str, dict[str, int]] = {}


# Volgorde van zwaarte: een element dat is afgewezen én becommentarieerd telt als afgewezen.
_ZWAARTE = {BeslissingType.reject: 3, BeslissingType.edit: 2, BeslissingType.approve: 1}


def _uitkomst(el: AnnotatieElement) -> str:
    """De reviewuitkomst van één element: afgewezen | aangepast | goedgekeurd | open."""
    zwaarste, score = "", 0
    for b in el.beslissingen:
        if (s := _ZWAARTE.get(b.type, 0)) > score:
            zwaarste, score = b.type.value, s
    return {"reject": "afgewezen", "edit": "aangepast", "approve": "goedgekeurd"}.get(zwaarste, "open")


def _bij(doel: dict[str, dict[str, int]], sleutel: str, uitkomst: str) -> None:
    vak = doel.setdefault(sleutel, {"totaal": 0, "goedgekeurd": 0, "aangepast": 0, "afgewezen": 0, "open": 0})
    vak["totaal"] += 1
    vak[uitkomst] += 1


def rapport(documenten: list[AnnotatieDocument]) -> ReviewStatistiek:
    """Tel de review-uitkomsten over een verzameling documenten."""
    st = ReviewStatistiek(documenten=len(documenten))
    redenen: Counter[str] = Counter()
    verschuivingen: Counter[str] = Counter()
    critic: dict[str, dict[str, int]] = {}

    for doc in documenten:
        for el in doc.elementen:
            st.elementen += 1
            if el.herkomst == "mens":
                st.van_jurist += 1
                # Een eigen markering staat bij het aanmaken al op human_approved: gemaakt, niet
                # beoordeeld. Meetellen als "goedgekeurd voorstel" zou het beeld vertekenen.
                continue
            st.van_agent += 1

            uitkomst = _uitkomst(el)
            setattr(st, uitkomst, getattr(st, uitkomst) + 1)
            _bij(st.per_klasse, el.klasse, uitkomst)

            run = el.geproduceerd_door
            sleutel = " · ".join(x for x in (run.model, run.agent_versie) if x) if run else "onbekend"
            _bij(st.per_model, sleutel or "onbekend", uitkomst)

            for b in el.beslissingen:
                if b.review_reason:
                    redenen[b.review_reason.value] += 1
                # De klasse die de jurist eroverheen zette. `wijziging` is de diff die de router
                # berekende, dus dit is wat er feitelijk veranderde – niet wat iemand claimde.
                klasse_diff = (b.wijziging or {}).get("klasse") or {}
                voor, na = klasse_diff.get("voor"), klasse_diff.get("na")
                if voor and na and voor != na:
                    verschuivingen[f"{voor} → {na}"] += 1

            # Had de Critic gelijk? Zijn laatste oordeel tegenover wat de jurist deed. Alleen
            # elementen die de jurist ook echt bekeek tellen mee – bij `open` weten we het niet, en
            # dat als "niet gecorrigeerd" boeken zou rood kunstmatig goed laten lijken.
            #
            # `critic_rondes` is het volledige spoor, maar het is pas sinds kort gevuld en de Critic
            # kan uit staan (`CRITIC_MAX_RONDES=0`). `aandacht` op het element draagt hetzelfde
            # laatste oordeel, dus dat is de terugval – anders valt deze doorsnede weg op precies de
            # documenten die er al zijn.
            laatste = el.critic_rondes[-1].aandacht if el.critic_rondes else el.aandacht
            if laatste and uitkomst != "open":
                vak = critic.setdefault(laatste.value,
                                        {"beoordeeld": 0, "gecorrigeerd": 0})
                vak["beoordeeld"] += 1
                if uitkomst in ("aangepast", "afgewezen"):
                    vak["gecorrigeerd"] += 1

    st.per_review_reason = dict(redenen.most_common())
    st.klasse_verschuivingen = dict(verschuivingen.most_common())
    st.critic = critic
    return st


def rapport_uit_export(export: dict[str, Any]) -> ReviewStatistiek:
    """Hetzelfde rapport, maar over één JSON-export in plaats van de database.

    De export draagt beslissingen, `geproduceerd_door` en `critic_rondes` al mee
    (`annotatie_export.bouw_export`), dus dit is de ingang die werkt zonder databasetoegang — en dat
    is vandaag de enige plek waar de data van een echte werkplek te vinden is.
    """
    meta = export.get("document") or {}
    doc = AnnotatieDocument(
        slug=meta.get("slug", ""),
        bwbId=meta.get("bwbId", ""),
        artikel=meta.get("artikel", ""),
        lid=meta.get("lid", "") or "",
        elementen=[AnnotatieElement.model_validate(_naar_element(e))
                   for e in (export.get("elementen") or [])],
    )
    return rapport([doc])


def _naar_element(e: dict[str, Any]) -> dict[str, Any]:
    """Een `ExportElement` terug naar de velden die `AnnotatieElement` verwacht.

    De export is platter: `aandacht` is daar een string in plaats van een enum-of-None, en
    `lifecycle` heet er `status` met een leesbaar label. Alleen wat het rapport gebruikt hoeft
    te kloppen; de rest laten we op de defaults staan.
    """
    uit = dict(e)
    uit.pop("status", None)
    if not uit.get("aandacht"):
        uit["aandacht"] = None
    return uit
