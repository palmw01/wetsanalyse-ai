"""
Agent-instap: dunne wrapper rond de LangGraph-orkestrator (agent/orchestrator.py).

Behoudt de publieke `answer_stream`-signatuur en het SSE-event-contract, zodat de API
en frontend ongewijzigd blijven. De stroom (plan→retrieve→reason→verify→finalize) en de
token-streaming leven in de toestandsgraaf.

Geheugen loopt via de LangGraph-checkpointer (thread_id = conversation_id). Backend-keuze
(voorrang): `checkpoint_db_url` → **Postgres** (AsyncPostgresSaver; gedeeld tussen replica's,
horizontaal veilig) → `checkpoint_db_path` → **SQLite** (durable file, maar per-instance) →
anders in-proces (MemorySaver). De wrapper reset per beurt de werkvelden en levert de nieuwe
user-message; de append-reducer plakt die aan de gepersisteerde historie.
"""
from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langgraph.errors import GraphRecursionError

from .agent_common import BeurtGestopt, run_sync
from .config import Settings
from .beurtmeting import route_van
from .models import Verbruiksmeter
from .observability import get_tracer
from .ports import GraphPort, LLMPort
from .tools.annotatie_tools import is_leesvraag
from .agentvorm import vorm_van

logger = logging.getLogger(__name__)


def _checkpointer_ctx(settings: Settings):
    """Async context manager die de gekozen checkpointer levert. Voorrang: Postgres (gedeeld →
    horizontaal veilig) → SQLite-bestand (durable, per-instance) → in-memory."""
    url = settings.checkpoint_db_url
    if url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        @asynccontextmanager
        async def _pg():
            async with AsyncPostgresSaver.from_conn_string(url) as saver:
                await saver.setup()  # idempotent: maakt de checkpoint-tabellen als ze ontbreken
                yield saver

        return _pg()

    path = settings.checkpoint_db_path
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).parent.parent / p  # stabiel t.o.v. cwd (graph-qa-root)
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        return AsyncSqliteSaver.from_conn_string(str(p))

    from langgraph.checkpoint.memory import MemorySaver

    @asynccontextmanager
    async def _mem():
        yield MemorySaver()

    return _mem()


#: Hoe de provider een te grote vraag noemt. De statuscode zegt dat niet: elke 400 is een
#: `BadRequestError`, ook een ongeldige berichtenreeks, en "begin een nieuw gesprek" is daar geen hulp.
_TE_LANG_RE = re.compile(r"too long|too large|too many tokens|maximum context|context length|exceed", re.IGNORECASE)


def _provider_fout(exc: Exception) -> tuple[str, str]:
    """Foutsoort en melding uit de body van de provider, voor zover die er is.

    Een fout midden in een stream komt binnen bij HTTP 200: de SDK maakt er een kale `APIStatusError`
    van, en alleen `body.error.type` zegt dan wat er aan de hand is."""
    body = getattr(exc, "body", None)
    fout = body.get("error") if isinstance(body, dict) else None
    if not isinstance(fout, dict):
        return "", str(getattr(exc, "message", "") or "")
    return str(fout.get("type") or ""), str(fout.get("message") or "")


def _foutmelding(exc: Exception) -> str:
    """Wat de jurist te zien krijgt als een beurt sneuvelt – per soort fout iets anders.

    De provider-uitzonderingen worden op naam herkend in plaats van geïmporteerd: de anthropic-SDK
    is een optionele extra (`--extra llm`), en deze module hoort ook te draaien in een omgeving die
    hem niet heeft.
    """
    soort = type(exc).__name__
    body_soort, bericht = _provider_fout(exc)
    if soort in ("RateLimitError", "OverloadedError", "ServiceUnavailableError") or body_soort in (
            "rate_limit_error", "overloaded_error"):
        return ("De modelprovider is momenteel overbelast. Probeer het over een halve minuut "
                "opnieuw – je vraag is niet verloren, hij is alleen niet uitgevoerd.")
    if soort == "RequestTooLargeError" or body_soort == "request_too_large" or (
            soort in ("BadRequestError", "UnprocessableEntityError") and _TE_LANG_RE.search(bericht)):
        return ("Deze beurt paste niet binnen de grenzen van het model – meestal is het gesprek te "
                "lang geworden. Begin een nieuw gesprek of stel de vraag gerichter.")
    if soort in ("BadRequestError", "UnprocessableEntityError"):
        return ("De modelprovider weigerde deze beurt door een technische fout. Probeer het opnieuw; "
                "blijft het misgaan, dan staat de oorzaak in het server-log.")
    if soort in ("APIConnectionError", "APITimeoutError"):
        return ("Ik kon de modelprovider niet bereiken. Probeer het zo opnieuw; blijft het "
                "misgaan, dan staat de oorzaak in het server-log.")
    return ("Er ging iets mis bij het beantwoorden. Probeer het opnieuw; "
            "blijft het misgaan, dan staat de oorzaak in het server-log.")


