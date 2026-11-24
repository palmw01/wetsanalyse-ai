"""Het denkproces van "annoteer artikel 9 lid 1 van de Invorderingswet 1990" als de laag al af is (acceptatie 24 nov 2026).

Daar stond:

    · Lex · zoekt in de wetgeving en Kamerstukken, Staatsblad en Staatscourant, Rechtspraak, … (alle aangezette bronnen)
    · Wetgeving · artikel 9, lid 1 (Invorderingswet 1990) gelezen      ← get_lid van de ophaal-agent
    · Wetgeving · artikel 9, lid 1 (Invorderingswet 1990) gelezen      ← get_bronnode van de code
    · Annotaties · gelezen                                              ← get_annotatiedekking
    · Annotaties · gelezen                                              ← get_annotatieweergave
    · Hergebruik · … 9 markeringen uit de graaf (7 beoordeeld, 1 te beoordelen)

Vijf echte, verschillende aanroepen, maar drie paren gelijke regels, een bronregel met bronnen die de ophaal-agent niet
kan gebruiken, en een telling die niet sluit (de afgewezen markering viel weg). Elke aanroep houdt zijn regel (D-2, één
op één), maar elke regel zegt wat déze aanroep opleverde.
"""
from __future__ import annotations

import asyncio
import json

from agent.agent import answer_stream
from agent.bron_annotatie import telling_tekst
from agent.spoorbronnen import uitkomstregel
from bron_fakes import BronGraph, bronrijen
from bronmodel import bouw_snapshot
from fakes import FakeGraph, KetenLLM, make_settings, response, text_block, tool_block

BWB = "BWBR0004770"
LID1 = "urn:bwb:BWBR0004770:artikel:9:lid:1"
ARTIKEL_TSV = json.dumps(
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\n"
    f'\t"jci"\t<{LID1}>\t"1"\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening."\n'
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:2>\t"2"\t"De ontvanger kan uitstel van betaling verlenen."')
DOEL = {"bwbId": BWB, "artikel": "9", "citeertitel": "Invorderingswet 1990"}
ALLE = {f"connector_{n}": True for n in ("kamerstukken", "rechtspraak", "bekendmakingen", "kennisgroepen",
                                          "wetgeving_live")}


class AfgerondeLaag:
    """De laag van lid 1 is af: drie markeringen, één per review-stand (beoordeeld, afgewezen, te beoordelen)."""

    def __init__(self):
        self.snapshot = bouw_snapshot(bronrijen(ARTIKEL_TSV, DOEL), bwb_id=BWB, artikel="9", lid="1")
        self.iri = self.snapshot["segmenten"][0]["bron_iri"]

    def dekking(self, _doel):
        return {"status": "ok", "snapshot_id": self.snapshot["snapshot_id"], "voltooid": True, "parent_context": True,
                "bereik": [self.iri], "peilmoment": "2026-11-24T08:43:40Z"}

    def weergave(self, _doel):
        return {"schema_versie": 2, "snapshot_id": self.snapshot["snapshot_id"], "lagen": [],
                "elementen": [{"id": f"e{i}", "klasse": "Rechtssubject", "tekst": "De ontvanger", "eigenaar_iri": self.iri,
                               "lifecycle": lc, "lid": "1"}
                              for i, lc in enumerate(("human_approved", "rejected", "voorgesteld"))]}


def _beurt() -> list[dict]:
    graph = BronGraph(FakeGraph(result=ARTIKEL_TSV), {**DOEL, "lid": "1"})
    llm = KetenLLM([
        response([tool_block("t1", "get_lid", {"bwb_id": BWB, "artikel": "9", "lid": "1"})], "tool_use"),
        response([text_block('{"bwbId":"BWBR0004770","artikel":"9","lid":"1","nummer":"","citeertitel":"IW 1990"}')],
                 "end_turn"),
    ])

    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer artikel 9 lid 1 van de Invorderingswet 1990", settings=make_settings(**ALLE), llm=llm,
            graph=graph, annotaties=AfgerondeLaag())]
    return asyncio.run(verzamel())


