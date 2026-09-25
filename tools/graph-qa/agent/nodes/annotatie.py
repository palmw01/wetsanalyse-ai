"""De annotatieketen: van bepaling naar voorgestelde JAS-markeringen (ADR-001).

`annoteer → emit`. `annoteer` haalt de bron gericht op, toetst hergebruik en afronding, en draait
daarna `jas_pipeline.keten.analyseer`: taalanalyse, deterministische detectoren, fusie met de
JAS-voorrangsregels, één kleine classifier-call op kandidaat-labels, validatie, een gerichte
reviewer op twijfelgevallen en een resolver met een vaste tabel. `emit` is de enige uitgang, zodat
de werkplek nooit tussenversies ziet.

Tot 25 sep 2026 stond hier een generatieve keten (annoteerder → Critic → patch → herziening →
Critic). Die is weggehaald na een A/B-meting (`docs/architectuur/metingen/`); zie ADR-001 PR 18.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.config import get_stream_writer
from bronmodel import BronFout

from ..agent_common import truncate
from ..annotatie import aanduiding_in_woorden
from ..artikel import OngeldigeVindplaats
from ..bron_annotatie import controleer_hergebruik, doel_event, lees_bron, lokale_elementen
from ..doel import _bepaal_doel, _kandidaten_uit_json
from ..jas_klassen import methode_versie
from ..jas_pipeline.classificatie import promptversie
from ..jas_pipeline.beslisregister import compact as beslisregister
from ..jas_pipeline.keten import analyseer
from ..models import AgentRun
from ..narratie import _stap
from ..state import State
from .context import Bouw

logger = logging.getLogger("graph_qa.orchestrator")


def _hergebruik_melding(hergebruik: dict[str, Any]) -> str:
    leden = [ld["lid"] for ld in hergebruik["leden"]]
    wat = ("het artikel" if leden == [""] else
           f"lid {leden[0]}" if len(leden) == 1 else "leden " + ", ".join(leden))
    t = hergebruik["telling"]
    return (f"{wat} ongewijzigd sinds de vorige annotatie · {t['markeringen']} markeringen uit de "
            f"graaf ({t['beoordeeld']} beoordeeld, {t['te_beoordelen']} te beoordelen)")


def _bereid_voor(b: Bouw, state: State, writer) -> dict[str, Any]:
    """De bron gericht ophalen, hergebruik en afronding toetsen, het `doel`-event bij volledig
    hergebruik. Geeft `{"klaar": update}` als de beurt hier eindigt, anders doel, bron, hergebruik,
    soort en aanduiding."""
    doel = _bepaal_doel(state)
    try:
        bron = lees_bron(b, state, doel, writer)
        bron, hergebruik = controleer_hergebruik(b, state, bron, writer)
    except (OngeldigeVindplaats, BronFout) as fout:
        # De beurt eindigt hier, en dat is de bedoeling. Doorgaan zou markeringen opleveren onder een
        # aanduiding die de werkplek niet kan openen – de jurist ziet dan pas bij het openen dat er
        # iets mis is, en heeft ondertussen een document in zijn werkvoorraad dat nergens bij hoort.
        melding = f"Ik kan de gevraagde bepaling nu niet annoteren: {fout}."
        writer({"type": "token", "content": melding})
        return {"klaar": {"answer": melding, "voorstellen": [], "messages": [{"role": "assistant", "content": melding}]}}

    soort = bron["bron_snapshot"]["doel"]["type"]
    doel = _bepaal_doel({**state, **bron})
    aanduiding = doel.get("artikel") or doel.get("nummer") or ""
    if not bron["corpus"].strip():
        melding = ("Ik kon de gevraagde bepaling niet ophalen om te annoteren – controleer de wet en het "
                   "artikel/lid (bij een beleidsregel bv. '9.1').")
        writer({"type": "token", "content": melding})
        return {"klaar": {"answer": melding, "voorstellen": [], "messages": [{"role": "assistant", "content": melding}]}}

    if hergebruik:
        _stap(writer, "Hergebruik", _hergebruik_melding(hergebruik))
        if hergebruik["volledig"]:
            # Geen modelaanroep: de laag staat er, met de oordelen van de juristen erbij. `emit` meldt
            # het en de driver legt vast dát er hergebruikt is.
            writer({"type": "doel", "doel": doel_event(doel, bron)})
            return {"klaar": {**bron, "hergebruik": hergebruik, "voorstellen": [], "answer": ""}}
    return {"doel": doel, "bron": bron, "hergebruik": hergebruik, "soort": soort, "aanduiding": aanduiding}


def annoteer_node(b: Bouw, state: State) -> dict[str, Any]:
    writer = get_stream_writer()
    if state.get("annotaties_lezen"):
        raise ValueError("Een leesroute mag geen annotatie produceren")
    # Een ONDERWERP in plaats van een bepaling: de ophaal-agent legt kandidaten voor en wij
    # annoteren nog niets. Welke bepaling de werkvoorraad in gaat is een keuze van de jurist.
    kandidaten = _kandidaten_uit_json(state.get("answer", ""))
    if kandidaten:
        writer({"type": "kandidaten", "kandidaten": kandidaten})
        melding = f"Ik vond {len(kandidaten)} bepalingen over dit onderwerp. Kies welke je wilt laten annoteren."
        writer({"type": "token", "content": melding})
        return {"answer": melding, "voorstellen": [], "messages": [{"role": "assistant", "content": melding}]}

    voorbereid = _bereid_voor(b, state, writer)
    if "klaar" in voorbereid:
        return voorbereid["klaar"]
    doel, bron, hergebruik = voorbereid["doel"], voorbereid["bron"], voorbereid["hergebruik"]
    soort, aanduiding, lid = voorbereid["soort"], voorbereid["aanduiding"], doel.get("lid", "")
    plek = aanduiding_in_woorden(aanduiding, lid, soort)
    _stap(writer, "Bron", f"{plek} ({len(bron['corpus'])} tekens)")

    uitkomst = analyseer(
        snapshot=bron["bron_snapshot"], corpus_segmenten=bron["corpus_segmenten"], corpus=bron["corpus"],
        llm=b.llm, model=b.model, settings=b.settings, lid=lid,
        vindplaats=f"{doel.get('bwbId', '')} {plek}",
        hergebruikte_nodes=frozenset(bron.get("hergebruikte_nodes") or []),
        melding=lambda fase, samenvatting, ms: _stap(writer, fase, samenvatting, duur_ms=ms),
    )
    if uitkomst.meting.get("gedegradeerd"):
        # De beurt slaagt, maar zonder zinsontleding ontbraken subject-, object- en bijzindetectie.
        # Dat hoort de jurist te weten, niet alleen in een ingeklapte statusregel.
        writer({"type": "waarschuwing", "message": (
            f"De zinsontleding was niet beschikbaar voor {len(uitkomst.meting['gedegradeerd'])} "
            "bronnode(s). Alleen vaste patronen (termijnen, bedragen, verwijzingen, formules) zijn "
            "gezocht; onderwerpen, voorwerpen en bijzinnen kunnen ontbreken.")})
    writer({"type": "doel", "doel": doel_event(doel, bron)})

    analyse = {"meting": uitkomst.meting,
               # Per kandidaat de uitkomst, óók als die "niets" was (validatieplan V4). Reist met de
               # dekking mee naar de batch; zie `jas_pipeline/beslisregister.py`.
               "beslissingen": beslisregister(uitkomst.fusie.kandidaten, uitkomst.beslissingen,
                                              uitkomst.voorstellen),
               "detectoren": [list(d) for d in uitkomst.fusie.detectoren],
               "overgeslagen": [o.model_dump() for o in uitkomst.fusie.overgeslagen]}
    if not uitkomst.voorstellen:
        leeg = f"Ik vond geen JAS-elementen om te markeren in {plek}."
        writer({"type": "token", "content": leeg})
        return {"answer": leeg, "voorstellen": [], **bron, "hergebruik": hergebruik or {}, "analyse": analyse,
                "messages": [{"role": "assistant", "content": leeg}]}
    return {"voorstellen": uitkomst.voorstellen, **bron, "hergebruik": hergebruik or {},
            "analyse": analyse, "answer": ""}


def _instellingen(b: Bouw, state: State) -> dict[str, Any]:
    """Wat de uitkomst van deze beurt stuurt, plus wat er gemeten is – voor de run-provenance."""
    s = b.settings
    return {"taal_provider": s.taal_provider, "classifier_granulariteit": s.classifier_granulariteit,
            "classifier_temperature": s.classifier_temperature, "classifier_spankeuze": s.classifier_spankeuze,
            "deterministisch_accepteren": s.deterministisch_accepteren, "gerichte_review": s.gerichte_review,
            "meting": (state.get("analyse") or {}).get("meting", {})}


def emit_node(b: Bouw, state: State) -> dict[str, Any]:
    """De enige plek die annotatie-events uitstuurt: één `run`, een `element` per voorstel en de
    samenvattings-`token`."""
    writer = get_stream_writer()
    if state.get("annotaties_lezen"):
        raise ValueError("Een leesroute mag geen annotatie opslaan")
    voorstellen = list(state.get("voorstellen") or [])
    hergebruik = state.get("hergebruik") or {}
    if not voorstellen and not hergebruik and not state.get("bron_snapshot"):
        return {}
    doel = _bepaal_doel(state)
    if hergebruik:
        # Vóór alles: de werkplek toont "hergebruikt uit een eerdere annotatie", en de driver legt
        # vast dát er hergebruikt is. Het event draagt geen elementen: de laag komt bij de api
        # vandaan (Postgres is de waarheid).
        writer({"type": "hergebruik", "hergebruik": {
            k: hergebruik[k] for k in ("slug", "status", "bijgewerkt", "leden", "telling", "volledig")
        }})
    if hergebruik.get("volledig"):
        return _emit_hergebruik(b, state, doel, hergebruik, writer)
    aanduiding = doel.get("artikel") or doel.get("nummer") or ""
    voorstellen = lokale_elementen(voorstellen, state)

    # Vóór de elementen: waarmee deze voorstellen zijn gemaakt. De werkplek legt het vast bij de api
    # en de export draagt het als herkomst; per element staat het spoor in `trace`.
    writer({"type": "run", "run": AgentRun(
        model=b.model, provider=b.settings.llm_provider, agent_versie=b.settings.agent_versie,
        modus="opnieuw" if state.get("hergebruik_modus") == "opnieuw" else "nieuw",
        prompt_hash=promptversie(b.settings.classifier_spankeuze), methode_versie=methode_versie(),
        instellingen=_instellingen(b, state), tijd=datetime.now(timezone.utc),
    ).model_dump(mode="json")})

    meting = (state.get("analyse") or {}).get("meting") or {}
    if meting.get("dekking") is not None:
        # Vóór de elementen: wat de keten wel en niet heeft kunnen bekijken. Vervangt de vervallen
        # `ontbrekend`-lijst – geen gok van een model over wat mist, maar een meting van welke tekst
        # geen enkele detector raakte. Nooit te lezen als recall.
        writer({"type": "dekking", "dekking": {
            "per_bron": meting["dekking"], "proces": meting.get("per_status", {}),
            "gedegradeerd": meting.get("gedegradeerd", []), "taal_model": meting.get("taal_model", ""),
            "fasen": meting.get("fasen", []),
            "beslissingen": (state.get("analyse") or {}).get("beslissingen", []),
        }})

    ter_keuze = 0
    for v in voorstellen:
        ter_keuze += v.get("aandacht") == "geel"
        writer({"type": "element", "element": v})

    plek = f"artikel {aanduiding}" + (f" lid {doel['lid']}" if doel.get("lid") else "")
    delen = [f"Ik heb {len(voorstellen)} JAS-elementen voorgesteld voor {plek}"]
    if ter_keuze:
        delen.append(f"{ter_keuze} met een keuze voor jou")
    samenvatting = "; ".join(delen) + "."
    _stap(writer, "Klaar", f"{len(voorstellen)} elementen ter beoordeling")
    writer({"type": "token", "content": samenvatting})

    # Geheugen: een leesbaar spoor van de annotatie, zodat een vervolgvraag ("waarom
    # Rechtssubject?") context heeft.
    elems = "; ".join(f"{v.get('klasse', '')}: '{truncate(str(v.get('tekst', '')), 80)}'" for v in voorstellen[:12])
    geheugen = f"[Annotatie {plek}] Ik markeerde {len(voorstellen)} JAS-elementen: {elems}" + (
        " (…)" if len(voorstellen) > 12 else "."
    )
    return {"answer": samenvatting, "messages": [{"role": "assistant", "content": geheugen}]}


def _emit_hergebruik(
    b: Bouw, state: State, doel: dict[str, Any], hergebruik: dict[str, Any], writer,
) -> dict[str, Any]:
    """De uitgang zonder nieuwe voorstellen: alles kwam uit de laag."""
    aanduiding = doel.get("artikel") or doel.get("nummer") or ""
    plek = f"artikel {aanduiding}" + (f" lid {doel['lid']}" if doel.get("lid") else "")
    writer({"type": "run", "run": AgentRun(
        model=b.model, provider=b.settings.llm_provider, agent_versie=b.settings.agent_versie,
        stop_reden="hergebruikt", modus="hergebruik",
        leden=[str(ld.get("lid", "")) for ld in hergebruik["leden"]],
        prompt_hash=promptversie(b.settings.classifier_spankeuze), methode_versie=methode_versie(),
        tijd=datetime.now(timezone.utc),
    ).model_dump(mode="json")})
    t = hergebruik["telling"]
    samenvatting = (
        f"{plek[0].upper()}{plek[1:]} is al geannoteerd en de wettekst is sindsdien niet veranderd. "
        f"Ik heb de bestaande annotatie hergebruikt: {t['markeringen']} markeringen, waarvan "
        f"{t['beoordeeld']} beoordeeld en {t['te_beoordelen']} nog te beoordelen."
        " Wil je toch een nieuwe ronde, vraag dan om opnieuw annoteren – wat al beoordeeld is "
        "blijft staan."
    )
    _stap(writer, "Klaar", f"hergebruikt · {t['markeringen']} markeringen uit de laag")
    writer({"type": "token", "content": samenvatting})
    markeringen = hergebruik.get("markeringen") or []
    elems = "; ".join(f"{m.get('klasse', '')}: '{truncate(m.get('tekst', ''), 80)}'"
                      for m in markeringen[:12])
    geheugen = (f"[Annotatie {plek}, hergebruikt] De laag bevat {len(markeringen)} JAS-elementen: "
                f"{elems}" + (" (…)" if len(markeringen) > 12 else "."))
    return {"answer": samenvatting, "messages": [{"role": "assistant", "content": geheugen}]}
