"""De begrippenrun: de keten van ADR-004 op het manifest van een werkgebied (spoor D, levering 3a).

De api bouwt en bewaart het manifest (`api/app/begrip_manifest.py`); deze run haalt het op, draait
`begrippen_pipeline.keten.analyseer` en zet de uitkomst terug. Geen model, dus geen tokens en geen
budgetpoort: de keten is deterministisch, en dezelfde invoer geeft dezelfde groep-id's. Een herstart
op hetzelfde manifest schrijft daarom idempotent.

Wat de keten zelf niet levert, zet deze run er per groep bij als **voorstel**: een naam (de term die
de leden het vaakst dragen) en, als een lid de term van een begripsbepaling is, de letterlijke
definitie uit die bron. Een samengestelde of geformuleerde definitie is L3b (model).

Events in dezelfde vorm als een beurt: `status` per fase, dan `opgeslagen` en `done`; bij een fout
een `error` (en de api hoort het via `…/mislukt`).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .begrippen_pipeline import definities
from .begrippen_pipeline.kaart import naam_en_letterlijk
from .begrippen_pipeline.keten import Uitkomst, analyseer
from .begrippen_pipeline.model import Bron, Formulering, Manifest
from .jas_pipeline.taal.provider import TaalProvider
from .config import Settings
from .runstore import Run
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger(__name__)


def manifest_uit(data: dict[str, Any]) -> Manifest:
    return Manifest(bronnen=tuple(Bron(**b) for b in data["bronnen"]),
                    formuleringen=tuple(Formulering(**f) for f in data["formuleringen"]))


def voorstel(manifest: Manifest, uitkomst: Uitkomst, leden: tuple[str, ...]) -> dict[str, str]:
    """Naam en (als die er letterlijk is) definitie bij een groep."""
    taal = {t.element_id: t for t in uitkomst.taal}
    return naam_en_letterlijk(manifest, taal, definities.wettelijke_termen(manifest, taal), leden)


def naar_uitkomst(manifest: Manifest, uitkomst: Uitkomst) -> dict[str, Any]:
    """De uitkomst in de vorm van het api-contract (`api/app/begrippen_run_contracts.py`)."""
    return {
        "manifest_id": manifest.id,
        "groepen": [{"id": g.id, "leden": list(g.leden), "aandacht": g.aandacht.value, "uitleg": list(g.uitleg),
                     "conflicten": list(g.conflicten), "voorstel": voorstel(manifest, uitkomst, g.leden)}
                    for g in uitkomst.groepen],
        "relaties": [{"kandidaat_id": r.kandidaat_id, "hypothese": r.hypothese.value, "van": r.van, "naar": r.naar,
                      "aandacht": r.aandacht.value, "uitleg": list(r.uitleg)} for r in uitkomst.relaties],
        "vragen": [{"kandidaat_id": v.kandidaat_id, "van": v.van, "naar": v.naar, "regel": v.regel,
                    "uitleg": list(v.uitleg)} for v in uitkomst.vragen],
        "meting": uitkomst.meting,
    }


def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


async def begrippen_stroom(werkgebied_id: str, api_run_id: str, run: Run, *, settings: Settings,
                           user_id: str, provider: TaalProvider | None = None) -> AsyncIterator[dict[str, Any]]:
    api = WetsanalyseApi(settings, user_id)
    try:
        try:
            data = await api.haal_begrippen_run(werkgebied_id, api_run_id)
            await api.meld_begrippen_loopt(werkgebied_id, api_run_id)
            manifest = manifest_uit(data["manifest"])
        except WetsanalyseApiFout as fout:
            yield {"type": "error", "message": "De voorstellen konden niet beginnen: de run is niet op te halen.",
                   "soort": "api", "status": fout.status}
            return
        except ValueError as fout:                    # het manifest klopt niet met het model van de keten
            await _mislukt(api, werkgebied_id, api_run_id, f"Ongeldig manifest: {fout}")
            yield {"type": "error", "message": "Het manifest van dit werkgebied is ongeldig voor de keten.",
                   "soort": "manifest"}
            return

        yield _status(f"{len(manifest.formuleringen)} passages uit {len(manifest.bronnen)} bepalingen")
        if run.stop_gevraagd:
            await _mislukt(api, werkgebied_id, api_run_id, "Gestopt op verzoek.")
            yield {"type": "done"}
            return

        # De keten is synchroon (spaCy); in een thread, met de fasen als events zodra ze er zijn.
        lus = asyncio.get_running_loop()
        wachtrij: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def melding(fase: str, samenvatting: str, ms: int) -> None:
            lus.call_soon_threadsafe(wachtrij.put_nowait, _status(f"{fase}: {samenvatting} ({ms} ms)"))

        taak = asyncio.ensure_future(asyncio.to_thread(analyseer, manifest, provider, melding))
        while not taak.done() or not wachtrij.empty():
            try:
                yield await asyncio.wait_for(wachtrij.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
        try:
            uitkomst = taak.result()
        except Exception as fout:  # noqa: BLE001 – elke fout van de keten is een mislukte run, geen crash
            logger.exception("begrippenketen mislukt", extra={"categorie": "technisch", "run_id": run.run_id})
            await _mislukt(api, werkgebied_id, api_run_id, f"De keten faalde: {type(fout).__name__}")
            yield {"type": "error", "message": "De begrippenketen liep vast; de voorstellen zijn niet gemaakt.",
                   "soort": "keten"}
            return

        if run.stop_gevraagd:
            await _mislukt(api, werkgebied_id, api_run_id, "Gestopt op verzoek.")
            yield {"type": "done"}
            return
        try:
            await api.zet_begrippen_uitkomst(werkgebied_id, api_run_id, naar_uitkomst(manifest, uitkomst))
        except WetsanalyseApiFout as fout:
            await _mislukt(api, werkgebied_id, api_run_id, f"Opslaan geweigerd ({fout.status}): {fout.reden}")
            yield {"type": "error", "message": "De voorstellen zijn gemaakt, maar de api weigerde ze op te slaan.",
                   "soort": "api", "status": fout.status}
            return
        yield {"type": "opgeslagen", "begrippen_run": api_run_id, "groepen": len(uitkomst.groepen),
               "relaties": len(uitkomst.relaties), "vragen": len(uitkomst.vragen)}
        yield {"type": "done"}
    finally:
        await api.aclose()


async def _mislukt(api: WetsanalyseApi, werkgebied_id: str, run_id: str, reden: str) -> None:
    """Best-effort: lukt ook dit niet, dan ziet de api de run na `VERLOPEN` als vastgelopen."""
    try:
        await api.meld_begrippen_mislukt(werkgebied_id, run_id, reden)
    except Exception:  # noqa: BLE001
        logger.warning("mislukte begrippenrun niet gemeld", exc_info=True)
