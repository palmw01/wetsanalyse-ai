"""Het antwoord als toolaanroep (ADR-008): de feiten komen uit de trace, nooit van het model."""
from __future__ import annotations

import asyncio
import json

import pytest

from agent.agent import answer_stream

from agent.sjablonen import Onvulbaar, sjabloon_schemas, vul
from bronmodel.antwoord import Antwoord, Definities, Leemte, antwoord_tekst
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

K = "urn:bwb:BWBR0004770:artikel:2:lid:1:o:k"


def definitie(**rij) -> tuple[str, str]:
    basis = {"node": K, "begrip": "belastingschuldige", "tekst": "belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;",
             "jci": "jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k", "citeertitel": "Invorderingswet 1990"}
    return "zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{**basis, **rij}]})


def begrip(**rij) -> tuple[str, str]:
    basis = {"id": "b1", "naam": "belastingschuldige", "status": "geaccordeerd", "definitie": "degene te wiens naam", "werkgebied": "Rekeningafspraak"}
    return "search_begrippen", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{**basis, **rij}]})


def test_het_schema_is_strict_en_klein():
    schema = sjabloon_schemas(frozenset({"antwoord_begrip"}))[0]
    assert schema["strict"] is True
    assert schema["input_schema"]["additionalProperties"] is False
    assert set(schema["input_schema"]["required"]) == set(schema["input_schema"]["properties"])


def test_de_definitie_komt_uit_de_rij_niet_van_het_model():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": "De tenaamstelling beslist."}, [definitie(), begrip()])
    assert [b.soort for b in a.blokken] == ["definities", "begrippen", "toelichting"]
    d = a.blokken[0].items[0]
    assert d.tekst.startswith("belastingschuldige: degene")
    assert d.vindplaats.label == "Artikel 2, lid 1, onderdeel k" and d.vindplaats.regeling == "Invorderingswet 1990"
    assert [v.iri for v in a.doelen] == [K]
    assert a.blokken[-1].door == "lex"


def test_alleen_dezelfde_term_telt():
    a = vul("antwoord_begrip", {"begrip": "aanslag", "toelichting": ""}, [definitie(begrip="belastingaanslag")])
    assert [b.soort for b in a.blokken] == ["leemte"]
    assert a.doelen == []


def test_meervoud_en_opsomming_tellen_wel():
    a = vul("antwoord_begrip", {"begrip": "ontvangers", "toelichting": ""}, [definitie(begrip="directeur, inspecteur of ontvanger")])
    assert isinstance(a.blokken[0], Definities)


def test_nul_rijen_is_een_leemte_en_zegt_in_de_graaf():
    leeg = ("zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": []}))
    a = vul("antwoord_begrip", {"begrip": "kwijtschelding", "toelichting": ""}, [leeg])
    assert isinstance(a.blokken[0], Leemte) and "in de graaf" in a.blokken[0].tekst


def test_zonder_zoekactie_vult_het_niet():
    with pytest.raises(Onvulbaar, match="zoek_definitie"):
        vul("antwoord_begrip", {"begrip": "x", "toelichting": ""}, [])


def test_een_mislukte_zoekactie_is_geen_leemte():
    with pytest.raises(Onvulbaar):
        vul("antwoord_begrip", {"begrip": "x", "toelichting": ""}, [("zoek_definitie", json.dumps({"status": "error", "reden": "graaf_weg"}))])


def test_een_voorproef_wordt_nooit_getoond():
    trace = [definitie(tekst="belastingschuldige: begin", tekst_volledig=False)]
    with pytest.raises(Onvulbaar, match="get_lid"):
        vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, trace)
    trace.append(("get_lid", json.dumps({"status": "ok", "volledig": True, "resultaten": [{"iri": K, "tekst": "belastingschuldige: de hele tekst"}]})))
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, trace)
    assert a.blokken[0].items[0].tekst == "belastingschuldige: de hele tekst"


def test_de_tekst_volgt_uit_de_blokken_en_het_model_reist_rond():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": "Uitleg."}, [definitie(), begrip()])
    tekst = antwoord_tekst(a)
    assert '"belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;"' in tekst
    assert "Artikel 2, lid 1, onderdeel k, Invorderingswet 1990" in tekst and "Uitleg." in tekst
    assert antwoord_tekst(Antwoord.model_validate(a.model_dump())) == tekst


RIJ = ("node\tbegrip\ttekst\tjci\tbwbId\tciteertitel\n"
       f'<{K}>\t"belastingschuldige"\t"belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;"\t'
       '"jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k"\t"BWBR0004770"\t"Invorderingswet 1990"\n')
KIES = response([text_block("WORKERS: antwoord\nSPECIALIST: definitie\nPLAN: zoek de definitie")], "end_turn")
ZOEK = response([tool_block("t1", "zoek_definitie", {"term": "belastingschuldige"})], "tool_use")


