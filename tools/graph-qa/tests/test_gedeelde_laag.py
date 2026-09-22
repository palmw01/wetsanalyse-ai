"""graph-qa schrijft naar de gedeelde annotatielaag: hash per lid, ankers op het hele artikel, en
één PUT naar `/v1/annotatie/lagen/{bwbId}/{artikel}/elementen`."""
from __future__ import annotations

import asyncio
import json

import httpx

from bron_fakes import answer_stream
from agent.annotatie import _fnv1a_32, herankeer, lid_hashes
from agent.annotatie_prompt import methode_versie, prompt_hash
from agent.wetsanalyse_api import WetsanalyseApi
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

LID1 = "1. Een belastingaanslag is invorderbaar zes weken na de dagtekening."
LID2 = "2. De ontvanger kan uitstel van betaling verlenen."
ARTIKEL = f"{LID1}\n\n{LID2}"


# --- hash per lid ----------------------------------------------------------------------------------

def test_lidhash_is_de_hash_van_het_segment():
    """Dezelfde lidtekst geeft dezelfde hash, of hij nu als los lid of binnen het artikel is opgehaald
    – anders zou een beurt op één lid de laag van het hele artikel als gewijzigd zien."""
    assert lid_hashes(ARTIKEL) == {"1": _fnv1a_32(LID1), "2": _fnv1a_32(LID2)}
    assert lid_hashes(LID2) == {"2": _fnv1a_32(LID2)}


def test_artikel_zonder_leden_heeft_een_segment():
    assert lid_hashes("Deze wet heet Invorderingswet 1990.") == {"": _fnv1a_32(
        "Deze wet heet Invorderingswet 1990.")}


# --- herankeren -------------------------------------------------------------------------------------

def _anker(corpus: str, fragment: str, lid: str) -> dict:
    start = corpus.index(fragment)
    return {"lid": lid, "start": start, "eind": start + len(fragment), "voor": "", "na": "",
            "bron_hash": _fnv1a_32(corpus)}


def test_herankeer_van_lid_naar_artikel():
    voorstel = {"id": "e1", "klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2",
                "anker": _anker(LID2, "De ontvanger", "2")}
    uit, = herankeer([voorstel], LID2, ARTIKEL)
    a = uit["anker"]
    assert ARTIKEL[a["start"]:a["eind"]] == "De ontvanger"
    assert a["bron_hash"] == _fnv1a_32(ARTIKEL) and a["lid_hash"] == _fnv1a_32(LID2)
    assert a["na"].startswith(" kan uitstel") and a["voor"].endswith("\n\n2. ")


def test_herankeer_zonder_scope_zet_alleen_de_lidhash():
    voorstel = {"id": "e1", "tekst": "Een belastingaanslag", "lid": "1",
                "anker": _anker(ARTIKEL, "Een belastingaanslag", "1")}
    uit, = herankeer([voorstel], ARTIKEL, ARTIKEL)
    assert (uit["anker"]["start"], uit["anker"]["lid_hash"]) == (3, _fnv1a_32(LID1))


def test_herankeer_laat_ontbrekend_en_eigen_werk_staan_en_wist_wat_niet_klopt():
    zonder = {"id": "a", "tekst": "x", "anker": None}
    eigen = {"id": "b", "tekst": "x", "van_jurist": True, "anker": {"start": 0, "eind": 1}}
    # Het segment in het artikel wijkt af van wat de annoteerder las: niet gokken, geen anker.
    anders = {"id": "c", "tekst": "De ontvanger", "lid": "2",
              "anker": _anker(LID2, "De ontvanger", "2")}
    uit = herankeer([zonder, eigen, anders], LID2, f"{LID1}\n\n2. De ontvanger mag uitstel geven.")
    assert uit[0] is zonder and uit[1] is eigen
    assert uit[2]["anker"] is None


# --- de api-client ---------------------------------------------------------------------------------

def test_client_put_naar_de_laag_en_leest_de_headers():
    """Tegen de échte client, niet tegen een nabootsing: `X-Verworpen` werd tot nu toe met
    hoofdletters gelezen uit headers die httpx in kleine letters teruggeeft – de melding kon nooit
    afgaan, en de tests zagen dat niet omdat ze de client nabootsten."""
    verzoeken: list[httpx.Request] = []

    def api(request: httpx.Request) -> httpx.Response:
        verzoeken.append(request)
        return httpx.Response(200, json={"slug": "laag1"},
                              headers={"X-Verworpen": "2", "X-Hergebruikt-Leden": "1,3"})

    client = WetsanalyseApi(make_settings(wetsanalyse_api_url="http://api:3000",
                                          wetsanalyse_api_token="t", qa_api_token="q"), "jurist")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(api))

    async def draai():
        try:
            return await client.zet_laag_elementen(
                bwb_id="BWBR0024096", artikel="25.1", citeertitel="Leidraad",
                elementen=[{"id": "e1", "klasse": "Rechtssubject", "tekst": "t", "aandacht": ""}],
                suggesties=[], run={"model": "m", "tijd": None},
                leden=[{"lid": "", "hash": "h", "iri": ""}], bron_hash="art", modus="opnieuw",
            )
        finally:
            await client.aclose()

    laag = asyncio.run(draai())
    assert laag == {"slug": "laag1"}
    assert client.verworpen == 2 and client.hergebruikt == ["1", "3"]
    verzoek, = verzoeken
    assert verzoek.method == "PUT"
    assert verzoek.url.path == "/v1/annotatie/lagen/BWBR0024096/25.1/elementen"
    body = json.loads(verzoek.content)
    assert body["modus"] == "opnieuw" and body["bron_hash"] == "art" and body["leden"][0]["hash"] == "h"
    assert body["elementen"][0]["aandacht"] is None          # naar_contract op de grens
    assert "tijd" not in body["run"]
    assert verzoek.headers["x-user-id"] == "jurist"


