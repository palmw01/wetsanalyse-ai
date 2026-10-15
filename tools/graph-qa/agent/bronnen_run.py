"""De bronnenrun: de ontdekmethoden op de selectie van een werkgebied (spoor D, fase A).

Twee ingangen, één stroom:

- `POST /v1/bronnen-runs {werkgebied_id, run_id}` (de tab Bronnen): `bronnen_stroom` haalt de invoer
  bij de api, past de methoden toe (`bronnen_vinden.vind`) en zet de kandidaten terug – het patroon
  van `begrippen_run.py`. Runstore-sleutel `werkgebied:<id>:bronnen`.
- **De bronnenroute in het gesprek** (`bronnen_beurt`): binnen een werkgebied gaat "zoek bepalingen" of
  "welke bepalingen horen erbij?" een harde route in, vóór de supervisor en zonder model – zoals de
  begrippenroute. Die maakt of hergebruikt de run, rekent, en legt een bericht vast met een
  **bronnenartefact** (`{soort: "bronnen", ref: {werkgebied_id, run_id}}`).

Geen model, dus geen tokens. Events: `status` per methode, dan `opgeslagen` en `done`; een fout is een
`error`, en de api hoort het via `…/mislukt`.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

from .bronnen_vinden import STANDAARD, vind
from .config import Settings
from .ports import GraphPort
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger(__name__)

WACHT_OP_ANDERE_RUN_S = 120.0
PEIL_S = 2.0

METHODE_NAAM = {"overzicht": "Overzicht op de analysevraag", "verwijzing_uit": "Verwijzingen vanuit de kern",
                "verwijzing_in": "Verwijzingen naar de kern", "definitie": "Definities van termen",
                "opbouw": "Opbouw van de wet", "gelijkenis": "Tekstuele gelijkenis"}

# "zoek bepalingen", "welke bepalingen horen erbij", "wat ontbreekt er nog?" – binnen een werkgebied.
# Een overzichtsvraag ("welke artikelen gaan over X?") is iets anders: die noemt een onderwerp en
# blijft de overzichtsroute, ook binnen een werkgebied.
_BRONNEN = re.compile(r"\b(bepalingen|bronnen|artikelen)\b", re.I)
_HANDELING = re.compile(r"\b(zoek|vind|horen erbij|hoort erbij|ontbreken|ontbreekt|mis ik|aanvullen|uitbreiden)\b", re.I)
_GAAN_OVER = re.compile(r"\bgaan over\b|\bover\s+\w+", re.I)

WEIGERING = {"geen_vertrekpunt": "Geef het werkgebied een analysevraag of neem eerst een bepaling op om te "
                                 "analyseren; daar zoek ik vanuit."}


def is_bronnenvraag(vraag: str) -> bool:
    return bool(_BRONNEN.search(vraag) and _HANDELING.search(vraag) and not _GAAN_OVER.search(vraag))


def bronnen_artefact(werkgebied_id: str, run_id: str, titel: str) -> dict[str, Any]:
    """In de vorm van `api/app/gesprek_contracts.Artefact`."""
    return {"soort": "bronnen", "titel": titel[:300], "ref": {"werkgebied_id": werkgebied_id, "run_id": run_id}}


def samenvatting(naam: str, kandidaten: list[dict[str, Any]], meting: dict[str, Any] | None) -> str:
    """Uit de getallen, geen model. Telt alleen open voorstellen; noemt een onvolledige methode."""
    open_ = [k for k in kandidaten if k.get("status") == "voorgesteld" and not k.get("in_selectie")]
    per_rol = {r: sum(1 for k in open_ if k.get("rol") == r) for r in ("kern", "afhankelijkheid", "aanverwant")}
    if not open_:
        zin = f"Ik vond voor werkgebied *{naam}* geen nieuwe bepalingen om voor te stellen."
    else:
        delen = [f"{n} {w}" for n, w in ((per_rol["kern"], "kern"), (per_rol["afhankelijkheid"], "afhankelijkheid"),
                                          (per_rol["aanverwant"], "aanverwant")) if n]
        zin = (f"Ik stel **{len(open_)}** {'bepaling' if len(open_) == 1 else 'bepalingen'} voor in werkgebied "
               f"*{naam}*: {', '.join(delen)}.")
    onvolledig = [METHODE_NAAM.get(m, m).lower() for m, x in (meting or {}).items() if not x.get("volledig", True)]
    if onvolledig:
        zin += f" Niet volledig: {', '.join(onvolledig)} (plafond geraakt of de graaf haperde)."
    return zin + " Neem op wat erbij hoort; sluit uit wat er niet bij hoort, met een reden."


def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


def _graaf(settings: Settings) -> GraphPort:
    from .adapters.graphdb_graph import make_graph
    return make_graph(settings)


async def bronnen_stroom(werkgebied_id: str, api_run_id: str, run: Any, *, settings: Settings, user_id: str,
                         graph: GraphPort | None = None, methoden: tuple[str, ...] = STANDAARD
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


async def bronnen_beurt(request: Any, run: Any, *, settings: Settings, user_id: str,
                        graph: GraphPort | None = None) -> AsyncIterator[dict[str, Any]]:
    """De bronnenroute in het gesprek; legt zelf vast, zoals `voer_beurt_uit`."""
    werkgebied_id: str = request.werkgebied_id
    run_id: str = getattr(run, "run_id", "") or ""
    denk: list[str] = []

    def status(ev: dict[str, Any]) -> dict[str, Any]:
        denk.append("· " + str(ev.get("message", "")).removeprefix("Lex · "))
        return ev

    api = WetsanalyseApi(settings, user_id)
    try:
        artefact: dict[str, Any] | None = None
        try:
            wg = await api.haal_werkgebied(werkgebied_id)
            naam = str(wg.get("naam") or "zonder naam")
            api_run = await api.start_bronnen_run(werkgebied_id)
        except WetsanalyseApiFout as fout:
            if fout.status not in (404, 409):
                raise
            tekst = ("Dit werkgebied bestaat niet (meer)." if fout.status == 404
                     else f"Ik kan nog niet zoeken. {WEIGERING.get(fout.reden, '')}".strip())
        else:
            fout_tekst = ""
            if api_run.get("status") in ("wacht", "mislukt"):
                async for ev in bronnen_stroom(werkgebied_id, str(api_run["id"]), run, settings=settings,
                                               user_id=user_id, graph=graph):
                    if ev["type"] == "status":
                        yield status(ev)
                    elif ev["type"] == "error":
                        fout_tekst = str(ev.get("message", ""))
            elif api_run.get("status") == "loopt":
                yield status(_status("Er loopt al een zoekopdracht op deze selectie; ik wacht op de uitkomst"))
                fout_tekst = await _wacht(api, werkgebied_id, str(api_run["id"]), run)
            else:
                yield status(_status("Voor deze selectie had ik al gezocht"))
            if fout_tekst:
                tekst = f"{fout_tekst} Probeer het opnieuw."
            else:
                lijst = await api.haal_kandidaten(werkgebied_id)
                tekst = samenvatting(naam, lijst.get("kandidaten", []), (lijst.get("run") or {}).get("meting"))
                artefact = bronnen_artefact(werkgebied_id, str(api_run["id"]), naam)

        if run is not None and run.stop_gevraagd:
            yield {"type": "done"}
            return
        yield {"type": "token", "content": tekst}
        bericht = {"rol": "assistant", "tekst": tekst, "denk": "\n".join(denk), "run_id": run_id,
                   **({"artefact": artefact} if artefact else {})}
        try:
            await api.voeg_bericht_toe(request.conversation_id or "", bericht)
        except GesprekVerdwenen:
            yield {"type": "done"}
            return
        yield {"type": "opgeslagen", "run_id": run_id, **({"artefact": artefact} if artefact else {})}
        yield {"type": "done"}
    except WetsanalyseApiFout as fout:
        logger.error("bronnenbeurt: api-fout", extra={"categorie": "technisch", "http_status": fout.status})
        yield {"type": "error", "message": "Het zoeken naar bepalingen kon niet worden gedaan of bewaard; "
               "probeer het opnieuw.", "soort": "api", "status": fout.status}
        yield {"type": "done"}
    finally:
        await api.aclose()


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
