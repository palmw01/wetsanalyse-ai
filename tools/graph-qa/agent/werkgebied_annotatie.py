"""Lex annoteert het werkgebied (spoor D, fase B): de nieuwe bepalingen van de analysebronnen in één run.

De werkvoorraad komt van de api (`GET /v1/werkgebieden/{id}/annotatie-werkvoorraad`), nooit van de
browser: alleen bronnen met rol *analyseren*, alleen eenheden die nog **nieuw** zijn, per lid zoals
de keuzekaart. Per eenheid draait de gewone annotatiebeurt – dezelfde `reeks_stroom` en
`beurt_fabriek` als een reeks op de keuzekaart, dus dezelfde events, berichten en het `ReeksBlok`.

Twee stappen, en nooit meteen starten:

1. **Zonder `bevestigd`** (de getypte vraag via de supervisor, `werkgebied_voorstel`, of de knop die
   eerst wil weten wat het kost): Lex noemt het aantal, de schatting, het budget en wat er niet
   meegaat, en het bericht draagt een `bevestiging` – de werkplek toont er de knop bij, ook na herladen.
2. **Met `bevestigd: n`**: alleen als `n` gelijk is aan de actuele werkvoorraad. Anders is het
   antwoord "de werkvoorraad veranderde", met een nieuwe bevestiging – nooit stil iets anders doen dan
   wat bevestigd is.

Hoogstens `PLAFOND` eenheden per run; de rest blijft nieuw en komt bij een volgende run. Tussen
eenheden houden stop en budget de run tegen. Aan het eind volgt een samenvatting als gewoon bericht.

**Het bereik** (`bereik`, `deelvraag_id`): het hele werkgebied, of alleen de bronnen onder de actieve
deelvragen – allemaal, of die van één deelvraag. De api filtert (`?bereik=deelvragen`); de bevestiging
draagt het bereik, zodat de knop precies dat start, ook na herladen.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from .agents import Context, Uitkomst, geweigerd
from .reeks import _budget_poort, beurt_fabriek, reeks_stroom
from .wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.werkgebied_annotatie")

PLAFOND = 40


def _getal(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _bepalingen(n: int) -> str:
    return "bepaling" if n == 1 else "bepalingen"


def _deelvragen(wv: dict[str, Any]) -> bool:
    return wv.get("bereik") == "deelvragen"


def plek(naam: str, wv: dict[str, Any]) -> str:
    """Waar het over gaat, in kleine letters: "in werkgebied *X*", "onder deelvraag *…*", "onder de 4
    deelvragen van werkgebied *X*"."""
    if not _deelvragen(wv):
        return f"in werkgebied *{naam}*"
    dv = list(wv.get("deelvragen") or [])
    if wv.get("deelvraag_id") and dv:
        return f"onder deelvraag *{dv[0].get('vraag', '')}*"
    k = len(dv)
    return (f"onder de deelvraag van werkgebied *{naam}*" if k == 1
            else f"onder de {k} deelvragen van werkgebied *{naam}*")


def _hoofd(t: str) -> str:
    return t[:1].upper() + t[1:]


def _bronnen_en_bepalingen(wv: dict[str, Any], n: int) -> str:
    """Waarom er meer bepalingen zijn dan bronnen: een artikel met leden gaat per lid, een bepaling met
    subbepalingen per subbepaling (`bronmodel.annotatie_eenheden`). Zonder die zin leest "60 bepalingen"
    bij 18 bronnen als een fout. Met de bronnen die het meest bijdragen; leeg als elke bron één is."""
    selecties = [s for s in wv.get("selecties") or [] if not s.get("onbereikbaar")]
    if not selecties or n <= len(selecties):
        return ""
    k = len(selecties)
    zin = (f"Ze komen uit {k} {'bron' if k == 1 else 'bronnen'}: een artikel met leden annoteer ik per lid, "
           "een bepaling met subbepalingen per subbepaling.")
    groot = sorted((s for s in selecties if int((s.get("per_stand") or {}).get("nieuw") or 0) > 1),
                   key=lambda s: -int(s["per_stand"]["nieuw"]))[:3]
    if groot:
        zin += " Het meest: " + ", ".join(f"{s.get('label') or s.get('bron_iri', '')} ({s['per_stand']['nieuw']})"
                                          for s in groot) + "."
    return zin


