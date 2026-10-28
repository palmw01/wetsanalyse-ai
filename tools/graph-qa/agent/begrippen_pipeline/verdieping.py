"""De model-laag op de uitkomst van de keten (spoor D, fase C).

De deterministische uitkomst (`keten.Uitkomst`) blijft wat ze is. Deze module legt er de oordelen van
het model op (`classificatie.py`) en groepeert opnieuw – met dezelfde `groeperen.groepeer`, dus met
dezelfde conflictcontrole:

- alleen een *possible link* van de familie zelfde betekenis kan door het model veranderen; een link
  of non-link van de beslistabel nooit;
- ook niet als de wet het paar al als relatie noemt (`Z-RELATIE-GAAT-VOOR`): zo'n paar gaat niet
  eens naar het model (`te_vergelijken`);
- `zelfde_betekenis` → link door het model: een gele groep, die de jurist ziet en kan splitsen;
- `verwant_ander_begrip`, `betekenisverschil` en `onbeslist` → de vraag **blijft**, met het oordeel
  erbij als advies. Een scheiding door het model zou de vraag laten verdwijnen; een foute scheiding
  is dan onzichtbaar, een foute samenvoeging niet. Gemeten: op de AWR-set scheidde het model in 2 van
  3 runs een paar dat volgens de set hetzelfde begrip is.

Zuiver: dezelfde uitkomst en dezelfde oordelen geven dezelfde groepen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import besluit as besluit_mod, classificatie, definities, groeperen, kaart as kaart_mod
from .keten import Uitkomst
from .model import (
    Aandacht, Besluit, Beslissing, Betekenisgroep, Hypothese, Kaart, Manifest, ModelOordeel, Onderzoek, Oordeel, Relatie,
    Vraag, _hash,
)

VERSIE = "1"

_NAAR_BESLUIT = {Oordeel.ZELFDE_BETEKENIS: (Besluit.LINK, "M-ZELFDE")}


@dataclass(frozen=True)
class Hergroepering:
    groepen: tuple[Betekenisgroep, ...]
    relaties: tuple[Relatie, ...]
    vragen: tuple[Vraag, ...]                  # wat na het model nog open is (met advies in `oordelen`)
    oordelen: tuple[ModelOordeel, ...]         # alle oordelen, ook onbeslist en ongeldig


def te_vergelijken(uitkomst: Uitkomst) -> list[Vraag]:
    """De vragen die naar het model mogen."""
    return [v for v in uitkomst.vragen if v.regel != besluit_mod.RELATIE_GAAT_VOOR.id]


def hergroepeer(manifest: Manifest, uitkomst: Uitkomst, oordelen: list[ModelOordeel]) -> Hergroepering:
    beslissingen = {b.kandidaat_id: b for b in uitkomst.beslissingen}
    kandidaten = {k.id: k for k in uitkomst.kandidaten}
    mag = {v.kandidaat_id for v in te_vergelijken(uitkomst)}
    for o in sorted(oordelen, key=lambda o: o.kandidaat_id):
        k, oud = kandidaten.get(o.kandidaat_id), beslissingen.get(o.kandidaat_id)
        if o.kandidaat_id not in mag or k is None or oud is None or o.oordeel not in _NAAR_BESLUIT:
            continue
        if k.hypothese is not Hypothese.ZELFDE_BETEKENIS or oud.besluit is not Besluit.POSSIBLE_LINK:
            continue
        besluit, regel = _NAAR_BESLUIT[o.oordeel]
        beslissingen[o.kandidaat_id] = Beslissing(
            kandidaat_id=o.kandidaat_id, besluit=besluit, door="model", regel=regel,
            reden=f"Lex: {o.motivatie}" if o.motivatie else "oordeel van Lex")
    groepen, relaties, vragen = groeperen.groepeer(
        [f.element_id for f in manifest.formuleringen], list(uitkomst.kandidaten), beslissingen)
    return Hergroepering(tuple(groepen), tuple(relaties), tuple(vragen),
                         tuple(sorted(oordelen, key=lambda o: o.kandidaat_id)))


def batch_id(soort: str, ids: list[str], promptversie: str, model: str, onderzoek_id: str = "") -> str:
    """Inhoudelijk: dezelfde batch op dezelfde invoer met hetzelfde model en dezelfde prompt draait één keer.
    Daarmee is een herstart hervatbaar én reproduceerbaar, ondanks het model. Met een onderzoek (spoor M)
    telt de onderzoeksstand mee: dezelfde groepen met andere context zijn een andere batch. Zonder
    onderzoek blijft het id zoals het was."""
    return "B" + _hash(soort, promptversie, model, *sorted(ids), *([onderzoek_id] if onderzoek_id else []))[:16]


def kaartopdrachten(manifest: Manifest, uitkomst: Uitkomst, groepen: tuple[Betekenisgroep, ...],
                    onderzoek: Onderzoek | None = None) -> tuple[dict[str, Kaart], list[kaart_mod.Opdracht]]:
    """Per groep de kaart zonder model, en de opdrachten voor wat open is (met de context van het
    onderzoek, als de run er een heeft)."""
    taal = {t.element_id: t for t in uitkomst.taal}
    wts = definities.wettelijke_termen(manifest, taal)
    kaarten, opdrachten = {}, []
    for g in groepen:
        k, o = kaart_mod.basis(manifest, taal, wts, g.id, g.leden, g.aandacht is Aandacht.GEEL, onderzoek)
        kaarten[g.id] = k
        if o is not None:
            opdrachten.append(o)
    return kaarten, opdrachten


@dataclass(frozen=True)
class Verdieping:
    hergroepering: Hergroepering
    kaarten: dict[str, Kaart]
    meting: dict[str, Any] = field(default_factory=dict, compare=False)


def verdiep(manifest: Manifest, uitkomst: Uitkomst, llm: Any, model: str,
            onderzoek: Onderzoek | None = None) -> Verdieping:
    """Alles in één keer, zonder bewaren tussendoor – voor de eval. De run in graph-qa doet hetzelfde per
    batch (`batch_id`), zodat hij kan hervatten."""
    meting: dict[str, int] = {}
    oordelen = [o for b in classificatie.batches(te_vergelijken(uitkomst))
                for o in classificatie.vergelijk(llm, model, manifest, b, meting)]
    her = hergroepeer(manifest, uitkomst, oordelen)
    kaarten, opdrachten = kaartopdrachten(manifest, uitkomst, her.groepen, onderzoek)
    geel = {g.id: g.aandacht is Aandacht.GEEL for g in her.groepen}
    for b in kaart_mod.batches(opdrachten):
        for k in kaart_mod.vul(llm, model, manifest, b, geel, meting):
            kaarten[k.groep_id] = k
    return Verdieping(her, kaarten, {"llm_calls": meting.get("llm_calls", 0),
                                     "promptversie": {"vraag": classificatie.promptversie(),
                                                      "kaart": kaart_mod.promptversie()}})
