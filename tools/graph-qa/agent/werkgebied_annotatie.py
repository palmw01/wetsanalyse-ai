"""Lex annoteert het werkgebied (spoor D, fase B): de nieuwe bepalingen van de analysebronnen in één run.

De werkvoorraad komt van de api (`GET /v1/werkgebieden/{id}/annotatie-werkvoorraad`), nooit van de
browser: alleen bronnen met rol *analyseren*, alleen eenheden die nog **nieuw** zijn, per lid zoals
de keuzekaart. Per eenheid draait de gewone annotatiebeurt – dezelfde `reeks_stroom` en
`beurt_fabriek` als een reeks op de keuzekaart, dus dezelfde events, berichten en het `ReeksBlok`.

Twee stappen, en nooit meteen starten:

1. **Zonder `bevestigd`** (de chatvraag "annoteer het werkgebied", of de knop die eerst wil weten
   wat het kost): Lex noemt het aantal, de schatting, het budget en wat er niet meegaat, en legt een
   bericht vast met een `bevestiging` – de werkplek toont er de knop bij, ook na herladen.
2. **Met `bevestigd: n`**: alleen als `n` gelijk is aan de actuele werkvoorraad. Anders is het
   antwoord "de werkvoorraad veranderde", met een nieuwe bevestiging – nooit stil iets anders doen dan
   wat bevestigd is.

Hoogstens `PLAFOND` eenheden per run; de rest blijft nieuw en komt bij een volgende run. Tussen
eenheden houden stop en budget de run tegen. Aan het eind volgt een samenvatting als gewoon bericht.
"""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .reeks import _budget_poort, beurt_fabriek, reeks_stroom
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.werkgebied_annotatie")

PLAFOND = 40

# "annoteer het werkgebied", "annoteer wat nog niet geannoteerd is", "annoteer alles" – binnen een
# werkgebied. "annoteer artikel 9" blijft de gewone annotatieroute, en "annoteer alles over X" de
# onderwerproute (een keuze uit kandidaten).
_ANNOTEER = re.compile(r"\bannoteer\b|\bannoteren\b", re.I)
_GEHEEL = re.compile(r"\bwerkgebied\b|\bnog niet geannoteerd\b|\balle (nieuwe )?bepalingen\b"
                     r"|^\s*annoteer alles\s*[.!?]?\s*$", re.I)


def is_werkgebied_annoteervraag(vraag: str) -> bool:
    return bool(_ANNOTEER.search(vraag) and _GEHEEL.search(vraag))


def _getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _bepalingen(n: int) -> str:
    return "bepaling" if n == 1 else "bepalingen"