def voorstel(naam: str, wv: dict[str, Any], alternatief: dict[str, Any] | None = None
             ) -> tuple[str, dict[str, Any] | None]:
    """De tekst vóór de bevestiging, en de bevestiging zelf (geen als er niets te doen is).

    `alternatief` is de werkvoorraad onder de deelvragen, bij een voorstel over het hele werkgebied:
    is die kleiner, dan noemt Lex dat de analist ook alleen die kan laten annoteren."""
    te = list(wv.get("te_annoteren") or [])
    n, deze_run = len(te), min(len(te), PLAFOND)
    al = sum(1 for e in wv.get("eenheden") or [] if (e.get("stand") or {}).get("status") != "nieuw")
    context = int(wv.get("context_niet_meegenomen") or 0)
    buiten = int(wv.get("buiten_bereik") or 0) if _deelvragen(wv) else 0
    waar = plek(naam, wv)
    zinnen = []
    if not n and _deelvragen(wv) and not wv.get("eenheden"):
        hier = "bij deze deelvraag" if wv.get("deelvraag_id") else "per deelvraag"
        zinnen.append(f"{_hoofd(waar)} staan nog geen analysebronnen. Bepaal eerst met Lex de bronnen "
                      f"(*Bepaal de bronnen {hier}*), of koppel bronnen aan de deelvraag.")
    elif not n:
        zinnen.append(f"{_hoofd(waar)} is niets nieuws te annoteren: elke bepaling van de "
                      "analysebronnen heeft al een annotatie.")
    else:
        zin = f"{_hoofd(waar)} {'is' if n == 1 else 'zijn'} **{n}** {_bepalingen(n)} nog niet geannoteerd."
        if uitleg := _bronnen_en_bepalingen(wv, n):
            zin += " " + uitleg
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
    if buiten:
        niet.append(f"{buiten} {'analysebron' if buiten == 1 else 'analysebronnen'} buiten "
                    f"{'deze deelvraag' if wv.get('deelvraag_id') else 'de deelvragen'}")
    if niet:
        zinnen.append(f"Niet mee: {' en '.join(niet)}.")
    for punt in wv.get("open_punten") or []:
        zinnen.append(f"Niet bereikbaar: {punt}")
    m = len((alternatief or {}).get("te_annoteren") or [])
    if not _deelvragen(wv) and 0 < m < n:
        zinnen.append(f"Alleen de bepalingen onder de deelvragen? Dat {'is er' if m == 1 else 'zijn er'} {m}: "
                      "vraag *Annoteer de bepalingen van de deelvragen*.")
    if n:
        zinnen.append("Bevestig om te starten; je volgt de voortgang hier per bepaling.")
    bevestiging = None
    if n:
        schat = wv.get("schatting")
        bevestiging = {"soort": "werkgebied_annoteren", "werkgebied_id": str(wv.get("werkgebied_id") or ""),
                       "aantal": n, "schatting": schat["per_bepaling"] * deze_run if schat else None,
                       "bereik": "deelvragen" if _deelvragen(wv) else "werkgebied",
                       "deelvraag_id": str(wv.get("deelvraag_id") or "")}
    return " ".join(zinnen), bevestiging


def samenvatting(naam: str, uitkomsten: dict[str, str], eind: dict[str, Any], rest: int,
                 wv: dict[str, Any] | None = None) -> str:
    """Uit de getallen, geen model."""
    tel = {s: sum(1 for u in uitkomsten.values() if u == s) for s in ("klaar", "hergebruik", "fout", "gestopt")}
    gedaan = tel["klaar"] + tel["hergebruik"]
    delen = [f"{gedaan} {_bepalingen(gedaan)} geannoteerd {plek(naam, wv or {})}"]
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


async def zonder_api() -> AsyncIterator[dict[str, Any]]:
    """Zonder koppeling met de api is er geen werkgebied en niets om naar terug te schrijven."""
    yield {"type": "error", "message": "Zonder koppeling met de wetsanalyse-api kan Lex het werkgebied niet annoteren.",
           "soort": "api"}
    yield {"type": "done"}


#: Wat de api met een weigering bedoelt, in de woorden van Lex.
WEIGERING = {
    "niet_actief": "Die deelvraag is niet (meer) actief. Kies *Vraag Lex* bij een actieve deelvraag.",
    "geen_deelvragen": "Dit werkgebied heeft nog geen deelvragen. Vraag *Stel deelvragen voor*, of laat Lex "
                       "het hele werkgebied annoteren.",
}


