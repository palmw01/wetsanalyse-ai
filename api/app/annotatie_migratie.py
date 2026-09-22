"""Per-gebruiker-documenten samenvoegen tot de gedeelde laag per artikel.

Vóór de lagen maakte elke Lex-beurt een nieuw document, per gebruiker. Voor één artikel liggen er dus
vaak meerdere, met overlappende markeringen en soms tegenstrijdige oordelen. Deze module legt vast hoe
die samengaan; `plan_samenvoeging` is **puur** (geen database), zodat de dry-run precies laat zien wat
de echte run gaat doen en de regels los te testen zijn.

De regels, in volgorde van belang:

1. **Het oordeel van een jurist gaat voor.** Een element met een beslissing of van de jurist zelf wint
   van een onbeoordeeld voorstel met dezelfde tekst in hetzelfde lid.
2. **Twee oordelen: het laatste telt**, op het tijdstip van de laatste beslissing. Het andere
   verdwijnt niet stil maar gaat volledig mee in de audit (`migratie-conflict`) – twee juristen die
   het oneens waren is informatie.
3. **Twee onbeoordeelde voorstellen: het meest recente document wint.** Heeft het andere een andere
   klasse, dan komt die als alternatief mee: dat is dezelfde regel als in de merge ("andere klasse →
   alternatief"), en het is precies de twijfel die de jurist moet zien.

Ontdubbelen gebeurt op `_sleutel` (genormaliseerde tekst + lid), dezelfde regel als de merge en als
graph-qa's `sleutel_van`. Een botsend element-id wordt hernummerd; de mapping staat in de audit, zodat
oude auditregels terug te leiden blijven.

Het meest recente document **wordt** de laag (zijn slug blijft), tenzij er al een laag voor dat artikel
bestaat. De rest krijgt `samengevoegd_in`. Idempotent: een tweede run vindt niets meer te doen.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .annotatie_contracts import (
    AgentRun, Alternatief, AnnotatieDocument, AnnotatieElement, DocumentStatus,
)
from .annotatie_store import laag_sleutel
from .routers.annotatie import _sleutel

_OUDST = datetime.min.replace(tzinfo=timezone.utc)


@dataclass
class LaagPlan:
    sleutel: str
    doel_slug: str
    doel_was_laag: bool
    doel_updated: datetime | None            # de stand van het doel waarop dit plan rekende
    bronnen: list[str]                       # slugs die in de laag opgaan (zonder het doel)
    elementen: list[AnnotatieElement]
    runs: list[AgentRun]
    status: DocumentStatus
    elementen_voor: int                      # som over alle betrokken documenten
    id_hernoemd: dict[str, dict[str, str]] = field(default_factory=dict)   # {bron: {oud: nieuw}}
    conflicten: list[dict] = field(default_factory=list)
    dubbel: int = 0                          # onbeoordeelde dubbelen die opgingen in een ander

    def rapport(self) -> dict:
        return {
            "sleutel": self.sleutel, "doel_slug": self.doel_slug, "doel_was_laag": self.doel_was_laag,
            "bronnen": self.bronnen, "elementen_voor": self.elementen_voor,
            "elementen_na": len(self.elementen), "dubbel": self.dubbel,
            "conflicten": len(self.conflicten), "id_hernoemd": self.id_hernoemd,
            "status": self.status.value,
        }


def _beoordeeld(el: AnnotatieElement) -> bool:
    return el.herkomst == "mens" or bool(el.beslissingen)


def _oordeel_tijd(el: AnnotatieElement, doc: AnnotatieDocument) -> datetime:
    """Wanneer de jurist zich over dit element uitsprak. Een eigen markering zonder beslissingen is
    gemaakt, niet beslist: dan telt het moment dat het document voor het laatst veranderde."""
    if el.beslissingen:
        return max(b.tijd for b in el.beslissingen)
    return doc.updated or _OUDST


def _voeg_alternatief_toe(winnaar: AnnotatieElement, klasse: str) -> None:
    # Een eigen markering van de jurist is geen voorstel met twijfel; daar hoort geen alternatief bij.
    if (winnaar.herkomst == "agent" and klasse != winnaar.klasse
            and all(a.klasse != klasse for a in winnaar.alternatieven)):
        winnaar.alternatieven = [*winnaar.alternatieven,
                                 Alternatief(klasse=klasse, motivatie="uit een samengevoegde annotatie")]


def _plan_groep(docs: list[AnnotatieDocument], laag: AnnotatieDocument | None, sleutel: str) -> LaagPlan:
    recent_eerst = sorted(docs, key=lambda d: d.updated or _OUDST, reverse=True)
    doel = laag or recent_eerst[0]
    volgorde = [doel, *(d for d in recent_eerst if d.slug != doel.slug)]

    plan = LaagPlan(
        sleutel=sleutel, doel_slug=doel.slug, doel_was_laag=laag is not None,
        doel_updated=doel.updated,
        bronnen=[d.slug for d in volgorde[1:]], elementen=[], runs=[],
        status=DocumentStatus.in_review,
        elementen_voor=sum(len(d.elementen) for d in volgorde),
    )
    # Per sleutel het element dat nu in de laag staat, en uit welk document het kwam.
    in_laag: dict[tuple[str, str], tuple[AnnotatieElement, AnnotatieDocument]] = {}
    ids: set[str] = set()

    for doc in volgorde:
        for bron_el in doc.elementen:
            el = bron_el.model_copy(deep=True)
            if el.verouderd:
                # Historie gaat mee zoals hij is; die doet nergens aan ontdubbelen mee.
                plan.elementen.append(_met_uniek_id(el, doc, ids, plan))
                continue
            k = _sleutel(el.tekst, el.lid)
            if k not in in_laag:
                el = _met_uniek_id(el, doc, ids, plan)
                plan.elementen.append(el)
                in_laag[k] = (el, doc)
                continue

            huidig, huidig_doc = in_laag[k]
            nieuw_wint = False
            if _beoordeeld(el) and _beoordeeld(huidig):
                nieuw_wint = _oordeel_tijd(el, doc) > _oordeel_tijd(huidig, huidig_doc)
                verliezer, verliezer_doc = (huidig, huidig_doc) if nieuw_wint else (el, doc)
                plan.conflicten.append({
                    "sleutel": {"tekst": k[0], "lid": k[1]},
                    "winnaar_uit": doc.slug if nieuw_wint else huidig_doc.slug,
                    "verliezer_uit": verliezer_doc.slug,
                    "verliezer": verliezer.model_dump(mode="json"),
                })
            elif _beoordeeld(el):
                nieuw_wint = True
            else:
                plan.dubbel += 1

            if nieuw_wint:
                el = _met_uniek_id(el, doc, ids, plan)
                _voeg_alternatief_toe(el, huidig.klasse)
                plek = next(i for i, x in enumerate(plan.elementen) if x is huidig)
                plan.elementen[plek] = el
                in_laag[k] = (el, doc)
            else:
                _voeg_alternatief_toe(huidig, el.klasse)

        plan.runs.extend(doc.runs)

    plan.runs.sort(key=lambda r: r.tijd)
    # Afgerond alleen als álles afgerond was: één document in review betekent dat iemand nog bezig
    # was, en een samengevoegde laag bevat dat werk.
    if all(d.status is not DocumentStatus.in_review for d in volgorde):
        plan.status = DocumentStatus.geaccordeerd
    return plan


def _met_uniek_id(el: AnnotatieElement, doc: AnnotatieDocument, ids: set[str], plan: LaagPlan) -> AnnotatieElement:
    if el.id in ids:
        nieuw = uuid.uuid4().hex[:12]
        plan.id_hernoemd.setdefault(doc.slug, {})[el.id] = nieuw
        el.id = nieuw
    ids.add(el.id)
    return el


def plan_samenvoeging(
    docs: list[AnnotatieDocument], lagen: dict[str, AnnotatieDocument],
) -> list[LaagPlan]:
    """Het samenvoegplan voor alle nog niet gemigreerde documenten.

    `docs` zijn de per-gebruiker-documenten zonder `samengevoegd_in`; `lagen` de bestaande lagen per
    sleutel. Een document met een lid komt in de laag van zijn artikel: de laaggrens is het artikel,
    het lid is een focus.
    """
    groepen: dict[str, list[AnnotatieDocument]] = {}
    for d in docs:
        if d.laag_sleutel or d.samengevoegd_in or not d.bwbId or not d.artikel:
            continue
        groepen.setdefault(laag_sleutel(d.bwbId, d.artikel), []).append(d)
    return [_plan_groep(groep, lagen.get(sleutel), sleutel) for sleutel, groep in sorted(groepen.items())]
