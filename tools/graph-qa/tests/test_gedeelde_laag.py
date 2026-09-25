"""graph-qa schrijft naar de gedeelde annotatielaag: lokale ankers per bronnode, de herkomst van de
beurt, en de client die de laag wegschrijft."""
from __future__ import annotations

import asyncio
import json

import httpx

from bron_fakes import answer_stream
from agent.annotatie import _fnv1a_32
from agent.jas_klassen import methode_versie
from agent.jas_pipeline.classificatie import promptversie
from agent.jas_pipeline.kandidaten import GEEN_ANNOTATIE
from agent.wetsanalyse_api import WetsanalyseApi
from fakes import FakeGraph, KetenLLM, make_settings, response, text_block, tool_block

LID1 = "1. Een belastingaanslag is invorderbaar zes weken na de dagtekening."
LID2 = "2. De ontvanger kan uitstel van betaling verlenen."
ARTIKEL = f"{LID1}\n\n{LID2}"


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
                run={"model": "m", "tijd": None},
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
    def kies(toegestaan, fragment):
        return "Rechtssubject" if fragment == "De ontvanger" and "Rechtssubject" in toegestaan else GEEN_ANNOTATIE
    llm = KetenLLM([
        response([text_block("WORKERS: annotatie\nPLAN: annoteer art 9 lid 2")], "end_turn"),
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
        response([text_block('{"bwbId":"BWBR0004770","artikel":"9","lid":"2","nummer":"","citeertitel":"IW 1990"}')], "end_turn"),
    ], kies=kies)

    async def verzamel():
        return [e async for e in answer_stream(
            "annoteer artikel 9 lid 2 van de Invorderingswet 1990",
            settings=make_settings(enable_decomposition=True),
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
    element, = [e["element"] for e in events if e["type"] == "element" and e["element"]["tekst"] == "De ontvanger"]
    assert element["klasse"] == "Rechtssubject"
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
    assert run["prompt_hash"] == promptversie() and run["methode_versie"] == methode_versie()
    assert {"taal_provider", "classifier_granulariteit", "classifier_spankeuze", "gerichte_review",
            "meting"} <= set(run["instellingen"])

    run = next(e for e in _events("opnieuw") if e["type"] == "run")["run"]
    assert run["modus"] == "opnieuw"


def test_ankerhash_is_gelijk_aan_de_frontend():
    """De ankerhash moet aan beide kanten hetzelfde opleveren, ook buiten ASCII.

    Waarom deze guard er is. `anker.bron_hash` wordt hier gemaakt en in de browser vergeleken
    (`frontend/lib/selectie.ts:bronHash`). Kloppen ze niet, dan faalt de exacte-offsetstap in
    `vindPositie` altijd en valt de weergave stil terug op contextmatching — geen foutmelding, alleen
    markeringen die net verkeerd kunnen landen. Dat was het geval: hier werd over UTF-8-BYTES gehasht
    en daar over UTF-16-CODE-UNITS, wat alleen voor ASCII toevallig gelijk uitvalt. Nederlandse
    wettekst heeft '°' in geneste onderdelen en typografische aanhalingstekens, dus het speelde.

    De vectoren staan in één bestand dat beide kanten lezen; `selectie.test.ts` toetst dezelfde lijst.
    """
    import json
    from pathlib import Path


    pad = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "bronHash.vectoren.json"
    assert pad.exists(), f"gedeelde hashvectoren ontbreken: {pad}"
    vectoren = json.loads(pad.read_text(encoding="utf-8"))["vectoren"]
    assert len(vectoren) >= 5

    afwijkend = {t: (v, _fnv1a_32(t)) for t, v in vectoren.items() if _fnv1a_32(t) != v}
    assert not afwijkend, "hash wijkt af van de gedeelde vectoren: " + repr(afwijkend)

    niet_ascii = [t for t in vectoren if any(ord(c) > 127 for c in t)]
    assert len(niet_ascii) >= 4, "de vectoren moeten juist het niet-ASCII-geval dekken"