def _sjabloon(toelichting: str = "De tenaamstelling beslist.", id: str = "t2"):
    return response([tool_block(id, "antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": toelichting})], "tool_use")


def _beurt(*rondes):
    llm = FakeLLM([KIES, *rondes])
    settings = make_settings(enable_planning=True, grounding_correct=True)

    async def alles():
        return [e async for e in answer_stream("Wat betekent belastingschuldige?", settings=settings, llm=llm, graph=FakeGraph(result=RIJ))]

    return asyncio.run(alles()), llm


def _eerste(events, soort):
    return next(e for e in events if e["type"] == soort)


def test_een_beurt_rondt_af_met_het_sjabloon():
    events, _ = _beurt(ZOEK, _sjabloon())
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "begrip"
    assert antwoord["doelen"][0]["iri"] == K
    token = _eerste(events, "token")["content"]
    assert "degene te wiens naam" in token and "De tenaamstelling beslist." in token
    assert _eerste(events, "grounding")["grounded"] is True
    assert [e["type"] for e in events if e["type"] in ("antwoord", "token")] == ["antwoord", "token"], "eerst de blokken"
    assert [s["uri"] for s in _eerste(events, "sources")["sources"]] == [K]


def test_een_onvulbaar_sjabloon_gaat_terug_naar_het_model():
    events, llm = _beurt(_sjabloon(id="t0"), ZOEK, _sjabloon())
    assert llm.index == 4
    assert _eerste(events, "antwoord")["antwoord"]["blokken"][0]["soort"] == "definities"


def test_vrije_tekst_blijft_een_geldig_antwoord():
    events, _ = _beurt(ZOEK, response([text_block("Een vrij antwoord.")], "end_turn"))
    assert not [e for e in events if e["type"] == "antwoord"]
    assert _eerste(events, "token")["content"] == "Een vrij antwoord."


def test_een_verzonnen_verwijzing_in_de_toelichting_gaat_door_de_correctie():
    events, llm = _beurt(ZOEK, _sjabloon("Zie BWBR9999999."), _sjabloon("Zonder verzinsel.", id="t3"))
    assert llm.index == 4
    assert "BWBR9999999" not in _eerste(events, "token")["content"]
    assert [e for e in events if e["type"] == "antwoord"][-1]["antwoord"]["blokken"][-1]["tekst"] == "Zonder verzinsel."


def test_een_sjabloon_naast_een_graaftool_wacht_op_de_graaftool():
    beide = response([tool_block("t1", "zoek_definitie", {"term": "x"}), tool_block("t2", "antwoord_begrip", {"begrip": "x", "toelichting": ""})], "tool_use")
    events, llm = _beurt(beide, _sjabloon())
    assert llm.index == 3
    assert [e for e in events if e["type"] == "antwoord"]


def test_het_model_krijgt_de_tool_echt_aangeboden():
    """Op acceptatie stond de tool niet in het verzoek: `get_specialist` liet het veld vallen, en een nepmodel dat de tool
    toch aanroept ziet dat niet. Dus kijken naar wat er naar het model gaat."""
    _, llm = _beurt(ZOEK, _sjabloon())
    assert "antwoord_begrip" in [t["name"] for t in llm.calls[1]["tools"]]
    assert next(t for t in llm.calls[1]["tools"] if t["name"] == "antwoord_begrip")["strict"] is True


def test_zonder_definitie_blijven_de_opgehaalde_bronnen_herleidbaar():
    llm = FakeLLM([KIES, ZOEK, response([tool_block("t2", "get_artikel", {"bwb_id": "BWBR0018472", "artikel": "7"})], "tool_use"),
                   response([tool_block("t3", "antwoord_begrip", {"begrip": "draagkracht", "toelichting": "Zie artikel 7."})], "tool_use")])
    graph = FakeGraph(results=lambda q: RIJ if "definieertBegrip" in q else "node\ttekst\n<urn:bwb:BWBR0018472:artikel:7>\t\"Tekst\"\n")

    async def alles():
        return [e async for e in answer_stream("Wat betekent draagkracht?", settings=make_settings(enable_planning=True), llm=llm, graph=graph)]

    events = asyncio.run(alles())
    assert _eerste(events, "antwoord")["antwoord"]["blokken"][0]["soort"] == "leemte"
    assert _eerste(events, "sources")["sources"], "de toelichting rust ergens op"



# Het sjabloon `bepaling`: een lid zonder zijn onderdelen is een stil onjuiste wettekst.
ART = "urn:bwb:BWBR0004770:artikel:9"
LID = f"{ART}:lid:11"


def artikel(*leden, **extra) -> tuple[str, str]:
    return "get_artikel", json.dumps({"status": "ok", "volledig": True, "aantal": len(leden), "artikel": {"iri": ART, "delen": len(leden), **extra},
                                      "resultaten": list(leden)})


