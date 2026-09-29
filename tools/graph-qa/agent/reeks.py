"""Een reeks: meerdere onderdelen van één artikel in één run, na elkaar.

De jurist vinkt op de keuzekaart leden (of subbepalingen) aan; de werkplek start daarvoor **één**
run met `doelen`. Hier draait per onderdeel de gewone beurt – dezelfde keten, hetzelfde
vastleggen – zodat elk lid een eigen laag, batch, review en hergebruik houdt. Wat de reeks zelf
toevoegt:

- **Eén artikel.** Vooraf toetst `bronmodel.gedeelde_bepaling` tegen de brongraaf dat alle doelen
  onderdelen van dezelfde bepaling zijn. Meer artikelen samen is een werkgebied, een andere functie.
- **Indeling van de eventstroom.** `reeks` (start/eind) om het geheel, `onderdeel` (start/eind) om
  elk lid, en elk event daartussen draagt `onderdeel: <bron_iri>`. De tussentijdse `done` van een
  beurt wordt ingeslikt; de reeks eindigt met één `done`.
- **Stoppen en budget per onderdeel.** Vóór elk volgend onderdeel: is er om stoppen gevraagd, of is
  het tokenbudget op? Dan stopt de reeks en zegt ze welke onderdelen niet meer aan bod kwamen. Een
  lopend onderdeel maakt altijd af – een halve annotatie is erger dan een kleine overschrijding.
- **Een fout in één onderdeel stopt de rest niet.** Hij wordt bij dat onderdeel gemeld.

Beide SSE-wegen (`/v1/runs` en `/v1/chat`) gebruiken `reeks_stroom`; ze verschillen alleen in hoe
één beurt draait (met of zonder vastleggen).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from bronmodel import BronFout, gedeelde_bepaling, resolve

from .agent_common import run_sync

logger = logging.getLogger("graph_qa.reeks")

# Eén beurt voor één onderdeel: (doel, index) → eventstroom. Het `done` aan het eind hoort erbij.
BeurtFabriek = Callable[[dict[str, Any], int], AsyncIterator[dict[str, Any]]]


class DeelRun:
    """De run zoals één onderdeel hem ziet: een eigen `run_id` (`<run>.<n>`), hetzelfde stopverzoek.

    Het eigen id is nodig omdat de api op `run_id` ontdubbelt – batch, chatbericht en verbruik. Met
    het id van de hele reeks zou alleen het eerste lid bewaard en geboekt worden."""

    def __init__(self, run, index: int) -> None:
        self._run = run
        self.run_id = f"{run.run_id}.{index + 1}"

    @property
    def stop_gevraagd(self) -> bool:
        return bool(self._run.stop_gevraagd)


def _label(doel: dict[str, Any]) -> str:
    return str(doel.get("label") or doel.get("bron_iri") or "")


async def controleer(doelen: list[dict[str, Any]], graph) -> dict[str, Any]:
    """De bepaling waar de reeks over gaat, of een `BronFout`. Eén graafbevraging voor de hele
    regeling; daarna is het rekenwerk."""
    snapshot = await run_sync(lambda: resolve(graph.sparql, bron_iri=doelen[0]["bron_iri"]))
    return gedeelde_bepaling(snapshot["nodes"], [d["bron_iri"] for d in doelen])


async def reeks_stroom(
    doelen: list[dict[str, Any]],
    *,
    run_id: str,
    beurt: BeurtFabriek,
    ouder: dict[str, Any],
    stop_gevraagd: Callable[[], bool] = lambda: False,
    budget_toegestaan: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    totaal = len(doelen)
    yield {"type": "reeks", "fase": "start", "run_id": run_id, "totaal": totaal,
           "ouder": {"bron_iri": ouder["bron_iri"], "label": ouder.get("label", "")},
           "onderdelen": [{"bron_iri": d["bron_iri"], "label": _label(d)} for d in doelen]}
    klaar: list[str] = []
    reden = ""
    for index, doel in enumerate(doelen):
        if index and stop_gevraagd():
            reden = "gestopt"
            break
        if index and budget_toegestaan is not None and not await budget_toegestaan():
            reden = "budget_op"
            break
        iri = doel["bron_iri"]
        yield {"type": "onderdeel", "fase": "start", "index": index, "totaal": totaal,
               "bron_iri": iri, "label": _label(doel)}
        uitkomst, voorstellen, fout = "klaar", 0, ""
        try:
            async for event in beurt(doel, index):
                soort = event.get("type")
                if soort == "done":
                    continue
                if soort == "element":
                    voorstellen += 1
                elif soort == "hergebruik" and (event.get("hergebruik") or {}).get("volledig"):
                    uitkomst = "hergebruik"
                elif soort == "error":
                    uitkomst, fout = "fout", str(event.get("message") or "")
                yield {**event, "onderdeel": iri}
        except Exception:  # noqa: BLE001 – één onderdeel mag de reeks niet meenemen
            logger.exception("onderdeel van een reeks mislukt", extra={"run_id": run_id, "bron_iri": iri})
            uitkomst, fout = "fout", "Dit onderdeel kon niet worden geannoteerd."
            yield {"type": "error", "message": fout, "onderdeel": iri}
        if uitkomst == "klaar" and stop_gevraagd():
            uitkomst = "gestopt"
        klaar.append(iri)
        yield {"type": "onderdeel", "fase": "eind", "index": index, "totaal": totaal, "bron_iri": iri,
               "uitkomst": uitkomst, "voorstellen": voorstellen, **({"fout": fout} if fout else {})}
        if uitkomst == "gestopt":
            reden = "gestopt"
            break
    overgeslagen = [d["bron_iri"] for d in doelen if d["bron_iri"] not in klaar]
    yield {"type": "reeks", "fase": "eind", "run_id": run_id, "totaal": totaal, "verwerkt": len(klaar),
           "overgeslagen": overgeslagen, **({"reden": reden} if reden else {})}
    yield {"type": "done"}


async def reeks_run(
    request,
    run=None,
    *,
    settings,
    user_id: str = "",
    legt_vast: bool = True,
    graph=None,
    llm=None,
    annotaties=None,
    budget_toegestaan: Callable[[], Awaitable[bool]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """De eventstroom van een reeks voor `request.doelen`.

    `legt_vast`: via `/v1/runs` legt elke beurt zijn uitkomst vast (`voer_beurt_uit`); via
    `/v1/chat` niet – dezelfde verdeling als bij een gewone beurt. `graph`, `llm` en `annotaties`
    zijn er voor tests; in productie bouwt elke beurt ze zelf.
    """
    from .agent import answer_stream
    from .beurt import voer_beurt_uit
    from .models import Verbruiksmeter

    doelen = [d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in request.doelen]
    run_id = getattr(run, "run_id", "") or ""
    stop = (lambda: bool(run.stop_gevraagd)) if run is not None else (lambda: False)

    controle = graph
    if controle is None:
        from .adapters.graphdb_graph import make_graph
        controle = make_graph(settings)
    try:
        await run_sync(controle.initialize)
        ouder = await controleer(doelen, controle)
    except BronFout as fout:
        for event in weigering(fout):
            yield event
        return
    except Exception:  # noqa: BLE001
        logger.exception("reeks: brongraaf niet bereikbaar", extra={"run_id": run_id})
        yield {"type": "error", "message": "De brongraaf is nu niet bereikbaar; probeer het zo opnieuw."}
        yield {"type": "done"}
        return
    finally:
        if graph is None:
            controle.close()

    if budget_toegestaan is None and legt_vast and settings.legt_zelf_vast and user_id:
        budget_toegestaan = _budget_poort(settings, user_id)

    def beurt(doel: dict[str, Any], index: int) -> AsyncIterator[dict[str, Any]]:
        deel = DeelRun(run, index) if run is not None else None
        meter = Verbruiksmeter()
        stroom = answer_stream(
            f"Annoteer {_label(doel)}", request.conversation_id,
            doel=doel, hergebruik=request.hergebruik, settings=settings, llm=llm, graph=graph,
            annotaties=annotaties, user_id=user_id, run_id=deel.run_id if deel else "",
            stop_check=stop, meter=meter,
        )
        if not legt_vast or deel is None:
            return stroom
        return voer_beurt_uit(stroom, settings=settings, run=deel, gesprek_id=request.conversation_id or "",
                              user_id=user_id, meter=meter,
                              reeks={"run_id": run_id, "index": index, "totaal": len(doelen),
                                     "ouder": ouder.get("label", "")})

    async for event in reeks_stroom(doelen, run_id=run_id, beurt=beurt, ouder=ouder,
                                    stop_gevraagd=stop, budget_toegestaan=budget_toegestaan):
        yield event


def _budget_poort(settings, user_id: str) -> Callable[[], Awaitable[bool]]:
    """Dezelfde poort als vóór een run (`api/main._budget_check`), maar dan vóór elk volgend
    onderdeel. Fail-open, net als daar: een haperende boekhouding legt het werk niet stil."""
    from .wetsanalyse_api import WetsanalyseApi

    async def toegestaan() -> bool:
        api = WetsanalyseApi(settings, user_id)
        try:
            ok, _stand = await api.budget_toegestaan()
            return bool(ok)
        except Exception:  # noqa: BLE001
            logger.warning("reeks: budget niet te controleren", exc_info=True)
            return True
        finally:
            await api.aclose()
    return toegestaan


def weigering(fout: BronFout | str) -> list[dict[str, Any]]:
    """Wat een reeks zegt die niet mag beginnen – als gewone beurt: tekst, geen onderdelen."""
    melding = f"Deze reeks kan ik niet annoteren: {fout}."
    return [{"type": "token", "content": melding}, {"type": "done"}]
