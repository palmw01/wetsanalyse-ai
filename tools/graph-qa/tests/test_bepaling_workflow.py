"""D1 (ADR-010): de tekst van een bepaling zonder modelronde – alleen bij één eenduidige lezing, nooit gokken."""
from __future__ import annotations

import pytest

from agent import bepaling_workflow as wf
from agent import overzicht
from fakes import FakeGraph

IW = "BWBR0004770"
NAMEN = ("?regeling\t?citeertitel\t?soort\t?afkortingen\n"
         f"<urn:bwb:{IW}>\t\"Invorderingswet 1990\"\t\"wet\"\t\"IW | Iw 1990\"\n"
         "<urn:bwb:BWBR0005537>\t\"Algemene wet bestuursrecht\"\t\"wet\"\t\"Awb\"\n")
INT = "^^<http://www.w3.org/2001/XMLSchema#integer>"


@pytest.fixture(autouse=True)
def _schone_namen():
    overzicht._REGELINGEN_CACHE.clear()
    yield
    overzicht._REGELINGEN_CACHE.clear()


def _graaf(**per_query) -> FakeGraph:
    """Antwoordt op de namenlijst en op de queries die een sleutelwoord bevatten (`:artikel:9:lid:1>` …)."""
    def antwoord(q: str) -> str:
        if "bwb:Regeling" in q:
            return NAMEN
        for sleutel, tsv in per_query.items():
            if sleutel.replace("_", ":") in q:
                return tsv
        return ""
    return FakeGraph(results=antwoord)


LID_9_1 = "?nummer\t?tekst\n\"1\"\t\"Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet.\"\n"


@pytest.mark.parametrize("vraag,verwacht", [
    ("Wat staat er in artikel 9, eerste lid, van de Invorderingswet 1990?", ("9", "1")),
    ("Wat zegt artikel 9 lid 1 IW?", ("9", "1")),
    ("Geef de tekst van artikel 25 van de Invorderingswet", ("25", "")),
    ("Wat staat er precies in art. 22 Iw 1990?", ("22", "")),
])
def test_een_tekstvraag_met_een_regeling_en_een_artikel_wordt_gelezen(vraag, verwacht):
    v = wf.lees(vraag, _graaf())
    assert v is not None and (v.bwb_id, v.artikel, v.lid) == (IW, *verwacht)


@pytest.mark.parametrize("vraag", [
    "Wat staat er in artikel 3?",                                          # geen regeling: doorvragen, niet gokken
    "Wat betekent artikel 9 van de Invorderingswet 1990?",                 # uitleg
    "Wat houdt lid 2 van artikel 25 Invorderingswet 1990 in?",             # uitleg
    "Wat staat er in artikel 8 en 9 van de Invorderingswet 1990?",         # twee artikelen
    "Wat staat er in artikel 9 lid 1 en 2 van de Invorderingswet 1990?",   # twee leden
    "Wat staat er in artikel 9 van de Invorderingswet 1990 en de Awb?",    # twee regelingen
    "Wat staat er in 25.1 van de Invorderingswet 1990?",                   # geen artikelnummer
    "Hoe verhoudt artikel 22 Invorderingswet 1990 zich tot artikel 9?",
])
def test_wat_de_code_niet_eenduidig_leest_gaat_de_gewone_weg(vraag):
    assert wf.lees(vraag, _graaf()) is None


def test_een_lid_wordt_opgehaald_en_door_de_code_aangewezen():
    g = _graaf(**{"artikel_9_lid_1>": LID_9_1})
    v = wf.lees("Wat staat er in artikel 9, eerste lid, van de Invorderingswet 1990?", g)
    trace = wf.haal(g, v)
    a = wf.antwoord(v, trace)
    assert a is not None and a.sjabloon == "bepaling"
    [item] = a.blokken[0].items
    assert item.tekst.startswith("Een belastingaanslag is invorderbaar") and item.vindplaats.iri == v.iri
    assert [naam for naam, _ in trace] == ["get_lid"]


