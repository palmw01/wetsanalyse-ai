"""Twee knoppen die de annotatieketen goedkoper én betrouwbaarder maken.

1. **Model per rol** – de router en de ophaal-agent mogen op een ander model draaien dan de
   annoteerder en de Critic. Die laatste twee vellen het juridische oordeel en houden daarom geen
   eigen knop: er is geen env-var waarmee je ze per ongeluk degradeert.
2. **Een meegegeven `doel`** – weet de werkplek de bepaling al, dan slaat de beurt de supervisor én
   de ophaal-agent over. Dat scheelt calls, maar de echte winst is dat de agent dan niet meer bij
   een ándere bepaling kan uitkomen dan de jurist aanwees.
"""
from __future__ import annotations

import asyncio
import json

from bron_fakes import answer_stream
from agent.config import Settings
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from fakes import FakeGraph, KetenLLM, make_settings, response, text_block, tool_block

#: Antwoord op `get_lid` – wat de ophaal-agent als tool-resultaat terugkrijgt.
LID_TSV = json.dumps(
    '?nummer\t?tekst\t?jci\n"1"\t"De ontvanger verleent uitstel van betaling indien de schuldenaar '
    'daarom verzoekt."@nl\t"jci"'
)

#: Antwoord op `get_artikel` – de vorm die `artikel_corpus` leest bij het GERICHT ophalen. Zonder
#: ophaal-agent is er geen tool-trace om op terug te vallen, dus loopt het corpus hier langs.
ARTIKEL_TSV = json.dumps(
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\t?onderdeel\t?onderdeeltekst\n"
    '\t"jci"\t"lid-1"\t"1"\t"De ontvanger verleent uitstel van betaling indien de schuldenaar '
    'daarom verzoekt."@nl\t\t'
)

VRAAG = "annoteer artikel 9 lid 1 van de Invorderingswet 1990"
DOEL = {"bwbId": "BWBR0004770", "artikel": "9", "lid": "1", "citeertitel": "Invorderingswet 1990"}


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _keten(responses: list | None = None) -> KetenLLM:
    """Classifier-nep: alleen "De ontvanger" wordt Rechtssubject, de rest wordt afgewezen."""
    return KetenLLM(responses, kies=lambda toegestaan, fragment: (
        "Rechtssubject" if fragment == "De ontvanger" and "Rechtssubject" in toegestaan else GEEN_ANNOTATIE))


def _ketencalls(llm) -> list[dict]:
    """De calls van de annotatieketen zelf: classifier en gerichte reviewer."""
    return [c for c in llm.calls if (c.get("tools") or [{}])[0].get("name") in {"classificeer", "beoordeel"}]


def _aanloop() -> list:
    """Supervisor + de twee ophaal-beurten – de weg zonder meegegeven doel."""
    return [
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 1")], "end_turn"),
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})],
                 "tool_use"),
        response([text_block('{"bwbId":"BWBR0004770","artikel":"9","lid":"1"}')], "end_turn"),
    ]


# --- 1. model per rol -----------------------------------------------------------------------------

def test_model_voor_valt_terug_op_het_hoofdmodel():
    s = Settings(llm_model="sterk")
    assert s.model_voor("router") == "sterk"
    assert s.model_voor("ophaal") == "sterk"
    # De classifier en de reviewer hebben géén eigen knop: dat is de grens, geen omissie.
    assert s.model_voor("annoteerder") == "sterk"
    assert s.model_voor("critic") == "sterk"
    assert s.model_voor("bestaat-niet") == "sterk"


def test_model_voor_gebruikt_de_rol_override():
    s = Settings(llm_model="sterk", llm_model_router="klein", llm_model_ophaal="middel")
    assert s.model_voor("router") == "klein"
    assert s.model_voor("ophaal") == "middel"
    assert s.model_voor("annoteerder") == "sterk"


def test_from_env_leest_de_rol_modellen():
    s = Settings.from_env({"LLM_MODEL": "sterk", "LLM_MODEL_ROUTER": "klein"})
    assert (s.model_voor("router"), s.model_voor("ophaal")) == ("klein", "sterk")


def test_elke_rol_draait_op_zijn_eigen_model():
    """De volgorde van de calls is de volgorde van de keten: router → ophaal ×2 → classifier (→ reviewer)."""
    llm = _keten(_aanloop())
    _run(answer_stream(
        VRAAG,
        settings=make_settings(llm_model="sterk", llm_model_router="klein", llm_model_ophaal="middel"),
        llm=llm, graph=FakeGraph(result=LID_TSV),
    ))

    modellen = [c["model"] for c in llm.calls]
    assert modellen[:3] == ["klein", "middel", "middel"]
    assert _ketencalls(llm) and set(modellen[3:]) == {"sterk"}, "wie het oordeel velt, draait op het hoofdmodel"


