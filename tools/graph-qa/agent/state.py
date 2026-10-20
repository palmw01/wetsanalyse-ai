"""De gedeelde toestand van de agentgraaf.

Staat apart zodat de node-modules hem kunnen importeren zonder de orchestrator (en daarmee een
circulaire import) binnen te halen.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

# De reducer van `messages` staat in een Annotated en wordt door LangGraph pas op bouwtijd
# geëvalueerd, in de globals van déze module — hij moet hier dus echt geïmporteerd zijn.
from .berichten import _voeg_toe_en_snoei

class State(TypedDict, total=False):
    question: str
    run_id: str
    user_id: str
    annotaties_lezen: bool
    # De leesroute voor begrippen (fase F4): de supervisor herkende een vraag naar vastgelegde begrippen.
    begrippen_lezen: bool
    # Het werkgebied van waaruit de werkplek het gesprek opende (of leeg). Zijn begrippen staan vooraan
    # bij `search_begrippen`; het is context, geen filter. Komt elke beurt opnieuw van het verzoek.
    werkgebied_id: str
    # Het dossier van dat werkgebied als contextblok (`werkgebied_context.als_blok`), per beurt opgehaald;
    # `memory_context` zet het naast de focus. Context, geen filter.
    werkgebied_context: str
    # Waar de analist *Vraag Lex* op koos (F3b, `models.Onderwerp` als dict) en het blok dat
    # `agent/onderwerp.py` daarvan maakt; beide per beurt gereset. Het object zelf blijft in de focus
    # (`focus.bij_onderwerp`) voor vervolgvragen.
    onderwerp: dict[str, Any]
    onderwerp_context: str
    # Een klik op een suggestie (F3b/F3c): de handeling, en bij een bevestiging het aantal. Per beurt gereset.
    actie: str
    bevestigd: int | None
    # Wat de supervisor een agent liet doen (F3c, `nodes/agent_taak.py`): {agent, taak, parameters}, en de
    # uitkomst (`agents.Uitkomst` als dict). Per beurt gereset.
    agent_taak: dict[str, Any]
    agent_uitkomst: dict[str, Any]
    # Het gesprek van deze beurt (= de thread); de agents boeken er hun eigen verbruik onder.
    gesprek_id: str
    # De overzichtsroute (`agent/overzicht.py`): de supervisor herkende "welke artikelen gaan over X";
    # `overzicht` is het deterministisch gebouwde overzicht. Beide per beurt gereset.
    overzicht_route: bool
    overzicht: dict[str, Any]
    bron_snapshot: dict[str, Any]
    annotatie_weergave: dict[str, Any]
    corpus_segmenten: list[dict[str, Any]]
    hergebruikte_nodes: list[str]
    annotatie_fout: str
    # Episodisch geheugen, gepersisteerd door de checkpointer. De reducer voegt toe én snoeit: zonder
    # dat groeide de bewaarde historie onbeperkt door (inclusief elk tool-resultaat van 8000 tekens),
    # en werd elke checkpoint-write in een lang gesprek trager en dikker. Snoeien gebeurt alleen op
    # een platte user-beurt – een losgeknipt tool_result zou de volgende beurt laten crashen.
    messages: Annotated[list[dict[str, Any]], _voeg_toe_en_snoei]
    entities_seen: Annotated[list[str], operator.add]            # semantisch/entiteit-tier
    # Waar het gesprek over gaat (`agent/focus.py`): de laatst geannoteerde bepaling met haar
    # markeringen, een aangewezen element, de bronnen van het vorige antwoord. Bewust NIET in de
    # per-beurt-reset van `answer_stream`: dit is het geheugen dat een vervolgvraag nodig heeft.
    focus: dict[str, Any]
    # De vraag van deze beurt, door de supervisor zo herschreven dat hij zonder het gesprek te begrijpen
    # is ("en lid 2?" → "Wat regelt artikel 9 lid 2 van de Invorderingswet 1990?"). Voedt de
    # deterministische regels en filters; het user-bericht in de historie blijft de echte vraag.
    # Per beurt gereset; leeg = de vraag zelf.
    zelfstandige_vraag: str
    # Wat er eerder in dit gesprek letterlijk uit de graaf is opgehaald (`agent/bronregister.py`), als
    # [toolnaam, resultaat]. De brongetrouwheidscontrole toetst ertegen, zodat een vervolgantwoord
    # een eerder opgehaald citaat mag herhalen. Niet in de per-beurt-reset; begrensd.
    bronregister: list[list[str]]
    specialist: str
    plan: str
    worker_plan: list[str]   # geordende worker-keten (specialist-namen) die de supervisor koos
    afwijzen: bool           # supervisor plaatste de vraag buiten de scope → geen worker draait
    afwijs_melding: str      # eigen afwijstekst (b.v. meer dan één artikel); leeg = buiten de scope
    worker_idx: int          # index van de huidige worker in worker_plan
    source_trace: list[tuple[str, str]]
    answer: str
    grounded: bool
    cited: int
    unsupported: list[str]
    niet_letterlijk: list[str]   # als citaat gepresenteerd, maar niet letterlijk in de trace
    grounding_niveau: str        # gegrond | onbepaald | ongegrond
    sources: list[dict[str, Any]]
    pending_tools: list[dict[str, Any]]
    turns: int
    corrected: bool
    # Decompositie (multi-hop): deelvragen + per-deelvraag bevindingen (last-value-wins;
    # solve_node zet ze in één keer). De per-deelvraag agent⇄tools-loop draait lokaal in solve_node.
    sub_questions: list[str]
    sub_findings: list[dict[str, str]]
    # Het doel dat de AANROEPER meegaf ({bwbId, artikel, lid?, citeertitel?}). Weet de werkplek de
    # bepaling al – een open document, een item uit de werkvoorraad, een gekozen kandidaat – dan
    # hoeft niemand hem meer te zoeken: de supervisor doet geen LLM-call en de ophaal-agent draait
    # helemaal niet. Dat scheelt niet alleen calls; het verwijdert de gevaarlijkste faalmodus uit
    # die route, want een ophaal-agent die de verkeerde bepaling kiest levert werk op dat
    # brongetrouw én verkeerd is.
    opgegeven_doel: dict[str, str]
    # Het samenstellen van een werkgebied (activiteit 1, `agent/werkgebied_intake.py`): stap,
    # antwoorden en voorstellen. Bewust NIET in de per-beurt-reset: een tussenvraag laat de intake
    # staan, zodat het open kaartje daarna nog werkt.
    intake: dict[str, Any]
    # De klik op een kaartje van deze beurt; per beurt gereset.
    intake_actie: dict[str, Any]
    # De tekst waarop deze annotatiebeurt draait: de niet-lege bronsegmenten van de snapshot,
    # samengevoegd (`bronmodel.CorpusMap`). Eén ophaalactie, en alles daarna leest deze tekst.
    corpus: str
    # "opnieuw" = de jurist vroeg expliciet om een nieuwe ronde op een al geannoteerde bepaling.
    hergebruik_modus: str
    # Wat er uit de gedeelde laag is hergebruikt (`bron_annotatie.controleer_hergebruik`): leden,
    # telling en of het volledig was. Leeg = niets hergebruikt.
    hergebruik: dict[str, Any]
    # De voorstellen (als dicts, `AnnotatieVoorstel`-vorm) die `annoteer` maakt en `emit` uitstuurt.
    voorstellen: list[dict[str, Any]]
    # Wat de analyse mat en besloot (ADR-001): meting, beslissingen, detectoren, overgeslagen
    # detectoren. Gaat als provenance mee in de `run`.
    analyse: dict[str, Any]
    # Wat de werkplek meestuurt over de bepaling/markering die in beeld staat. `modus == "advies"`
    # betekent: een vraag bij een bestaande annotatie, die niets mag wijzigen.
    modus: str
    context: dict[str, Any]
