"""De begrippenroute in het gesprek: "stel begrippen voor" binnen een werkgebied (spoor D, fase AF2).

Een harde route, net als een reeks: wie in de werkplek vanuit een werkgebied om begrippen vraagt,
komt niet bij de supervisor of een model uit, maar bij de keten van ADR-004 op het manifest van dat
werkgebied. De beurt doet wat de tab Begrippen doet – de api legt het manifest vast en maakt de run
(of geeft die op dezelfde stand terug), de keten rekent – en legt daarna een bericht vast met een
**begrippenartefact** (`{soort: "begrippen", ref: {werkgebied_id, run_id}}`). De werkplek opent dat
als paneel naast de chat.

Geen model, dus geen tokens; de budgetpoort van `/v1/runs` geldt wel, zoals voor elke beurt.

Wat de api weigert (te weinig passages, een onvolledige inventaris, een onbekend werkgebied) is
geen storing maar een antwoord: Lex zegt het, en het staat na herladen in het gesprek.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncIterator

from .begrippen_run import begrippen_stroom
from .config import Settings
from .jas_pipeline.taal.provider import TaalProvider
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger(__name__)

# Hoe lang deze beurt wacht op een run die een ander (de tab Begrippen) al draait.
WACHT_OP_ANDERE_RUN_S = 180.0
PEIL_S = 2.0

# Wat de api weigert, in de woorden van Lex (`api/app/begrippen_run_store.py`). `api_reden` geeft de
# foutcode, niet de melding.
WEIGERING = {
    "te_weinig_passages": "Er zijn minder dan twee geannoteerde passages in dit werkgebied; laat eerst "
                          "de bepalingen annoteren.",
    "inventaris_onvolledig": "Niet elke bron van het werkgebied kon worden opgehaald; probeer het straks opnieuw.",
}

_BEGRIPPEN = re.compile(r"\bbegrippen\b", re.IGNORECASE)
_HANDELING = re.compile(r"\b(stel|stelt|voorstel\w*|maak|geef|welke|vind|zoek|formuleer|bepaal|herken)\b",
                        re.IGNORECASE)


def is_begrippenvraag(vraag: str) -> bool:
    """"Stel begrippen voor", "welke begrippen zitten hierin?" – maar niet "wat betekent het begrip X?":
    dat is een definitievraag over de graaf, en die hoort bij de antwoord-worker."""
    return bool(_BEGRIPPEN.search(vraag) and _HANDELING.search(vraag))


def begrippen_artefact(werkgebied_id: str, run_id: str, titel: str) -> dict[str, Any]:
    """In de vorm van `api/app/gesprek_contracts.Artefact`."""
    return {"soort": "begrippen", "titel": titel[:300], "ref": {"werkgebied_id": werkgebied_id, "run_id": run_id}}


def samenvatting(naam: str, open_groepen: int, passages: int, vragen: int, al_gerekend: bool) -> str:
    """Hoogstens drie zinnen, uit de getallen – geen model."""
    if open_groepen == 0:
        zin = f"Ik vond in werkgebied *{naam}* geen open begripsvoorstellen meer"
        zin += " – voor deze stand was al gerekend, en elk voorstel is beoordeeld." if al_gerekend else "."
    else:
        woord = "begrip" if open_groepen == 1 else "begrippen"
        zin = f"Ik stel **{open_groepen}** {woord} voor in werkgebied *{naam}*, uit {passages} passages."
        if al_gerekend:
            zin += " Voor deze stand van het werkgebied had ik al gerekend; dit zijn de voorstellen die nog open staan."
    if vragen:
        zin += f" Bij {vragen} {'twijfelpunt' if vragen == 1 else 'twijfelpunten'} laat ik de keuze aan jou."
    return zin + " Open de voorstellen om ze te beoordelen."


async def meedenk_aanbod(api: WetsanalyseApi, werkgebied_id: str) -> tuple[str, dict[str, Any] | None]:
    """Fase C: kan het model meedenken (twijfelpunten, begrippen zonder definitie), dan een zin en een
    bevestiging erbij – nooit meteen starten. Lukt het ophalen niet, dan geen aanbod: de voorstellen
    zelf staan er wel."""
    from .begrippen_verdieping import voorstel_tekst
    try:
        wv = await api.haal_verdieping(werkgebied_id)
    except Exception:  # noqa: BLE001 – een aanbod is bijzaak
        logger.warning("begrippenbeurt: verdieping niet op te halen", exc_info=True)
        return "", None
    if wv.get("verdiept") or not int(wv.get("aantal") or 0):
        return "", None
    _, bevestiging = voorstel_tekst("", {"werkgebied_id": werkgebied_id, **wv})
    vragen, kaarten = len(wv.get("vragen") or []), len(wv.get("kaarten") or [])
    delen = [x for x in (f"{vragen} {'twijfelpunt' if vragen == 1 else 'twijfelpunten'}" if vragen else "",
                         f"{kaarten} {'begrip' if kaarten == 1 else 'begrippen'} zonder definitie" if kaarten else "") if x]
    schat = wv.get("schatting")
    kosten = f" (naar schatting ~{schat['totaal']:,} tokens)".replace(",", ".") if schat else ""
    return (f" Wil je dat ik meedenk over {' en '.join(delen)}{kosten}? Dat kost tokens; bevestig als je dat wilt.",
            bevestiging)


async def zonder_api() -> AsyncIterator[dict[str, Any]]:
    """Zonder koppeling met de api is er geen werkgebied en niets om naar terug te schrijven."""
    yield {"type": "error", "message": "Zonder koppeling met de wetsanalyse-api kan Lex geen begrippen voorstellen.",
           "soort": "api"}
    yield {"type": "done"}


def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


async def begrippen_beurt(request: Any, run: Any, *, settings: Settings, user_id: str,
                          provider: TaalProvider | None = None) -> AsyncIterator[dict[str, Any]]:
    """De eventstroom van de begrippenroute; legt zelf vast, zoals `voer_beurt_uit`."""
    werkgebied_id: str = request.werkgebied_id
    gesprek_id: str = request.conversation_id or ""
    run_id: str = getattr(run, "run_id", "") or ""
    denk: list[str] = []

    def status(bericht: str) -> dict[str, Any]:
        denk.append(f"· {bericht}")
        return _status(bericht)

    api = WetsanalyseApi(settings, user_id)
    try:
        artefact: dict[str, Any] | None = None
        bevestiging: dict[str, Any] | None = None
        try:
            wg = await api.haal_werkgebied(werkgebied_id)
            naam = str(wg.get("naam") or "zonder naam")
            yield status(f"Werkgebied {naam}: passages verzamelen")
            api_run = await api.start_begrippen_run(werkgebied_id)
        except WetsanalyseApiFout as fout:
            if fout.status not in (404, 409, 422):
                raise
            tekst = ("Dit werkgebied bestaat niet (meer)." if fout.status == 404
                     else f"Ik kan hier nog geen begrippen voorstellen. {WEIGERING.get(fout.reden, '')}".strip())
        else:
            uitkomst: bool | str = False
            async for ev in _reken(api, werkgebied_id, api_run, run, settings=settings, user_id=user_id,
                                   provider=provider):
                if ev["type"] == "uitkomst":
                    uitkomst = ev["waarde"]
                else:
                    yield status(ev["bericht"])
            if isinstance(uitkomst, str):
                tekst = uitkomst
            else:
                groepen = await api.haal_groepen(werkgebied_id)
                open_groepen = sum(1 for g in groepen.get("groepen", []) if g.get("besluit") == "open")
                vragen = len(((groepen.get("run") or {}).get("uitkomst") or {}).get("vragen") or [])
                tekst = samenvatting(naam, open_groepen, int(api_run.get("aantal_formuleringen") or 0), vragen,
                                     al_gerekend=uitkomst)
                artefact = begrippen_artefact(werkgebied_id, str(api_run["id"]), naam)
                aanbod, bevestiging = await meedenk_aanbod(api, werkgebied_id)
                tekst += aanbod

        if run is not None and run.stop_gevraagd:
            yield {"type": "done"}
            return
        yield {"type": "token", "content": tekst}
        extra = {**({"artefact": artefact} if artefact else {}),
                 **({"bevestiging": bevestiging} if bevestiging else {})}
        bericht = {"rol": "assistant", "tekst": tekst, "denk": "\n".join(denk), "run_id": run_id, **extra}
        try:
            await api.voeg_bericht_toe(gesprek_id, bericht)
        except GesprekVerdwenen:
            yield {"type": "done"}
            return
        yield {"type": "opgeslagen", "run_id": run_id, **extra}
        yield {"type": "done"}
    except WetsanalyseApiFout as fout:
        logger.error("begrippenbeurt: api-fout", extra={"categorie": "technisch", "run_id": run_id,
                                                         "http_status": fout.status})
        yield {"type": "error", "message": "De begripsvoorstellen konden niet worden gemaakt of bewaard; "
               "probeer het opnieuw.", "soort": "api", "status": fout.status}
        yield {"type": "done"}
    finally:
        await api.aclose()


async def _reken(api: WetsanalyseApi, werkgebied_id: str, api_run: dict[str, Any], run: Any, *,
                 settings: Settings, user_id: str, provider: TaalProvider | None) -> AsyncIterator[dict[str, Any]]:
    """Zorg dat de run klaar is. Levert `{type: "stap", bericht}` per fase en eindigt met
    `{type: "uitkomst", waarde}`: `True` = er was al gerekend, `False` = nu gerekend, tekst = waarom niet."""
    rid = str(api_run["id"])
    if api_run.get("status") == "klaar":
        yield {"type": "uitkomst", "waarde": True}
        return
    if api_run.get("status") == "loopt":
        # Iemand anders (de tab Begrippen) rekent al op deze stand: wacht op die uitkomst.
        yield {"type": "stap", "bericht": "Er loopt al een berekening op deze stand; ik wacht op de uitkomst"}
        wacht = 0.0
        while wacht < WACHT_OP_ANDERE_RUN_S:
            await asyncio.sleep(PEIL_S)
            wacht += PEIL_S
            stand = await api.haal_begrippen_run(werkgebied_id, rid)
            if stand.get("status") == "klaar":
                yield {"type": "uitkomst", "waarde": False}
                return
            if stand.get("status") == "mislukt" or (run is not None and run.stop_gevraagd):
                break
        yield {"type": "uitkomst", "waarde": "De berekening die al liep, is niet afgerond. Vraag het straks nog eens."}
        return
    fout = ""
    async for ev in begrippen_stroom(werkgebied_id, rid, run, settings=settings, user_id=user_id, provider=provider):
        if ev.get("type") == "status":
            yield {"type": "stap", "bericht": str(ev.get("message", "")).removeprefix("Lex · ")}
        elif ev.get("type") == "error":
            fout = str(ev.get("message", ""))
    yield {"type": "uitkomst", "waarde": f"{fout} Probeer het opnieuw." if fout else False}
