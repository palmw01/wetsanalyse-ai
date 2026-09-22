"""Hergebruik van de gedeelde annotatielaag: een artikel dat al geannoteerd is en niet veranderde,
gaat niet opnieuw door het model."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest

from agent.agent import answer_stream
from agent.annotatie import _fnv1a_32
from agent.beurt import voer_beurt_uit
from agent.runs import Run
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block

LID1 = "1. Een belastingaanslag is invorderbaar zes weken na de dagtekening."
LID2 = "2. De ontvanger kan uitstel van betaling verlenen."
ARTIKEL = f"{LID1}\n\n{LID2}"
DOEL = {"bwbId": "BWBR0004770", "artikel": "9", "citeertitel": "IW 1990"}

ARTIKEL_TSV = json.dumps(
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\n"
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:1>\t"1"'
    '\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening."\n'
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:2>\t"2"'
    '\t"De ontvanger kan uitstel van betaling verlenen."'
)


def _laag_tsv(leden: dict[str, str]) -> str:
    rijen = "".join(
        f'\n"laag1"\t<urn:jas-ns:status-in_review>\t"2026-09-01T12:00:00+00:00"\t"{lid}"\t"{h}"'
        for lid, h in leden.items()
    )
    return json.dumps("?slug\t?status\t?bijgewerkt\t?lid\t?hash" + rijen)


MARKERINGEN_TSV = json.dumps(
    "?id\t?klasse\t?tekst\t?lid\t?lifecycle"
    '\n"e1"\t"Rechtsobject"\t"Een belastingaanslag"\t"1"\t"human_approved"'
    '\n"e2"\t"Rechtssubject"\t"De ontvanger"\t"2"\t"voorgesteld"'
)


def _graaf(laag: dict[str, str] | None, *, laag_faalt: bool = False) -> FakeGraph:
    def antwoord(query: str) -> str:
        if "jas:AnnotatieLaag" in query:
            if laag_faalt:
                raise RuntimeError("GraphDB even weg")
            return _laag_tsv(laag) if laag else json.dumps("?slug\t?status\t?bijgewerkt\t?lid\t?hash")
        if "jas:Markering" in query:
            return MARKERINGEN_TSV
        return ARTIKEL_TSV
    return FakeGraph(results=antwoord)


def _annotatie(*elementen: dict) -> Any:
    return response([text_block(json.dumps({"elementen": list(elementen)}))], "end_turn")


GEEN_OORDEEL = response([text_block(json.dumps({"oordelen": [], "ontbrekend": []}))], "end_turn")


def _draai(llm: FakeLLM, graaf: FakeGraph, *, lid: str = "", hergebruik: str = "auto",
           **settings: Any) -> list[dict]:
    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer", doel={**DOEL, "lid": lid}, llm=llm, graph=graaf, hergebruik=hergebruik,
            settings=make_settings(enable_decomposition=True, critic_max_rondes=0, **settings),
        )]
    return asyncio.run(verzamel())


def _van(events: list[dict], soort: str) -> list[dict]:
    return [e for e in events if e["type"] == soort]


# --- de keten ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("splitsing", [False, True], ids=["annoteer", "kandidaat-splitsing"])
def test_ongewijzigd_lid_kost_geen_llm_call(splitsing: bool):
    llm = FakeLLM([])        # elke aanroep zou een IndexError geven
    graaf = _graaf({"2": _fnv1a_32(LID2)})
    events = _draai(llm, graaf, lid="2", enable_kandidaat_splitsing=splitsing)

    assert llm.calls == [] and not _van(events, "error")
    assert not _van(events, "element")
    hergebruik, = [e["hergebruik"] for e in _van(events, "hergebruik")]
    assert hergebruik["volledig"] and hergebruik["slug"] == "laag1"
    assert [ld["lid"] for ld in hergebruik["leden"]] == ["2"]
    # Alleen de markeringen van dít lid tellen mee.
    assert hergebruik["telling"] == {"markeringen": 1, "beoordeeld": 0, "afgewezen": 0,
                                     "te_beoordelen": 1}
    run, = [e["run"] for e in _van(events, "run")]
    assert run["modus"] == "hergebruik" and run["leden"] == ["2"]
    assert "hergebruikt" in "".join(e["content"] for e in _van(events, "token"))
    # Het doel draagt de lidstand, zodat de driver het hergebruik kan vastleggen.
    doel, = [e["doel"] for e in _van(events, "doel")]
    assert doel["leden"][0]["hash"] == _fnv1a_32(LID2)
    # De laag is gelezen uit zijn eigen named graph, niet uit de union.
    assert any("GRAPH <urn:jas:graph:BWBR0004770:artikel:9>" in q for q in graaf.queries)


def test_gewijzigd_lid_wordt_gewoon_geannoteerd():
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    events = _draai(llm, _graaf({"2": "oude-hash"}), lid="2")
    assert not _van(events, "hergebruik")
    assert [e["element"]["tekst"] for e in _van(events, "element")] == ["De ontvanger"]
    assert _van(events, "run")[0]["run"]["modus"] == "nieuw"


def test_deels_gewijzigd_artikel_annoteert_alleen_het_gewijzigde_lid():
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    events = _draai(llm, _graaf({"1": _fnv1a_32(LID1), "2": "oude-hash"}))

    # Het model kreeg alleen lid 2 te lezen.
    prompt = llm.calls[0]["messages"][0]["content"]
    assert LID2 in prompt and LID1 not in prompt

    hergebruik, = [e["hergebruik"] for e in _van(events, "hergebruik")]
    assert not hergebruik["volledig"] and [ld["lid"] for ld in hergebruik["leden"]] == ["1"]
    # Naar de api gaat alleen de stand van het lid dat opnieuw is geannoteerd.
    doel, = [e["doel"] for e in _van(events, "doel")]
    assert [ld["lid"] for ld in doel["leden"]] == ["2"]
    assert doel["leden_teksten"][0]["tekst"] == ARTIKEL
    # En het anker staat gewoon op het hele artikel.
    a = _van(events, "element")[0]["element"]["anker"]
    assert ARTIKEL[a["start"]:a["eind"]] == "De ontvanger" and a["lid_hash"] == _fnv1a_32(LID2)


def test_opnieuw_annoteren_kijkt_niet_naar_de_laag():
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    graaf = _graaf({"2": _fnv1a_32(LID2)})
    events = _draai(llm, graaf, lid="2", hergebruik="opnieuw")
    assert not _van(events, "hergebruik") and _van(events, "element")
    assert not any("jas:AnnotatieLaag" in q for q in graaf.queries)
    assert _van(events, "run")[0]["run"]["modus"] == "opnieuw"


def test_onleesbare_laag_betekent_gewoon_annoteren():
    """Een GraphDB die hapert is geen reden om niet te annoteren; de api is het vangnet."""
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    events = _draai(llm, _graaf(None, laag_faalt=True), lid="2")
    assert not _van(events, "error") and _van(events, "element")


def test_geen_laag_betekent_gewoon_annoteren():
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    events = _draai(llm, _graaf(None), lid="2")
    assert not _van(events, "hergebruik") and _van(events, "element")


# --- vastleggen -------------------------------------------------------------------------------------

class NepApi:
    def __init__(self, hergebruikt: list[str] | None = None) -> None:
        self.hergebruik_posts: list[dict] = []
        self.laag_puts: list[dict] = []
        self.berichten: list[dict] = []
        self.verworpen = 0
        self.hergebruikt = hergebruikt or []

    async def hergebruik(self, **kw: Any) -> dict:
        self.hergebruik_posts.append(kw)
        return {"slug": "laag1"}

    async def zet_laag_elementen(self, **kw: Any) -> dict:
        self.laag_puts.append(kw)
        return {"slug": "laag1"}

    async def voeg_bericht_toe(self, gesprek_id: str, bericht: dict) -> dict:
        self.berichten.append(bericht)
        return {}

    async def aclose(self) -> None:
        pass


def _leg_vast(events: list[dict], nep: NepApi, monkeypatch) -> list[dict]:
    monkeypatch.setattr("agent.beurt.WetsanalyseApi", lambda *_a, **_k: nep)

    async def stroom():
        for e in events:
            yield e

    async def draai():
        return [e async for e in voer_beurt_uit(
            stroom(), run=Run(run_id="r1", conversation_id="g1", vraag="v"), gesprek_id="g1",
            user_id="jurist", settings=make_settings(wetsanalyse_api_url="http://api",
                                                     wetsanalyse_api_token="t", qa_api_token="q"),
        )]
    return asyncio.run(draai())


def test_volledig_hergebruik_wordt_vastgelegd_zonder_merge(monkeypatch):
    events = _draai(FakeLLM([]), _graaf({"2": _fnv1a_32(LID2)}), lid="2")
    nep = NepApi()
    uit = _leg_vast(events, nep, monkeypatch)

    post, = nep.hergebruik_posts
    assert (post["bwb_id"], post["artikel"]) == ("BWBR0004770", "9")
    assert [ld["lid"] for ld in post["leden"]] == ["2"] and post["run"]["modus"] == "hergebruik"
    assert nep.laag_puts == []
    assert nep.berichten[0]["annotatie_slug"] == "laag1"
    assert [e for e in uit if e["type"] == "opgeslagen"][0]["annotatie_slug"] == "laag1"


def test_gemist_hergebruik_is_meetbaar(monkeypatch, caplog):
    """De graaf zag het lid niet als geannoteerd, de api wel: de projectie liep achter. Dat kost
    tokens, geen werk – maar het moet in de log staan."""
    llm = FakeLLM([_annotatie({"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}),
                   GEEN_OORDEEL])
    events = _draai(llm, _graaf(None), lid="2")
    with caplog.at_level(logging.WARNING, logger="graph_qa.beurt"):
        _leg_vast(events, NepApi(hergebruikt=["2"]), monkeypatch)
    assert any(r.getMessage() == "hergebruik_gemist" for r in caplog.records)
