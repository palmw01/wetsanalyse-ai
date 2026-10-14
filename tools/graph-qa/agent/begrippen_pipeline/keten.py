"""De begrippenketen als één functie (ADR-004), naar het voorbeeld van `jas_pipeline/keten.py`.

    manifest → taal → signalen (definities, verwijzingen, patronen, kop) → kandidaten
             → beslistabel → groepen / relaties / vragen (met uitleg)

Zuiver: geen LangGraph, geen graafverkeer, geen model. Dezelfde invoer levert dezelfde uitkomst;
de fasenduur staat in `meting` en hoort niet bij wat vergeleken wordt. `melding(fase,
samenvatting, ms)` meldt de voortgang, zoals bij de annotatieketen.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import besluit as besluit_mod, definities, groeperen, patronen, signalen, taal as taal_mod
from .model import (
    Aandacht, Besluit, Beslissing, Betekenisgroep, Kandidaat, Manifest, Relatie, Taalanalyse, Vraag,
)
from ..jas_pipeline.taal.provider import TaalProvider, maak_provider

Melding = Callable[[str, str, int], None]


@dataclass(frozen=True)
class Uitkomst:
    groepen: tuple[Betekenisgroep, ...]
    relaties: tuple[Relatie, ...]
    vragen: tuple[Vraag, ...]
    kandidaten: tuple[Kandidaat, ...]
    beslissingen: tuple[Beslissing, ...]
    taal: tuple[Taalanalyse, ...]
    meting: dict[str, Any] = field(default_factory=dict, compare=False)


def _kandidaten(sigs: list[signalen.Signaal]) -> list[Kandidaat]:
    """Eén kandidaat per (hypothese, van, naar), met al het bewijs in volgorde van waarneming."""
    per: dict[str, Kandidaat] = {}
    for s in sigs:
        k = Kandidaat.maak(s.hypothese, s.van, s.naar, [s.bewijs])
        per[k.id] = per[k.id].met_bewijs([s.bewijs]) if k.id in per else k
    return sorted(per.values(), key=lambda k: (k.hypothese.value, k.van, k.naar))


def analyseer(manifest: Manifest, provider: TaalProvider | None = None,
              melding: Melding | None = None) -> Uitkomst:
    provider = provider or maak_provider("spacy")
    meld = melding or (lambda fase, samenvatting, ms: None)
    fasen: list[dict[str, Any]] = []

    def fase(naam: str, start: float, samenvatting: str) -> None:
        ms = int((time.perf_counter() - start) * 1000)
        fasen.append({"fase": naam, "ms": ms, "samenvatting": samenvatting})
        meld(naam, samenvatting, ms)

    t = time.perf_counter()
    taal = taal_mod.analyseer(manifest, provider)
    gedegradeerd = sum(x.gedegradeerd for x in taal.values())
    fase("Taalanalyse", t, f"{len(taal)} formuleringen" + (f", {gedegradeerd} zonder parse" if gedegradeerd else ""))

    t = time.perf_counter()
    wts = definities.wettelijke_termen(manifest, taal)
    sigs = [*signalen.zelfde_term(manifest, taal), *signalen.uit_definities(manifest, taal, wts),
            *signalen.afwijkende_kwalificatie(manifest, taal, wts), *signalen.uit_verwijzingen(manifest, taal),
            *patronen.toepassen(manifest, taal, wts), *patronen.kopsignalen(manifest, taal)]
    kandidaten = _kandidaten(sigs)
    fase("Signalen", t, f"{len(wts)} wettelijke termen, {len(sigs)} signalen, {len(kandidaten)} kandidaten")

    t = time.perf_counter()
    beslissingen = besluit_mod.beslis_alle(kandidaten)
    groepen, relaties, vragen = groeperen.groepeer(
        [f.element_id for f in manifest.formuleringen], kandidaten, beslissingen)
    geel = sum(x.aandacht is Aandacht.GEEL for x in (*groepen, *relaties)) + len(vragen)
    fase("Groeperen", t, f"{len(groepen)} groepen, {len(relaties)} relaties, {len(vragen)} vragen, {geel} geel")

    per_besluit = {b.value: sum(x.besluit is b for x in beslissingen.values()) for b in Besluit}
    return Uitkomst(
        groepen=tuple(groepen), relaties=tuple(relaties), vragen=tuple(vragen),
        kandidaten=tuple(kandidaten),
        beslissingen=tuple(beslissingen[k.id] for k in kandidaten),
        taal=tuple(taal[f.element_id] for f in manifest.formuleringen),
        meting={"manifest_id": manifest.id, "pijplijn": "begrippen_v1",
                "versies": {"taal": taal_mod.VERSIE, "definities": definities.VERSIE,
                            "signalen": signalen.VERSIE, "patronen": patronen.VERSIE,
                            "besluit": besluit_mod.VERSIE, "groeperen": groeperen.VERSIE},
                "taalmodel": getattr(provider, "model", ""), "gedegradeerd": gedegradeerd,
                "besluiten": per_besluit, "fasen": fasen})
