"""
LangGraph-orkestrator: plan → retrieve → reason → verify → finalize.

LangGraph levert het toestandsgraaf-substraat (nodes, conditionele edges, streaming,
checkpointing); de domeinlogica blijft die van Fase 1/2 – de nodes roepen de bestaande
LLMPort/GraphPort, de typed tool-registry, provenance en grounding aan. Geen
langchain-chatmodel: Azure Foundry blijft via AnthropicLLM.

Geheugen zit in de state en wordt door de checkpointer (thread_id = conversation_id)
gepersisteerd: `messages` (episodisch, append-reducer) en `entities_seen` (de "in
beeld"-set geraadpleegde bepalingen, semantische/entiteit-tier). De wrapper compileert
`build_graph()` met de gekozen checkpointer.

Streaming loopt via LangGraph's custom-stream (get_stream_writer); answer_stream
consumeert het en houdt het SSE-contract gelijk. Nodes zijn synchroon (threadpool),
zodat de blocking LLM-/MCP-calls de event-loop niet blokkeren.
"""
from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from .agent_common import BeurtGestopt, truncate
from .annotatie import (
    _verwerk, _verwerk_critic, demp_zelfweerspreking, komt_letterlijk_voor, pas_critic_toe,
    openstaand_voorstel, sleutel_van, vervang_ids_door_citaat,
    parse_kandidaten, filter_kandidaten,
)
from .doel import (  # noqa: F401 – re-export: tests importeren _kandidaten_uit_json hiervandaan
    _bepaal_doel,
    _corpus_uit_trace,
    _corpus_voor_doel,
    _doel_uit_json,
    _doel_uit_toolcalls,
    _heeft_opgegeven_doel,
    _kandidaten_uit_json,
    _ontbrekend_sleutel,
)
from .nodes.antwoord import (
    agent_node,
    correct_node,
    finalize_node,
    route_after_agent,
    route_after_verify,
    tools_node,
    verify_node,
)
from .nodes.context import Bouw
from .nodes.supervisie import (
    _entry_node,
    advance_node,
    afwijs_node,
    route_after_advance,
    supervisor_node,
)
from .nodes.decompositie import (
    decompose_node,
    resynth_node,
    route_after_solve,
    solve_node,
    synthesize_node,
)
from .berichten import (  # noqa: F401 – re-export: tests en node-modules importeren ze hiervandaan
    MAX_HISTORIE_CHARS,
    _msg_lengte,
    _parse_final,
    _schoon_messages,
    _snoei_historie,
    _trim_messages,
    _voeg_toe_en_snoei,
)
from .narratie import (  # noqa: F401 – re-export, zie hierboven
    _annoteer_melding,
    _critic_melding,
    _grounding_melding,
    _herzien_melding,
    _stap,
    _toolregel,
)
from .state import State
from .annotatie_prompt import (
    annotatie_systeemprompt,
    annotatie_userprompt,
    critic_systeemprompt,
    critic_userprompt,
    herziening_systeemprompt,
    herziening_userprompt,
    kandidaten_systeemprompt,
    kandidaten_userprompt,
    klasseer_systeemprompt,
    klasseer_userprompt,
)
from .config import Settings
from .models import AgentRun
from .ports import GraphPort, LLMPort

logger = logging.getLogger("graph_qa.orchestrator")



