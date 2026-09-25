"""De annotatie-flow in de supervisor-graaf: supervisor → OPHAAL-agent (retrieval) → annoteer
(de hybride keten, ADR-001) → emit. Draait de échte LangGraph (prod-config: decompositie aan) met
KetenLLM/FakeGraph.

KetenLLM-volgorde per annotatie: supervisor(create) → ophaal-agent turn1(stream, tool_use) →
ophaal-agent turn2(stream, doel-JSON) → classifier (create, tool `classificeer`). De classifier-nep
leest de kandidaat-labels uit de prompt; `_alleen` kiest per fragment, de rest wordt afgewezen.
"""
from __future__ import annotations

import asyncio
import json

from bron_fakes import answer_stream
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from fakes import FakeGraph, FakeLLM, KetenLLM, make_settings, response, text_block, tool_block

# get_lid/get_bepaling leveren SPARQL-TSV met ?tekst; JSON-string-encoded zoals de MCP.
LID_TSV = json.dumps('?nummer\t?tekst\t?jci\n"1"\t"De ontvanger verleent uitstel van betaling."@nl\t"jci"')
DOEL_91 = '{"bwbId":"BWBR0004770","artikel":"9","lid":"1","nummer":"","citeertitel":"IW 1990"}'


def _aanloop(tool: str = "get_lid", invoer: dict | None = None, doel: str = DOEL_91,
             plan: str = "annoteer art 9 lid 1") -> list:
    return [
        response([text_block(f"WORKERS: annotatie\nPLAN: {plan}")], "end_turn"),                   # supervisor
        response([tool_block("t1", tool, invoer or {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})],
                 "tool_use"),
        response([text_block(doel)], "end_turn"),
    ]


def _alleen(**keuze: str):
    """Classifier-keuze per fragment; alles wat niet genoemd is, wordt afgewezen."""
    def kies(toegestaan, fragment):
        klasse = keuze.get(fragment)
        return klasse if klasse in toegestaan else GEEN_ANNOTATIE
    return kies


def _run(gen):
    async def collect():
        return [ev async for ev in gen]

    return asyncio.run(collect())


def _elementen(events):
    return [e["element"] for e in events if e["type"] == "element"]


def test_ophalen_dan_annoteren_grondt_lid():
    llm = KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
    events = _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        settings=make_settings(enable_decomposition=True), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))

    doel = next(e for e in events if e["type"] == "doel")["doel"]
    assert doel["bwbId"] == "BWBR0004770" and doel["artikel"] == "9" and doel["lid"] == "1"
    assert doel["leden_teksten"][0]["tekst"].startswith("De ontvanger")  # opgehaalde tekst meegestuurd

    elementen = _elementen(events)
    assert ("Rechtssubject", "De ontvanger") in {(el["klasse"], el["tekst"]) for el in elementen}
    for el in elementen:
        assert el["vindplaats"] == "BWBR0004770 art. 9 lid 1"
        assert el["trace"]["kandidaat"]["bewijs"], "elk voorstel draagt zijn spoor"


def test_get_bepaling_route_voor_decimaal_nummer():
    # Beleidsregel/divisie: de ophaal-agent gebruikt get_bepaling('9.1'); doel.nummer/artikel = '9.1'.
    bep_tsv = json.dumps('?nummer\t?tekst\t?label\n"9.1"\t"In de gevallen waarin binnen zes weken een voorlopige aanslag wordt opgelegd."@nl\t"Afwijking"')
    llm = KetenLLM(_aanloop(
        "get_bepaling", {"bwb_id": "BWBR0024096", "nummer": "9.1"},
        '{"bwbId":"BWBR0024096","nummer":"9.1","artikel":"","lid":"","citeertitel":"Leidraad Invordering 2008"}',
        "annoteer 9.1"))
    events = _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Leidraad Invordering 2008",
        settings=make_settings(enable_decomposition=True), llm=llm, graph=FakeGraph(result=bep_tsv),
    ))
    doel = next(e for e in events if e["type"] == "doel")["doel"]
    assert doel["nummer"] == "9.1" and doel["artikel"] == "9.1"
    elementen = _elementen(events)
    assert elementen
    assert {el["vindplaats"] for el in elementen} == {"BWBR0024096 bepaling 9.1"}


def test_annotatie_laat_leesbaar_spoor_in_geheugen(tmp_path):
    """Na een annotatie-beurt ziet een vervolgvraag (zelfde conversation_id) de gemarkeerde elementen
    terug in de historie – zodat 'waarom Rechtssubject?' context heeft."""
    settings = make_settings(enable_decomposition=False, checkpoint_db_path=str(tmp_path / "cp.db"))

    # Beurt 1: annoteer art. 9 lid 1.
    llm1 = KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
    _run(answer_stream("annoteer artikel 9 lid 1 IW", "annot-mem", settings=settings, llm=llm1, graph=FakeGraph(result=LID_TSV)))

    # Beurt 2: vervolgvraag; de agent moet de annotatie-samenvatting in de meegegeven historie zien.
    llm2 = FakeLLM([
        response([text_block("SPECIALIST: algemeen\nPLAN: direct")], "end_turn"),  # supervisor
        response([text_block("Omdat 'De ontvanger' de dragende actor is.")], "end_turn"),  # agent
    ])
    _run(answer_stream("waarom markeerde je 'De ontvanger' als Rechtssubject?", "annot-mem",
                       settings=settings, llm=llm2, graph=FakeGraph(result="")))

    serialized = " ".join(str(c.get("messages")) for c in llm2.calls)
    assert "[Annotatie" in serialized
    assert "Rechtssubject" in serialized and "De ontvanger" in serialized