def _statussen(events: list[dict]) -> list[str]:
    return [e["message"] for e in events if e.get("type") == "status"]


def test_elke_aanroep_een_eigen_regel_en_geen_regel_twee_keer():
    events = _beurt()
    regels = _statussen(events)
    aanroepen = [e["tool"] for e in events if e.get("type") == "tool_execution" and e.get("phase") == "end"]
    assert aanroepen == ["get_lid", "get_bronnode", "get_annotatiedekking", "get_annotatieweergave"], aanroepen
    assert len(regels) == len(set(regels)), regels
    assert not any(regels[i] == regels[i + 1] for i in range(len(regels) - 1)), regels
    tekst = "\n".join(regels)
    assert "Wetgeving · tekst van artikel 9, lid 1" in tekst and "vastgelegd om te annoteren" in tekst, regels
    assert any(r.startswith("Annotaties · ") and r.endswith(": al geannoteerd") for r in regels), regels
    assert any(r.startswith("Annotaties · ") and r.endswith(": 3 markeringen gelezen") for r in regels), regels
    assert "Annotaties · gelezen" not in regels


def test_de_ophaal_agent_noemt_geen_bronnen_die_hij_niet_gebruikt():
    """De ophaal-agent (profiel `retrieval`) leest alleen de wetgeving: geen regel met Kamerstukken, Rechtspraak, …,
    ook niet als die aanstaan."""
    regels = _statussen(_beurt())
    assert not any(label in r for r in regels
                   for label in ("Kamerstukken", "Rechtspraak", "Staatsblad", "Kennisgroepstandpunten")), regels


def test_de_telling_sluit():
    events = _beurt()
    hergebruik, = [e["hergebruik"] for e in events if e.get("type") == "hergebruik"]
    assert hergebruik["telling"] == {"markeringen": 3, "beoordeeld": 1, "afgewezen": 1, "te_beoordelen": 1}
    regel, = [r for r in _statussen(events) if r.startswith("Hergebruik · ")]
    assert "3 markeringen uit de graaf (1 beoordeeld, 1 afgewezen en 1 te beoordelen)" in regel, regel
    antwoord = "".join(e["content"] for e in events if e.get("type") == "token")
    assert "3 markeringen, waarvan 1 beoordeeld, 1 afgewezen en 1 nog te beoordelen." in antwoord, antwoord


def test_telling_tekst_sluit_altijd():
    assert telling_tekst({"markeringen": 9, "beoordeeld": 7, "afgewezen": 1, "te_beoordelen": 1}) == \
        "7 beoordeeld, 1 afgewezen en 1 te beoordelen"
    assert telling_tekst({"markeringen": 33, "beoordeeld": 33, "afgewezen": 0, "te_beoordelen": 0}) == "33 beoordeeld"
    assert telling_tekst({"markeringen": 2, "beoordeeld": 0, "afgewezen": 0, "te_beoordelen": 2}, nog=True) == \
        "2 nog te beoordelen"
    assert telling_tekst({"markeringen": 0}) == "geen"


def test_dekking_en_weergave_zeggen_wat_ze_opleverden():
    eind = {"status": "ok", "aantal": None, "has_more": False}
    doel = {"bron_iri": LID1}
    assert uitkomstregel("get_annotatiedekking", doel, eind, {"bereik": [], "voltooid": False}).endswith(
        ": nog niet geannoteerd")
    assert uitkomstregel("get_annotatiedekking", doel, eind, {"bereik": [LID1], "voltooid": False}).endswith(
        ": deels geannoteerd")
    assert uitkomstregel("get_annotatieweergave", doel, eind, {"elementen": []}).endswith(": nog geen markeringen")
    assert uitkomstregel("get_annotatieweergave", doel, eind, {"elementen": [{}]}).endswith(": 1 markering gelezen")
    # Zonder herkenbare vorm de gewone regel, nooit leeg.
    assert uitkomstregel("get_annotatieweergave", doel, eind, {}).endswith("gelezen")
