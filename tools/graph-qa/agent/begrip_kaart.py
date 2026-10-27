"""Lex naast de kaart: één actie op één begrip, als voorstel per veld (spoor D, fase E).

`kaart_stroom` (via `kaart_beurt.kaart_kern`, een taak van de begrippen-agent): haal de run met invoer
bij de api (`GET …/begrippen/{id}/kaart-runs/{run}?invoer=true`), meld `…/loopt`, reken, en zet de
voorstellen terug (`PUT …/uitkomst`); de api toetst de garanties opnieuw. Het patroon van
`bronnen_run.py`. Het eigen endpoint `/v1/kaart-runs` is met F3e vervallen.

- **Zoek de brondefinitie** kost geen model: een graafquery op `bwb:definieertBegrip` voor de naam en de
  alternatieve termen, en per treffer zijn plaats (`plaats`): in het werkgebied, in een regeling van
  het werkgebied, in een regeling waar een begripsbepaling van het werkgebied naar verwijst
  (`q_verwezen`), of elders. Geen budgetpoort.
- **Scherper, uitleg, betekenisverschil en voorbeelden** gebruiken het model (`begrippen_pipeline/kaartacties.py`),
  op `LLM_MODEL`: een oordeel over wetgeving. Vooraf de budgetpoort; het verbruik wordt geboekt op
  `kaart-<run>`, ook als de actie faalt.
- **Elk faalpad is zichtbaar**: run niet op te halen, graaf of model faalt, de api weigert de
  voorstellen, budget op, gestopt → `error` (of stil `done` bij stoppen) en `…/mislukt` bij de api.
- **Lege uitkomst is een antwoord**: geen brondefinitie, geen scherpere definitie – de api bewaart de
  `melding` bij de run, en de werkplek toont die.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Awaitable, Callable

from .begrippen_pipeline import kaartacties as ka
from .begrippen_run import manifest_uit, onderzoek_uit
from .bronnen_vinden import _bwb, _rijen, in_selectie
from .config import Settings
from .graph.queries import BEVAT, NS, PREFIXES, _lit
from .ports import GraphPort
from .wetsanalyse_api import WetsanalyseApi, WetsanalyseApiFout

logger = logging.getLogger("graph_qa.begrip_kaart")

MODEL_ACTIES = {"scherper", "uitleg", "betekenisverschil", "voorbeelden"}
NAAM = {"brondefinitie": "Brondefinitie zoeken", "scherper": "Scherpere definitie", "uitleg": "Uitleg in B1",
        "betekenisverschil": "Betekenisverschil", "voorbeelden": "Voorbeelden"}
MAX_TREFFERS = 40


# --- de graaf (brondefinitie) ------------------------------------------------------------------

def q_brondefinities(termen: list[str], limit: int = MAX_TREFFERS) -> str:
    waarden = ", ".join(_lit(t) for t in termen)
    return PREFIXES + f"""SELECT DISTINCT ?node ?begrip ?tekst ?aanhef WHERE {{
  ?node bwb:definieertBegrip ?begrip .
  FILTER(STRSTARTS(STR(?node), {_lit(NS)}))
  FILTER(LCASE(STR(?begrip)) IN ({waarden}))
  ?node bwb:tekst ?tekst .
  OPTIONAL {{ ?ouder ({BEVAT}) ?node . ?ouder bwb:tekst ?aanhef }}
}} ORDER BY ?node LIMIT {limit + 1}"""


def q_verwezen(bwb_ids: list[str], limit: int = 200) -> str:
    """De regelingen waar een begripsbepaling uit deze regelingen naar verwijst (IW art. 2 → AWR)."""
    filters = " || ".join(f"STRSTARTS(STR(?vanuit), {_lit(NS + b + ':')})" for b in sorted(set(bwb_ids)))
    return PREFIXES + f"""SELECT DISTINCT ?naar WHERE {{
  ?vanuit bwb:definieertBegrip ?d ; bwb:heeftVerwijzing ?v .
  ?v bwb:naar ?naar .
  FILTER({filters})
  FILTER(STRSTARTS(STR(?naar), {_lit(NS)}))
}} LIMIT {limit}"""


def plaats(bron_iri: str, selecties: list[str], regelingen: set[str], verwezen: set[str]) -> str:
    if in_selectie(bron_iri, selecties):
        return "werkgebied"
    if _bwb(bron_iri) in regelingen:
        return "regeling"
    if _bwb(bron_iri) in verwezen:
        return "definitieverwijzing"
    return "elders"


def zoek_brondefinities(graph: GraphPort, invoer: dict[str, Any]) -> ka.Uitkomst:
    from .overzicht import definitie_vindplaats
    from .regelingnamen import regelingnamen

    inhoud = invoer["begrip"]["inhoud"]
    termen = ka.termen(inhoud)
    if not termen:
        return ka.Uitkomst(melding="Het begrip heeft geen naam om op te zoeken.")
    selecties = [s["bron_iri"] for s in invoer.get("selecties") or []]
    regelingen = {_bwb(s) for s in selecties if _bwb(s)}
    rijen = _rijen(graph, q_brondefinities(termen))
    verwezen = {_bwb(r["naar"]) for r in _rijen(graph, q_verwezen(sorted(regelingen)))} - regelingen \
        if regelingen else set()
    namen = regelingnamen(graph, {_bwb(r["node"]) for r in rijen})
    per_node: dict[str, ka.Treffer] = {}
    for r in rijen[:MAX_TREFFERS]:
        iri = r["node"]
        if iri in per_node and not r.get("aanhef"):
            continue
        plek = definitie_vindplaats(iri) or iri
        naam = namen.get(_bwb(iri))
        per_node[iri] = ka.Treffer(bron_iri=iri, tekst=r.get("tekst", ""), aanhef=r.get("aanhef", ""),
                                   vindplaats=f"{plek} – {naam}" if naam else plek,
                                   term=r.get("begrip", "").strip(), plaats=plaats(iri, selecties, regelingen, verwezen))
    voorstellen = ka.brondefinities(list(per_node.values()), huidig=inhoud.get("definitie", ""))
    if voorstellen:
        return ka.Uitkomst(voorstellen=voorstellen)
    return ka.Uitkomst(melding=ka.geen_definitie_melding(list(per_node.values()), termen))


# --- het model ------------------------------------------------------------------------------------

def reken_met_model(llm: Any, model: str, invoer: dict[str, Any], meting: dict[str, int]) -> ka.Uitkomst:
    manifest = manifest_uit(invoer["manifest"])
    onderzoek = onderzoek_uit(invoer.get("onderzoek"), manifest)
    kant = ka.kant_uit({**invoer["begrip"], "leden": invoer.get("leden") or []}, manifest)
    actie = invoer["actie"]
    if actie == "scherper":
        return ka.scherper(llm, model, manifest, kant, meting, onderzoek)
    if actie == "voorbeelden":
        return ka.voorbeelden(llm, model, manifest, kant, meting)
    if actie == "uitleg":
        return ka.uitleg(llm, model, manifest, kant, meting)
    ander = ka.kant_uit(invoer.get("ander"), manifest)
    if ander is None:
        return ka.Uitkomst(melding="Er is geen begrip om mee te vergelijken.")
    return ka.verschil(llm, model, manifest, kant, ander, meting, onderzoek)


# --- de stroom ------------------------------------------------------------------------------------

def _status(bericht: str) -> dict[str, Any]:
    return {"type": "status", "message": f"Lex · {bericht}"}


def _graaf(settings: Settings) -> GraphPort:
    from .adapters.graphdb_graph import make_graph
    return make_graph(settings)


def _anthropic(settings: Settings) -> Any:
    from .adapters.anthropic_llm import AnthropicLLM
    return AnthropicLLM(settings)


async def kaart_stroom(werkgebied_id: str, begrip_id: str, api_run_id: str, run: Any, *, settings: Settings,
                       user_id: str, graph: GraphPort | None = None, maak_llm: Callable[[Any], Any] | None = None,
                       budget_toegestaan: Callable[[], Awaitable[bool]] | None = None,
                       api: WetsanalyseApi | None = None) -> AsyncIterator[dict[str, Any]]:
    """`graph`, `maak_llm`, `budget_toegestaan` en `api` zijn er voor tests."""
    from .begrippen_verdieping import _boek
    from .reeks import _budget_poort

    eigen_api = api is None
    api = api or WetsanalyseApi(settings, user_id)

    async def mislukt(reden: str) -> None:
        try:
            await api.meld_kaart_mislukt(werkgebied_id, begrip_id, api_run_id, reden)
        except Exception:  # noqa: BLE001 – de api ziet de run anders na vijf minuten als vastgelopen
            logger.warning("mislukte kaartrun niet gemeld", exc_info=True)

    def gestopt() -> bool:
        return run is not None and bool(run.stop_gevraagd)

    try:
        try:
            data = await api.haal_kaartrun(werkgebied_id, begrip_id, api_run_id)
            await api.meld_kaart_loopt(werkgebied_id, begrip_id, api_run_id)
        except WetsanalyseApiFout as fout:
            yield {"type": "error", "message": "Lex kon niet beginnen: de opdracht is niet op te halen.",
                   "soort": "api", "status": fout.status}
            return
        invoer = data["invoer"]
        actie = invoer["actie"]
        naam = invoer["begrip"]["inhoud"].get("naam", "")
        yield _status(f"{NAAM.get(actie, actie)} voor “{naam}”")
        if gestopt():
            await mislukt("Gestopt op verzoek.")
            yield {"type": "done"}
            return

        model, llm, meting = "", None, {"llm_calls": 0}
        if actie in MODEL_ACTIES:
            if budget_toegestaan is None and settings.legt_zelf_vast and user_id:
                budget_toegestaan = _budget_poort(settings, user_id)
            if budget_toegestaan is not None and not await budget_toegestaan():
                await mislukt("Het tokenbudget is op.")
                yield {"type": "error", "message": "Je tokenbudget voor deze periode is op.", "soort": "budget"}
                return
            model = settings.llm_model
            llm = (maak_llm or _anthropic)(settings)

        def reken() -> ka.Uitkomst:
            if actie not in MODEL_ACTIES:
                g = graph or _graaf(settings)
                try:
                    return zoek_brondefinities(g, invoer)
                finally:
                    if graph is None:
                        g.close()
            return reken_met_model(llm, model, invoer, meting)

        try:
            uitkomst = await asyncio.to_thread(reken)
        except Exception as fout:  # noqa: BLE001 – een storing is een mislukte run, geen crash
            logger.exception("kaartrun mislukt", extra={"categorie": "technisch", "actie": actie})
            if llm is not None:
                await _boek(api, llm, model, "", f"kaart-{api_run_id}")
            await mislukt(f"{NAAM.get(actie, actie)} faalde: {type(fout).__name__}")
            yield {"type": "error", "message": ("De graaf is mogelijk niet bereikbaar." if llm is None else
                                                "Het model gaf geen antwoord; probeer het opnieuw."),
                   "soort": "graaf" if llm is None else "model"}
            return
        tokens = await _boek(api, llm, model, "", f"kaart-{api_run_id}") if llm is not None else 0
        if gestopt():
            await mislukt("Gestopt op verzoek.")
            yield {"type": "done"}
            return
        try:
            await api.zet_kaart_uitkomst(werkgebied_id, begrip_id, api_run_id, {
                "invoer_id": data["invoer_id"], "voorstellen": uitkomst.voorstellen, "melding": uitkomst.melding,
                "model": model, "promptversie": ka.promptversie(actie), "tokens": tokens, "meting": meting})
        except WetsanalyseApiFout as fout:
            await mislukt(f"Opslaan geweigerd ({fout.status}): {fout.reden}")
            yield {"type": "error", "message": "Lex had een voorstel, maar de api weigerde het op te slaan.",
                   "soort": "api", "status": fout.status}
            return
        if uitkomst.voorstellen:
            n = len(uitkomst.voorstellen)
            yield _status(f"{n} {'voorstel' if n == 1 else 'voorstellen'} bij de kaart")
        else:
            yield _status(uitkomst.melding or "Geen voorstel")
        yield {"type": "opgeslagen", "kaart_run": api_run_id, "voorstellen": len(uitkomst.voorstellen),
               "melding": uitkomst.melding}
        yield {"type": "done"}
    finally:
        if eigen_api:
            await api.aclose()