def _recursielimiet(settings: Settings) -> int:
    """Hoeveel LangGraph-stappen één beurt hoogstens mag zetten.

    Dit was `max_turns * 2 + 10` – een formule van vóór de annotatieketen, die alleen de
    agent⇄tools-lus telde. Met de default (20 beurten) kwam één annotatie-worker die zijn
    beurtlimiet vol gebruikt al op ~49 van de 50 stappen, en een keten van twee workers ging er
    zeker overheen. De uitkomst was bovendien onleesbaar: `GraphRecursionError` viel in de generieke
    `except` hieronder en werd "Er ging iets mis", terwijl het werk van tientallen calls weg was.

    Nu volgt de limiet de topologie: per worker de agent⇄tools-lus (2 stappen per beurt) plus de
    vaste nodes eromheen (supervisor/annoteer/emit/advance ≈ 6), maal het maximum aantal workers
    (`supervisor._MAX_WORKERS`), met marge.

    Dit is een vangnet, geen kostenknop: de echte begrenzing is `max_turns`.
    """
    from .supervisor import _MAX_WORKERS

    per_worker = 2 * settings.max_turns + 6
    return _MAX_WORKERS * per_worker + 10


async def delete_conversation(conversation_id: str, *, settings: Settings | None = None) -> None:
    """Wis het volledige agent-geheugen (checkpointer-thread) van één gesprek. Idempotent: een
    onbekende `conversation_id` is geen fout. Aangeroepen als de werkplek een gesprek verwijdert, zodat
    de inhoud niet in de checkpointer-DB achterblijft (privacy – parallel aan de API-berichten-delete)."""
    await delete_conversations([conversation_id], settings=settings)


async def delete_conversations(conversation_ids: list[str], *, settings: Settings | None = None) -> None:
    """Hetzelfde voor een reeks gesprekken (opruimen in de instellingen), in **één** checkpointer-context: per
    gesprek een nieuwe verbinding openen maakte 71 losse rondes van wat één ronde is."""
    if not conversation_ids:
        return
    settings = settings or Settings.from_env()
    async with _checkpointer_ctx(settings) as saver:
        # Zorg dat de checkpoint-tabellen bestaan (SQLite maakt ze anders pas bij de eerste write →
        # adelete_thread op een verse DB zou "no such table" geven). Idempotent; Postgres deed dit al.
        setup = getattr(saver, "setup", None)
        if setup is not None:
            try:
                await setup()
            except Exception:  # noqa: BLE001 – MemorySaver e.d. hebben geen tabellen
                pass
        for conversation_id in conversation_ids:
            await saver.adelete_thread(conversation_id)


async def _werkgebied_stand(settings: Settings, user_id: str, werkgebied_id: str) -> tuple[str, str]:
    """Het contextblok van het werkgebied (`werkgebied_context.als_blok`) en zijn peildatum (JJJJ-MM-DD). Zonder api of
    bij een storing allebei leeg: het dossier is context, geen voorwaarde om te antwoorden."""
    if not settings.legt_zelf_vast:
        return "", ""
    from .werkgebied_context import als_blok
    from .wetsanalyse_api import WetsanalyseApi

    api = WetsanalyseApi(settings, user_id)
    try:
        werkgebied = await api.haal_werkgebied(werkgebied_id)
        return als_blok(werkgebied), str(werkgebied.get("peildatum") or "").strip()
    except Exception:  # noqa: BLE001
        logger.warning("werkgebiedcontext niet opgehaald", extra={"categorie": "technisch"}, exc_info=True)
        return "", ""
    finally:
        await api.aclose()


