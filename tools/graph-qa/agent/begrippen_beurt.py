"""Begrippen voorstellen in het gesprek (spoor D, fase AF2; sinds F3c taak `voorstellen` van de
begrippen-agent, `agents/begrippen.py`).

`begrippen_kern` doet wat de tab Begrippen doet: de api legt het manifest vast en maakt de run (of
geeft die op dezelfde stand terug), de keten van ADR-004 rekent, en de uitkomst draagt een
**begrippenartefact** (`{soort: "begrippen", ref: {werkgebied_id, run_id}}`). De werkplek opent dat
als paneel naast de chat. Er is geen tekstpatroon meer: de supervisor kiest de agent, of een klik op
een suggestie (`actie`).

Geen model, dus geen tokens; de budgetpoort van `/v1/runs` geldt wel, zoals voor elke beurt.

Wat de api weigert (te weinig passages, een onvolledige inventaris, een onbekend werkgebied) is
geen storing maar een antwoord: Lex zegt het, en het staat na herladen in het gesprek.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .begrippen_run import begrippen_stroom
from .config import Settings
from .jas_pipeline.taal.provider import TaalProvider
from .agents import Context, Uitkomst, geweigerd
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

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


async def begrippen_kern(ctx: Context, werkgebied_id: str) -> Uitkomst:
    """Begrippen voorstellen (taak `voorstellen` van de begrippen-agent): het manifest bij de api, de keten
    (of wachten op wie al rekent), de open groepen tellen, en het aanbod om mee te denken."""
    api, taak = ctx.api, "voorstellen"
    try:
        wg = await api.haal_werkgebied(werkgebied_id)
        naam = str(wg.get("naam") or "zonder naam")
        ctx.melding(f"Werkgebied {naam}: passages verzamelen")
        api_run = await api.start_begrippen_run(werkgebied_id)
    except WetsanalyseApiFout as fout:
        if fout.status == 404:
            return geweigerd(taak, "Dit werkgebied bestaat niet (meer).")
        if fout.status in (409, 422):
            return geweigerd(taak, f"Ik kan hier nog geen begrippen voorstellen. {WEIGERING.get(fout.reden, '')}".strip())
        raise
    uitkomst: bool | str = False
    async for ev in _reken(api, werkgebied_id, api_run, ctx.run, settings=ctx.settings, user_id=ctx.user_id,
                           provider=ctx.provider):
        if ev["type"] == "uitkomst":
            uitkomst = ev["waarde"]
        else:
            ctx.melding(ev["bericht"])
    if isinstance(uitkomst, str):
        return Uitkomst(taak=taak, status="fout", reden=uitkomst)
    groepen = await api.haal_groepen(werkgebied_id)
    open_ids = [str(g.get("id")) for g in groepen.get("groepen", []) if g.get("besluit") == "open"]
    vragen = len(((groepen.get("run") or {}).get("uitkomst") or {}).get("vragen") or [])
    tekst = samenvatting(naam, len(open_ids), int(api_run.get("aantal_formuleringen") or 0), vragen,
                         al_gerekend=uitkomst)
    aanbod, bevestiging = await meedenk_aanbod(api, werkgebied_id)
    return Uitkomst(taak=taak, tekst=tekst + aanbod, voorstellen=open_ids, bevestiging=bevestiging,
                    artefact=begrippen_artefact(werkgebied_id, str(api_run["id"]), naam),
                    meting={"groepen": len(open_ids), "vragen": vragen, "model": False})


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
