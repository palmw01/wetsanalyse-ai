"""De ophaalstap van een annotatie haalt zelf op, ook als het gesprek zegt dat de bepaling al geannoteerd is.

Acceptatie 23 nov 2026, gesprek "acc-test-annoteer-herhaald": twee keer "annoteer leidraad artikel 1.1.2". De tweede keer
deed de ophaal-agent één ronde zonder tool (hij las in het gesprek dat het werk gedaan was) en gaf geen doel. Daarna riep
de keten `get_bronnode` aan met een leeg doel, en het antwoord was "Ik kan de gevraagde bepaling nu niet annoteren:
Ongeldig BWB-id".
"""
from __future__ import annotations

import asyncio

from bron_fakes import answer_stream
from fakes import FakeGraph, KetenLLM, make_settings, response, text_block
from test_annotatie_worker import LID_TSV, _aanloop, _alleen

from agent.nodes.annotatie import GEEN_DOEL
from agent.nodes.antwoord import OPHALEN_GEVRAAGD

VRAAG = "annoteer artikel 9 lid 1 van de Invorderingswet 1990"
AL_GEDAAN = response([text_block("Artikel 9 lid 1 is in de vorige beurt al geannoteerd; de markeringen staan in de "
                                 "gesprekscontext.")], "end_turn")


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def _beurt(llm, settings, gesprek="herhaald-ophalen"):
    return _run(answer_stream(VRAAG, gesprek, settings=settings, llm=llm, graph=FakeGraph(result=LID_TSV)))


def _doel(events):
    return next((e["doel"] for e in events if e["type"] == "doel"), None)


def test_haalt_de_tweede_keer_niets_op_dan_vraagt_de_code_het_een_keer(tmp_path):
    settings = make_settings(checkpoint_db_path=str(tmp_path / "cp.db"))
    eerste = _beurt(KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"})), settings)
    assert _doel(eerste)

    llm = KetenLLM([AL_GEDAAN, *_aanloop()], kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
    tweede = _beurt(llm, settings)
    doel = _doel(tweede)
    assert doel and (doel["bwbId"], doel["artikel"], doel["lid"]) == ("BWBR0004770", "9", "1")
    # De tweede modelronde kreeg de vraag om zelf op te halen, na het antwoord uit het gesprek.
    assert OPHALEN_GEVRAAGD in str(llm.calls[1].get("messages"))
    assert "Ongeldig BWB-id" not in str(tweede)


def test_haalt_hij_ook_daarna_niets_op_dan_een_melding_en_geen_leeg_doel(tmp_path):
    settings = make_settings(checkpoint_db_path=str(tmp_path / "cp.db"))
    graaf = FakeGraph(result=LID_TSV)
    llm = KetenLLM([AL_GEDAAN, AL_GEDAAN])
    events = _run(answer_stream(VRAAG, "geen-doel", settings=settings, llm=llm, graph=graaf))
    assert llm.index == 2, "één keer terug, niet vaker"
    assert _doel(events) is None and not [e for e in events if e["type"] == "element"]
    tekst = "".join(e.get("content", "") for e in events if e["type"] == "token")
    assert GEEN_DOEL in tekst and "Ongeldig BWB-id" not in tekst
    assert not [e for e in events if e.get("type") == "tool_execution" and e.get("tool") == "get_bronnode"], \
        "geen aanroep met een leeg doel"