# --- de keten ----------------------------------------------------------------------------------------

ARTIKEL_TSV = json.dumps(
    "?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\n"
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:1>\t"1"'
    '\t"Een belastingaanslag is invorderbaar zes weken na de dagtekening."\n'
    '\t"jci"\t<urn:bwb:BWBR0004770:artikel:9:lid:2>\t"2"'
    '\t"De ontvanger kan uitstel van betaling verlenen."'
)


def _events(hergebruik: str = "auto") -> list[dict]:
    llm = FakeLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 2")], "end_turn"),
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block('{"bwbId":"BWBR0004770","artikel":"9","lid":"2","nummer":"","citeertitel":"IW 1990"}')], "end_turn"),
        response([text_block(json.dumps({"elementen": [
            {"klasse": "Rechtssubject", "tekst": "De ontvanger", "lid": "2", "toelichting": "wie"},
        ]}))], "end_turn"),
        response([text_block(json.dumps({"oordelen": [], "ontbrekend": []}))], "end_turn"),
    ])

    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer artikel 9 lid 2 van de Invorderingswet 1990",
            settings=make_settings(enable_decomposition=True, critic_max_rondes=0),
            llm=llm, graph=FakeGraph(result=ARTIKEL_TSV), hergebruik=hergebruik,
        )]

    return asyncio.run(verzamel())


def test_lid_annoteren_ankert_lokaal_op_de_bronnode():
    from hashlib import sha256
    events = _events()
    doel = next(e["doel"] for e in events if e["type"] == "doel")
    assert doel["leden_teksten"][0]["tekst"] == LID2.removeprefix("2. ")
    segment, = doel["segmenten"]
    assert segment["bron_iri"] == "urn:bwb:BWBR0004770:artikel:9:lid:2"
    element, = [e["element"] for e in events if e["type"] == "element"]
    a, = element["ankers"]
    assert a["start"] == 0
    assert segment["tekst"][a["start"]:a["eind"]] == "De ontvanger"
    assert a["bron_hash"] == sha256(segment["tekst"].encode()).hexdigest()
    assert "anker" not in element


def test_run_draagt_herkomst_en_modus():
    run = next(e for e in _events()[::-1] if e["type"] == "run")["run"]
    assert run["modus"] == "nieuw"
    doel = next(e["doel"] for e in _events() if e["type"] == "doel")
    assert doel["bereik"] == ["urn:bwb:BWBR0004770:artikel:9:lid:2"]
    assert run["prompt_hash"] == prompt_hash() and run["methode_versie"] == methode_versie()
    assert set(run["instellingen"]) == {"annotatie_prompt_kort", "enable_kandidaat_splitsing",
                                        "critic_max_rondes"}

    run = next(e for e in _events("opnieuw") if e["type"] == "run")["run"]
    assert run["modus"] == "opnieuw"


def test_lidstand_volgt_het_api_contract():
    """De lidstand die graph-qa meestuurt moet exact `LidInvoer` in de api zijn; een veld dat daar
    ontbreekt valt stil weg, een verplicht veld dat hier ontbreekt is een 422 op de hele beurt."""
    from agent.artikel import ArtikelScope
    from agent.nodes.annotatie import _scope_velden
    import re

    from test_contract_drift import CONTRACT, _api_velden

    velden = _scope_velden(ArtikelScope(corpus=LID2, soort="", artikel_corpus=ARTIKEL,
                                        leden=[{"lid": "2", "iri": "x"}]))
    assert set(velden["lidstand"][0]) == set(_api_velden("LidInvoer"))
    # En wat de laag-PUT naast de ElementenInvoer-velden verwacht. `_api_velden` kent alleen klassen
    # die direct van BaseModel erven, en deze erft van ElementenInvoer.
    blok = re.search(r"^class LaagElementenInvoer\(ElementenInvoer\):(.*?)(?=^class )",
                     CONTRACT.read_text(), re.S | re.M)
    assert blok, "LaagElementenInvoer niet gevonden in het api-contract"
    velden = set(re.findall(r"^    (\w+)\s*:", blok.group(1), re.M))
    assert velden == {"citeertitel", "leden", "bron_hash", "modus"}
