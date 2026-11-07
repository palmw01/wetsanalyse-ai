"""De bronnenrun: de ontdekmethoden op de selectie van een werkgebied (spoor D, fase A).

Eén ingang: `zoek_run`, de zoekfunctie van de bronselectie (spoor J, `nodes/bronselectie.py`). De run maken of
hergebruiken, dan `bronnen_stroom` – de invoer bij de api halen, de methoden toepassen (`bronnen_vinden.vind`) en
de kandidaten terugzetten, het patroon van `begrippen_run.py`. Wat er gevonden is, toont de bronselectie per
deelvraag; deze module zegt alleen of het zoeken lukte.

Geen model, dus geen tokens. Events: `status` per methode, dan `opgeslagen` en `done`; een fout is een
`error`, en de api hoort het via `…/mislukt`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .bronnen_vinden import vind
from .config import Settings
from .ports import GraphPort
from .agents import Context
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger(__name__)

WACHT_OP_ANDERE_RUN_S = 120.0
PEIL_S = 2.0

METHODE_NAAM = {"overzicht": "Overzicht op de analysevraag", "deelvraag": "Overzicht per deelvraag",
                "verwijzing_uit": "Verwijzingen vanuit de kern",
                "verwijzing_in": "Verwijzingen naar de kern", "definitie": "Definities van termen",
                "opbouw": "Opbouw van de wet", "gelijkenis": "Tekstuele gelijkenis"}

WEIGERING = {"geen_vertrekpunt": "Geef het werkgebied een analysevraag of neem eerst een bepaling op om te "
                                 "analyseren; daar zoek ik vanuit."}


def is_open(k: dict[str, Any]) -> bool:
    """Een open voorstel: voorgesteld, niet met de hand opgenomen, en gevonden door de laatste zoekopdracht
    (`vervallen` zet de api, `bronnen_run_store.vervallen`)."""
    return k.get("status") == "voorgesteld" and not k.get("in_selectie") and not k.get("vervallen")


def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


def _graaf(settings: Settings) -> GraphPort:
    from .adapters.graphdb_graph import make_graph
    return make_graph(settings)


async def bronnen_stroom(werkgebied_id: str, api_run_id: str, run: Any, *, settings: Settings, user_id: str,
                         graph: GraphPort | None = None, methoden: tuple[str, ...] | None = None
                         ) -> AsyncIterator[dict[str, Any]]:
    api = WetsanalyseApi(settings, user_id)
    eigen_graaf = graph is None
    try:
        try:
            data = await api.haal_bronnen_run(werkgebied_id, api_run_id)
            await api.meld_bronnen_loopt(werkgebied_id, api_run_id)
        except WetsanalyseApiFout as fout:
            yield {"type": "error", "message": "Het zoeken kon niet beginnen: de run is niet op te halen.",
                   "soort": "api", "status": fout.status}
            return
        invoer = data["invoer"]
        yield _status(f"Zoeken vanuit {len(invoer.get('kern', []))} bepalingen"
                      + (" en de analysevraag" if invoer.get("analysevraag") else ""))
        if run is not None and run.stop_gevraagd:
            await _mislukt(api, werkgebied_id, api_run_id, "Gestopt op verzoek.")
            yield {"type": "done"}
            return

        lus = asyncio.get_running_loop()
        wachtrij: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def melding(m: str, aantal: int, volledig: bool, ms: int) -> None:
            tekst = f"{METHODE_NAAM.get(m, m)}: {aantal}{'' if volledig else ' (onvolledig)'} ({ms} ms)"
            lus.call_soon_threadsafe(wachtrij.put_nowait, _status(tekst))

        def zoek() -> dict[str, Any]:
            g = graph or _graaf(settings)
            try:
                return vind(g, invoer, methoden, melding)
            finally:
                if eigen_graaf:
                    g.close()

        taak = asyncio.ensure_future(asyncio.to_thread(zoek))
        while not taak.done() or not wachtrij.empty():
            try:
                yield await asyncio.wait_for(wachtrij.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
        try:
            uitkomst = taak.result()
        except Exception as fout:  # noqa: BLE001 – een onbereikbare graaf is een mislukte run, geen crash
            logger.exception("bronnenrun mislukt", extra={"categorie": "technisch"})
            await _mislukt(api, werkgebied_id, api_run_id, f"Zoeken faalde: {type(fout).__name__}")
            yield {"type": "error", "message": "Het zoeken naar bepalingen liep vast; de graaf is mogelijk niet bereikbaar.",
                   "soort": "graaf"}
            return
        if run is not None and run.stop_gevraagd:
            await _mislukt(api, werkgebied_id, api_run_id, "Gestopt op verzoek.")
            yield {"type": "done"}
            return
        if uitkomst["meting"] and all(m.get("fout") for m in uitkomst["meting"].values()):
            # Geen enkele methode kon de graaf bevragen: dat is geen lege uitkomst maar een storing.
            await _mislukt(api, werkgebied_id, api_run_id, "Geen enkele methode kon de graaf bevragen.")
            yield {"type": "error", "message": "Het zoeken naar bepalingen liep vast; de graaf is mogelijk niet bereikbaar.",
                   "soort": "graaf"}
            return
        try:
            meting = {m: {k: v for k, v in x.items() if k != "fout"} for m, x in uitkomst["meting"].items()}
            await api.zet_bronnen_uitkomst(werkgebied_id, api_run_id,
                                           {"invoer_id": data["invoer_id"], **uitkomst, "meting": meting})
        except WetsanalyseApiFout as fout:
            await _mislukt(api, werkgebied_id, api_run_id, f"Opslaan geweigerd ({fout.status}): {fout.reden}")
            yield {"type": "error", "message": "De kandidaten zijn gevonden, maar de api weigerde ze op te slaan.",
                   "soort": "api", "status": fout.status}
            return
        yield {"type": "opgeslagen", "bronnen_run": api_run_id, "kandidaten": len(uitkomst["kandidaten"])}
        yield {"type": "done"}
    finally:
        await api.aclose()


async def _mislukt(api: WetsanalyseApi, werkgebied_id: str, run_id: str, reden: str) -> None:
    try:
        await api.meld_bronnen_mislukt(werkgebied_id, run_id, reden)
    except Exception:  # noqa: BLE001
        logger.warning("mislukte bronnenrun niet gemeld", exc_info=True)


def zoekmodules() -> tuple:
    """De modules die bepalen wat er gevonden wordt: de zoekstappen zelf, de queries (ook de fts) en het lezen van
    de rijen, de namen en plekken van een treffer, de aanwijzing in de vraag en de gedeelde taallijsten. Niet de
    toollaag of de taalprovider: die raken veel meer dan zoeken, en elke wijziging daar zou een nieuwe zoekronde
    starten."""
    from bronmodel import taal, vindplaats

    from . import (aanwijzing, bepaling_namen, bronnen_vinden, deelvraag_zoeken, overzicht, plekken, regelingnamen,
                   zoektermen, zoekvragen)
    from .graph import queries, results, structuur

    return (bronnen_vinden, deelvraag_zoeken, zoekvragen, zoektermen, queries, results, structuur, bepaling_namen,
            overzicht, plekken, regelingnamen, aanwijzing, taal, vindplaats)


def _zoekversie(lees=None) -> str:
    """De versie van de zoekcode: een hash van `zoekmodules()`. Gaat mee naar de api (`start_bronnen_run`), zodat
    nieuwe zoekcode tot een nieuwe zoekopdracht leidt, ook als het werkgebied gelijk bleef – anders bleef de uitkomst
    van de oude code staan, ook na *Verder onderzoeken* (Rekeningafspraken, 4 nov 2026). `lees` (pad → bytes) is er
    voor de test."""
    import hashlib
    from pathlib import Path

    lees = lees or Path.read_bytes
    h = hashlib.sha256()
    for module in zoekmodules():
        h.update(lees(Path(module.__file__)))
    return "z" + h.hexdigest()[:12]


ZOEKVERSIE = _zoekversie()


async def zoek_run(ctx: Context, werkgebied_id: str) -> str:
    """Bepalingen zoeken bij een werkgebied, voor de bronselectie (`nodes/bronselectie.py`): de run bij de api maken
    of hergebruiken, de methoden draaien (of wachten op wie al zoekt). Leeg als het lukte, anders waarom niet; wat
    er gevonden is, leest de bronselectie daarna per deelvraag bij de api."""
    api = ctx.api
    try:
        api_run = await api.start_bronnen_run(werkgebied_id, ZOEKVERSIE)
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return "dit werkgebied bestaat niet (meer)"
        if fout.status == 409:
            return f"ik kan nog niet zoeken. {WEIGERING.get(fout.reden, '')}".strip()
        raise
    rid = str(api_run["id"])
    if api_run.get("status") in ("wacht", "mislukt"):
        fout_tekst = ""
        async for ev in bronnen_stroom(werkgebied_id, rid, ctx.run, settings=ctx.settings, user_id=ctx.user_id,
                                       graph=ctx.graph):
            if ev["type"] == "status":
                ctx.melding(str(ev.get("message", "")).removeprefix("Lex · "))
            elif ev["type"] == "error":
                fout_tekst = str(ev.get("message", ""))
        return fout_tekst
    if api_run.get("status") == "loopt":
        ctx.melding("Er loopt al een zoekopdracht op deze selectie; ik wacht op de uitkomst")
        return await _wacht(api, werkgebied_id, rid, ctx.run)
    ctx.melding("Voor deze selectie had ik al gezocht")
    return ""


async def _wacht(api: WetsanalyseApi, werkgebied_id: str, rid: str, run: Any) -> str:
    """Wacht op een run die een ander draait. Leeg = klaar, anders waarom niet."""
    gewacht = 0.0
    while gewacht < WACHT_OP_ANDERE_RUN_S:
        await asyncio.sleep(PEIL_S)
        gewacht += PEIL_S
        stand = await api.haal_bronnen_run(werkgebied_id, rid)
        if stand.get("status") == "klaar":
            return ""
        if stand.get("status") == "mislukt" or (run is not None and run.stop_gevraagd):
            break
    return "De zoekopdracht die al liep, is niet afgerond."
