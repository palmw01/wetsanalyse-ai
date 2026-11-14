"""De regisseur (ADR-012): het werk in een werkgebied verdelen over kindgesprekken, volgen en bundelen.

Een vaste workflow (ADR-010, laag 2), geen node en geen model. Hij draait als eigen stroom in `_stroom_voor`, net als
de reeks, omdat hij zelf runs start:

1. **Het plan** komt uit de stand bij de api (`plan.py`). Zonder `plan_id` gelijk aan dat van nu: alleen het voorstel
   met een bevestiging (`soort: "regie"`). De jurist start, nooit Lex.
2. **De regie** wordt een delegatie bij de api (soort `regie`; één per werkgebied en één per gebruiker, 409 anders),
   met een hartslag.
3. **Per taak een kindgesprek** (`ouder_id`, `delegatie_id`) en een gewone run met de actie van de taak, langs de ene
   ingang (`start_kind` = `api.main.start_beurt`, met `ouder_run_id`). Hoogstens `REGIE_PARALLEL` tegelijk.
4. **Volgen** met `await` op de taak van het kind, op deze replica; stoppen van de regie stopt de kinderen.
5. **De bundel** leest de stand bij de api na afloop (nooit modeltekst): opgeleverd, wacht op jou, mislukt of niet
   aan bod.

De regisseur doet zelf geen besluit: opnemen, uitsluiten, beoordelen, afronden en accorderen zijn van de jurist.
`API_AANROEPEN` legt vast welke api-methoden hij gebruikt; `tests/test_regisseur.py` bewaakt dat.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..observability import get_tracer
from ..wetsanalyse_api import GesprekVerdwenen, WetsanalyseApi, WetsanalyseApiFout
from .plan import Opdracht, Plan, Taak, kind_verzoek, plan_annoteren, plan_bronnen

logger = logging.getLogger("graph_qa.regie")

#: Hoeveel kinderen er standaard tegelijk lopen, en hoeveel ten hoogste (ADR-012, *Hoeveel tegelijk*).
REGIE_PARALLEL = 2
MAX_PARALLEL = 3
#: Hoe vaak de regie bij de api laat weten dat hij leeft (de api verklaart hem na 3 minuten verweesd).
HARTSLAG_S = 30.0
#: Hoe vaak de regisseur kijkt of er om stoppen is gevraagd.
STOP_PEIL_S = 0.5

OPDRACHT_VAN_ACTIE: dict[str, Opdracht] = {"regie_bronnen": "bronnen", "regie_annoteren": "annoteren"}

#: De api-methoden die de regisseur gebruikt. Geen besluit: geen opnemen, uitsluiten, beoordelen, afronden of accorderen.
API_AANROEPEN = frozenset({
    "haal_werkgebied", "haal_bronselectie", "haal_annotatie_werkvoorraad", "start_bronnen_run", "haal_bronnen_run",
    "meld_bronnen_loopt", "zet_bronnen_uitkomst", "meld_bronnen_mislukt",
    "start_delegatie", "wijzig_delegatie", "maak_gesprek", "voeg_bericht_toe", "aclose"})

# "zoek per deelvraag de bronnen", "annoteer per deelvraag de kern", "laat Lex per deelvraag de bronnen bepalen".
_PER_DEELVRAAG = re.compile(r"\bper\s+deelvraag\b|\bvoor\s+(?:elke|iedere)\s+deelvraag\b|\bper\s+deelvragen\b", re.I)
_VRAAGWOORD = re.compile(r"^\s*(?:hoe|wat|waarom|welke|wanneer|wie|waar|is|zijn|kan\s+ik|moet)\b", re.I)
_BRONNEN = re.compile(r"\b(?:zoek|bepaal|verzamel|vind)\w*\b.*\bbron", re.I)
_ANNOTEER = re.compile(r"\bannote(?:er|ren)\b", re.I)


def opdracht_in(tekst: str) -> Opdracht | None:
    """Een getypte opdracht aan de regisseur: "per deelvraag" met bronnen zoeken of annoteren, in de vorm van een
    verzoek. Een vraag ("hoe annoteer ik per deelvraag?") is het niet. Met beide gaat eerst de bronnenronde: annoteren
    kan pas als de jurist de bronnen opnam."""
    if not tekst or not _PER_DEELVRAAG.search(tekst) or _VRAAGWOORD.match(tekst):
        return None
    if _BRONNEN.search(tekst):
        return "bronnen"
    if _ANNOTEER.search(tekst):
        return "annoteren"
    return None


StartKind = Callable[[Any, str, str], Awaitable[Any]]      # (ChatRequest, gebruiker, ouder_run_id) → Run
StopKind = Callable[[Any], Awaitable[None]]


@dataclass
class Afloop:
    """Hoe één kind afliep, voor de bundel."""
    taak: Taak
    gesprek_id: str = ""
    run_id: str = ""
    uitkomst: str = "niet_gestart"      # klaar | gestopt | mislukt | niet_gestart | budget_op
    reden: str = ""


def _getal(n: int | None) -> str:
    return f"{n or 0:,}".replace(",", ".")


def _gesprekken(n: int) -> str:
    return "deelgesprek" if n == 1 else "deelgesprekken"


def voorstel_tekst(plan: Plan, parallel: int) -> str:
    """Wat Lex zegt vóór de bevestiging: het plan, de kosten en wat er niet meegaat."""
    n = len(plan.taken)
    if plan.opdracht == "bronnen":
        kop = f"Ik zoek de bronnen per deelvraag, elk in een eigen deelgesprek: **{n}** {_gesprekken(n)}."
    else:
        b = sum(len(t.eenheden) for t in plan.taken)
        kop = (f"Ik annoteer **{b}** {'bepaling' if b == 1 else 'bepalingen'} onder de deelvragen, elk deel in een "
               f"eigen deelgesprek: **{n}** {_gesprekken(n)}.")
    regels = [kop, ""]
    for t in plan.taken:
        regel = f"- {t.titel}" + (f": {t.vraag}" if t.vraag and t.onder_deelvraag else "")
        if t.soort == "annoteren" and t.schatting:
            regel += f" (~{_getal(t.schatting)} tokens)"
        regels.append(regel)
    regels.append("")
    if plan.opdracht == "bronnen":
        regels.append("Dat kost geen tokens: het zoeken gebeurt zonder model. Wat Lex vindt, is een voorstel; je neemt "
                      "per deelvraag zelf op wat je houdt.")
    elif plan.schatting:
        regels.append(f"Naar schatting ~{_getal(plan.schatting)} tokens, hoogstens ~{_getal(plan.hoog)}"
                      + (f"; je hebt nog ~{_getal(plan.resterend)}." if plan.resterend is not None else "."))
    else:
        regels.append("Een schatting kan ik nog niet geven: er zijn nog geen annotatiebeurten van jou om op te baseren.")
    regels.append(f"Er lopen er hoogstens {parallel} tegelijk. Laat dit venster open tot het klaar is; wat af is, "
                  "blijft staan als het onderweg stopt.")
    if plan.buiten:
        regels += ["", "Niet in dit plan:"] + [f"- {z}" for z in plan.buiten]
    return "\n".join(regels)


def _bundel(plan: Plan, aflopen: list[Afloop], stand: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """De uitkomst in drie lijsten, uit de stand bij de api na afloop, en de tellingen voor de regie."""
    opgeleverd, wacht, mislukt = [], [], []
    for a in aflopen:
        t = a.taak
        if a.uitkomst == "klaar":
            opgeleverd.append(f"- {t.titel}")
        elif a.uitkomst == "niet_gestart":
            mislukt.append(f"- {t.titel}: niet aan bod gekomen{f' ({a.reden})' if a.reden else ''}")
        elif a.uitkomst == "budget_op":
            mislukt.append(f"- {t.titel}: niet gestart, je tokenbudget is op")
        elif a.uitkomst == "gestopt":
            mislukt.append(f"- {t.titel}: gestopt")
        else:
            mislukt.append(f"- {t.titel}: mislukt{f' ({a.reden})' if a.reden else ''}")
        if plan.opdracht == "bronnen":
            telling = (stand.get("bronselectie") or {}).get(t.deelvraag_id) or {}
            if telling.get("voorgesteld"):
                wacht.append(f"- {t.titel}: {telling['voorgesteld']} voorgestelde "
                             f"{'bron' if telling['voorgesteld'] == 1 else 'bronnen'} in het paneel")
        else:
            standen = [(stand.get("eenheden") or {}).get(i, "") for i in t.eenheden]
            te_beoordelen = sum(1 for s in standen if s == "te_beoordelen")
            if te_beoordelen:
                wacht.append(f"- {t.titel}: {te_beoordelen} "
                             f"{'bepaling' if te_beoordelen == 1 else 'bepalingen'} met markeringen te beoordelen")
            if a.uitkomst == "klaar" and (nieuw := sum(1 for s in standen if s == "nieuw")):
                wacht.append(f"- {t.titel}: {nieuw} {'bepaling' if nieuw == 1 else 'bepalingen'} nog niet "
                             "geannoteerd (stopte op het budgetaandeel, of de annotatie botste met een collega)")
    delen = []
    if opgeleverd:
        delen += ["**Opgeleverd**", *opgeleverd, ""]
    if wacht:
        delen += ["**Wacht op jou**", *wacht, ""]
    if mislukt:
        delen += ["**Mislukt of niet aan bod**", *mislukt, ""]
    if plan.opdracht == "bronnen":
        delen.append("Neem per deelvraag in het paneel op wat je wilt houden. Daarna kan ik annoteren wat je opnam: "
                     "*Annoteer per deelvraag de kern*.")
    else:
        delen.append("Beoordeel de markeringen per bepaling; wat Lex voorstelt is geel tot jij beslist.")
    tellingen = {"opgeleverd": len(opgeleverd), "wacht": len(wacht), "mislukt": len(mislukt),
                 "kinderen": [{"titel": a.taak.titel, "gesprek_id": a.gesprek_id, "run_id": a.run_id,
                               "uitkomst": a.uitkomst} for a in aflopen]}
    return "\n".join(delen).strip(), tellingen


async def _stand_na(api: Any, plan: Plan) -> dict[str, Any]:
    """Wat er na afloop ligt: per deelvraag de telling van de bronselectie, of per bepaling haar stand."""
    try:
        if plan.opdracht == "bronnen":
            ov = await api.haal_bronselectie(plan.werkgebied_id)
            return {"bronselectie": {v["id"]: v.get("telling") or {} for v in ov.get("deelvragen") or []}}
        wv = await api.haal_annotatie_werkvoorraad(plan.werkgebied_id)
        return {"eenheden": {e["bron_iri"]: (e.get("stand") or {}).get("status", "") for e in wv.get("eenheden") or []}}
    except WetsanalyseApiFout:
        logger.warning("regie: de stand na afloop is niet te lezen", extra={"categorie": "technisch"})
        return {}


async def plan_van(api: Any, werkgebied_id: str, opdracht: Opdracht) -> Plan:
    """Het plan uit de stand bij de api: dezelfde stand geeft hetzelfde plan, zonder tokens."""
    if opdracht == "bronnen":
        return plan_bronnen(werkgebied_id, await api.haal_bronselectie(werkgebied_id))
    return plan_annoteren(await api.haal_werkgebied(werkgebied_id), await api.haal_annotatie_werkvoorraad(werkgebied_id))


def voorstel(plan: Plan, parallel: int, *, bevestigd: str = "") -> tuple[str, dict[str, Any] | None]:
    """Wat Lex vóór een regie zegt, en de bevestiging die de jurist start (geen als er niets te verdelen is). Dezelfde
    tekst en knop voor de regie zelf en voor de tool `regie_plan` van de centrale agent (ADR-016 §A5)."""
    if not plan.taken:
        return ("Er is nu niets te verdelen." if not plan.buiten
                else "Er is nu niets te verdelen:\n" + "\n".join(f"- {z}" for z in plan.buiten)), None
    tekst = voorstel_tekst(plan, parallel)
    if bevestigd:
        tekst = "Het plan veranderde sinds je het bevestigde; ik ben niet begonnen. Dit is het plan van nu.\n\n" + tekst
    return tekst, {"soort": "regie", "werkgebied_id": plan.werkgebied_id, "aantal": len(plan.taken),
                   "schatting": plan.schatting, "plan_id": plan.plan_id, "opdracht": plan.opdracht}


async def regie_stroom(
    request: Any,
    run: Any,
    *,
    settings: Any,
    user_id: str,
    start_kind: StartKind,
    stop_kind: StopKind,
    api: Any | None = None,
    graph: Any | None = None,
    parallel: int | None = None,
    hartslag_s: float = HARTSLAG_S,
) -> AsyncIterator[dict[str, Any]]:
    """De regie in het regiegesprek; legt zelf vast, zoals `werkgebied_annotatie_beurt`.

    `api` en `graph` zijn er voor tests; `start_kind` en `stop_kind` geeft `api/main.py` mee (de ene ingang)."""
    werkgebied_id: str = request.werkgebied_id
    gesprek_id: str = request.conversation_id or ""
    run_id: str = getattr(run, "run_id", "") or ""
    opdracht: Opdracht = OPDRACHT_VAN_ACTIE.get(request.actie or "") or opdracht_in(request.question) or "bronnen"
    parallel = max(1, min(MAX_PARALLEL, parallel or getattr(settings, "regie_parallel", REGIE_PARALLEL)))
    eigen_api = api is None
    api = api or WetsanalyseApi(settings, user_id)

    async def leg_vast(tekst: str, **velden: Any) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "token", "content": tekst}
        try:
            await api.voeg_bericht_toe(gesprek_id, {"rol": "assistant", "tekst": tekst, "run_id": run_id, **velden})
        except GesprekVerdwenen:
            return
        yield {"type": "opgeslagen", "run_id": run_id, **velden}

    try:
        yield {"type": "status", "message": "Lex · Regie: het plan maken uit de stand van het werkgebied"}
        plan = await plan_van(api, werkgebied_id, opdracht)
        bevestigd = getattr(request, "plan_id", "") or ""
        if not plan.taken or bevestigd != plan.plan_id:
            tekst, bevestiging = voorstel(plan, parallel, bevestigd=bevestigd)
            async for ev in leg_vast(tekst, **({"bevestiging": bevestiging} if bevestiging else {})):
                yield ev
            return

        try:
            regie = await api.start_delegatie({
                "soort": "regie", "werkgebied_id": werkgebied_id, "gesprek_id": gesprek_id, "opdracht": plan.opdracht, "plan_id": plan.plan_id, "plan": plan.als_dict(),
                "budget_aandeel": sum(t.aandeel or 0 for t in plan.taken)})
        except WetsanalyseApiFout as fout:
            if fout.status != 409:
                raise
            tekst = ("Er loopt al een regie in dit werkgebied, of een andere regie van jou. Wacht tot die klaar is, "
                     "of stop hem in zijn regiegesprek.")
            async for ev in leg_vast(tekst):
                yield ev
            return
        regie_id = str(regie["id"])
        artefact = {"soort": "regie", "ref": {"werkgebied_id": werkgebied_id, "regie_id": regie_id},
                    "titel": f"Regie · {'bronnen' if plan.opdracht == 'bronnen' else 'annoteren'}"}
        yield {"type": "regie", "fase": "start", "regie_id": regie_id, "plan": plan.als_dict()}

        wachtrij: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        uitvoering = asyncio.create_task(_voer_uit(
            plan, regie_id, wachtrij, request=request, run=run, settings=settings, user_id=user_id, api=api,
            graph=graph, parallel=parallel, hartslag_s=hartslag_s, start_kind=start_kind, stop_kind=stop_kind))
        while (ev := await wachtrij.get()) is not None:
            yield ev
        aflopen: list[Afloop] = await uitvoering

        stand = await _stand_na(api, plan)
        tekst, tellingen = _bundel(plan, aflopen, stand)
        gestopt = bool(getattr(run, "stop_gevraagd", False))
        alles_mis = all(a.uitkomst not in ("klaar",) for a in aflopen)
        eind = "gestopt" if gestopt else "mislukt" if alles_mis else "klaar"
        with contextlib.suppress(WetsanalyseApiFout):
            await api.wijzig_delegatie(regie_id, {"status": eind, "uitkomst": tellingen})
        logger.info("regie_afloop", extra={"categorie": "functioneel", "regie_id": regie_id, "run_id": run_id,
                                           "opdracht": plan.opdracht, "eind": eind, "taken": len(plan.taken),
                                           "opgeleverd": tellingen["opgeleverd"], "mislukt": tellingen["mislukt"]})
        yield {"type": "regie", "fase": "eind", "regie_id": regie_id, "uitkomst": eind, **tellingen}
        async for ev in leg_vast(tekst, artefact=artefact):
            yield ev
    except WetsanalyseApiFout as fout:
        logger.error("regie: api-fout", extra={"categorie": "technisch", "http_status": fout.status})
        yield {"type": "error", "message": "De regie kon de stand van het werkgebied niet lezen of bewaren; probeer "
               "het opnieuw.", "soort": "api", "status": fout.status}
    finally:
        if eigen_api:
            await api.aclose()


async def _voer_uit(plan: Plan, regie_id: str, wachtrij: asyncio.Queue, *, request: Any, run: Any, settings: Any,
                    user_id: str, api: Any, graph: Any, parallel: int, hartslag_s: float,
                    start_kind: StartKind, stop_kind: StopKind) -> list[Afloop]:
    """De kinderen draaien, in een eigen taak: zo vallen ze onder de span van de regie (een kind-run erft de context van
    `create_task`), en hoeft geen span over een `yield` heen te lopen."""
    from ..models import ChatRequest

    tracer = get_tracer(__name__)
    werkgebied_id, run_id = plan.werkgebied_id, getattr(run, "run_id", "") or ""
    lopend: dict[int, Any] = {}
    stop = lambda: bool(getattr(run, "stop_gevraagd", False))  # noqa: E731
    try:
        with tracer.start_as_current_span("graph_qa.regie", attributes={
                "regie_id": regie_id, "run_id": run_id, "opdracht": plan.opdracht, "taken": len(plan.taken)}):
            hart = asyncio.create_task(_hartslag(api, werkgebied_id, regie_id, hartslag_s))
            waker = asyncio.create_task(_stopwacht(stop, lopend, stop_kind))
            try:
                if plan.opdracht == "bronnen":
                    await wachtrij.put({"type": "status", "message": "Lex · Regie: bepalingen zoeken voor het werkgebied"})
                    if reden := await _zoek_eenmaal(werkgebied_id, run, settings=settings, user_id=user_id, api=api,
                                                    graph=graph):
                        return [Afloop(taak=t, uitkomst="niet_gestart", reden=reden) for t in plan.taken]
                sem = asyncio.Semaphore(parallel)

                async def kind(index: int, taak: Taak) -> Afloop:
                    afloop = Afloop(taak=taak)
                    async with sem:
                        if stop():
                            afloop.reden = "de regie is gestopt"
                            return afloop
                        with tracer.start_as_current_span("graph_qa.regie.taak", attributes={
                                "regie_id": regie_id, "ouder_run_id": run_id, "index": index}) as span:
                            return await _draai_kind(index, taak, afloop, span, regie_id=regie_id, run_id=run_id,
                                                     werkgebied_id=werkgebied_id, request=request, user_id=user_id,
                                                     api=api, wachtrij=wachtrij, lopend=lopend, start_kind=start_kind,
                                                     maak_verzoek=ChatRequest)
                return list(await asyncio.gather(*(kind(i, t) for i, t in enumerate(plan.taken))))
            finally:
                for taak in (hart, waker):
                    taak.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await taak
    finally:
        await wachtrij.put(None)


async def _draai_kind(index: int, taak: Taak, afloop: Afloop, span: Any, *, regie_id: str, run_id: str,
                      werkgebied_id: str, request: Any, user_id: str, api: Any, wachtrij: asyncio.Queue,
                      lopend: dict[int, Any], start_kind: StartKind, maak_verzoek: Any) -> Afloop:
    begin = time.perf_counter()
    try:
        gesprek = await api.maak_gesprek({"titel": taak.titel, "werkgebied_id": werkgebied_id,
                                          "ouder_id": request.conversation_id or "", "delegatie_id": regie_id})
        afloop.gesprek_id = str(gesprek["id"])
        await wachtrij.put({"type": "regie_taak", "fase": "start", "regie_id": regie_id, "index": index,
                            "titel": taak.titel, "gesprek_id": afloop.gesprek_id})
        verzoek = maak_verzoek(**kind_verzoek(taak, werkgebied_id=werkgebied_id, gesprek_id=afloop.gesprek_id))
        kind_run = await start_kind(verzoek, user_id, run_id)
        afloop.run_id = kind_run.run_id
        if hasattr(span, "set_attribute"):
            span.set_attribute("run_id", kind_run.run_id)
        lopend[index] = kind_run
        await kind_run.taak
        afloop.uitkomst = kind_run.uitkomst or kind_run.status or "klaar"
    except Exception as fout:  # noqa: BLE001 – één kind mag de regie niet breken
        detail = getattr(fout, "detail", None)
        if isinstance(detail, dict) and detail.get("reden") == "budget_op":
            afloop.uitkomst = "budget_op"
        else:
            afloop.uitkomst, afloop.reden = "mislukt", type(fout).__name__
            logger.warning("regie: een kind mislukte", exc_info=True,
                           extra={"categorie": "technisch", "regie_id": regie_id, "index": index})
    finally:
        lopend.pop(index, None)
    logger.info("regie_taak", extra={"categorie": "functioneel", "regie_id": regie_id, "ouder_run_id": run_id,
                                     "run_id": afloop.run_id, "index": index, "uitkomst": afloop.uitkomst,
                                     "duur_ms": round((time.perf_counter() - begin) * 1000)})
    await wachtrij.put({"type": "regie_taak", "fase": "eind", "regie_id": regie_id, "index": index,
                        "titel": taak.titel, "gesprek_id": afloop.gesprek_id, "uitkomst": afloop.uitkomst})
    return afloop


async def _zoek_eenmaal(werkgebied_id: str, run: Any, *, settings: Any, user_id: str, api: Any, graph: Any) -> str:
    """De zoekrun één keer vooraf, zodat de kinderen niet op elkaar wachten. Leeg als het lukte."""
    from ..agents import Context
    from ..bronnen_run import zoek_run
    eigen = graph is None
    if eigen:
        from ..adapters.graphdb_graph import make_graph
        graph = make_graph(settings)
    try:
        ctx = Context(api=api, settings=settings, user_id=user_id, run_id=getattr(run, "run_id", ""), graph=graph,
                      gestopt=lambda: bool(getattr(run, "stop_gevraagd", False)))
        return await zoek_run(ctx, werkgebied_id)
    finally:
        if eigen:
            with contextlib.suppress(Exception):
                graph.close()


async def _hartslag(api: Any, werkgebied_id: str, regie_id: str, elke_s: float) -> None:
    while True:
        await asyncio.sleep(elke_s)
        with contextlib.suppress(Exception):
            await api.wijzig_delegatie(regie_id, {"status": "loopt"})


async def _stopwacht(stop: Callable[[], bool], lopend: dict[int, Any], stop_kind: StopKind) -> None:
    """Is de regie gestopt, dan stoppen de kinderen die lopen; wie nog wacht, start niet (`kind`). Hij blijft kijken
    tot de regie klaar is: een kind dat net startte toen de stop kwam, stopt dan alsnog."""
    gestopt: set[str] = set()
    while True:
        if stop():
            for kind_run in list(lopend.values()):
                if kind_run.run_id not in gestopt:
                    gestopt.add(kind_run.run_id)
                    with contextlib.suppress(Exception):
                        await stop_kind(kind_run)
        await asyncio.sleep(STOP_PEIL_S)