def test_gewone_vraag_blijft_antwoord_geen_annotatie():
    llm = FakeLLM([
        response([text_block("SPECIALIST: algemeen\nPLAN: direct")], "end_turn"),  # supervisor → antwoord
        response([text_block("1. Wat is de termijn?")], "end_turn"),               # decompose (één regel)
        response([tool_block("t1", "get_lid", {"bwb_id": "BWBR0004770", "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block("Zes weken (BWBR0004770 art. 9).")], "end_turn"),      # solve-antwoord
    ])
    events = _run(answer_stream(
        "wat is de betaaltermijn?", settings=make_settings(enable_decomposition=True), llm=llm, graph=FakeGraph(result=LID_TSV),
    ))
    assert not any(e["type"] in ("doel", "element") for e in events)
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert "Zes weken" in tokens


def test_run_event_draagt_de_herkomst_van_de_beurt():
    """Precies één `run`-event, vóór de elementen, met het model dat ze maakte.

    Zonder deze herkomst kan de werkplek niet vastleggen waarmee geannoteerd is, en is achteraf
    niet meer te zeggen waar een markering vandaan komt.
    """
    llm = KetenLLM(_aanloop())
    events = _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        settings=make_settings(enable_decomposition=True,
                               llm_model="claude-sonnet-4-6", agent_versie="9.9.9"),
        llm=llm, graph=FakeGraph(result=LID_TSV),
    ))

    runs = [e for e in events if e["type"] == "run"]
    assert len(runs) == 1
    run = runs[0]["run"]
    assert run["model"] == "claude-sonnet-4-6"
    assert run["provider"] == "anthropic_via_azure_foundry"
    assert run["agent_versie"] == "9.9.9"
    assert run["tijd"]

    soorten = [e["type"] for e in events]
    assert soorten.index("run") < soorten.index("element")



# --- Het corpus is de bepaling, niet de zoektocht ernaartoe -------------------------------------
#
# De ophaal-agent mag omwegen nemen (eerst het hele artikel, dan het lid). Het corpus waarop
# geannoteerd wordt hoort dát niet te weerspiegelen: het is precies de bepaling uit het doel,
# gericht opgehaald. Werd het uit de tool-trace gereconstrueerd, dan zat de tekst van álle
# opgehaalde leden erin – en dan keurt de brongetrouwheidscheck een fragment uit lid 2 goed als
# markering "in lid 1", mét de vindplaats van lid 1.

# Twee leden in één artikel-resultaat, zoals get_artikel dat teruggeeft.
ARTIKEL_TSV = json.dumps(
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\n"
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:1>\t"1"'
    '\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening."\n'
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:2>\t"2"'
    '\t"De ontvanger kan uitstel van betaling verlenen."'
)

def test_corpus_blijft_binnen_het_gevraagde_lid():
    # De ophaal-agent haalt het HELE artikel op – een normale omweg. De classifier accepteert alles.
    llm = KetenLLM(_aanloop("get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"}))
    graaf = FakeGraph(result=ARTIKEL_TSV)   # élke query levert beide leden; het lid-filter doet het werk
    events = _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        settings=make_settings(enable_decomposition=True),
        llm=llm, graph=graaf,
    ))

    # De canonieke bronnode beperkt zowel zichtbare tekst als annotatie-input tot lid 1.
    doel = next(e for e in events if e["type"] == "doel")["doel"]
    assert "uitstel van betaling" not in doel["leden_teksten"][0]["tekst"]
    assert [s["bron_iri"] for s in doel["segmenten"]] == ["urn:bwb:BWBR0004770:artikel:9:lid:1"]

    elementen = _elementen(events)
    assert elementen
    assert not [el for el in elementen if "uitstel" in el["tekst"]], "niets uit lid 2"
    assert {el["vindplaats"] for el in elementen} == {"BWBR0004770 art. 9 lid 1"}


def test_onoplosbare_bronnode_valt_niet_terug_op_de_trace():
    """Een gevonden citaat is geen vervanging voor een canonieke bronnode."""
    llm = KetenLLM(_aanloop())

    def alleen_voor_de_toolcall(query: str) -> str:
        # get_artikel (de gerichte ophaal) levert niets; de lid-query van de agent wél.
        return "" if "SELECT DISTINCT ?node ?type ?parent" in query else LID_TSV

    events = _run(answer_stream(
        "annoteer artikel 9 lid 1 van de Invorderingswet 1990",
        settings=make_settings(enable_decomposition=True),
        llm=llm, graph=FakeGraph(results=alleen_voor_de_toolcall),
    ))

    elementen = [e["element"] for e in events if e["type"] == "element"]
    assert elementen == []
    assert llm.index == 3 and len(llm.calls) == 3, "geen classifier-call op een onoplosbare bron"
