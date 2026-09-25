"""Hergebruik van de gedeelde annotatielaag: een artikel dat al geannoteerd is en niet veranderde,
gaat niet opnieuw door het model."""
from __future__ import annotations

import asyncio
import json
from typing import Any


from agent.agent import answer_stream
from bronmodel import bouw_snapshot
from bron_fakes import bronrijen
from agent.annotatie import _fnv1a_32
from agent.beurt import voer_beurt_uit
from agent.runs import Run
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from fakes import FakeGraph, FakeLLM, KetenLLM, make_settings

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
    graph = FakeGraph(result=bronrijen(ARTIKEL_TSV, DOEL))
    graph.laag, graph.laag_faalt, graph.api_calls = laag or {}, laag_faalt, []
    return graph


class NodeLeesApi:
    def __init__(self, graph, lid):
        self.graph = graph
        self.snapshot = bouw_snapshot(graph._result, bwb_id=DOEL["bwbId"], artikel="9", lid=lid)
        self.nodes = {s["nummer"]: s for s in self.snapshot["segmenten"]}
        self.complete = {self.nodes[n]["bron_iri"] for n, value in graph.laag.items()
                         if n in self.nodes and value == _fnv1a_32({"1": LID1, "2": LID2}[n])}
    def dekking(self, _doel):
        self.graph.api_calls.append("dekking")
        return {"status": "unavailable" if self.graph.laag_faalt else "ok",
                "snapshot_id": self.snapshot["snapshot_id"], "voltooid": len(self.complete) == len(self.nodes),
                "parent_context": len(self.complete) == len(self.nodes), "bereik": sorted(self.complete)}
    def weergave(self, _doel):
        self.graph.api_calls.append("weergave")
        elements = [{"id": "e"+n, "klasse": "Rechtssubject", "tekst": "De ontvanger" if n == "2" else "Een belastingaanslag",
                     "eigenaar_iri": node["bron_iri"], "lifecycle": "voorgesteld", "lid": n}
                    for n, node in self.nodes.items() if node["bron_iri"] in self.complete]
        return {"schema_versie": 2, "snapshot_id": self.snapshot["snapshot_id"], "elementen": elements, "lagen": []}


def _keten() -> KetenLLM:
    """Classifier-nep: "De ontvanger" wordt Rechtssubject, de rest wordt afgewezen."""
    return KetenLLM(kies=lambda toegestaan, fragment: (
        "Rechtssubject" if fragment == "De ontvanger" and "Rechtssubject" in toegestaan else GEEN_ANNOTATIE))


def _draai(llm: FakeLLM, graaf: FakeGraph, *, lid: str = "", hergebruik: str = "auto",
           **settings: Any) -> list[dict]:
    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer", doel={**DOEL, "lid": lid}, llm=llm, graph=graaf, hergebruik=hergebruik,
            settings=make_settings(enable_decomposition=True, **settings),
            annotaties=NodeLeesApi(graaf, lid),
        )]
    return asyncio.run(verzamel())


def _van(events: list[dict], soort: str) -> list[dict]:
    return [e for e in events if e["type"] == soort]


# --- de keten ---------------------------------------------------------------------------------------

def test_ongewijzigd_lid_kost_geen_llm_call():
    llm = FakeLLM([])        # elke aanroep zou een IndexError geven
    graaf = _graaf({"2": _fnv1a_32(LID2)})
    events = _draai(llm, graaf, lid="2")

    assert llm.calls == [] and not _van(events, "error")
    assert not _van(events, "element")
    hergebruik, = [e["hergebruik"] for e in _van(events, "hergebruik")]
    assert hergebruik["volledig"] and hergebruik["slug"] == "urn:bwb:BWBR0004770:artikel:9:lid:2"
    assert [ld["lid"] for ld in hergebruik["leden"]] == ["2"]
    # Alleen de markeringen van dít lid tellen mee.
    assert hergebruik["telling"] == {"markeringen": 1, "beoordeeld": 0, "afgewezen": 0,
                                     "te_beoordelen": 1}
    run, = [e["run"] for e in _van(events, "run")]
    assert run["modus"] == "hergebruik"
    assert "hergebruikt" in "".join(e["content"] for e in _van(events, "token"))
    # Het doel draagt de lidstand, zodat de driver het hergebruik kan vastleggen.
    doel, = [e["doel"] for e in _van(events, "doel")]
    assert doel["bereik"] == ["urn:bwb:BWBR0004770:artikel:9:lid:2"]
    assert len(doel["segmenten"][0]["bron_hash"]) == 64
    assert graaf.api_calls == ["dekking", "weergave"]
    assert not any("jas:AnnotatieLaag" in q for q in graaf.queries)


def test_gewijzigd_lid_wordt_gewoon_geannoteerd():
    llm = _keten()
    events = _draai(llm, _graaf({"2": "oude-hash"}), lid="2")
    assert not _van(events, "hergebruik")
    assert "De ontvanger" in [e["element"]["tekst"] for e in _van(events, "element")]
    assert _van(events, "run")[0]["run"]["modus"] == "nieuw"


