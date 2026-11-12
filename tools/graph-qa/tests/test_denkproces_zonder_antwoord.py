"""Het denkproces toont de stappen, niet het antwoord, en het model schrijft het antwoord één keer (12 nov 2026).

Op acceptatie eindigde het denkproces met het hele antwoord (K17: "Laat ik de bevindingen voor je samenvatten. …", ~1.500
tekens), en daarna stond hetzelfde in het sjabloon. De oorzaak: een ronde met tools ging als narratie naar het denkproces,
ook als die tool het afrondende sjabloon was. Nu is een ronde met een sjabloon het antwoord: wat het model ernaast schreef
gaat niet naar het denkproces en niet de historie in, en de telling `sjabloon.tekst_ernaast` meet hoeveel het was.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agent.agent import answer_stream
from agent.models import Verbruiksmeter
from agent.narratie import denk_bij, ronde_in_denk
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

VECTOREN = json.loads((Path(__file__).parent / "data" / "denkproces-vectoren.json").read_text(encoding="utf-8"))

K = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:k"
RIJ = ("node\tbegrip\ttekst\tjci\tbwbId\tciteertitel\n"
       f'<{K}>\t"belastingschuldige"\t"belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;"\t'
       '"jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k"\t"BWBR0004770"\t"Invorderingswet 1990"\n')
KIES = response([text_block("WORKERS: antwoord\nSPECIALIST: definitie\nPLAN: zoek de definitie")], "end_turn")
NARRATIE = "Ik zoek eerst de definitie op."
PROZA = "**Kort antwoord**\n\nDe belastingschuldige is degene op wiens naam de aanslag staat. Laat ik dat samenvatten."
ZOEK = response([text_block(NARRATIE), tool_block("t1", "zoek_definitie", {"term": "belastingschuldige"})], "tool_use")


def _sjabloon(id: str = "t2", proza: str = "") -> object:
    blokken = [text_block(proza)] if proza else []
    return response([*blokken, tool_block(id, "antwoord_begrip", {"begrip": "belastingschuldige",
                                                                   "toelichting": "De tenaamstelling beslist."})], "tool_use")


def _beurt(*rondes):
    llm, meter = FakeLLM([KIES, *rondes]), Verbruiksmeter()

    async def alles():
        return [e async for e in answer_stream("Wat betekent belastingschuldige?", settings=make_settings(enable_planning=True),
                                               llm=llm, graph=FakeGraph(result=RIJ), meter=meter)]

    return asyncio.run(alles()), llm, meter


def _denk(events) -> str:
    denk = ""
    for e in events:
        denk = denk_bij(denk, e)
    return denk


def _tekst(events) -> str:
    return "".join(e.get("content", "") for e in events if e["type"] == "token")


def test_proza_naast_het_sjabloon_staat_niet_in_het_denkproces():
    events, llm, meter = _beurt(ZOEK, _sjabloon(proza=PROZA))
    denk = _denk(events)
    assert NARRATIE in denk, "narratie naast een zoektool blijft"
    assert "Kort antwoord" not in denk and "samenvatten" not in denk
    assert "De tenaamstelling beslist." in _tekst(events)
    assert meter.sjabloon["tekst_ernaast"] == len(PROZA)
    assert meter.sjabloon["gevuld"] == {"antwoord_begrip": 1}


def test_proza_naast_het_sjabloon_gaat_niet_de_historie_in():
    """Weigert de code het sjabloon, dan gaat er nog een verzoek naar het model. Daarin staat de proza niet: anders las het
    model zijn eigen dubbele antwoord bij elke volgende ronde opnieuw."""
    events, llm, _ = _beurt(_sjabloon(id="t0", proza=PROZA), ZOEK, _sjabloon())
    assert llm.index == 4
    assert "Kort antwoord" not in json.dumps(llm.calls[2]["messages"], ensure_ascii=False)
    assert "Kort antwoord" not in _denk(events)


def test_het_antwoord_staat_nooit_in_het_denkproces():
    events, _, _ = _beurt(ZOEK, _sjabloon(proza=PROZA))
    tekst, denk = _tekst(events), _denk(events)
    assert tekst.strip()
    for alinea in (a.strip() for a in tekst.split("\n\n")):
        assert not alinea or alinea not in denk, alinea


def test_zonder_proza_telt_er_niets():
    _, _, meter = _beurt(ZOEK, _sjabloon())
    assert "tekst_ernaast" not in meter.sjabloon


def test_ronde_in_denk_slaat_een_afrondronde_over():
    uit: list[dict] = []
    ronde_in_denk(uit.append, [{"name": "antwoord_duiding"}], [PROZA], 1, afronden={"antwoord_duiding"})
    ronde_in_denk(uit.append, [{"name": "get_artikel"}], [NARRATIE], 1, afronden={"antwoord_duiding"})
    assert uit == [{"type": "reason", "content": "\n\n" + NARRATIE}]


@pytest.mark.parametrize("geval", VECTOREN["gevallen"], ids=lambda g: g["naam"])
def test_denk_bij_volgt_de_gedeelde_vectoren(geval):
    assert _denk(geval["events"]) == geval["denk"]
