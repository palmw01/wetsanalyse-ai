"""Een annoteeropdracht die zelf één artikel noemt, gaat in code naar de annotatieketen – ook als hij herhaald wordt.

Acceptatie 23 nov 2026: "annoteer leidraad artikel 1.1.2", vijf keer in één gesprek. Eén keer koos de centrale agent de
overdracht `annoteer` en opende de hergebruikte laag naast het gesprek; vier keer schreef hij zonder tools "de annotatie is
al uitgevoerd en staat in de gesprekscontext", zonder artefact en met een grounding-melding over artikel 1.1.2.
"""
from __future__ import annotations

import asyncio

import pytest

from bron_fakes import answer_stream
from fakes import FakeGraph, KetenLLM, make_settings
from test_annotatie_worker import LID_TSV, _aanloop, _alleen

from agent.nodes.supervisie import annoteeropdracht


@pytest.mark.parametrize("vraag", [
    "annoteer leidraad artikel 1.1.2",
    "Annoteer artikel 9 lid 1 van de Invorderingswet 1990.",
    "annoteer art. 3:40 Awb",
    "Markeer artikel 25 IW",
    "Kun je artikel 9 lid 1 IW annoteren?",
    "opnieuw annoteer artikel 9 IW",
    "annoteer 9.1 en 9.3 van de Leidraad, artikel 9.1 en 9.3",
])
def test_een_opdracht_met_een_artikel_routeert_de_code(vraag):
    assert annoteeropdracht(vraag)


@pytest.mark.parametrize("vraag", [
    "Welke bepalingen van artikel 9 zijn al geannoteerd?",     # geen opdracht
    "wat betekent annoteren bij artikel 9?",                    # geen opdracht
    "annoteer lid 2",                                           # leunt op het gesprek: de centrale agent
    "doe hetzelfde voor lid 2",
    "annoteer artikel 8 en 9 IW",                               # meer artikelen: de weigering van de overdracht
    "waarom markeerde je artikel 9 zo?",
    "annoteer de bronnen onder deelvraag 3",                    # het werkgebied: de annotatie-agent
])
def test_geen_opdracht_voor_een_artikel_blijft_bij_de_centrale_agent(vraag):
    assert not annoteeropdracht(vraag)


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_dezelfde_opdracht_twee_keer_in_een_gesprek_annoteert_twee_keer(tmp_path):
    """De tweede keer leest geen model het gesprek om te beslissen: de keten draait opnieuw (en hergebruikt in het echt de
    laag die af is), dus er komt opnieuw een doel en een artefact."""
    settings = make_settings(checkpoint_db_path=str(tmp_path / "cp.db"))
    vraag = "annoteer artikel 9 lid 1 van de Invorderingswet 1990"
    for _ in range(2):
        llm = KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
        events = _run(answer_stream(vraag, "herhaald-1", settings=settings, llm=llm, graph=FakeGraph(result=LID_TSV)))
        assert any(e.get("type") == "status" and e.get("route") == "annotatie" for e in events)
        doel = next(e["doel"] for e in events if e["type"] == "doel")
        assert (doel["bwbId"], doel["artikel"], doel["lid"]) == ("BWBR0004770", "9", "1")
        assert "rol agent" not in str(llm.calls[0].get("system")), "de centrale agent draaide niet"