def test_deels_gewijzigd_artikel_annoteert_alleen_het_gewijzigde_lid():
    llm = _keten()
    events = _draai(llm, _graaf({"1": _fnv1a_32(LID1), "2": "oude-hash"}))

    # De hele tekst blijft context, maar kandidaten komen alleen uit het gewijzigde lid.
    prompt = llm.calls[0]["messages"][0]["content"]
    context, kandidaten = prompt.split(">>>", 1)
    assert LID2.removeprefix("2. ") in context and LID1.removeprefix("1. ") in context
    assert "De ontvanger" in kandidaten and "belastingaanslag" not in kandidaten

    hergebruik, = [e["hergebruik"] for e in _van(events, "hergebruik")]
    assert not hergebruik["volledig"] and [ld["lid"] for ld in hergebruik["leden"]] == ["1"]
    # Naar de api gaat alleen de stand van het lid dat opnieuw is geannoteerd.
    doel, = [e["doel"] for e in _van(events, "doel")]
    assert doel["bereik"] == ["urn:bwb:BWBR0004770:artikel:9:lid:1", "urn:bwb:BWBR0004770:artikel:9:lid:2"]
    element, = [e["element"] for e in _van(events, "element") if e["element"]["tekst"] == "De ontvanger"]
    a, = element["ankers"]
    assert a["bron_iri"].endswith(":lid:2") and a["start"] == 0
    assert len(a["bron_hash"]) == 64
    assert all(e["element"]["eigenaar_iri"].endswith(":lid:2") for e in _van(events, "element"))


def test_opnieuw_annoteren_controleert_api_maar_hergebruikt_niet():
    llm = _keten()
    graaf = _graaf({"2": _fnv1a_32(LID2)})
    events = _draai(llm, graaf, lid="2", hergebruik="opnieuw")
    assert not _van(events, "hergebruik") and _van(events, "element")
    assert graaf.api_calls == ["dekking", "weergave"]
    assert _van(events, "run")[0]["run"]["modus"] == "opnieuw"


def test_onleesbare_dekking_stopt_zonder_nieuwe_annotatie():
    """Een API-storing is geen bewijs dat annotaties ontbreken."""
    llm = _keten()
    events = _draai(llm, _graaf(None, laag_faalt=True), lid="2")
    assert not _van(events, "element") and llm.calls == []
    assert any(e.get("status") == "unavailable" for e in _van(events, "tool_execution"))


def test_geen_laag_betekent_gewoon_annoteren():
    llm = _keten()
    events = _draai(llm, _graaf(None), lid="2")
    assert not _van(events, "hergebruik") and _van(events, "element")


# --- vastleggen -------------------------------------------------------------------------------------

class NepApi:
    def __init__(self, hergebruikt: list[str] | None = None) -> None:
        self.batches: list[dict] = []
        self.hergebruik_posts: list[dict] = []
        self.laag_puts: list[dict] = []
        self.berichten: list[dict] = []
        self.verworpen = 0
        self.hergebruikt = hergebruikt or []

    async def zet_bronnode_batch(self, batch):
        self.batches.append(batch)
        return {"annotatie_doel": {"bron_iri": batch["doel"]["bron_iri"], "snapshot_id": batch["snapshot_id"]}}

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

    batch, = nep.batches
    assert batch["doel"]["bron_iri"].endswith(":lid:2")
    assert batch["elementen"] == [] and batch["run"]["modus"] == "hergebruik"
    assert nep.laag_puts == [] and nep.hergebruik_posts == []
    assert nep.berichten[0]["annotatie_doel"]["bron_iri"].endswith(":lid:2")
    assert nep.berichten[0]["tool_executions"]
    assert _van(uit, "opgeslagen")[0]["annotatie_doel"]["bron_iri"].endswith(":lid:2")


def test_api_onbeschikbaarheid_wordt_in_het_toolspoor_vastgelegd():
    graph = _graaf(None, laag_faalt=True)
    events = _draai(FakeLLM([]), graph, lid="2")
    end = [e for e in _van(events, "tool_execution") if e["tool"] == "get_annotatiedekking" and e["phase"] == "end"]
    assert len(end) == 1 and end[0]["status"] == "unavailable"
    assert graph.api_calls == ["dekking"]


def test_dekking_gaat_mee_naar_de_laag_en_het_chatbericht(monkeypatch):
    """Het `dekking`-event van de keten landt in de batch (voor de weergave en de graaf) én in het
    chatbericht (zodat een heropend gesprek hem nog toont)."""
    dekking = {"per_bron": {"urn:bwb:BWBR0004770:artikel:9:lid:2": {
                   "dimensies": {"tijd": "uitgevoerd"}, "ongedekt": [{"tekst": "kan", "start": 13, "eind": 16}]}},
               "proces": {"ACCEPTED": 1}, "gedegradeerd": [], "taal_model": "", "fasen": []}
    events = [
        {"type": "doel", "doel": {"schema_versie": 2, "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:2",
                                  "snapshot_id": "s1", "bwbId": "BWBR0004770", "artikel": "9", "lid": "2"}},
        {"type": "run", "run": {"model": "m"}},
        {"type": "dekking", "dekking": dekking},
        {"type": "element", "element": {"id": "e1", "klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2"}},
        {"type": "done"},
    ]
    nep = NepApi()
    _leg_vast(events, nep, monkeypatch)
    batch, = nep.batches
    assert batch["dekking"]["structureel"] == dekking["per_bron"]
    assert batch["dekking"]["proces"] == {"ACCEPTED": 1}
    assert nep.berichten[0]["dekking"] == dekking