async def _bronnen_van_beurt(settings: Settings, user_id: str, bronnen: list[str] | None,
                             herkomst: str | None = None) -> tuple[list[str] | None, dict[str, dict[str, Any]]]:
    """De bronconnectors van deze beurt en hun stand (ADR-013, `bronstand`): wat de beurt vraagt (of de straat
    aanbiedt), beperkt tot wat de beheerder in het register aanzette. Zonder connector in de straat of zonder api
    blijft de vraag zoals hij is. Een onleesbaar register zet niets aan: liever alleen wetgeving dan een bron die de
    beheerder uitzette."""
    from . import bronstand
    from .tools import actieve_connectors

    gevraagd = actieve_connectors(settings, bronnen)
    if not gevraagd or not settings.legt_zelf_vast:
        return bronnen, bronstand.bepaal(settings, bronnen, herkomst)
    from .wetsanalyse_api import WetsanalyseApi

    api = WetsanalyseApi(settings, user_id)
    try:
        register = set(await api.connectors())
    except Exception:  # noqa: BLE001
        logger.warning("connectorregister niet gelezen; alleen wetgeving", extra={"categorie": "technisch"},
                       exc_info=True)
        return [], bronstand.bepaal(settings, bronnen, herkomst, register_fout=True)
    finally:
        await api.aclose()
    return sorted(gevraagd & register), bronstand.bepaal(settings, bronnen, herkomst, register=register)


async def _onderwerp_blok(settings: Settings, user_id: str, onderwerp: dict[str, Any]) -> str:
    """Het contextblok van het aangewezen object (`onderwerp.haal`). Zonder api zegt het blok dat de
    gegevens ontbreken, met het label uit de werkplek."""
    from .onderwerp import als_blok, haal
    from .wetsanalyse_api import WetsanalyseApi

    # Een bepaling of stuk vraagt niets van de api: het blok zegt alleen wélk object het is (`onderwerp.haal`).
    if onderwerp.get("soort") in ("bepaling", "stuk"):
        return await haal(None, onderwerp)
    if not settings.legt_zelf_vast:
        return als_blok(onderwerp.get("soort", ""), None, onderwerp.get("label", ""))
    api = WetsanalyseApi(settings, user_id)
    try:
        return await haal(api, onderwerp)
    finally:
        await api.aclose()