def weigering(fout: WetsanalyseApiFout) -> str | None:
    """De zin bij een weigering van de api (404, 409); `None` als het een storing is."""
    if fout.status == 404:
        return ("Die deelvraag bestaat niet (meer)." if fout.reden.startswith("Deelvraag")
                else "Dit werkgebied bestaat niet (meer).")
    if fout.status == 409:
        return WEIGERING.get(fout.reden)
    return None


async def _haal(api: WetsanalyseApi, werkgebied_id: str, bereik: str, deelvraag_id: str) -> dict[str, Any]:
    wv = await api.haal_annotatie_werkvoorraad(werkgebied_id, bereik, deelvraag_id)
    return {"werkgebied_id": werkgebied_id, "bereik": bereik, "deelvraag_id": deelvraag_id, **wv}


async def _alternatief(api: WetsanalyseApi, werkgebied_id: str, wv: dict[str, Any]) -> dict[str, Any] | None:
    """Bij het hele werkgebied: de werkvoorraad onder de deelvragen, als die er zijn. Best-effort – een
    weigering of storing kost alleen de extra zin."""
    if _deelvragen(wv) or not wv.get("te_annoteren"):
        return None
    try:
        return await api.haal_annotatie_werkvoorraad(werkgebied_id, "deelvragen", "")
    except WetsanalyseApiFout:
        return None


async def werkgebied_voorstel(ctx: Context, werkgebied_id: str, bereik: str = "werkgebied",
                              deelvraag_id: str = "") -> Uitkomst:
    """Stap 1 als taak (`werkgebied` of `deelvragen` van de annotatie-agent, `agents/annotatie.py`): de
    getypte vraag "annoteer wat nog niet geannoteerd is" levert het voorstel met de bevestiging. Starten
    doet de bevestigingsknop, met `bevestigd` (de reeks hieronder)."""
    taak = "deelvragen" if bereik == "deelvragen" else "werkgebied"
    ctx.melding("Werkvoorraad van het werkgebied bepalen")
    try:
        wv = await _haal(ctx.api, werkgebied_id, bereik, deelvraag_id)
    except WetsanalyseApiFout as fout:
        if (zin := weigering(fout)) is None:
            raise
        return geweigerd(taak, zin)
    tekst, bevestiging = voorstel(str(wv.get("naam") or "zonder naam"), wv,
                                  await _alternatief(ctx.api, werkgebied_id, wv))
    return Uitkomst(taak=taak, status="bevestiging" if bevestiging else "ok", tekst=tekst, bevestiging=bevestiging,
                    meting={"te_annoteren": len(wv.get("te_annoteren") or []), "model": False})


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
    bereik: str = getattr(request, "bereik", "werkgebied") or "werkgebied"
    deelvraag_id: str = getattr(request, "deelvraag_id", "") or ""
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
            wv = await _haal(api, werkgebied_id, bereik, deelvraag_id)
        except WetsanalyseApiFout as fout:
            if (zin := weigering(fout)) is None:
                raise
            async for ev in leg_vast(zin):
                yield ev
            return
        naam = str(wv.get("naam") or "zonder naam")
        te = list(wv.get("te_annoteren") or [])
        bevestigd = getattr(request, "bevestigd", None)

        if bevestigd is None or bevestigd != len(te) or not te:
            tekst, bevestiging = voorstel(naam, wv, await _alternatief(api, werkgebied_id, wv) if bevestigd is None else None)
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
        if not _deelvragen(wv):
            ouder = {"bron_iri": f"urn:wa:werkgebied:{werkgebied_id}", "label": f"werkgebied {naam}"}
        elif deelvraag_id:
            dv = (wv.get("deelvragen") or [{}])[0]
            ouder = {"bron_iri": f"urn:wa:werkgebied:{werkgebied_id}:deelvraag:{deelvraag_id}",
                     "label": f"deelvraag {str(dv.get('vraag') or '')[:80]}".strip()}
        else:
            ouder = {"bron_iri": f"urn:wa:werkgebied:{werkgebied_id}:deelvragen", "label": f"deelvragen van {naam}"}
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
        async for ev in leg_vast(samenvatting(naam, uitkomsten, eind, max(0, len(te) - PLAFOND), wv)):
            yield ev
    except WetsanalyseApiFout as fout:
        logger.error("werkgebied annoteren: api-fout", extra={"categorie": "technisch", "http_status": fout.status})
        yield {"type": "error", "message": "De werkvoorraad van het werkgebied kon niet worden opgehaald of "
               "bewaard; probeer het opnieuw.", "soort": "api", "status": fout.status}
        yield {"type": "done"}
    finally:
        if eigen_api:
            await api.aclose()