def build_graph(
    settings: Settings,
    llm: LLMPort,
    graph: GraphPort,
    stop_check: Callable[[], bool] | None = None,
) -> StateGraph:
    """Bouw de (ongecompileerde) toestandsgraaf; de wrapper compileert 'm met een checkpointer."""
    # `model` is het sterke model: annoteerder, Critic, herziener en de QA-specialisten. De router
    # en de ophaal-agent mogen apart worden gezet (`Settings.model_voor`); staat er niets, dan is
    # het alle drie hetzelfde en draait de keten exact als voorheen.
    model = settings.llm_model
    model_router = settings.model_voor("router")
    model_ophaal = settings.model_voor("ophaal")

    def _memory_context(state: State) -> str:
        if not settings.enable_memory_context:
            return ""
        seen = list(dict.fromkeys(state.get("entities_seen") or []))  # dedup, volgorde behouden
        if not seen:
            return ""
        lijst = "\n".join(f"- {u}" for u in seen[-12:])
        return (
            "\n\nGESPREKSCONTEXT – eerder in dit gesprek geraadpleegde bepalingen (alléén als "
            "aanknopingspunt voor verwijzingen als 'dat artikel'; verifieer elk feit opnieuw via "
            f"de tools):\n{lijst}"
        )

    def _corpus(state: State) -> str:
        """De tekst van deze annotatiebeurt. `annoteer_node` haalde hem gericht op en zette hem in de
        state; de terugval is er voor een state van vóór dit veld (een hervatte thread)."""
        return state.get("corpus") or _corpus_uit_trace(state.get("source_trace", []))

    def _advies_context(state: State) -> str:
        """Contextblok voor een adviesvraag: waar gaat het over, en wat mag de agent niet doen.

        De 'wijzig niets'-instructie is hier een toelichting, geen slot – dat slot is topologisch
        (deze route emit geen element-events). Het staat er zodat het antwoord de juiste vorm heeft:
        een onderbouwing, geen voorstel voor een nieuwe annotatie.
        """
        if state.get("modus") != "advies":
            return ""
        c = state.get("context") or {}
        regels = ["", "--- WAAR DE VRAAG OVER GAAT ---"]
        plek = " ".join(x for x in (c.get("bwbId", ""), f"art. {c['artikel']}" if c.get("artikel") else "",
                                    f"lid {c['lid']}" if c.get("lid") else "") if x)
        if plek:
            regels.append(f"Bepaling: {plek}")
        if c.get("klasse"):
            regels.append(f"Voorgestelde JAS-klasse: {c['klasse']}")
        if c.get("fragment"):
            regels.append(f'Fragment: "{c["fragment"]}"')
        if c.get("corpus"):
            regels.append(f"\nArtikeltekst:\n{truncate(str(c['corpus']), 6000)}")
        regels += [
            "--- EINDE ---",
            "",
            "Dit is een ADVIESVRAAG bij een bestaande JAS-annotatie. Geef uitsluitend onderbouwing en "
            "duiding; stel geen nieuwe annotatie voor en zeg niet dat je iets hebt gewijzigd.",
        ]
        # Zonder deze afbakening motiveert het model álle markeringen die het in de gesprekshistorie
        # ziet staan – de annotatiebeurt zit immers in dezelfde thread. Wie één element aanklikt en
        # "motiveer" vraagt, verwacht één motivering. De laatste zin is de tegenkracht tegen dat
        # geheugen: zonder die toevoeging pakt het model er alsnog zijn eerdere voorstellen bij.
        if c.get("fragment"):
            buren = [b for b in (c.get("bestaande_elementen") or []) if isinstance(b, dict)]
            regels += [
                "",
                # Niet "ONDERWERP": dat woord gebruikt de basis-systeemprompt al voor de
                # onderwerp-afbakening van de agent (wel/geen wetgevingsvraag).
                f'AFBAKENING VAN DEZE VRAAG – het gaat over dit ene fragment: "{c["fragment"]}". '
                "Motiveer alleen dat element.",
                "Een andere markering uit dezelfde bepaling mag je erbij halen wanneer die NODIG is om "
                "dit element te onderbouwen – samenhang, afbakening, of het rechtsgevolg waar een "
                "voorwaarde bij hoort. Houd dat kort en breng het terug naar het onderwerp.",
                "Geef die andere markeringen GEEN eigen motivering, ook niet als je ze eerder in dit "
                "gesprek hebt voorgesteld.",
            ]
            if buren:
                # Meesturen in plaats van op het geheugen vertrouwen: anders hangt het antwoord af van
                # wat er toevallig nog in de historie stond, en verschilt het per gesprek.
                regels += [
                    "",
                    "--- ANDERE MARKERINGEN IN DEZE BEPALING (niet motiveren; alleen ter ondersteuning) ---",
                ]
                for b in buren[:20]:
                    klasse = str(b.get("klasse", "")).strip()
                    tekst = truncate(str(b.get("tekst", "")).strip(), 200)
                    if klasse and tekst:
                        regels.append(f'{klasse} – "{tekst}"')
                regels.append("--- EINDE ---")
        return "\n".join(regels)


    # Alles wat een verhuisde node uit deze scope nodig had, expliciet in één object. Nodes die nog
    # closure zijn gebruiken de vrije variabelen rechtstreeks; dat verschil verdwijnt naarmate de
    # rest volgt.
    b = Bouw(
        settings=settings, llm=llm, graph=graph, stop_check=stop_check,
        model=model, model_router=model_router, model_ophaal=model_ophaal,
        memory_context=_memory_context, corpus=_corpus, advies_context=_advies_context,
    )

    def annoteer_node(state: State) -> dict[str, Any]:
        """Aparte annoteer-stap: de ophaal-agent heeft de bepaling opgehaald (in de source_trace).
        Hier doet een PURE LLM-call (geen tools) de JAS-analyse op ALLEEN die tekst en gronden we elk
        element ertegen. De gegronde voorstellen gaan naar de state; de aparte critic_node scoort ze en
        emit ze dán als `element`-events. annoteer emit alléén `doel` (en een melding bij lege uitkomst)."""
        writer = get_stream_writer()

        # Een ONDERWERP in plaats van een bepaling: de ophaal-agent legt kandidaten voor en wij
        # annoteren nog niets. Welke bepaling de werkvoorraad in gaat is een inhoudelijke keuze van
        # de jurist, niet iets om te laten raden door een semantische zoekopdracht.
        kandidaten = _kandidaten_uit_json(state.get("answer", ""))
        if kandidaten:
            writer({"type": "kandidaten", "kandidaten": kandidaten})
            melding = (
                f"Ik vond {len(kandidaten)} bepalingen over dit onderwerp. Kies welke je wilt laten "
                "annoteren."
            )
            writer({"type": "token", "content": melding})
            return {"answer": melding, "voorstellen": [],
                    "messages": [{"role": "assistant", "content": melding}]}

        doel = _bepaal_doel(state)
        # Gericht ophalen op basis van het doel – niet reconstrueren uit de trace. Zie
        # `_corpus_voor_doel`: die reconstructie mengt bepalingen en is afgekapt op 8000 tekens.
        corpus = _corpus_voor_doel(doel, graph, state.get("source_trace", []))
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""

        if not corpus.strip():
            melding = (
                "Ik kon de gevraagde bepaling niet ophalen om te annoteren – controleer de wet en het "
                "artikel/lid (bij een beleidsregel bv. '9.1')."
            )
            writer({"type": "token", "content": melding})
            return {"answer": melding, "voorstellen": [], "messages": [{"role": "assistant", "content": melding}]}

        plek = f"art. {aanduiding}" + (f" lid {doel['lid']}" if doel.get("lid") else "")
        _stap(writer, "Annoteerder", f"leest {plek} ({len(corpus)} tekens)")

        resp = llm.create(
            model=model,
            max_tokens=8192,
            system=annotatie_systeemprompt(),
            tools=[],
            messages=[{"role": "user", "content": annotatie_userprompt(doel.get("bwbId", ""), aanduiding, corpus, doel.get("lid", ""))}],
        )
        llm_text = "".join(b.text for b in resp.content if b.type == "text")
        # Bewust zónder `geldige_ids`: in de eerste ronde is er binnen deze beurt nog geen element om
        # te overschrijven, dus een id uit het model is hooguit een raar id. De strengheid hoort in
        # de herziening, waar een verwisseld id wél een bestaande markering raakt.
        voorstellen, verworpen = _verwerk(
            llm_text, corpus, doel.get("bwbId", ""), aanduiding, doel.get("lid", ""),
        )
        _stap(writer, "Annoteerder", _annoteer_melding(voorstellen, verworpen))

        # Stuur de opgehaalde tekst mee zodat de frontend precies dít toont (één bron, ook voor divisies).
        doel_uit = {**doel, "leden_teksten": [{"lid": doel.get("lid", ""), "tekst": corpus}]}
        writer({"type": "doel", "doel": doel_uit})
        if not voorstellen:
            leeg = f"Ik vond geen JAS-elementen om te markeren in artikel {aanduiding}" + (
                f" lid {doel['lid']}." if doel.get("lid") else "."
            )
            writer({"type": "token", "content": leeg})
            return {"answer": leeg, "voorstellen": [], "verworpen_fragmenten": [], "corpus": corpus,
                    "messages": [{"role": "assistant", "content": leeg}]}
        # Markeringen die de JURIST zelf maakte gaan mee als BEVROREN voorstellen: de Critic mag er
        # iets van vinden (dat is een tweede paar ogen op eigen werk), maar ze doen niet mee in de
        # herzieningslus en worden nooit gewijzigd. De api weigert dat trouwens ook.
        # Ze moeten wél over DEZE bepaling gaan: een fragment dat niet letterlijk in het opgehaalde
        # corpus staat, kan de Critic niet beoordelen. Zonder deze grens oordeelt hij over een
        # markering uit een ander artikel die de werkplek meestuurde – en dat leest als een
        # kanttekening op werk dat hier niet ligt.
        meegestuurd = [
            e for e in ((state.get("context") or {}).get("bestaande_elementen") or [])
            if e.get("herkomst") == "mens" and e.get("tekst")
        ]
        eigen = [
            {
                "id": e.get("id", ""), "klasse": e.get("klasse", ""), "tekst": e.get("tekst", ""),
                "lid": e.get("lid", ""), "toelichting": "", "alternatieven": [],
                "grounded": True, "vindplaats": "", "aandacht": "", "critic": "",
                "van_jurist": True,
            }
            for e in meegestuurd
            if komt_letterlijk_voor(corpus, str(e.get("tekst", "")))
        ]
        if len(eigen) < len(meegestuurd):
            logger.info(
                "eigen markeringen buiten deze bepaling overgeslagen",
                extra={"meegestuurd": len(meegestuurd), "beoordeeld": len(eigen)},
            )

        # De verworpen fragmenten gaan mee de state in: de herzieningsronde (zie `route_na_critic`)
        # kan het model daarmee zijn eigen bijna-goede citaten laten repareren.
        return {
            "voorstellen": [v.model_dump() for v in voorstellen] + eigen,
            "verworpen_fragmenten": [x.model_dump() for x in verworpen],
            # De Critic en de herziening lezen dit; zonder dit zouden ze de bepaling opnieuw ophalen
            # (of erger: terugvallen op de trace en over een ándere tekst oordelen).
            "corpus": corpus,
            "answer": "",
        }

    def annoteer_kandidaten_node(state: State) -> dict[str, Any]:
        """Fase 2A stap 1: kandidaatgeneratie – zoekt tekstspans zonder JAS-klasse.

        Een aparte LLM-call die uitsluitend 'welke spans zijn mogelijk een juridisch element?'
        beantwoordt, zonder te classificeren. Dit maakt kandidaat-recall onafhankelijk van
        classificatie-accuracy meetbaar. De gefilterde kandidaten gaan als `kandidaten_v2a`
        de state in; de volgende node (`annoteer_klasseer_node`) classificeert ze.
        """
        writer = get_stream_writer()

        # Een ONDERWERP in plaats van een bepaling: dan legt de ophaal-agent kandidaat-bepalingen
        # voor en annoteren we nog niets. Identiek aan `annoteer_node` – welke bepaling de
        # werkvoorraad in gaat is een keuze van de jurist, en die keuze mag niet afhangen van of de
        # splitsing aan staat.
        kandidaat_bepalingen = _kandidaten_uit_json(state.get("answer", ""))
        if kandidaat_bepalingen:
            writer({"type": "kandidaten", "kandidaten": kandidaat_bepalingen})
            melding = (
                f"Ik vond {len(kandidaat_bepalingen)} bepalingen over dit onderwerp. Kies welke je "
                "wilt laten annoteren."
            )
            writer({"type": "token", "content": melding})
            return {"answer": melding, "voorstellen": [], "kandidaten_v2a": [],
                    "messages": [{"role": "assistant", "content": melding}]}

        doel = _bepaal_doel(state)
        # Gebruik het in state gecachede corpus; als dat leeg is haal het gericht op
        # (zelfde strategie als annoteer_node – zonder dit zou een direct-naar-annoteer
        # route met leeg corpus altijd een lege kandidatenlijst opleveren).
        corpus = state.get("corpus") or _corpus_voor_doel(doel, graph, state.get("source_trace", []))
        if not corpus.strip():
            # Zelfde melding als V1. Stil teruggeven liet de klasseer-node hierna een LLM-call doen
            # op een lege tekst, en las de jurist "geen JAS-elementen gevonden" waar "ik kon de
            # bepaling niet ophalen" de waarheid is.
            melding = (
                "Ik kon de gevraagde bepaling niet ophalen om te annoteren – controleer de wet en het "
                "artikel/lid (bij een beleidsregel bv. '9.1')."
            )
            writer({"type": "token", "content": melding})
            return {"answer": melding, "voorstellen": [], "kandidaten_v2a": [], "corpus": "",
                    "messages": [{"role": "assistant", "content": melding}]}

        aanduiding = doel.get("artikel") or doel.get("nummer") or ""
        _stap(writer, "Kandidaatgenerator", f"zoekt spans in art. {aanduiding}")

        resp = llm.create(
            model=model,
            max_tokens=4096,
            system=kandidaten_systeemprompt(),
            tools=[],
            messages=[{"role": "user", "content": kandidaten_userprompt(
                doel.get("bwbId", ""), aanduiding, corpus, doel.get("lid"),
            )}],
        )
        llm_text = "".join(b.text for b in resp.content if b.type == "text")
        ruw = parse_kandidaten(llm_text)
        gefilterd = filter_kandidaten(ruw, corpus)
        _stap(writer, "Kandidaatgenerator",
              f"{len(ruw)} gevonden, {len(gefilterd)} na filtering")
        # Het corpus MOET mee. `annoteer_klasseer_node` leest het uit de state, en zonder dit veld
        # staat daar niets – of, bij een tweede bepaling in dezelfde run, de tekst van de vórige.
        # Dan gront `_verwerk` elk fragment tegen de verkeerde tekst en verwerpt het alles.
        return {"kandidaten_v2a": gefilterd, "corpus": corpus}

    def annoteer_klasseer_node(state: State) -> dict[str, Any]:
        """Fase 2A stap 2: classificeer de gefilterde kandidaten.

        Krijgt de gefilterde kandidatenlijst en de brontekst; bepaalt per span de JAS-klasse.
        Hergebruikt _verwerk() voor brongetrouwheid-check en prioriteitsvalidatie, zodat de
        garanties ongewijzigd blijven. De Critic-keten daarna is identiek aan V1.

        Als er geen kandidaten zijn (kandidaatgenerator produceerde niets na filtering), valt
        deze node terug op de V1-gecombineerde aanpak – één call die zelf de spans zoekt én
        classificeert. Dat voorkomt dat een lege kandidatenlijst het annotatie-proces stillegt.
        """
        writer = get_stream_writer()
        doel = _bepaal_doel(state)
        corpus = state.get("corpus") or ""
        kandidaten = state.get("kandidaten_v2a") or []
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""

        if not kandidaten:
            # Fallback naar V1: gecombineerde kandidaat+classificatie in één call
            _stap(writer, "Classificator", "geen kandidaten – gecombineerde aanpak (V1-fallback)")
            resp = llm.create(
                model=model, max_tokens=8192,
                system=annotatie_systeemprompt(), tools=[],
                messages=[{"role": "user", "content": annotatie_userprompt(
                    doel.get("bwbId", ""), aanduiding, corpus, doel.get("lid"),
                )}],
            )
        else:
            _stap(writer, "Classificator",
                  f"classificeert {len(kandidaten)} kandidaten voor art. {aanduiding}")
            resp = llm.create(
                model=model, max_tokens=8192,
                system=klasseer_systeemprompt(), tools=[],
                messages=[{"role": "user", "content": klasseer_userprompt(
                    doel.get("bwbId", ""), aanduiding, corpus, kandidaten, doel.get("lid"),
                )}],
            )

        llm_text = "".join(b.text for b in resp.content if b.type == "text")
        voorstellen, verworpen = _verwerk(
            llm_text, corpus, doel.get("bwbId", ""), aanduiding, doel.get("lid"),
        )
        _stap(writer, "Classificator", _annoteer_melding(voorstellen, verworpen))

        # Stuur een `kandidaten`-event zodat eval candidate_recall kan meten
        if kandidaten:
            writer({"type": "kandidaten_v2a", "items": kandidaten})

        doel_uit = {**doel, "leden_teksten": [{"lid": doel.get("lid", ""), "tekst": corpus}]}
        writer({"type": "doel", "doel": doel_uit})

        if not voorstellen:
            leeg = (
                f"Ik vond geen JAS-elementen om te markeren in artikel {aanduiding}"
                + (f" lid {doel['lid']}." if doel.get("lid") else ".")
            )
            writer({"type": "token", "content": leeg})
            return {"answer": leeg, "voorstellen": [], "verworpen_fragmenten": [],
                    "corpus": corpus,
                    "messages": [{"role": "assistant", "content": leeg}]}

        meegestuurd = [
            e for e in ((state.get("context") or {}).get("bestaande_elementen") or [])
            if e.get("herkomst") == "mens" and e.get("tekst")
        ]
        eigen = [
            {
                "id": e.get("id", ""), "klasse": e.get("klasse", ""), "tekst": e.get("tekst", ""),
                "lid": e.get("lid", ""), "toelichting": "", "alternatieven": [],
                "grounded": True, "vindplaats": "", "aandacht": "", "critic": "",
                "van_jurist": True,
            }
            for e in meegestuurd
            if komt_letterlijk_voor(corpus, str(e.get("tekst", "")))
        ]
        return {
            "voorstellen": [v.model_dump() for v in voorstellen] + eigen,
            "verworpen_fragmenten": [x.model_dump() for x in verworpen],
            # Critic en herziening lezen corpus via _corpus(state); zonder dit veld vallen
            # zij terug op de trace-reconstructie over meerdere bepalingen.
            "corpus": corpus,
            "answer": "",
        }

    def critic_node(state: State) -> dict[str, Any]:
        """Critic-pas: beoordeelt de gegronde voorstellen en zet per element een aandacht-niveau
        (groen/geel/rood) + motivatie, plus een lijst waarschijnlijk ontbrekende elementen. Eén
        LLM-call (geen tools).

        Emit BEWUST NIETS: dat doet `emit_node`, na de laatste ronde. Zou deze node al `element`-events
        sturen, dan zag de werkplek elke tussenversie van de herzieningslus voorbijkomen.

        Faalt de Critic → `critic_gefaald`, elementen komen door met lege aandacht en de lus wordt
        overgeslagen (nooit de annotatie breken)."""
        writer = get_stream_writer()
        voorstellen = list(state.get("voorstellen") or [])
        if not voorstellen:
            return {}  # annoteer_node heeft de lege/foutmelding al geëmit

        _stap(writer, "Critic", f"beoordeelt {len(voorstellen)} markeringen")
        corpus = _corpus(state)

        oordelen: dict[str, Any] = {}
        ontbrekend: list[Any] = []
        gefaald = False
        try:
            resp = llm.create(
                model=model,
                max_tokens=2048,
                system=critic_systeemprompt(),
                tools=[],
                messages=[{"role": "user", "content": critic_userprompt(
                    voorstellen, corpus, list(state.get("gemeld_ontbrekend") or []),
                )}],
            )
            crit_text = "".join(b.text for b in resp.content if b.type == "text")
            oordelen, ontbrekend = _verwerk_critic(crit_text, [str(v.get("id", "")) for v in voorstellen])
        except Exception:  # noqa: BLE001 – Critic mag de annotatie nooit breken
            gefaald = True
            logger.warning("critic: beoordeling mislukt; elementen zonder aandacht doorgelaten", exc_info=True)

        if gefaald:
            _stap(writer, "Critic", "overgeslagen (fout) – de voorstellen blijven staan")
            # Laat de voorstellen ONGEMOEID. In een tweede ronde staat er al een oordeel van de
            # eerste pas op; dat overschrijven met lege waarden zou een geslaagde beoordeling
            # ongedaan maken omdat een latere poging mislukte.
            return {
                "voorstellen": voorstellen,
                "critic_feedback": [],
                "critic_gefaald": True,
            }

        # Rondenummer voor het spoor: 1 = het eerste oordeel, 2 = de eindbeoordeling na correctie.
        ronde = int(state.get("critic_ronde") or 0) + 1

        feedback: list[dict[str, Any]] = []
        for v in voorstellen:
            oordeel = oordelen.get(str(v.get("id", "")))
            aandacht = oordeel.aandacht if oordeel else ""
            # De motivatie gaat één-op-één naar de reviewkaart. Interne ids horen daar niet: de
            # Critic gebruikt ze om naar buurelementen te verwijzen, de jurist leest een hexcode.
            motivatie = vervang_ids_door_citaat(oordeel.motivatie, voorstellen) if oordeel else ""
            # Alternatieven forceren GEEN geel meer. Dat maakte disambiguatie ononderscheidbaar van
            # een probleem: een element met alternatieven kon nooit groen worden, dus stond straks
            # alles "met aandacht" en zei die vlag niets meer. Twijfel telt nu apart (zie emit_node).
            v["aandacht"] = aandacht
            v["critic"] = motivatie
            if oordeel is not None:
                feedback.append({"id": v.get("id", ""), **oordeel.model_dump()})
                # Het spoor per element: hierop leunt de volgende Critic-pas (geheugen), de kaart in
                # de werkplek (het heen-en-weer) en de merge in de api (die matcht op rondenummer).
                v.setdefault("critic_rondes", []).append({
                    "ronde": ronde,
                    "aandacht": aandacht,
                    "motivatie": motivatie,
                    "actie": oordeel.actie,
                    # Expliciet, ook al is False de default in het contract: de patcher zet dit
                    # verderop op True, en een spoor dat het veld pas krijgt zódra er iets gebeurde
                    # is moeilijker te lezen dan een spoor dat het altijd draagt.
                    "toegepast": False,
                    "voorstel_klasse": oordeel.voorstel_klasse,
                    "voorstel_tekst": oordeel.voorstel_tekst,
                })

        al_gemeld = set(state.get("gemeld_ontbrekend") or [])
        huidig = {_ontbrekend_sleutel(o.model_dump()) for o in ontbrekend}
        nieuw_ontbrekend = [o.model_dump() for o in ontbrekend
                            if _ontbrekend_sleutel(o.model_dump()) not in al_gemeld]

        # De eindbeoordeling gaat rechtstreeks naar de jurist; er komt geen patcher meer overheen
        # die haar kan wegen. Dus hier, en alleen hier, dempen we een oordeel dat de eigen
        # uitgevoerde correctie terugdraait – zie `demp_zelfweerspreking`.
        gedempt = demp_zelfweerspreking(voorstellen) if ronde >= 2 else 0

        _stap(writer, "Critic",
              _critic_melding(oordelen, ontbrekend, len(nieuw_ontbrekend), gedempt))

        # `voorstellen` expliciet teruggeven: eerder werkten de aandacht-velden alleen door omdat het
        # dezelfde dict-objecten waren. Dat is fragiel zodra er meerdere rondes over de state lopen.
        return {
            "voorstellen": voorstellen,
            "critic_feedback": feedback,
            "critic_ontbrekend": [o.model_dump() for o in ontbrekend],
            "critic_gefaald": gefaald,
            # De teller telt CRITIC-PASSEN (1 = eerste oordeel, 2 = eindbeoordeling na correctie) en
            # hoort daarom hier thuis. Hij zat in de herziener en telde daar pogingen – een teller die
            # ergens anders wordt opgehoogd dan waar hij over gaat.
            "critic_ronde": ronde,
            # Wat al ooit is gemeld start geen nieuwe ronde meer. Hier berekend en niet in de route:
            # daar is de accumulatie al bijgewerkt en zou álles als "al gemeld" gelden.
            "nieuw_ontbrekend": nieuw_ontbrekend,
            "gemeld_ontbrekend": sorted(al_gemeld | huidig),
        }

    def _open_werk(state: State) -> bool:
        """Ligt er werk dat alléén het model kan doen?

        Twee dingen, en ze hebben gemeen dat er brontekst voor gelezen moet worden in plaats van een
        instructie uitgevoerd: een gemeld ontbrekend element (waar staat het?) en een eerder verworpen
        fragment (welk citaat werd bedoeld?).

        Correctie-instructies staan hier NIET meer bij. `vervang` en `verwijder` waren de reden dat de
        herziener draaide, en die voert de patcher nu uit – exact, zonder call, zonder onderhandeling.

        Eén definitie, gebruikt door de routering én door de stopreden in `emit_node`. Stonden die los
        van elkaar, dan meldt de tijdlijn iets anders dan er gebeurde – en dat is precies het signaal
        waarmee je deze keten beoordeelt.
        """
        return bool(state.get("nieuw_ontbrekend")) or bool(state.get("verworpen_fragmenten"))

    def route_na_critic(state: State) -> str:
        """Naar de correctiestap, of naar de jurist?

        De keten is lineair: `critic₁ → patch → [herzie] → [critic₂] → emit`. Er valt hier dus niets
        te kiezen behalve of er nog een correctieronde ís – en of dit al de eindbeoordeling was.
        Eerder zat hier de ingang van een cyclus (`critic ⇄ herzie`) met vier guards eromheen.
        """
        if settings.critic_max_rondes <= 0:
            return "emit"                                   # correctie uit: exact het oude gedrag
        if state.get("critic_gefaald"):
            return "emit"                                   # nooit de annotatie breken
        if int(state.get("critic_ronde") or 0) >= 2:
            return "emit"                                   # dit wás de eindbeoordeling
        return "patch"

    def patch_node(state: State) -> dict[str, Any]:
        """Voer de correcties van de Critic uit – in code, niet via een tweede taalmodel.

        Zie `annotatie.pas_critic_toe` voor de regels en waarom ze zo liggen. Deze node kost niets:
        geen LLM-call, geen graafverkeer.
        """
        writer = get_stream_writer()
        voorstellen, telling, rest = pas_critic_toe(
            list(state.get("voorstellen") or []),
            list(state.get("critic_feedback") or []),
            _corpus(state),
        )
        if telling:
            delen = []
            if telling.toegepast:
                delen.append(f"{telling.toegepast} "
                             + ("aanwijzing" if telling.toegepast == 1 else "aanwijzingen") + " toegepast")
            if telling.alternatief:
                delen.append(f"{telling.alternatief} "
                             + ("twijfel" if telling.alternatief == 1 else "twijfels")
                             + " als alternatief doorgegeven")
            _stap(writer, "Correctie", ", ".join(delen))
        # Alleen een echte wijziging vraagt om een nieuw oordeel. Een alternatief laat het element
        # ongemoeid – daar geldt het oordeel van de eerste pas gewoon nog.
        #
        # `critic_feedback` wordt teruggebracht tot wat de patcher NIET heeft afgehandeld. Anders
        # krijgt de herziener dezelfde instructies opnieuw voorgelegd: de correcties die hier net
        # zijn uitgevoerd (dubbel werk) én de gele voorkeuren die hier bewust niet zijn uitgevoerd —
        # en dan voert een taalmodel alsnog uit wat juist aan de jurist zou worden voorgelegd.
        return {
            "voorstellen": voorstellen,
            "patch_toegepast": telling.toegepast,
            "critic_feedback": rest,
        }

    def route_na_patch(state: State) -> str:
        """Wat er ná het patchen nog over is.

        - **Restant voor het model**: een bijna-goed citaat repareren of een gemeld ontbrekend element
          toevoegen. Dat is brontekst lezen, geen instructie uitvoeren – dus daar draait de herziener.
        - **Alleen gepatcht**: dan volgt de eindbeoordeling, zodat het oordeel op de kaart gaat over
          de versie die de jurist vóór zich krijgt en niet over de versie die net is vervangen.
        - **Niets veranderd**: klaar. Dit is het normale geval en het kost geen enkele extra call.
        """
        if _open_werk(state):
            return "herzie"
        return "critic" if state.get("patch_toegepast") else "emit"

    def herzie_node(state: State) -> dict[str, Any]:
        """Laat de annoteerder de Critic-instructies verwerken. Eén LLM-call, geen tools.

        Conservatief samenvoegen: wat de herziening niet noemt blijft staan. Alleen een expliciete
        `verwijder`-instructie laat een element verdwijnen. Zo kan een doordrammende Critic geen goede
        elementen wegvagen, en levert een half-mislukte herziening nooit minder op dan we al hadden.
        """
        writer = get_stream_writer()
        alle = list(state.get("voorstellen") or [])
        # Markeringen van de jurist gaan de herziening NIET in: de agent herschrijft ze niet, ook niet
        # als de Critic er iets van vindt. Die bevinding komt terug als suggestie, niet als wijziging.
        van_jurist = [v for v in alle if v.get("van_jurist")]
        voorstellen = [v for v in alle if not v.get("van_jurist")]
        # De herziener draait hoogstens één keer en telt niets meer op: de keten is lineair, dus er
        # is geen ronde om te tellen. `critic_ronde` gaat over de Critic-passen en wordt daar gezet.
        ronde = int(state.get("critic_ronde") or 0)
        if not voorstellen:
            # Alleen markeringen van de jurist: er valt niets te herzien.
            return {"stop_reden": "niets te herzien"}
        doel = _bepaal_doel(state)
        corpus = _corpus(state)
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""
        feedback = [f for f in (state.get("critic_feedback") or [])
                    if f.get("id") not in {v.get("id") for v in van_jurist}]

        try:
            resp = llm.create(
                model=model,
                max_tokens=8192,
                system=herziening_systeemprompt(),
                tools=[],
                messages=[{"role": "user", "content": herziening_userprompt(
                    voorstellen, feedback,
                    state.get("critic_ontbrekend") or [],
                    state.get("verworpen_fragmenten") or [],
                    corpus,
                )}],
            )
            llm_text = "".join(b.text for b in resp.content if b.type == "text")
            herzien, verworpen = _verwerk(
                llm_text, corpus, doel.get("bwbId", ""), aanduiding, doel.get("lid", ""),
                # Alleen de id's die de herziener zélf voorgelegd kreeg. Verwisselt het model er
                # twee, dan zou het anders element A overschrijven met de inhoud van B.
                geldige_ids={str(v.get("id", "")) for v in voorstellen if v.get("id")},
            )
        except Exception:  # noqa: BLE001 – een mislukte herziening mag de annotatie niet breken
            logger.warning("herziening: mislukt; vorige voorstellen behouden", exc_info=True)
            _stap(writer, f"Herziening {ronde}", "mislukt – vorige voorstellen behouden")
            return {"critic_feedback": [], "stop_reden": "herziening mislukt"}

        if not herzien:
            logger.warning("herziening: leverde niets gegronds op; vorige voorstellen behouden")
            _stap(writer, f"Herziening {ronde}",
                  "leverde niets gegronds op – vorige voorstellen behouden")
            return {"critic_feedback": [], "stop_reden": "geen wijziging meer"}

        te_verwijderen = {f.get("id") for f in feedback if f.get("actie") == "verwijder"}
        samengevoegd = {v["id"]: v for v in voorstellen if v.get("id") not in te_verwijderen}
        # Een herziening die een bestaand fragment opnieuw voorstelt ZONDER het id mee te sturen,
        # krijgt een vers id – en dan staat dezelfde markering er twee keer. Dat viel op dev op:
        # "bij zijn in functie treden" tweemaal als Rechtsfeit. Koppel daarom ook op de inhoud.
        # De sleutel telt de klasse NIET mee: een herclassificatie is precies wat een herziening
        # hoort te doen, en met de klasse erin werd zo'n herziening een tweede element naast het
        # origineel – dezelfde span, twee tegenstrijdige klassen op het reviewscherm.
        op_inhoud = {
            sleutel_van(v.get("tekst", ""), v.get("lid", "")): v["id"]
            for v in samengevoegd.values()
        }
        for nieuw_v in herzien:
            nieuw_dict = nieuw_v.model_dump()
            bestaand_id = op_inhoud.get(sleutel_van(nieuw_v.tekst, nieuw_v.lid))
            if bestaand_id and bestaand_id != nieuw_v.id:
                # Het OUDSTE id wint: daar hangen de beslissingen van de jurist en het auditspoor aan.
                nieuw_dict["id"] = bestaand_id
                nieuw_v = nieuw_v.model_copy(update={"id": bestaand_id})
            vorig = samengevoegd.get(nieuw_v.id)
            # De rondegeschiedenis gaat ALTIJD mee: die gaat over wat er gebeurd is, niet over de
            # huidige versie. Zonder dit begint de volgende Critic-pas weer met een schone lei —
            # precies de reden dat de lus nooit convergeerde.
            if vorig:
                nieuw_dict["critic_rondes"] = list(vorig.get("critic_rondes") or [])
                # Ook de alternatieven blijven: de patcher zet de twijfel van de Critic daar neer, en
                # het model levert bij een herziening zijn eigen lijstje op. Namen we alleen dat
                # laatste over, dan wiste een herziening precies de voorkeur die de jurist met één
                # klik had kunnen overnemen – op dev verdween "Parameter en parameterwaarde" zo uit
                # beeld. Samenvoegen op klasse, het bestaande eerst.
                bestaand = list(vorig.get("alternatieven") or [])
                gezien_alt = {str(a.get("klasse")) for a in bestaand}
                nieuw_dict["alternatieven"] = bestaand + [
                    a for a in (nieuw_dict.get("alternatieven") or [])
                    if str(a.get("klasse")) not in gezien_alt
                ]
            # Een herziening levert verse voorstellen zonder oordeel. Is het element inhoudelijk
            # ongewijzigd, dan geldt het vorige oordeel nog gewoon – dat weggooien zou een groen
            # vinkje laten verdwijnen omdat er elders in de tekst iets veranderde. Bij een écht
            # gewijzigd element hoort de aandacht leeg: die versie is nog niet beoordeeld.
            if vorig and all(vorig.get(k) == nieuw_dict.get(k) for k in ("klasse", "tekst", "lid")):
                nieuw_dict["aandacht"] = vorig.get("aandacht", "")
                nieuw_dict["critic"] = vorig.get("critic", "")
            samengevoegd[nieuw_v.id] = nieuw_dict

        uit = list(samengevoegd.values())
        _stap(writer, f"Herziening {ronde}", _herzien_melding(voorstellen, uit))

        # Wat is er écht veranderd? De eindbeoordeling leest dit ("je zei X, en de annotator heeft het
        # wel/niet gedaan"). De boekhouding van gemotiveerd genegeerde instructies is weg: die bestond
        # om een cyclus te laten stoppen die er niet meer is.
        voor_op_id = {v.get("id"): v for v in voorstellen}
        gewijzigd = {
            v.get("id") for v in uit
            if v.get("id") not in voor_op_id
            or any(voor_op_id[v["id"]].get(k) != v.get(k) for k in ("klasse", "tekst", "lid"))
        }
        for v in uit:
            v["aangepast_na_kritiek"] = v.get("id") in gewijzigd

        return {
            "voorstellen": uit + van_jurist,
            "verworpen_fragmenten": [x.model_dump() for x in verworpen],
            "critic_feedback": [],
            # Niets meer voor het model te doen: de herziener draait per beurt hoogstens één keer.
            "nieuw_ontbrekend": [],
            "verworpen_fragmenten": [x.model_dump() for x in verworpen] if gewijzigd else [],
        }

    # Er is geen `route_na_herziening` meer: de herziener gaat altijd door naar de eindbeoordeling
    # (`g.add_edge("herzie", "critic")`). Dat was de terugweg van een cyclus, met
    # `herziening_wijzigde` als rem – en die cyclus bestaat niet meer.

    def emit_node(state: State) -> dict[str, Any]:
        """De enige plek die annotatie-events uitstuurt: één `run`, `element` per voorstel, één
        `ontbrekend`, en de samenvattings-`token`. Apart gehouden van de Critic zodat de
        herzieningslus zoveel rondes kan draaien als nodig zonder dat de werkplek tussenversies
        te zien krijgt."""
        writer = get_stream_writer()
        voorstellen = list(state.get("voorstellen") or [])
        if not voorstellen:
            return {}
        doel = _bepaal_doel(state)
        aanduiding = doel.get("artikel") or doel.get("nummer") or ""
        ontbrekend = state.get("critic_ontbrekend") or []
        corpus = _corpus(state)

        # Vóór de elementen: met welk model deze voorstellen zijn gemaakt. Zonder dit is achteraf
        # niet meer vast te stellen wat een markering produceerde – de werkplek legt het vast bij
        # de api en de export draagt het als herkomst.
        writer({"type": "run", "run": AgentRun(
            model=model,
            provider=settings.llm_provider,
            agent_versie=settings.agent_versie,
            critic_rondes=int(state.get("critic_ronde") or 0),
            stop_reden=str(state.get("stop_reden") or ""),
            tijd=datetime.now(timezone.utc),
        ).model_dump(mode="json")})

        met_aandacht = 0
        met_twijfel = 0
        for v in voorstellen:
            if v.get("van_jurist"):
                # Geen `element`-event: dit element bestaat al in het document en mag niet opnieuw
                # als voorstel binnenkomen. Alleen het oordeel gaat mee, als suggestie.
                if v.get("aandacht"):
                    writer({"type": "suggestie", "suggestie": {
                        "element_id": v.get("id", ""), "aandacht": v.get("aandacht", ""),
                        "motivatie": v.get("critic", ""),
                    }})
                continue
            if v.get("aandacht") in ("geel", "rood"):
                met_aandacht += 1
            elif v.get("alternatieven"):
                # Twijfel, geen bezwaar: de annoteerder zag twee plausibele klassen. Apart tellen,
                # anders verdrinkt een écht aandachtspunt tussen de disambiguaties.
                met_twijfel += 1
            writer({"type": "element", "element": v})

            # Een voorstel uit de EINDbeoordeling komt door geen enkele stap meer heen – de patcher
            # draaide al. Als suggestie ernaast leggen kan wel: dan neemt de jurist het over met één
            # klik, en landt het als zíjn beslissing in het spoor.
            klasse, tekst, waarom = openstaand_voorstel(v, corpus)
            if klasse or tekst:
                writer({"type": "suggestie", "suggestie": {
                    "element_id": v.get("id", ""), "aandacht": v.get("aandacht", ""),
                    "motivatie": waarom, "voorstel_klasse": klasse, "voorstel_tekst": tekst,
                }})
        writer({"type": "ontbrekend", "items": ontbrekend})

        # Verworpen fragmenten (niet-letterlijke of ongeldige-klasse citaten) – apart event
        # zodat de eval-harnas verworpen_per_100 kan meten. De werkplek negeert dit event;
        # voor eval is het de enige manier om het hallucinatie-aandeel te kwantificeren
        # zonder in de interne state te kijken.
        verworpen_frags = state.get("verworpen_fragmenten") or []
        if verworpen_frags:
            writer({"type": "verworpen", "items": verworpen_frags})

        eigen = [v for v in voorstellen if v.get("van_jurist")]
        voorstellen = [v for v in voorstellen if not v.get("van_jurist")]
        plek = f"artikel {aanduiding}" + (f" lid {doel['lid']}" if doel.get("lid") else "")
        delen = [f"Ik heb {len(voorstellen)} JAS-elementen voorgesteld voor {plek}"]
        if met_aandacht:
            delen.append(f"{met_aandacht} met aandacht")
        if met_twijfel:
            delen.append(f"{met_twijfel} met twijfel")
        if ontbrekend:
            delen.append(f"{len(ontbrekend)} mogelijk ontbrekend")
        met_suggestie = sum(1 for v in eigen if v.get("aandacht") in ("geel", "rood"))
        if met_suggestie:
            delen.append(f"{met_suggestie} kanttekening bij je eigen markeringen")
        if int(state.get("patch_toegepast") or 0):
            delen.append("na correctie door de Critic")
        samenvatting = "; ".join(delen) + "."
        # De stopreden hoort hier te worden afgeleid: `route_na_critic` weet hem wel, maar een
        # conditionele edge geeft alleen een naam terug en kan geen state schrijven. Alle feiten
        # staan hier, dus is dit de plek waar één waarheid overblijft.
        # Er is geen rondelimiet meer om te bereiken: de keten is lineair. Wat overblijft is of de
        # correctie überhaupt aanstond, of de Critic uitviel, en anders gewoon: klaar.
        reden = state.get("stop_reden") or (
            "Critic uitgevallen" if state.get("critic_gefaald")
            else "correctieronde uit" if settings.critic_max_rondes <= 0
            else "geen open punten"
        )
        _stap(writer, "Klaar", f"{reden} · {len(voorstellen)} elementen ter beoordeling")
        writer({"type": "token", "content": samenvatting})

        # Geheugen: leg een leesbaar spoor van de annotatie vast (met de elementen) zodat een
        # vervolgvraag ("waarom Rechtssubject?") context heeft.
        elems = "; ".join(f"{v.get('klasse', '')}: '{truncate(str(v.get('tekst', '')), 80)}'" for v in voorstellen[:12])
        geheugen = f"[Annotatie {plek}] Ik markeerde {len(voorstellen)} JAS-elementen: {elems}" + (
            " (…)" if len(voorstellen) > 12 else "."
        )
        return {"answer": samenvatting, "messages": [{"role": "assistant", "content": geheugen}]}

    g = StateGraph(State)

    def stopbaar(fn):
        """Elke node begint met de vraag of er nog gewerkt moet worden.

        Zo stopt een beurt op een **nodegrens** in plaats van halverwege een LLM-call: de state die
        al gecommit is blijft consistent, en de MCP-verbinding wordt netjes afgesloten. De prijs is
        dat stoppen tijd kost – de lopende stap maakt zichzelf af."""
        @functools.wraps(fn)
        def bewaakt(state: State) -> dict[str, Any]:
            if stop_check is not None and stop_check():
                raise BeurtGestopt()
            return fn(state)
        return bewaakt

    def add(naam: str, fn) -> None:
        """Registreer een node, altijd met de stopbewaking eromheen."""
        g.add_node(naam, stopbaar(fn))

    def annotatieketen() -> str:
        """Registreer de annotatie-worker en zijn edges; geeft de naam van de ingang terug.

        Lineair: annoteer → critic₁ → patch → [herzie → critic₂] → emit, met `emit` als enige
        uitgang zodat de werkplek nooit tussenversies ziet. Geen enkele edge wijst terug naar een
        eerdere stap, dus er is geen cyclus om te laten convergeren.

        Dit blok stond identiek in de decompositie- en de planning-tak. De antwoordketen verschilt
        wél echt tussen die twee (`verify → resynth` versus `verify → correct`), dus die blijft per
        tak apart staan; alleen wat aantoonbaar hetzelfde was is hier samengebracht.
        """
        if settings.enable_kandidaat_splitsing:
            add("annoteer_kandidaten", annoteer_kandidaten_node)
            add("annoteer_klasseer", annoteer_klasseer_node)
            entry = "annoteer_kandidaten"
        else:
            add("annoteer", annoteer_node)
            entry = "annoteer"
        add("critic", critic_node)
        add("patch", patch_node)
        add("herzie", herzie_node)
        add("emit", emit_node)

        if settings.enable_kandidaat_splitsing:
            g.add_edge("annoteer_kandidaten", "annoteer_klasseer")
            g.add_edge("annoteer_klasseer", "critic")
        else:
            g.add_edge("annoteer", "critic")
        g.add_conditional_edges("critic", route_na_critic, {"patch": "patch", "emit": "emit"})
        g.add_conditional_edges("patch", route_na_patch,
                                {"herzie": "herzie", "critic": "critic", "emit": "emit"})
        g.add_edge("herzie", "critic")
        g.add_edge("emit", "advance")
        return entry

    add("verify", functools.partial(verify_node, b))
    add("finalize", functools.partial(finalize_node, b))

    if settings.enable_decomposition:
        # Supervisor → (annotatie: agent⇄tools→annoteer_finalize | antwoord: decompose→solve→…→
        # finalize) → advance → (volgende worker | einde).
        add("supervisor", functools.partial(supervisor_node, b))
        add("decompose", functools.partial(decompose_node, b))
        add("solve", functools.partial(solve_node, b))
        add("synthesize", functools.partial(synthesize_node, b))
        add("resynth", functools.partial(resynth_node, b))
        add("agent", functools.partial(agent_node, b))
        add("tools", functools.partial(tools_node, b))
        add("advance", functools.partial(advance_node, b))
        add("afwijzen", functools.partial(afwijs_node, b))
        # Alle conditional-edges die "annoteer" als doel teruggeven moeten naar de ingang van de
        # keten; bij splitsing is dat `annoteer_kandidaten`.
        _annoteer_entry = annotatieketen()
        entrymap = {"agent": "agent", "annoteer": _annoteer_entry, "decompose": "decompose",
                    "afwijzen": "afwijzen"}
        g.add_edge(START, "supervisor")
        g.add_edge("afwijzen", END)
        g.add_conditional_edges("supervisor", functools.partial(_entry_node, b), entrymap)
        g.add_edge("decompose", "solve")
        g.add_conditional_edges("solve", functools.partial(route_after_solve, b), {"verify": "verify", "synthesize": "synthesize"})
        g.add_edge("synthesize", "verify")
        g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "resynth", "finalize": "finalize"})
        g.add_edge("resynth", "synthesize")
        g.add_conditional_edges(
            "agent", functools.partial(route_after_agent, b),
            {"tools": "tools", "verify": "verify", "annoteer": _annoteer_entry},
        )
        g.add_edge("tools", "agent")
        g.add_edge("finalize", "advance")
        g.add_conditional_edges("advance", functools.partial(route_after_advance, b), {**entrymap, "einde": END})
        return g

    # Één-loop-stroom.
    add("agent", functools.partial(agent_node, b))
    add("tools", functools.partial(tools_node, b))
    add("correct", functools.partial(correct_node, b))

    if settings.enable_planning:
        # Supervisor → agent⇄tools → (verify→finalize | annoteer_finalize) → advance → (volgende | einde).
        add("supervisor", functools.partial(supervisor_node, b))
        add("advance", functools.partial(advance_node, b))
        add("afwijzen", functools.partial(afwijs_node, b))
        _annoteer_entry = annotatieketen()
        g.add_edge(START, "supervisor")
        g.add_conditional_edges("supervisor", functools.partial(_entry_node, b),
                                {"agent": "agent", "annoteer": _annoteer_entry, "afwijzen": "afwijzen"})
        g.add_edge("afwijzen", END)
        g.add_conditional_edges(
            "agent", functools.partial(route_after_agent, b),
            {"tools": "tools", "verify": "verify", "annoteer": _annoteer_entry},
        )
        g.add_edge("tools", "agent")
        g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "correct", "finalize": "finalize"})
        g.add_edge("correct", "agent")
        g.add_edge("finalize", "advance")
        g.add_conditional_edges("advance", functools.partial(route_after_advance, b),
                                {"agent": "agent", "annoteer": _annoteer_entry,
                                 "afwijzen": "afwijzen", "einde": END})
        return g

    # Geen classificatie (planning off, decomp off): pure QA-agent, ongewijzigd (geen annotatie-route).
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", functools.partial(route_after_agent, b), {"tools": "tools", "verify": "verify"})
    g.add_edge("tools", "agent")
    g.add_conditional_edges("verify", functools.partial(route_after_verify, b), {"correct": "correct", "finalize": "finalize"})
    g.add_edge("correct", "agent")
    g.add_edge("finalize", END)
    return g