def test_een_artikel_haalt_de_onderdelen_van_zijn_leden_er_zelf_bij():
    """Wat het model nu in twee extra rondes deed (doorbladeren, get_lid per lid), doet de code."""
    art = f"urn:bwb:{IW}:artikel:22"
    artikel = ("?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\t?lidonderdelen\n"
               f"\t\t<{art}:lid:1>\t\"1\"\t\"Derden kunnen in beroep.\"\t\"false\"\n"
               f"\t\t<{art}:lid:3>\t\"3\"\t\"Derden kunnen nimmer verzet doen tegen:\"\t\"true\"\n")
    lid3 = ("?nummer\t?tekst\t?o\t?onummer\t?otekst\t?ovolg\n"
            f"\"3\"\t\"Derden kunnen nimmer verzet doen tegen:\"\t<urn:bwb:{IW}:id:Slottekst1>\t\t\"indien de vruchten er zijn.\"\t\"9\"{INT}\n"
            f"\"3\"\t\"Derden kunnen nimmer verzet doen tegen:\"\t<{art}:lid:3:o:a>\t\"a.\"\t\"de beslaglegging;\"\t\"1\"{INT}\n")
    g = _graaf(**{"artikel_22>": artikel, "artikel_22_lid_3>": lid3})
    v = wf.lees("Wat staat er in artikel 22 van de Invorderingswet 1990?", g)
    trace = wf.haal(g, v)
    assert [naam for naam, _ in trace] == ["get_artikel", "get_lid"]
    a = wf.antwoord(v, trace)
    lid3_tekst = a.blokken[0].items[1].tekst
    assert lid3_tekst.index("a. de beslaglegging") < lid3_tekst.index("indien de vruchten"), "slotzin na de onderdelen"


def test_een_bepaling_die_er_niet_is_geeft_geen_antwoord():
    g = _graaf()  # elke query leeg
    v = wf.lees("Wat staat er in artikel 999 van de Invorderingswet 1990?", g)
    trace = wf.haal(g, v)
    assert trace is None or wf.antwoord(v, trace) is None


def test_een_graaffout_geeft_geen_antwoord_maar_none():
    class Kapot(FakeGraph):
        def sparql(self, query: str) -> str:
            if "bwb:Regeling" in query:
                return NAMEN
            raise RuntimeError("Repository inning doesn't exist")
    g = Kapot()
    v = wf.lees("Wat staat er in artikel 9 lid 1 IW?", g)
    assert wf.haal(g, v) is None


# --- de hele beurt -------------------------------------------------------------------------------

def _beurt(vraag: str, g: FakeGraph, *rondes):
    import asyncio

    from agent.agent import answer_stream
    from fakes import FakeLLM, make_settings
    llm = FakeLLM(list(rondes))

    async def alles():
        return [e async for e in answer_stream(vraag, settings=make_settings(), llm=llm, graph=g)]
    return asyncio.run(alles()), llm


def _eerste(events, soort):
    return next(e for e in events if e["type"] == soort)


def test_een_bepalingsvraag_kost_een_modelaanroep_en_toont_de_tekst_uit_de_graaf():
    from fakes import response, text_block
    g = _graaf(**{"artikel_9_lid_1>": LID_9_1})
    events, llm = _beurt("Wat staat er in artikel 9, eerste lid, van de Invorderingswet 1990?", g,
                         response([text_block("Dit lid zegt wanneer je een aanslag moet betalen.")], "end_turn"))
    assert llm.index == 1, "alleen de toelichting: geen supervisor, geen toollus"
    assert llm.calls[0]["tools"] == []
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "bepaling"
    assert antwoord["blokken"][0]["items"][0]["tekst"].startswith("Een belastingaanslag is invorderbaar")
    assert antwoord["blokken"][1]["tekst"] == "Dit lid zegt wanneer je een aanslag moet betalen."
    assert [e["tool"] for e in events if e["type"] == "tool_execution" and e["phase"] == "start"] == ["get_lid"]
    assert _eerste(events, "grounding")["grounded"] is True
    assert "urn:bwb:BWBR0004770:artikel:9:lid:1" in {s["iri"] for s in _eerste(events, "sources")["sources"]}


def test_zonder_toelichting_staat_de_wettekst_er_toch():
    from fakes import response
    g = _graaf(**{"artikel_9_lid_1>": LID_9_1})
    events, _ = _beurt("Wat zegt artikel 9 lid 1 IW?", g, response([], "max_tokens"))
    blokken = _eerste(events, "antwoord")["antwoord"]["blokken"]
    assert [b["soort"] for b in blokken] == ["wettekst"]


def test_niet_op_te_halen_gaat_de_gewone_weg_via_de_agent():
    from fakes import response, text_block
    g = _graaf()  # de bepaling is er niet
    events, llm = _beurt("Wat staat er in artikel 999 van de Invorderingswet 1990?", g,
                         response([text_block("Artikel 999 staat niet in de graaf.")], "end_turn"))
    assert llm.index == 1 and llm.calls[0]["tools"], "de agent krijgt de vraag, met zijn tools"
    assert "999" in _eerste(events, "token")["content"]
