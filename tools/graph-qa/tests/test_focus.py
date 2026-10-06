"""De focus: waar het gesprek over gaat, als toestand naast de berichten.

Zonder focus routeerde de supervisor een vervolgvraag op de kale tekst, en wist een specialist na
een annotatie niet welke bepaling en welke markering ("die markering") bedoeld werd: de historie
bevatte één regel zonder bronnode of element-id.
"""
from __future__ import annotations

import asyncio

from bron_fakes import answer_stream
from fakes import FakeGraph, FakeLLM, KetenLLM, make_settings, response, text_block
from test_annotatie_worker import LID_TSV, _aanloop, _alleen

from agent.focus import als_context, bij_advies, na_annotatie, na_antwoord

SNAPSHOT = {"doel": {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "bwb_id": "BWBR0004770",
                     "citeertitel": "Invorderingswet 1990"}}


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_annotatie_zet_de_focus_en_een_antwoord_behoudt_haar():
    focus = na_annotatie(SNAPSHOT, "artikel 9 lid 1", "IW 1990",
                         [{"id": "e1", "klasse": "Rechtssubject", "tekst": "De ontvanger", "aandacht": "geel"}])
    assert focus["bron_iri"].endswith(":lid:1") and focus["label"] == "artikel 9 lid 1 IW 1990"
    na = na_antwoord(focus, "duiding", ["urn:bwb:BWBR0004770:artikel:9"])
    assert na["elementen"] == focus["elementen"], "een uitleg verschuift het onderwerp niet"
    assert na["laatste_route"] == "duiding" and na["bronnen"] == ["urn:bwb:BWBR0004770:artikel:9"]
    tekst = als_context(na, [])
    assert "e1 · Rechtssubject · \"De ontvanger\" (geel)" in tekst
    assert "get_annotatie" in tekst and "urn:bwb:BWBR0004770:artikel:9:lid:1" in tekst


def test_advies_wijst_een_element_aan_dat_blijft_staan():
    focus = bij_advies({}, {"element_id": "e7", "klasse": "Voorwaarde", "fragment": "indien x",
                            "bron_iri": "urn:bwb:BWBR0004770:artikel:12:lid:1"})
    assert focus["element"] == {"id": "e7", "klasse": "Voorwaarde", "tekst": "indien x"}
    volgende = na_antwoord(focus, "duiding", [])
    assert volgende["element"]["id"] == "e7"
    assert "Aangewezen markering: e7" in als_context(volgende, [])


def test_open_markeringen_gaan_mee_bij_een_gewone_vraag():
    tekst = als_context({}, [], [{"klasse": "Rechtssubject", "tekst": "de ontvanger"}])
    assert "nu open heeft" in tekst and "de ontvanger" in tekst
    assert als_context({}, [], []) == ""


def test_vervolgvraag_na_annotatie_kent_bepaling_en_element_ids(tmp_path):
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))
    llm1 = KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
    events = _run(answer_stream("annoteer artikel 9 lid 1 IW", "focus-1", settings=settings, llm=llm1,
                                graph=FakeGraph(result=LID_TSV)))
    element = next(e["element"] for e in events if e["type"] == "element")

    llm2 = FakeLLM([
        response([text_block("SPECIALIST: duiding\nPLAN: leg de markering uit")], "end_turn"),
        response([text_block("Omdat de ontvanger de handelende partij is.")], "end_turn"),
    ])
    _run(answer_stream("waarom die klasse?", "focus-1", settings=settings, llm=llm2, graph=FakeGraph(result="")))

    supervisor, specialist = (str(c.get("system")) for c in llm2.calls[:2])
    for systeem in (supervisor, specialist):
        assert "urn:bwb:BWBR0004770:artikel:9:lid:1" in systeem, "de bepaling staat in de context"
        assert element["id"] in systeem, "het element is bij id aan te spreken"
    historie = str(llm2.calls[1].get("messages"))
    assert element["id"] in historie and "bronnode urn:bwb:BWBR0004770:artikel:9:lid:1" in historie