async def answer_stream(
    question: str,
    conversation_id: str | None = None,
    *,
    modus: str = "auto",
    context: Any = None,
    doel: Any = None,
    settings: Settings | None = None,
    llm: LLMPort | None = None,
    graph: GraphPort | None = None,
    stop_check: Callable[[], bool] | None = None,
    meter: Verbruiksmeter | None = None,
    hergebruik: str = "auto",
    user_id: str = "",
    run_id: str = "",
    annotaties=None,
    begrippen=None,
    werkgebied_id: str = "",
    intake_actie: Any = None,
    onderwerp: Any = None,
    actie: str = "",
    bevestigd: int | None = None,
    werkvoorraad_id: str = "",
    agent_api: Any = None,
    bronnen: list[str] | None = None,
    bronnen_herkomst: str | None = None,
    beurtcontext_plek: str = "vraag",
    agentvorm: str | None = None,
    profiel: str = "",
    opdracht: Any = None,
    kinderen: Any = None,
    resultaat: dict[str, Any] | None = None,
    delegatie_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """
    Async generator die SSE-events yield:
      {"type": "status", "message": "..."}
      {"type": "token", "content": "..."}
      {"type": "sources", "sources": [...]}
      {"type": "grounding", "grounded": bool, "unsupported": [...]}
      {"type": "done"}
      {"type": "error", "message": "..."}
    """
    settings = settings or Settings.from_env()

    # Providers: injecteer voor tests, of bouw defaults uit Settings.
    try:
        if graph is None:
            from .adapters.graphdb_graph import make_graph

            graph = make_graph(settings)
        if llm is None:
            from .adapters.anthropic_llm import AnthropicLLM

            llm = AnthropicLLM(settings)
            # De aanroeper kan een eigen meter meegeven; die leest het verbruik ná afloop uit, ook
            # als deze beurt met een fout of een stopverzoek eindigt. Een SSE-event zou dat niet
            # halen: de foutpaden yielden geen verbruik meer, en de tokens zijn dan wél op.
            if meter is not None:
                llm.meter = meter
        try:
            await run_sync(graph.initialize)
        except Exception:
            if not is_leesvraag(question, modus):
                raise
            # Annotatiezoeken heeft een eigen API-poort. Een defecte brontool mag die read-route
            # niet uitschakelen; eventuele aanvullende brontools rapporteren hun eigen fout.
            logger.warning("brongraaf niet beschikbaar; annotatieleesroute blijft bereikbaar", exc_info=True)
    except Exception as exc:
        # Hetzelfde `try` bouwt ook de LLM-client, en de ruwe fout kan endpoints bevatten: de jurist krijgt
        # een vaste melding, het detail staat in het log. `soort` zoals bij elke andere fout.
        logger.warning("MCP-verbinding of modelclient mislukt", exc_info=True)
        yield {"type": "error", "soort": type(exc).__name__,
               "message": ("Ik kon de kennisgraaf of de modelprovider niet bereiken. Probeer het zo opnieuw; "
                           "blijft het misgaan, dan staat de oorzaak in het server-log.")}
        if graph is not None:
            graph.close()
        return

    from .orchestrator import build_graph

    # `kinderen` start en stopt een subagent langs de ene ingang (`api.main.start_beurt`, ADR-016 §A3); `resultaat`
    # krijgt na afloop wat een subagent opleverde, voor de ouder op deze replica.
    builder = build_graph(settings, llm, graph, stop_check=stop_check, annotaties=annotaties, begrippen=begrippen,
                          agent_api=agent_api, kinderen=kinderen)
    thread_id = conversation_id or uuid.uuid4().hex
    onderwerp_dict = onderwerp.model_dump() if hasattr(onderwerp, "model_dump") else dict(onderwerp or {})
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": _recursielimiet(settings),
    }
    # Per beurt: nieuwe user-message (append-reducer) + reset van de werkvelden.
    beurtbronnen, bronstand_nu = await _bronnen_van_beurt(
        settings, user_id, list(bronnen) if bronnen is not None else None, bronnen_herkomst)
    werkgebied_blok, werkgebied_peildatum = (await _werkgebied_stand(settings, user_id, werkgebied_id)
                                             if werkgebied_id else ("", ""))
    opdracht_dict = (opdracht.model_dump() if hasattr(opdracht, "model_dump") else dict(opdracht or {})) if profiel else {}
    init: dict[str, Any] = {
        "question": question,
        "run_id": run_id or uuid.uuid4().hex,
        "user_id": user_id,
        "annotaties_lezen": is_leesvraag(question, modus) and not opdracht_dict,
        "specialist": profiel if opdracht_dict else "annotaties_lezen" if is_leesvraag(question, modus) else "",
        "begrippen_lezen": False,
        "werkgebied_id": werkgebied_id or "",
        # De bronnen van deze beurt (ADR-013): toollaag en dispatch filteren erop; de stand zegt per connector waarom.
        "bronnen": beurtbronnen,
        "bronstand": bronstand_nu,
        # De meetvlag van ADR-015 (`ChatRequest.beurtcontext_plek`): waar de context van de beurt staat. Per beurt.
        "beurtcontext_plek": beurtcontext_plek,
        # De agentvorm van deze beurt (ADR-016 §A7): de straat beslist of het verzoek mag kiezen.
        "agentvorm": vorm_van(settings.centrale_agent, agentvorm),
        # Een subagent (ADR-016 §A3): de supervisor stuurt de beurt zonder model naar de agent met dit profiel.
        "opdracht": opdracht_dict,
        "rapport": {},
        "subagenten": [],
        "rapporten": "",
        # Een deelgesprek onthoudt zijn delegatie en profiel (ADR-016 §A4); alleen gezet met een opdracht, dus niet in de
        # per-beurt-reset: een latere beurt van de jurist in dit gesprek leest het.
        **({"deelgesprek": {"delegatie_id": delegatie_id, "profiel": profiel}} if opdracht_dict else {}),
        "overdracht_naar": "",
        "bron_lezen": [],
        "bron_lijst": {},
        # Het dossier van dat werkgebied, per beurt vers uit de api: elke bewaarde wijziging telt meteen.
        "werkgebied_context": werkgebied_blok,
        # Zijn peildatum: de vaste lijstroute geeft hem mee aan een zoektool die er een kent (meting 11 nov 2026).
        "werkgebied_peildatum": werkgebied_peildatum,
        # Waar de analist *Vraag Lex* op koos: alleen deze beurt; het object blijft in de focus.
        "onderwerp": onderwerp_dict,
        "onderwerp_context": await _onderwerp_blok(settings, user_id, onderwerp_dict) if onderwerp_dict else "",
        # Een klik op een suggestie, en wat de agent deed (F3c): alleen deze beurt.
        "actie": actie or "",
        "bevestigd": bevestigd,
        "werkvoorraad_id": werkvoorraad_id or "",
        "agent_taak": {},
        "agent_uitkomst": {},
        "gesprek_id": conversation_id or "",
        "bron_snapshot": {},
        "annotatie_weergave": {},
        "corpus_segmenten": [],
        "hergebruikte_nodes": [],
        "annotatie_fout": "",
        "messages": [{"role": "user", "content": question}],
        "zelfstandige_vraag": "",
        # Een overzicht hoort bij de vraag die erom vroeg: bleef het staan, dan kreeg de volgende
        # vraag in dezelfde thread het blok en de bronnen van de vorige.
        "overzicht_route": False,
        "overzicht": {},
        "bepalingsvraag": {},
        "antwoord": {},
        "modus": modus,
        "context": context.model_dump() if hasattr(context, "model_dump") else (context or {}),
        # Het doel dat de aanroeper meegaf – MOET mee in de reset, net als de annotatievelden
        # hieronder: bleef het staan, dan annoteert de vólgende vraag in dezelfde thread opnieuw
        # de vorige bepaling zonder dat iemand daarom vroeg.
        "opgegeven_doel": doel.model_dump() if hasattr(doel, "model_dump") else (doel or {}),
        # Een klik op een vraagkaartje geldt alleen deze beurt; de intake zelf blijft staan.
        "intake_actie": (intake_actie.model_dump() if hasattr(intake_actie, "model_dump")
                         else (intake_actie or {})),
        "intake_modus": "",
        "source_trace": [],
        "turns": 0,
        "corrected": False,
        "sjabloon_gevraagd": False,
        "sjabloon_nu": False,
        "sjabloon_telling": {},
        "afgekapt": False,
        "onbevestigd": [],
        "beweringen": [],
        "answer": "",
        # Een afwijzing geldt de vráág, niet het gesprek. Bleef deze vlag staan, dan werd elke
        # volgende beurt in dezelfde thread ook afgewezen – dezelfde soort fout als een blijvend
        # corpus hieronder.
        "afwijzen": False,
        "afwijs_melding": "",
        "afwijs_stap": "",
        # Annotatie-velden: MOETEN mee in de reset. De checkpointer bewaart de state per thread, dus
        # zonder dit annoteert een tweede vraag in hetzelfde gesprek tegen de tekst of de voorstellen
        # van de vórige bepaling – precies de verwisseling die de gerichte ophaal moet uitsluiten.
        "corpus": "",
        "hergebruik_modus": hergebruik,
        "hergebruik": {},
        "voorstellen": [],
        "analyse": {},
    }

    tracer = get_tracer(__name__)
    grounded = True
    laatste: dict[str, Any] = {}
    if any(s["reden"] != "straat" for s in bronstand_nu.values()):
        # Vóór alles: de werkplek en de meting weten zo welke bronnen deze beurt had, en waarom niet. Biedt de straat
        # geen connector aan, dan is er niets te melden en blijft de stroom gelijk aan een straat zonder connectors.
        from .bronstand import event as bronstand_event
        yield bronstand_event(bronstand_nu)
    try:
        async with _checkpointer_ctx(settings) as saver:
            app = builder.compile(checkpointer=saver)
            with tracer.start_as_current_span("graph_qa.answer") as span:
                async for mode, chunk in app.astream(init, config=config, stream_mode=["custom", "values"]):
                    if mode == "custom":
                        yield chunk
                    elif mode == "values":
                        laatste = chunk
                        grounded = chunk.get("grounded", grounded)
                        if meter is not None:
                            meter.route = route_van(chunk)
                            meter.sjabloon = chunk.get("sjabloon_telling") or {}
                span.set_attribute("graph_qa.grounded", grounded)
                if resultaat is not None and laatste:
                    # Wat de ouder van een subagent leest (`agent/subagent.py`): het rapport en de toolresultaten, nooit
                    # modeltekst die niet door de controle ging.
                    resultaat.update(rapport=laatste.get("rapport") or {}, antwoord=laatste.get("antwoord") or {},
                                     answer=laatste.get("answer") or "", grounded=grounded,
                                     source_trace=[tuple(x) for x in laatste.get("source_trace") or []])
                logger.info(
                    "antwoord klaar",
                    extra={"grounded": grounded, "chat_session_id": conversation_id or ""},
                )

            # Yield done BINNEN de checkpointer-context: anders kan AsyncSqliteSaver.__aexit__
            # (SQLite-commit/flush) de generator blokkeren vóórdat 'done' de client bereikt.
            if conversation_id:
                yield {"type": "conversation_id", "conversation_id": conversation_id}
            yield {"type": "done"}

    except BeurtGestopt:
        # Geen fout: de jurist vroeg om te stoppen en de graaf is op een nodegrens uitgestapt. Wat er
        # tot hier geëmit is, is gewoon geldig; de aanroeper legt het vast.
        logger.info(
            "beurt gestopt op verzoek",
            extra={"categorie": "functioneel", "chat_session_id": conversation_id or ""},
        )
        if conversation_id:
            yield {"type": "conversation_id", "conversation_id": conversation_id}
        yield {"type": "done"}
    except GraphRecursionError:
        # Eigen melding: dit is geen storing maar een beurt die te lang werd, en de gebruiker kan er
        # zelf iets mee (gerichter vragen). Onder de generieke tekst hieronder was niet te zien
        # waaróm er niets kwam.
        logger.warning(
            "beurt raakte de stappenlimiet",
            extra={"categorie": "functioneel", "chat_session_id": conversation_id or "",
                   "recursion_limit": config["recursion_limit"]},
        )
        yield {
            "type": "error",
            "message": "Deze beurt werd te lang en is afgebroken. Stel de vraag gerichter – "
                       "bijvoorbeeld met een specifiek artikel of lid.",
        }
    except Exception as exc:
        # Gesaniteerde melding naar de client, volledige fout alleen in het log – zoals de api dat
        # bij de modelprovider-test doet. De ruwe exception van een LLM- of MCP-fout bevat
        # request-details (endpoints, payload-fragmenten) die niet in de browser thuishoren.
        #
        # Wél onderscheid maken waar de gebruiker er iets mee kan. "Er ging iets mis" gooide drie
        # gevallen op één hoop die om verschillende dingen vragen: even wachten, korter vragen, of
        # een storing melden. De statusregels van deze agent zijn elders juist precies; een
        # foutmelding hoort dat ook te zijn.
        logger.error("agent-fout", exc_info=True)
        # `soort` draagt de EXCEPTION-NAAM mee, naast de gesaniteerde melding. De melding zelf is
        # voor de jurist en zegt bewust niets technisch; zonder `soort` is achteraf niet te zien of
        # een beurt sneuvelde op de analyse of op een overbelaste provider, en telt de eval een
        # `overloaded_error` als een gezakte case — een storing die leest als een
        # kwaliteitsregressie.
        #
        # Additief op het SSE-contract: consumenten die het veld niet kennen negeren het. Geen
        # request-details, alleen de klasse-naam — die lekt niets.
        yield {"type": "error", "message": _foutmelding(exc), "soort": type(exc).__name__}
    finally:
        graph.close()