def lid(*onderdelen, verwacht=None) -> tuple[str, str]:
    return "get_lid", json.dumps({"status": "ok", "volledig": True, "aantal": len(onderdelen),
                                  "lid": {"iri": LID, "nummer": "11", "tekst": "In afwijking van het eerste lid:", "onderdelen": len(onderdelen) if verwacht is None else verwacht},
                                  "resultaten": list(onderdelen)})


EEN = {"lid": f"{ART}:lid:1", "nummer": "1", "tekst": "Een belastingaanslag is invorderbaar."}
ELF = {"lid": LID, "nummer": "11", "tekst": "In afwijking van het eerste lid:", "heeft_onderdelen": True}
A = {"onderdeel": f"{LID}:o:a", "nummer": "a.", "tekst": "zolang twijfel bestaat;"}
B1 = {"onderdeel": f"{LID}:o:b:o:1", "nummer": "1°.", "tekst": "de eerste grond;"}


def test_een_artikel_toont_elk_lid_met_zijn_eigen_vindplaats():
    a = vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": "Regelt de termijn."}, [artikel(EEN)])
    assert [b.soort for b in a.blokken] == ["wettekst", "toelichting"]
    assert [(i.vindplaats.label, i.tekst) for i in a.blokken[0].items] == [("Artikel 9, lid 1", EEN["tekst"])]
    assert a.sjabloon == "bepaling" and [v.iri for v in a.doelen] == [ART]


def test_een_lid_zonder_zijn_onderdelen_wordt_nooit_getoond():
    with pytest.raises(Onvulbaar, match="lid 11.*get_lid"):
        vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": ""}, [artikel(EEN, ELF)])


def test_met_get_lid_erbij_staan_de_onderdelen_onder_de_aanhef():
    a = vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": ""}, [artikel(EEN, ELF), lid(A, B1)])
    assert a.blokken[0].items[1].tekst == "In afwijking van het eerste lid:\na. zolang twijfel bestaat;\n1°. de eerste grond;"


def test_een_vervolgvraag_wijst_een_lid_uit_het_eerdere_artikel_aan():
    a = vul("antwoord_bepaling", {"bepalingen": [EEN["lid"]], "toelichting": ""}, [artikel(EEN, ELF)])
    assert [i.tekst for i in a.blokken[0].items] == [EEN["tekst"]]


def test_een_halve_pagina_is_onvulbaar():
    with pytest.raises(Onvulbaar, match="vervolg"):
        vul("antwoord_bepaling", {"bepalingen": [LID], "toelichting": ""}, [lid(A, verwacht=25)])


def test_een_verzonnen_iri_is_onvulbaar():
    with pytest.raises(Onvulbaar, match="niet opgehaald"):
        vul("antwoord_bepaling", {"bepalingen": [f"{ART}:lid:99"], "toelichting": ""}, [artikel(EEN)])


def test_een_container_noemt_zijn_subdivisies_en_toont_geen_begin():
    bep = ("get_bepaling", json.dumps({"status": "ok", "volledig": True, "aantal": 2, "bepaling": {"iri": "urn:bwb:BWBR0024096:x", "nummer": "25.1", "subdivisies": 2}, "resultaten": []}))
    with pytest.raises(Onvulbaar, match="subdivisies"):
        vul("antwoord_bepaling", {"bepalingen": ["urn:bwb:BWBR0024096:x"], "toelichting": ""}, [bep])


def test_de_specialisten_voor_een_tekstvraag_krijgen_het_sjabloon():
    from agent import specialists
    assert "antwoord_bepaling" in specialists.get("duiding").sjablonen and "antwoord_bepaling" in specialists.get("algemeen").sjablonen
    assert "antwoord_bepaling" not in specialists.get("definitie").sjablonen


def test_een_beurt_rondt_af_met_de_wettekst_uit_de_graaf():
    tsv = "?lid\t?lidnummer\t?lidtekst\t?lidonderdelen\n<urn:bwb:BWBR0004770:artikel:9:lid:1>\t\"1\"\t\"Een belastingaanslag is invorderbaar.\"\t\"false\"\n"
    llm = FakeLLM([response([text_block("SPECIALIST: duiding\nPLAN: artikel ophalen.")], "end_turn"),
                   response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "9"})], "tool_use"),
                   response([tool_block("t2", "antwoord_bepaling", {"bepalingen": [ART], "toelichting": "Regelt de termijn."})], "tool_use")])
    settings = make_settings(enable_planning=True, grounding_correct=True)

    async def alles():
        return [e async for e in answer_stream("Wat staat er in artikel 9?", settings=settings, llm=llm, graph=FakeGraph(result=tsv))]

    events = asyncio.run(alles())
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "bepaling"
    assert antwoord["blokken"][0]["items"][0]["tekst"] == "Een belastingaanslag is invorderbaar."
    assert _eerste(events, "grounding")["grounded"] is True