def voorstel(naam: str, wv: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """De tekst vóór de bevestiging, en de bevestiging zelf (geen als er niets te doen is)."""
    te = list(wv.get("te_annoteren") or [])
    n, deze_run = len(te), min(len(te), PLAFOND)
    al = sum(1 for e in wv.get("eenheden") or [] if (e.get("stand") or {}).get("status") != "nieuw")
    context = int(wv.get("context_niet_meegenomen") or 0)
    zinnen = []
    if not n:
        zinnen.append(f"In werkgebied *{naam}* is niets nieuws te annoteren: elke bepaling van de "
                      "analysebronnen heeft al een annotatie.")
    else:
        zin = f"In werkgebied *{naam}* {'is' if n == 1 else 'zijn'} **{n}** {_bepalingen(n)} nog niet geannoteerd."
        if n > PLAFOND:
            zin += f" Per run doe ik er hoogstens {PLAFOND}; de rest volgt bij een volgende run."
        zinnen.append(zin)
        schat = wv.get("schatting")
        budget = wv.get("budget") or {}
        if schat:
            zin = (f"Naar schatting kost dat ~{_getal(schat['per_bepaling'] * deze_run)} tokens "
                   f"(mediaan van je laatste {schat['basis']} annotatiebeurten)")
        else:
            zin = "Een schatting kan ik nog niet geven: er zijn nog geen annotatiebeurten van jou om op te baseren"
        if budget.get("actief"):
            zin += f"; je hebt nog {_getal(int(budget.get('resterend') or 0))} tokens."
        else:
            zin += "."
        zinnen.append(zin)
    niet = []
    if al:
        niet.append(f"{al} {_bepalingen(al)} met voorstellen, een oordeel of afgerond")
    if context:
        niet.append(f"{context} {'contextbron' if context == 1 else 'contextbronnen'}")
    if niet:
        zinnen.append(f"Niet mee: {' en '.join(niet)}.")
    for punt in wv.get("open_punten") or []:
        zinnen.append(f"Niet bereikbaar: {punt}")
    if n:
        zinnen.append("Bevestig om te starten; je volgt de voortgang hier per bepaling.")
    bevestiging = None
    if n:
        schat = wv.get("schatting")
        bevestiging = {"soort": "werkgebied_annoteren", "werkgebied_id": str(wv.get("werkgebied_id") or ""),
                       "aantal": n, "schatting": schat["per_bepaling"] * deze_run if schat else None}
    return " ".join(zinnen), bevestiging


def samenvatting(naam: str, uitkomsten: dict[str, str], eind: dict[str, Any], rest: int) -> str:
    """Uit de getallen, geen model."""
    tel = {s: sum(1 for u in uitkomsten.values() if u == s) for s in ("klaar", "hergebruik", "fout", "gestopt")}
    gedaan = tel["klaar"] + tel["hergebruik"]
    delen = [f"{gedaan} {_bepalingen(gedaan)} geannoteerd in werkgebied *{naam}*"]
    if tel["fout"]:
        delen.append(f"{tel['fout']} mislukt")
    overgeslagen = len(eind.get("overgeslagen") or [])
    if overgeslagen:
        waarom = {"budget_op": " – je tokenbudget is op", "gestopt": " – gestopt op verzoek"}.get(eind.get("reden", ""), "")
        delen.append(f"{overgeslagen} niet aan bod gekomen{waarom}")
    tekst = "; ".join(delen) + "."
    if rest:
        tekst += f" Er {'staat' if rest == 1 else 'staan'} nog {rest} {_bepalingen(rest)} buiten deze run (plafond {PLAFOND})."
    if gedaan:
        tekst += " Beoordeel de voorstellen per bepaling via *Open ›*, of op de tab Elementen van het werkgebied."
    return tekst


async def werkgebied_annotatie_beurt(
    request: Any,
    run: Any,
    *,
    settings,
    user_id: str,
    api: WetsanalyseApi | None = None,
    graph=None,
    llm=None,
    annotaties=None,
    budget_toegestaan: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """De werkgebied-annotatierun in het gesprek; legt zelf vast, zoals `voer_beurt_uit`.

    `api`, `graph`, `llm`, `annotaties` en `budget_toegestaan` zijn er voor tests."""
    werkgebied_id: str = request.werkgebied_id
    run_id: str = getattr(run, "run_id", "") or ""
    eigen_api = api is None
    api = api or WetsanalyseApi(settings, user_id)

    async def leg_vast(tekst: str, bevestiging: dict[str, Any] | None = None) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "token", "content": tekst}
        bericht = {"rol": "assistant", "tekst": tekst, "run_id": run_id,
                   **({"bevestiging": bevestiging} if bevestiging else {})}
        try:
            await api.voeg_bericht_toe(request.conversation_id or "", bericht)
        except GesprekVerdwenen:
            yield {"type": "done"}
            return
        yield {"type": "opgeslagen", "run_id": run_id, **({"bevestiging": bevestiging} if bevestiging else {})}
        yield {"type": "done"}

    try:
        yield {"type": "status", "message": "Lex · Werkvoorraad van het werkgebied bepalen"}
        try:
            wv = await api.haal_annotatie_werkvoorraad(werkgebied_id)
        except WetsanalyseApiFout as fout:
            if fout.status != 404:
                raise
            async for ev in leg_vast("Dit werkgebied bestaat niet (meer)."):
                yield ev
            return
        wv = {"werkgebied_id": werkgebied_id, **wv}
        naam = str(wv.get("naam") or "zonder naam")
        te = list(wv.get("te_annoteren") or [])
        bevestigd = getattr(request, "bevestigd", None)

        if bevestigd is None or bevestigd != len(te) or not te:
            tekst, bevestiging = voorstel(naam, wv)
            if bevestigd is not None and bevestigd != len(te):
                tekst = (f"De werkvoorraad veranderde: nu {len(te)} {_bepalingen(len(te))} in plaats van "
                         f"{bevestigd}. Ik ben niet begonnen. " + tekst)
            async for ev in leg_vast(tekst, bevestiging):
                yield ev
            return

        per_iri = {e["bron_iri"]: e for e in wv.get("eenheden") or []}
        doelen = [{"bron_iri": i, "label": ", ".join(x for x in (per_iri.get(i, {}).get("regeling"),
                                                                  per_iri.get(i, {}).get("label")) if x) or i}
                  for i in te[:PLAFOND]]
        ouder = {"bron_iri": f"urn:wa:werkgebied:{werkgebied_id}", "label": f"werkgebied {naam}"}
        if budget_toegestaan is None and settings.legt_zelf_vast and user_id:
            budget_toegestaan = _budget_poort(settings, user_id)
        beurt = beurt_fabriek(run, gesprek_id=request.conversation_id, hergebruik="auto", totaal=len(doelen),
                              ouder=ouder["label"], settings=settings, user_id=user_id,
                              graph=graph, llm=llm, annotaties=annotaties)
        stop = (lambda: bool(run.stop_gevraagd)) if run is not None else (lambda: False)
        uitkomsten: dict[str, str] = {}
        eind: dict[str, Any] = {}
        async for ev in reeks_stroom(doelen, run_id=run_id, beurt=beurt, ouder=ouder,
                                     stop_gevraagd=stop, budget_toegestaan=budget_toegestaan):
            if ev["type"] == "done":
                continue
            if ev["type"] == "onderdeel" and ev.get("fase") == "eind":
                uitkomsten[ev["bron_iri"]] = ev.get("uitkomst", "")
            elif ev["type"] == "reeks" and ev.get("fase") == "eind":
                eind = ev
            yield ev
        async for ev in leg_vast(samenvatting(naam, uitkomsten, eind, max(0, len(te) - PLAFOND))):
            yield ev
    except WetsanalyseApiFout as fout:
        logger.error("werkgebied annoteren: api-fout", extra={"categorie": "technisch", "http_status": fout.status})
        yield {"type": "error", "message": "De werkvoorraad van het werkgebied kon niet worden opgehaald of "
               "bewaard; probeer het opnieuw.", "soort": "api", "status": fout.status}
        yield {"type": "done"}
    finally:
        if eigen_api:
            await api.aclose()