def test_zonder_overrides_draait_alles_op_een_model():
    """Terugdraaien is een lege env-var: dan is de keten byte-voor-byte de oude."""
    llm = _keten(_aanloop())
    _run(answer_stream(
        VRAAG, settings=make_settings(llm_model="sterk"), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert {c["model"] for c in llm.calls} == {"sterk"}


# --- 2. een meegegeven doel -----------------------------------------------------------------------

def _met_doel(doel: dict, llm: KetenLLM):
    return _run(answer_stream(
        VRAAG, doel=doel, settings=make_settings(), llm=llm, graph=FakeGraph(result=ARTIKEL_TSV),
    ))


def test_een_meegegeven_doel_slaat_supervisor_en_ophaal_over():
    """Alleen de annotatieketen zelf draait: geen supervisor, geen ophaal-agent."""
    llm = _keten()
    events = _met_doel(DOEL, llm)

    assert llm.calls and llm.calls == _ketencalls(llm), "supervisor en ophaal-agent horen niet te draaien"
    elementen = [e["element"] for e in events if e["type"] == "element"]
    assert ("Rechtssubject", "De ontvanger") in {(el["klasse"], el["tekst"]) for el in elementen}


def test_het_meegegeven_doel_is_het_doel_dat_eruit_komt():
    """De bepaling die de jurist aanwees, niet een die een agent erbij zocht."""
    llm = _keten()
    events = _met_doel(DOEL, llm)

    doel_ev = next(e["doel"] for e in events if e["type"] == "doel")
    assert doel_ev["bwbId"] == "BWBR0004770"
    assert (doel_ev["artikel"], doel_ev["lid"]) == ("9", "1")
    assert doel_ev["citeertitel"] == "Invorderingswet 1990"


def test_het_corpus_komt_gericht_uit_de_graaf():
    """Zonder ophaal-agent is er geen tool-trace; het corpus moet dus uit de gerichte SPARQL komen."""
    graaf = FakeGraph(result=ARTIKEL_TSV)
    llm = _keten()
    _run(answer_stream(VRAAG, doel=DOEL, settings=make_settings(), llm=llm, graph=graaf))

    assert graaf.queries, "er hoort één gerichte ophaalactie te zijn gedaan"
    assert "De ontvanger" in str(llm.calls[0]["messages"])


def test_een_half_doel_gaat_gewoon_de_gewone_weg():
    """Alleen een bwbId is geen bepaling: dan is er wél iets te zoeken."""
    llm = _keten(_aanloop())
    _run(answer_stream(
        VRAAG, doel={"bwbId": "BWBR0004770"}, settings=make_settings(),
        llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert "WORKERS" in llm.calls[0]["system"] and llm.index == 3, "supervisor en ophaal-agent draaiden"


def test_zonder_doel_verandert_er_niets():
    llm = _keten(_aanloop())
    events = _run(answer_stream(
        VRAAG, settings=make_settings(), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert llm.index == 3 and _ketencalls(llm)
    assert "De ontvanger" in [e["element"]["tekst"] for e in events if e["type"] == "element"]


# ── adviesvragen hebben een onderwerp nodig ──────────────────────────────────────────────────────

def test_een_adviesvraag_zonder_context_wordt_geweigerd():
    """Zonder onderwerp bouwt _advies_context een kop zonder inhoud en antwoordt het model over
    "de markering" zonder te weten welke — een vaag antwoord in plaats van een fout."""
    import pytest
    from pydantic import ValidationError

    from agent.models import ChatRequest

    with pytest.raises(ValidationError) as fout:
        ChatRequest(question="Waarom deze klasse?", modus="advies")
    assert "fragment" in str(fout.value)


def test_een_fragment_is_genoeg_voor_een_adviesvraag():
    from agent.models import ChatContext, ChatRequest

    r = ChatRequest(question="Waarom?", modus="advies",
                    context=ChatContext(fragment="de ontvanger kan aansprakelijk stellen"))
    assert r.modus == "advies"


def test_een_bepaling_is_ook_genoeg():
    from agent.models import ChatContext, ChatRequest

    r = ChatRequest(question="Waarom?", modus="advies",
                    context=ChatContext(bwbId="BWBR0004770", artikel="36"))
    assert r.context.bwbId == "BWBR0004770"


def test_een_gewone_vraag_heeft_geen_context_nodig():
    """De eis geldt alleen voor modus 'advies'; een normale vraag mag kaal binnenkomen."""
    from agent.models import ChatRequest

    assert ChatRequest(question="Wat regelt artikel 36?").context is None
