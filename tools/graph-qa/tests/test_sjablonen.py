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


def definitie(term="belastingschuldige", **rij) -> tuple[str, str]:
    basis = {"node": K, "begrip": "belastingschuldige", "tekst": "belastingschuldige: degene te wiens naam de belastingaanslag is gesteld;",
             "jci": "jci1.3:c:BWBR0004770&artikel=2&lid=1&o=k", "citeertitel": "Invorderingswet 1990"}
    return "zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "term": term, "resultaten": [{**basis, **rij}]})


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
    a = vul("antwoord_begrip", {"begrip": "aanslag", "toelichting": ""}, [definitie("aanslag", begrip="belastingaanslag")])
    assert [b.soort for b in a.blokken] == ["leemte"]
    assert a.doelen == []


def test_meervoud_en_opsomming_tellen_wel():
    a = vul("antwoord_begrip", {"begrip": "ontvangers", "toelichting": ""}, [definitie("ontvanger", begrip="directeur, inspecteur of ontvanger")])
    assert isinstance(a.blokken[0], Definities)


def test_nul_rijen_is_een_leemte_en_zegt_in_de_graaf():
    leeg = ("zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "term": "kwijtschelding", "resultaten": []}))
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
    beide = response([tool_block("t1", "zoek_definitie", {"term": "belastingschuldige"}), tool_block("t2", "antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""})], "tool_use")
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
    llm = FakeLLM([KIES, response([tool_block("t1", "zoek_definitie", {"term": "draagkracht"})], "tool_use"), response([tool_block("t2", "get_artikel", {"bwb_id": "BWBR0018472", "artikel": "7"})], "tool_use"),
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


def test_een_lid_erft_dat_zijn_artikel_nog_niet_geldt():
    a = vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": ""}, [artikel(EEN, nog_niet_in_werking=True)])
    assert [b.nog_niet_in_werking for b in a.blokken[0].items] == [True]
    assert "nog niet in werking getreden" in antwoord_tekst(a)
    assert not vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": ""}, [artikel(EEN)]).blokken[0].items[0].nog_niet_in_werking


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
    grounding = _eerste(events, "grounding")
    assert grounding["grounded"] is True and grounding["niveau"] == "gegrond", "de vindplaats staat erbij, dus niet: niets te controleren"


# Het sjabloon `duiding`: het model wijst aan, de code toetst per bepaling, en de uitleg blijft door de controle gaan.
TIEN = "urn:bwb:BWBR0004770:artikel:10"
TIEN_1, TIEN_2 = f"{TIEN}:lid:1", f"{TIEN}:lid:2"
ZIN_1 = "De ontvanger kan uitstel verlenen voor de duur van zes maanden."
ZIN_2 = "Het uitstel eindigt zodra de belastingschuldige een nieuwe aanslag ontvangt."


def tien(**lid2) -> tuple[str, str]:
    leden = [{"lid": TIEN_1, "nummer": "1", "tekst": ZIN_1}, {"lid": TIEN_2, "nummer": "2", "tekst": ZIN_2, **lid2}]
    return "get_artikel", json.dumps({"status": "ok", "volledig": True, "aantal": 2, "artikel": {"iri": TIEN, "delen": 2}, "resultaten": leden})


def duiding(van: str = "De ontvanger kan uitstel", tot: str = "van zes maanden.", bepaling: str = TIEN_1, kort: str = "Uitstel is mogelijk.",
            waarom: str = "Dit geeft de bevoegdheid.", twijfel: list[str] | None = None, **extra) -> dict:
    return {"kort_antwoord": kort, "onderbouwing": [{"bepaling": bepaling, "van": van, "tot": tot, "waarom": waarom}], "twijfel": twijfel or [], **extra}


def test_duiding_is_strict_ook_in_de_geneste_rij():
    schema = sjabloon_schemas(frozenset({"antwoord_duiding"}))[0]
    rij = schema["input_schema"]["properties"]["onderbouwing"]["items"]
    assert schema["strict"] is True and rij["additionalProperties"] is False
    assert set(rij["required"]) == set(rij["properties"]) and set(schema["input_schema"]["required"]) == set(schema["input_schema"]["properties"])


def test_duiding_heeft_kort_antwoord_citaten_en_twijfel_in_die_volgorde():
    a = vul("antwoord_duiding", duiding(twijfel=["Of dit ook voor naheffingen geldt, zegt de tekst niet."]), [tien()])
    assert [b.soort for b in a.blokken] == ["toelichting", "citaten", "twijfel"]
    assert a.sjabloon == "duiding" and a.blokken[0].kop == "Kort antwoord" and a.blokken[0].door == "lex"
    c = a.blokken[1].items[0]
    assert (c.tekst, c.vindplaats.iri, c.vindplaats.label, c.waarom) == (ZIN_1, TIEN_1, "Artikel 10, lid 1", "Dit geeft de bevoegdheid.")
    assert [v.iri for v in a.doelen] == [TIEN_1]


def test_duiding_zonder_twijfel_heeft_geen_twijfelblok_en_ontdubbelt_de_doelen():
    invoer = duiding()
    invoer["onderbouwing"] *= 2
    a = vul("antwoord_duiding", invoer, [tien()])
    assert [b.soort for b in a.blokken] == ["toelichting", "citaten"] and [v.iri for v in a.doelen] == [TIEN_1]


def test_de_tekst_tussen_de_ankers_komt_uit_de_bron_niet_van_het_model():
    """D5: het model schrijft het citaat niet meer uit; wat ertussen staat neemt de code letterlijk uit de bron."""
    a = vul("antwoord_duiding", duiding(van="kan uitstel", tot="duur"), [tien()])
    assert a.blokken[1].items[0].tekst == "kan uitstel verlenen voor de duur"


def test_bijna_letterlijke_ankers_worden_de_brontekst():
    a = vul("antwoord_duiding", duiding(van="de ontvanger kan uitstel verlenen", tot="zes maanden"), [tien()])
    assert a.blokken[1].items[0].tekst == ZIN_1.rstrip(".")


def test_zonder_ankers_telt_het_hele_lid_en_met_een_anker_tot_het_begin_of_eind():
    assert vul("antwoord_duiding", duiding(van="", tot=""), [tien()]).blokken[1].items[0].tekst == ZIN_1
    assert vul("antwoord_duiding", duiding(van="voor de duur", tot=""), [tien()]).blokken[1].items[0].tekst == "voor de duur van zes maanden."
    assert vul("antwoord_duiding", duiding(van="", tot="uitstel verlenen"), [tien()]).blokken[1].items[0].tekst == "De ontvanger kan uitstel verlenen"


def test_een_lang_lid_zonder_ankers_gaat_terug_naar_het_model():
    lang = "De ontvanger kan uitstel verlenen. " * 30
    with pytest.raises(Onvulbaar, match="te lang om heel te tonen"):
        vul("antwoord_duiding", duiding(van="", tot="", bepaling=TIEN_2), [tien(tekst=lang)])


def test_staat_het_begin_er_vaker_dan_telt_de_plek_waarna_het_eind_volgt():
    tekst = "Het uitstel geldt. Het uitstel eindigt zodra een nieuwe aanslag komt."
    a = vul("antwoord_duiding", duiding(van="Het uitstel", tot="aanslag komt.", bepaling=TIEN_2), [tien(tekst=tekst)])
    assert a.blokken[1].items[0].tekst == tekst
    a = vul("antwoord_duiding", duiding(van="Het uitstel", tot="eindigt", bepaling=TIEN_2), [tien(tekst=tekst)])
    assert a.blokken[1].items[0].tekst == "Het uitstel geldt. Het uitstel eindigt"


@pytest.mark.parametrize("van,tot", [("De ontvanger mag uitstel", "zes maanden."), ("De ontvanger kan uitstel", "zes weken."),
                                      ("zes maanden.", "De ontvanger")])
def test_ankers_die_niet_of_omgekeerd_in_de_bron_staan_worden_nooit_getoond(van, tot):
    with pytest.raises(Onvulbaar, match="staat niet in Artikel 10, lid 1"):
        vul("antwoord_duiding", duiding(van=van, tot=tot), [tien()])


def test_een_echte_zin_bij_het_verkeerde_lid_wordt_geweigerd():
    """De controle op de tekst ziet dit niet: de zin staat in de trace. Alleen de toets per bepaling vangt het."""
    with pytest.raises(Onvulbaar, match="staat niet in Artikel 10, lid 2"):
        vul("antwoord_duiding", duiding(bepaling=TIEN_2), [tien()])


def test_een_onbekende_iri_is_onvulbaar():
    with pytest.raises(Onvulbaar, match="niet \\(helemaal\\) opgehaald"):
        vul("antwoord_duiding", duiding(bepaling=f"{ART}:lid:99"), [tien()])


def test_wijst_het_model_het_artikel_aan_dan_is_de_vindplaats_het_lid():
    a = vul("antwoord_duiding", duiding(bepaling=TIEN), [tien()])
    assert a.blokken[1].items[0].vindplaats.iri == TIEN_1


def test_staat_de_passage_in_twee_leden_dan_blijft_het_artikel_de_vindplaats():
    a = vul("antwoord_duiding", duiding(van="uitstel", tot="", bepaling=TIEN, waarom=""), [tien(tekst=f"Het uitstel eindigt. {ZIN_1}")])
    assert a.blokken[1].items[0].vindplaats.iri == TIEN


def test_een_onderdeel_van_het_aangewezen_lid_telt_met_zijn_eigen_vindplaats():
    a = vul("antwoord_duiding", duiding(van="zolang twijfel", tot="bestaat", bepaling=LID), [lid(A)])
    assert a.blokken[1].items[0].vindplaats.iri == A["onderdeel"]


# De weigeringen uit de duidingseval van 7 nov 2026: de tekst stond in de bron, de code vond hem niet.

def test_een_typografische_apostrof_in_de_bron_telt_als_de_gewone_en_de_bron_blijft_staan():
    """Iw 9 lid 8: de wet schrijft personenauto’s, het model personenauto's (vier weigeringen)."""
    tekst = "Terstond invorderbaar is een naheffingsaanslag ter zake van personenauto’s en motorrijwielen."
    a = vul("antwoord_duiding", duiding(van="Terstond invorderbaar", tot="personenauto's en motorrijwielen.", bepaling=TIEN_2),
            [tien(tekst=tekst)])
    assert a.blokken[1].items[0].tekst == tekst, "de getoonde tekst is die van de bron, met ’"
    a = vul("antwoord_duiding", duiding(van="een naheffingsaanslag – ter", tot="", bepaling=TIEN_2),
            [tien(tekst="Het is een naheffingsaanslag – ter zake van iets.")])
    assert a.blokken[1].items[0].tekst == "een naheffingsaanslag – ter zake van iets."


SLOT = {"onderdeel": "urn:bwb:BWBR0004770:id:Slottekst1", "tekst": "Op verzoek van de belastingschuldige is de ontvanger verplicht te verrekenen."}


@pytest.mark.parametrize("bepaling", [LID, ART])
def test_de_slotzin_van_een_lid_met_onderdelen_telt_onder_dat_lid(bepaling):
    """Iw 24 lid 1: de slotzin heeft een eigen `:id:`-iri, buiten die van het lid (twee weigeringen)."""
    a = vul("antwoord_duiding", duiding(van="Op verzoek van", tot="te verrekenen.", bepaling=bepaling), [lid(A, SLOT)])
    c = a.blokken[1].items[0]
    assert c.tekst == SLOT["tekst"] and c.vindplaats.iri == LID and c.vindplaats.label == "Artikel 9, lid 11"


def test_een_slotzin_van_een_ander_lid_telt_niet():
    with pytest.raises(Onvulbaar, match="staat niet in"):
        vul("antwoord_duiding", duiding(van="Op verzoek van", tot="te verrekenen.", bepaling=f"{ART}:lid:1"),
            [artikel(EEN), lid(A, SLOT)])


def test_een_jci_als_bepaling_wordt_de_iri_van_de_rij():
    """Het model nam de jci van het lid uit het toolresultaat, met de toestandsstaart (één weigering)."""
    jci = "jci1.3:c:BWBR0004770&hoofdstuk=II&artikel=9&lid=11"
    rij = ("get_lid", json.dumps({"status": "ok", "volledig": True, "lid": {"iri": LID, "nummer": "11", "tekst": "In afwijking van het eerste lid:",
                                                                               "jci": jci + "&z=2026-10-01&g=2026-10-01"}, "resultaten": [A]}))
    for opgegeven in (jci + "&z=2026-10-01&g=2026-10-01", jci):
        a = vul("antwoord_duiding", duiding(van="zolang twijfel", tot="bestaat", bepaling=opgegeven), [rij])
        assert a.blokken[1].items[0].vindplaats.iri == A["onderdeel"], opgegeven


def test_een_passage_over_twee_rijen_is_onvulbaar():
    with pytest.raises(Onvulbaar, match="één lid of onderdeel"):
        vul("antwoord_duiding", duiding(van="De ontvanger kan", tot="nieuwe aanslag ontvangt.", bepaling=TIEN), [tien()])


def test_een_voorproef_is_geen_bron_voor_een_citaat():
    zoek = ("search_wetgeving", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{"node": TIEN_1, "tekst": ZIN_1[:30], "tekst_volledig": False}]}))
    with pytest.raises(Onvulbaar, match="get_artikel"):
        vul("antwoord_duiding", duiding(van=ZIN_1[:10], tot=ZIN_1[20:30]), [zoek])


def test_get_context_draagt_geen_vindplaats_per_tekst():
    ctx = ("get_context", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{"relatie": "5-lid", "a": "1", "b": ZIN_1}]}))
    with pytest.raises(Onvulbaar, match="get_artikel"):
        vul("antwoord_duiding", duiding(), [ctx])


def test_een_annotatie_is_geen_bron_voor_een_citaat():
    ann = ("get_annotatie", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [{"iri": TIEN_1, "tekst": ZIN_1}]}))
    with pytest.raises(Onvulbaar, match="niet \\(helemaal\\) opgehaald"):
        vul("antwoord_duiding", duiding(), [ann])


def test_zonder_kort_antwoord_of_passage_vult_het_niet():
    with pytest.raises(Onvulbaar, match="korte antwoord"):
        vul("antwoord_duiding", duiding(kort=" "), [tien()])
    with pytest.raises(Onvulbaar, match="ten minste één passage"):
        vul("antwoord_duiding", {"kort_antwoord": "x", "onderbouwing": [], "twijfel": []}, [tien()])


@pytest.mark.parametrize("veld", ["kort", "waarom", "twijfel"])
def test_een_bepaling_in_de_uitleg_zonder_passage_gaat_terug_naar_het_model(veld):
    """De werkplek toont bij doelen geen bronnenlijst: deze vermelding zou nergens herleidbaar zijn, ook als hij is opgehaald."""
    tekst = "Zie ook artikel 12."
    invoer = duiding(twijfel=[tekst]) if veld == "twijfel" else duiding(**{veld: tekst})
    with pytest.raises(Onvulbaar, match="artikel 12 zonder passage"):
        vul("antwoord_duiding", invoer, [tien(), artikel(EEN)])


def test_de_eigen_bepaling_en_een_verwijzing_in_de_passage_mag_de_uitleg_noemen():
    tekst = f"Bedoeld in artikel 9 komt {ZIN_1}"
    a = vul("antwoord_duiding", duiding(van="Bedoeld in artikel 9", tot="", bepaling=TIEN, kort="Artikel 10 lid 2 sluit aan op artikel 9."), [tien(tekst=tekst)])
    assert a.blokken[1].items[0].vindplaats.iri == TIEN_2


def test_de_uitleg_komt_in_de_tekst_die_verify_controleert():
    a = vul("antwoord_duiding", duiding(kort="KORT", waarom="WAAROM", twijfel=["TWIJFEL"]), [tien()])
    tekst = antwoord_tekst(a)
    assert all(x in tekst for x in ("**Kort antwoord**", "KORT", f'"{ZIN_1}"', "Artikel 10, lid 1", "WAAROM", "**Twijfel en aannames**", "- TWIJFEL"))
    assert antwoord_tekst(Antwoord.model_validate(a.model_dump())) == tekst


def test_een_bijna_letterlijk_citaat_in_de_uitleg_wordt_hersteld():
    a = vul("antwoord_duiding", duiding(kort="De wet zegt: \"de ontvanger kan uitstel verlenen voor de duur van zes maanden.\""), [tien()])
    assert f'"{ZIN_1[:-1]}".' in a.blokken[0].tekst


TIEN_TSV = ("?lid\t?lidnummer\t?lidtekst\t?lidonderdelen\n"
            f'<{TIEN_1}>\t"1"\t"{ZIN_1}"\t"false"\n<{TIEN_2}>\t"2"\t"{ZIN_2}"\t"false"\n')
KIES_DUIDING = response([text_block("SPECIALIST: duiding\nPLAN: artikel ophalen.")], "end_turn")
HAAL = response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "10"})], "tool_use")


def _sluit_af(id: str = "t2", **velden):
    return response([tool_block(id, "antwoord_duiding", duiding(**velden))], "tool_use")


def _duidingsbeurt(*rondes, **instellingen):
    llm = FakeLLM([KIES_DUIDING, *rondes])
    settings = make_settings(enable_planning=True, grounding_correct=True, **instellingen)

    async def alles():
        return [e async for e in answer_stream("Hoe werkt uitstel?", settings=settings, llm=llm, graph=FakeGraph(result=TIEN_TSV))]

    return asyncio.run(alles()), llm


def test_de_duidingsspecialist_krijgt_beide_sjablonen_en_algemeen_niet():
    from agent import specialists
    duidend = specialists.get("duiding")
    assert {"antwoord_bepaling", "antwoord_duiding"} <= duidend.sjablonen
    assert "antwoord_bepaling" in duidend.system and "antwoord_duiding" in duidend.system
    assert "antwoord_duiding" not in specialists.get("algemeen").sjablonen


def test_een_beurt_rondt_af_met_de_duiding():
    events, llm = _duidingsbeurt(HAAL, _sluit_af())
    assert llm.index == 3
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "duiding" and antwoord["blokken"][1]["items"][0]["tekst"] == ZIN_1
    grounding = _eerste(events, "grounding")
    assert grounding["grounded"] is True and grounding["niveau"] == "gegrond"
    assert [s["uri"] for s in _eerste(events, "sources")["sources"]] == [TIEN_1]


@pytest.mark.parametrize("veld", ["kort", "waarom", "twijfel"])
def test_een_verzonnen_verwijzing_in_de_uitleg_gaat_door_de_correctie(veld):
    fout = "Zie BWBR9999999."
    velden = {"twijfel": [fout]} if veld == "twijfel" else {veld: fout}
    events, llm = _duidingsbeurt(HAAL, _sluit_af(**velden), _sluit_af("t3"))
    assert llm.index == 4
    assert "BWBR9999999" not in _eerste(events, "token")["content"]
    assert _eerste(events, "grounding")["grounded"] is True


@pytest.mark.parametrize("veld", ["kort", "waarom", "twijfel"])
def test_een_verzonnen_citaat_in_de_uitleg_gaat_door_de_correctie(veld):
    fout = '"De ontvanger mag altijd en zonder enige voorwaarde uitstel verlenen."'
    velden = {"twijfel": [fout]} if veld == "twijfel" else {veld: fout}
    events, llm = _duidingsbeurt(HAAL, _sluit_af(**velden), _sluit_af("t3"))
    assert llm.index == 4
    assert "zonder enige voorwaarde" not in _eerste(events, "token")["content"]


def test_een_passage_buiten_de_bron_komt_nooit_bij_de_controle_of_de_jurist():
    events, llm = _duidingsbeurt(HAAL, _sluit_af(van="Dit staat nergens in de wet,", tot="klinkt wel zo."), _sluit_af("t3"))
    assert llm.index == 4 and len([e for e in events if e["type"] == "antwoord"]) == 1
    assert "nergens in de wet" not in _eerste(events, "token")["content"]


def test_een_sjabloon_dat_onvulbaar_blijft_stopt_bij_de_beurtlimiet():
    onvulbaar = [_sluit_af(f"t{n}", van="Dit staat nergens", tot="in de wet.") for n in range(2, 7)]
    events, llm = _duidingsbeurt(HAAL, *onvulbaar, max_turns=3)
    assert llm.index == 5, "na de ronde op de limiet vraagt niets het model meer"
    assert "beurtlimiet" in _eerste(events, "token")["content"]
    assert not [e for e in events if e["type"] == "antwoord"]


def test_een_vervolgvraag_vindt_de_doelen_in_het_register():
    """De bepaling kwam in de vorige beurt binnen; de bronnen van deze beurt mogen dan niet leeg zijn."""
    from agent.nodes.antwoord import finalize_node
    from types import SimpleNamespace
    from unittest.mock import patch

    a = vul("antwoord_duiding", duiding(), [tien()])
    naam, tekst = tien()
    state = {"answer": "x", "antwoord": a.model_dump(), "bronregister": [[naam, tekst]], "source_trace": []}
    b = SimpleNamespace(graph=FakeGraph(result=""), settings=make_settings())
    with patch("agent.nodes.antwoord.get_stream_writer", return_value=lambda _: None):
        uit = finalize_node(b, state)
    assert [s["uri"] for s in uit["sources"]] == [TIEN_1]
# De garantie van "geen wettelijke definitie": alleen over wat er echt op deze term gezocht is.
def test_een_zoekactie_op_een_andere_term_is_geen_bewijs():
    """Het bronregister draagt `zoek_definitie` uit eerdere beurten mee: die zegt niets over deze term."""
    with pytest.raises(Onvulbaar, match="kwijtschelding"):
        vul("antwoord_begrip", {"begrip": "kwijtschelding", "toelichting": ""}, [definitie()])


def test_de_kortere_zoekterm_dekt_de_langere_maar_niet_andersom():
    a = vul("antwoord_begrip", {"begrip": "belastingaanslag", "toelichting": ""}, [definitie("aanslag", begrip="aanslag", node=K)])
    assert isinstance(a.blokken[0], Leemte)
    with pytest.raises(Onvulbaar):
        vul("antwoord_begrip", {"begrip": "aanslag", "toelichting": ""}, [definitie("belastingaanslag")])


def test_de_tool_noemt_de_term_waarop_hij_zocht():
    from agent.tools import dispatch
    data = json.loads(dispatch("zoek_definitie", FakeGraph(result=RIJ), {"term": "aanslag", "bwb_id": "BWBR0004770"}))
    assert data["term"] == "aanslag" and data["bwb_id"] == "BWBR0004770"


def test_een_zoekactie_binnen_een_regeling_spreekt_niet_voor_de_graaf():
    leeg = ("zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "term": "x", "bwb_id": "BWBR0004770", "resultaten": []}))
    assert "in de gezochte regeling" in vul("antwoord_begrip", {"begrip": "x", "toelichting": ""}, [leeg]).blokken[0].tekst


def test_een_onvolledige_zoekuitkomst_is_geen_leemte():
    meer = ("zoek_definitie", json.dumps({"status": "ok", "volledig": False, "aantal": 0, "term": "x", "resultaten": [], "vervolg": {"tool": "zoek_definitie", "args": {}}}))
    with pytest.raises(Onvulbaar, match="vervolg"):
        vul("antwoord_begrip", {"begrip": "x", "toelichting": ""}, [meer])


def test_een_onvolledige_lijst_met_definities_zegt_dat():
    trace = [("zoek_definitie", definitie()[1].replace('"volledig": true', '"volledig": false'))]
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, trace)
    assert [b.soort for b in a.blokken] == ["definities", "leemte"]


# De begrippen-leesroute: zonder term een lijst, en geen woord over de wet.
def test_de_leesroute_toont_de_begrippen_en_zegt_niets_over_de_wet():
    a = vul("antwoord_begrip", {"begrip": "", "toelichting": "Eén begrip is geaccordeerd."}, [begrip(naam="bestemming bankrekening")])
    assert [b.soort for b in a.blokken] == ["begrippen", "toelichting"]
    assert a.blokken[0].items[0].naam == "bestemming bankrekening", "de zoekterm stond al in de zoekopdracht"
    assert "wettelijke definitie" not in antwoord_tekst(a).casefold().replace("vastgelegd begrip", "")


def test_met_een_term_blijft_zoek_definitie_verplicht():
    with pytest.raises(Onvulbaar, match="laat begrip dan leeg"):
        vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [begrip()])


def test_de_leesroute_zonder_zoekactie_vult_niet():
    with pytest.raises(Onvulbaar, match="search_begrippen"):
        vul("antwoord_begrip", {"begrip": "", "toelichting": ""}, [])


def test_de_laatste_zoekopdracht_telt():
    a = vul("antwoord_begrip", {"begrip": "", "toelichting": ""}, [begrip(id="b1"), begrip(id="b2", naam="termijn")])
    assert [x.id for x in a.blokken[0].items] == ["b2"]


def test_nul_treffers_zegt_de_code_en_de_toelichting_vervalt():
    leeg = ("search_begrippen", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "resultaten": [], "geen_treffers": "Ik vond er geen. Dat zegt niet dat ze er niet zijn."}))
    a = vul("antwoord_begrip", {"begrip": "", "toelichting": "Er zijn geen begrippen."}, [leeg])
    assert [(b.soort, b.tekst) for b in a.blokken] == [("leemte", "Ik vond er geen. Dat zegt niet dat ze er niet zijn.")]


def test_een_storing_klinkt_niet_als_geen_begrippen():
    a = vul("antwoord_begrip", {"begrip": "", "toelichting": "Er zijn geen begrippen."}, [("search_begrippen", json.dumps({"status": "unavailable"}))])
    assert [b.soort for b in a.blokken] == ["leemte"] and "niet betrouwbaar" in a.blokken[0].tekst


def test_onvolledig_blijft_zichtbaar_bij_de_begrippen():
    trace = [("search_begrippen", begrip()[1].replace('"status": "ok", "volledig": true', '"status": "partial", "volledig": false'))]
    assert "onvolledig" in antwoord_tekst(vul("antwoord_begrip", {"begrip": "", "toelichting": ""}, trace))
    assert "onvolledig" in antwoord_tekst(vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(), *trace]))


def test_een_storing_bij_de_begrippen_zwijgt_niet_naast_een_definitie():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": "Uitleg."}, [definitie(), ("search_begrippen", "Fout bij tool")])
    assert [b.soort for b in a.blokken] == ["definities", "leemte", "toelichting"]


def test_de_begrippen_specialist_krijgt_het_sjabloon():
    from agent import specialists
    assert "antwoord_begrip" in specialists.get("begrippen_lezen").sjablonen


# Het bereik staat in de aanhef van het lid, niet in het onderdeel.
LID_RIJ = ("get_lid", json.dumps({"status": "ok", "volledig": True, "lid": {"iri": K.rsplit(":o:", 1)[0], "tekst": "Voor de toepassing van dit artikel wordt verstaan onder:"}, "resultaten": []}))


def test_het_bereik_komt_uit_de_aanhef_van_de_rij():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(aanhef="Deze wet verstaat onder:")])
    assert a.blokken[0].items[0].bereik == "Deze wet"


def test_het_bereik_komt_uit_het_opgehaalde_lid():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(), LID_RIJ])
    assert a.blokken[0].items[0].bereik == "Voor de toepassing van dit artikel"


def test_het_bereik_komt_ook_uit_een_lid_van_get_artikel():
    rij = ("get_artikel", json.dumps({"status": "ok", "volledig": True, "artikel": {"iri": "x"}, "resultaten": [{"lid": K.rsplit(":o:", 1)[0], "tekst": "In dit artikel wordt verstaan onder:"}]}))
    assert vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(), rij]).blokken[0].items[0].bereik == "In dit artikel"


def test_de_aanhef_gaat_voor_wat_de_definitie_zelf_noemt():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""},
            [definitie(tekst="belastingschuldige: degene als bedoeld in deze wet;", aanhef="In dit artikel wordt verstaan onder:")])
    assert a.blokken[0].items[0].bereik == "In dit artikel"


def test_een_subonderdeel_vindt_de_aanhef_van_het_lid():
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(node=f"{K}:o:1"), LID_RIJ])
    assert a.blokken[0].items[0].bereik == "Voor de toepassing van dit artikel"


def test_zonder_aanhef_blijft_de_eigen_tekst_gelden_en_anders_leeg():
    assert vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie()]).blokken[0].items[0].bereik == ""
    a = vul("antwoord_begrip", {"begrip": "belastingschuldige", "toelichting": ""}, [definitie(tekst="In deze wet is de belastingschuldige degene die betaalt.")])
    assert a.blokken[0].items[0].bereik == "deze wet"


# Het sjabloon `annotaties`.
def zoek(*rijen, **kop) -> tuple[str, str]:
    return "search_annotaties", json.dumps({"bewijssoort": "annotatie", "status": "ok", "volledig": True, "filters": {"jas_klassen": ["Rechtssubject"], "offset": 0, "limit": 25},
                                            "volgende_offset": None, "resultaten": list(rijen), **kop})


M1 = {"id": "e1", "klasse": "Rechtssubject", "tekst": "de ontvanger", "vindplaats": "BWBR0004770 art. 9 lid 1", "bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1"}


M2 = {"id": "e2", "klasse": "Rechtssubject", "tekst": "de belastingschuldige", "vindplaats": "BWBR0004770 art. 9 lid 2"}


def test_de_treffers_komen_uit_de_rijen():
    a = vul("antwoord_annotaties", {"toelichting": "Gefilterd op Rechtssubject."}, [zoek(M1, M2)])
    assert a.sjabloon == "annotaties" and [b.soort for b in a.blokken] == ["annotaties", "toelichting"]
    blok = a.blokken[0]
    assert [m.id for m in blok.items] == ["e1", "e2"] and blok.totaal == 2 and blok.volledig is True
    assert blok.items[0].vindplaats == M1["vindplaats"] and blok.door == "bron"


def test_een_volgende_pagina_is_onvolledig_ook_als_de_api_volledig_zegt():
    """De api zet `volledig` op de dekking van de projectie; de paginering staat in `volgende_offset`."""
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1, volgende_offset=25)])
    assert a.blokken[0].volledig is False
    assert "niet alle markeringen" in antwoord_tekst(a)


def test_pagina_s_van_dezelfde_zoekopdracht_voegen_samen():
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1, volgende_offset=1), zoek(M1, M2)])
    assert [m.id for m in a.blokken[0].items] == ["e1", "e2"] and a.blokken[0].totaal == 2 and a.blokken[0].volledig is True


def test_de_laatste_zoekopdracht_telt_bij_de_annotaties():
    ander = zoek(M2, filters={"tekst": "belastingschuldige"})
    assert [m.id for m in vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1), ander]).blokken[0].items] == ["e2"]


def test_partial_is_onvolledig():
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1, status="partial", volledig=False)])
    assert a.blokken[0].volledig is False


def test_een_mislukte_zoekopdracht_na_een_gelukte_maakt_onvolledig():
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1), ("search_annotaties", "Fout bij tool")])
    assert a.blokken[0].volledig is False and [m.id for m in a.blokken[0].items] == ["e1"]


def test_nul_treffers_klinkt_niet_als_bestaat_niet():
    a = vul("antwoord_annotaties", {"toelichting": "Er zijn geen rechtssubjecten geannoteerd."}, [zoek()])
    assert [b.soort for b in a.blokken] == ["leemte"], "de toelichting vervalt: die kan de leegte duiden"
    assert "Rechtssubject" in a.blokken[0].tekst and "zegt niet dat ze er niet zijn" in a.blokken[0].tekst


def test_een_toolfout_klinkt_niet_als_bestaat_niet():
    for fout in (json.dumps({"status": "unavailable", "volledig": False}), "Fout bij tool search_annotaties"):
        a = vul("antwoord_annotaties", {"toelichting": "Er zijn geen annotaties."}, [("search_annotaties", fout)])
        assert [b.soort for b in a.blokken] == ["leemte"] and "niet betrouwbaar" in a.blokken[0].tekst


def test_zonder_zoekactie_vult_het_annotatiesjabloon_niet():
    with pytest.raises(Onvulbaar, match="search_annotaties"):
        vul("antwoord_annotaties", {"toelichting": ""}, [])


def test_het_overzicht_telt_markeringen_niet_groepen():
    ov = ("overzicht_annotaties", json.dumps({"status": "ok", "volledig": False, "bekeken": 90, "meer_groepen": 2, "filters": {},
          "groepen": [{"klasse": "Rechtssubject", "tekst": "de ontvanger", "aantal": 3, "vindplaatsen": ["BWBR0004770 art. 9", "BWBR0004770 art. 10"], "voorbeeld_id": "e1"}]}))
    a = vul("antwoord_annotaties", {"toelichting": ""}, [ov])
    blok = a.blokken[0]
    assert blok.totaal == 3 and blok.volledig is False and blok.items[0].id == "e1"
    assert blok.items[0].vindplaats == "3×: BWBR0004770 art. 9, BWBR0004770 art. 10"


def test_een_verwijzing_en_een_verouderde_annotatie_blijven_herkenbaar():
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek({"id": "e3", "klasse": "Voorwaarde", "soort": "verwijzing"}, {**M1, "verouderd": True})])
    assert a.blokken[0].items[0].tekst == "Annotatie met een ruimere bronselectie"
    assert a.blokken[0].items[1].vindplaats.endswith("(verouderd)")


class _Port:
    def __init__(self, *paginas):
        self.paginas = list(paginas)

    def zoeken(self, _):
        return self.paginas.pop(0)


def test_het_echte_overzicht_past_op_het_sjabloon():
    from agent.tools.annotatie_tools import overzicht
    e = {"id": "e1", "klasse": "Rechtssubject", "tekst": "de ontvanger", "eigenaar_iri": "urn:bwb:BWBR0004770:artikel:9"}
    uit = overzicht({"jas_klassen": ["Rechtssubject"]}, _Port({"status": "ok", "volledig": True, "resultaten": [e, {**e, "id": "e2"}]}))
    blok = vul("antwoord_annotaties", {"toelichting": ""}, [("overzicht_annotaties", json.dumps(uit))]).blokken[0]
    assert blok.totaal == 2 and blok.volledig is True


LEES = response([tool_block("t2", "antwoord_annotaties", {"toelichting": "Op klasse gefilterd."})], "tool_use")


class _Lees:
    def zoeken(self, _):
        return {"status": "ok", "volledig": True, "filters": {}, "volgende_offset": None,
                "resultaten": [{"id": "e1", "klasse": "Rechtssubject", "tekst": 'de "ontvanger van de rijksbelastingen in deze wet" zelf', "eigenaar_iri": "urn:bwb:BWBR0004770:artikel:9"}]}


def _leesbeurt(*rondes, graaf=""):
    llm = FakeLLM(list(rondes))
    graph = FakeGraph(result=graaf)

    async def alles():
        return [e async for e in answer_stream("Welke annotaties zijn er?", settings=make_settings(grounding_correct=True), llm=llm, graph=graph, annotaties=_Lees())]

    return asyncio.run(alles()), llm


def test_een_beurt_rondt_af_met_de_annotaties_zonder_correctieronde():
    """Annotaties tellen niet als bron: zonder uitzondering gaven hun BWB-id's en aanhalingstekens elke beurt een correctieronde."""
    events, llm = _leesbeurt(LEES)
    assert llm.index == 1
    assert llm.calls[0]["tools"][-1]["name"] == "antwoord_annotaties"
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert antwoord["sjabloon"] == "annotaties" and antwoord["blokken"][0]["totaal"] == 1
    assert _eerste(events, "grounding")["grounded"] is True


def test_een_opgezochte_regeling_is_geen_bron_van_het_annotatieantwoord():
    """`list_regelingen` geeft alle regelingen terug om een BWB-id te vinden: het antwoord rust daar niet op."""
    opzoeken = response([tool_block("t1", "list_regelingen", {})], "tool_use")
    events, _ = _leesbeurt(opzoeken, LEES, graaf=json.dumps("regeling\ttitel\n<urn:bwb:BWBR0005537>\tAlgemene wet bestuursrecht\n"))
    assert _eerste(events, "sources")["sources"] == []


def test_een_verzinsel_in_de_toelichting_gaat_ook_hier_door_de_correctie():
    fout = response([tool_block("t2", "antwoord_annotaties", {"toelichting": "Zie BWBR9999999."})], "tool_use")
    events, llm = _leesbeurt(fout, response([tool_block("t3", "antwoord_annotaties", {"toelichting": "Zonder verzinsel."})], "tool_use"))
    assert llm.index == 2
    assert "BWBR9999999" not in _eerste(events, "token")["content"]


def test_een_vindplaats_van_de_treffers_staat_in_woorden_in_de_toelichting():
    """Het model schreef "Gezocht op bron_iri `urn:bwb:BWBR0004770:artikel:9`" (acceptatie 7 nov 2026). De treffers
    staan op lid 1 van dat artikel, dus het is een bekende plek in een onleesbare vorm."""
    a = vul("antwoord_annotaties", {"toelichting": "Gezocht op `urn:bwb:BWBR0004770:artikel:9`, ook urn:bwb:BWBR0004770:artikel:9:lid:1."},
            [zoek(M1)])
    tekst = a.blokken[1].tekst
    assert "urn:" not in tekst and "`" not in tekst
    assert tekst == "Gezocht op Artikel 9, ook Artikel 9, lid 1."


def test_een_vindplaats_die_de_treffers_niet_dragen_blijft_staan_voor_de_controle():
    a = vul("antwoord_annotaties", {"toelichting": "Zie urn:bwb:BWBR9999999:artikel:1 en urn:bwb:BWBR0004770:artikel:10."}, [zoek(M1)])
    assert "urn:bwb:BWBR9999999:artikel:1" in a.blokken[1].tekst and "urn:bwb:BWBR0004770:artikel:10" in a.blokken[1].tekst


def test_een_iri_van_de_gezochte_bepaling_kost_geen_correctieronde():
    iri = response([tool_block("t2", "antwoord_annotaties", {"toelichting": "Gezocht op `urn:bwb:BWBR0004770:artikel:9`."})], "tool_use")
    events, llm = _leesbeurt(iri)
    assert llm.index == 1
    assert _eerste(events, "grounding")["niveau"] != "ongegrond"
    assert "urn:" not in _eerste(events, "token")["content"]


def test_vrije_tekst_in_de_leesroute_blijft_begrensd():
    events, _ = _leesbeurt(response([text_block("Er zijn annotaties.")], "end_turn"))
    assert not [e for e in events if e["type"] == "antwoord"]
    assert _eerste(events, "token")["content"] == "Er zijn annotaties."


def test_de_vindplaats_van_een_markering_krijgt_de_naam_van_de_regeling(monkeypatch):
    from types import SimpleNamespace
    from agent.nodes import sjabloon
    monkeypatch.setattr(sjabloon, "regelingnamen", lambda _, bwbs: {b: "Invorderingswet 1990" for b in bwbs})
    a = vul("antwoord_annotaties", {"toelichting": ""}, [zoek(M1)])
    sjabloon._met_regelingen(SimpleNamespace(graph=None), a)
    assert a.blokken[0].items[0].vindplaats == "Invorderingswet 1990 art. 9 lid 1"


class _Begrippen:
    werkgebied_id = ""

    def verifieer(self, ids, werkgebieden):
        return {"status": "ok", "werkgebieden": {},
                "begrippen": {i: {"id": i, "naam": "termijn", "status": "geaccordeerd", "werkgebied_id": "w1", "werkgebied_naam": "Rekeningafspraak"} for i in ids}}


def test_de_begrippen_leesroute_rondt_af_met_het_sjabloon():
    llm = FakeLLM([response([tool_block("t2", "antwoord_begrip", {"begrip": "", "toelichting": "Eén begrip."})], "tool_use")])
    graph = FakeGraph(results=lambda q: 'wid\thash\n' if 'projectieHash' in q else 'c\twid\n<urn:wa:begrip:b1>\t"w1"\n')

    async def alles():
        return [e async for e in answer_stream("Welke begrippen hebben we al geaccordeerd?", settings=make_settings(grounding_correct=True), llm=llm, graph=graph, begrippen=_Begrippen())]

    events = asyncio.run(alles())
    assert llm.index == 1 and "antwoord_begrip" in [x["name"] for x in llm.calls[0]["tools"]]
    antwoord = _eerste(events, "antwoord")["antwoord"]
    assert [b["soort"] for b in antwoord["blokken"]] == ["begrippen", "toelichting"]
    assert antwoord["blokken"][0]["items"][0]["naam"] == "termijn"
    assert "Geen wettelijke definitie" not in _eerste(events, "token")["content"]


def test_de_regelingnaam_komt_ook_op_de_doelen():
    from types import SimpleNamespace

    from agent.nodes.sjabloon import _met_regelingen
    from agent.regelingnamen import _CACHE
    _CACHE["BWBR0004770"] = "Invorderingswet 1990"
    a = vul("antwoord_bepaling", {"bepalingen": [ART], "toelichting": ""}, [artikel(EEN)])
    _met_regelingen(SimpleNamespace(graph=FakeGraph(result="")), a)
    assert a.doelen[0].regeling == a.blokken[0].items[0].vindplaats.regeling == "Invorderingswet 1990"


def test_een_ander_aantal_in_de_toelichting_valt_weg():
    """Het model nam het getal van zijn eigen `limit` over ("50 annotaties") terwijl de lijst er 54 toonde."""
    a = vul("antwoord_annotaties", {"toelichting": "Er zijn 50 annotaties gevonden. Opvallend zijn de rechtssubjecten."}, [zoek(M1, M2)])
    assert a.blokken[1].tekst == "Opvallend zijn de rechtssubjecten."


def test_het_juiste_aantal_in_de_toelichting_blijft():
    tekst = "Er zijn 2 annotaties gevonden, beide in artikel 9."
    assert vul("antwoord_annotaties", {"toelichting": tekst}, [zoek(M1, M2)]).blokken[1].tekst == tekst


def test_een_toelichting_met_alleen_een_ander_aantal_vervalt():
    a = vul("antwoord_annotaties", {"toelichting": "Er zijn 7 treffers."}, [zoek(M1, M2)])
    assert [b.soort for b in a.blokken] == ["annotaties"]


ALS_TEKST = ('<invoke name="antwoord_annotaties">\n<parameter name="toelichting">Op klasse gefilterd.</parameter>\n</invoke>')


def test_een_sjabloonaanroep_als_tekst_wordt_een_echte_aanroep():
    from agent.sjablonen import sjabloon_uit_tekst
    aanroep = sjabloon_uit_tekst([ALS_TEKST], frozenset({"antwoord_annotaties"}))
    assert aanroep["name"] == "antwoord_annotaties" and aanroep["input"] == {"toelichting": "Op klasse gefilterd."}
    assert sjabloon_uit_tekst([ALS_TEKST], frozenset({"antwoord_begrip"})) is None, "alleen de sjablonen van deze specialist"
    assert sjabloon_uit_tekst(['<invoke name="antwoord_annotaties"><parameter name="onbekend">x</parameter></invoke>'],
                              frozenset({"antwoord_annotaties"})) is None, "wat niet bij het schema past blijft tekst"


def test_een_beurt_met_de_aanroep_als_tekst_toont_de_blokken_en_geen_markup():
    events, _ = _leesbeurt(response([text_block(ALS_TEKST)], "end_turn"))
    assert _eerste(events, "antwoord")["antwoord"]["sjabloon"] == "annotaties"
    assert "<invoke" not in _eerste(events, "token")["content"]


# --- D: genoemd is gelezen ------------------------------------------------------------------------------------------
# Een artikel dat het antwoord noemt, staat in beeld met een passage of niet. Wijst de opgehaalde tekst het aan zonder zijn
# tekst (get_context: Iw 28 verwijst naar 25 en 9, eval 7 nov 2026), dan haalt de code het op en kiest het model daarna.
ACHTTIEN = "urn:bwb:BWBR0004770:artikel:28"
ZIN_28 = "Over het bedrag waarvoor uitstel is verleend, wordt invorderingsrente berekend."


def context_met_28(regeling: str = "BWBR0004770") -> tuple[str, str]:
    rij = {"relatie": "verwezen_door", "node": f"urn:bwb:{regeling}:artikel:28:lid:3", "label": "Artikel 28, lid 3"}
    return "get_context", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "resultaten": [rij]})


def test_een_genoemd_artikel_dat_de_context_aanwijst_haalt_de_code_op():
    with pytest.raises(Onvulbaar, match="tekst staat hieronder") as fout:
        vul("antwoord_duiding", duiding(twijfel=["Ook artikel 28 kan hier gelden."]), [tien(), context_met_28()])
    assert fout.value.ophalen == [{"bwb_id": "BWBR0004770", "artikel": "28"}]


def test_een_genoemd_artikel_uit_het_geheugen_wordt_niet_opgehaald_en_blijft_geweigerd():
    with pytest.raises(Onvulbaar, match="artikel 28 zonder passage, en de tekst daarvan heb je niet opgehaald") as fout:
        vul("antwoord_duiding", duiding(twijfel=["Ook artikel 28 kan hier gelden."]), [tien()])
    assert fout.value.ophalen == []


def test_staat_het_artikel_in_twee_regelingen_dan_haalt_de_code_niets():
    with pytest.raises(Onvulbaar, match="niet opgehaald") as fout:
        vul("antwoord_duiding", duiding(twijfel=["Ook artikel 28 kan hier gelden."]),
            [tien(), context_met_28(), context_met_28("BWBR0002320")])
    assert fout.value.ophalen == []


def test_een_opgehaald_maar_niet_aangewezen_artikel_wordt_niet_nog_eens_opgehaald():
    achtentwintig = ("get_artikel", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "artikel": {"iri": ACHTTIEN},
                                                "resultaten": [{"lid": f"{ACHTTIEN}:lid:3", "nummer": "3", "tekst": ZIN_28}]}))
    with pytest.raises(Onvulbaar, match="terwijl de tekst al is opgehaald") as fout:
        vul("antwoord_duiding", duiding(twijfel=["Ook artikel 28 kan hier gelden."]), [tien(), context_met_28(), achtentwintig])
    assert fout.value.ophalen == []


def test_artikel_2_is_niet_artikel_28():
    from agent.sjablonen.vullen import artikel_in_trace
    assert artikel_in_trace("2", [context_met_28()]) == ""
    assert artikel_in_trace("28", [context_met_28()]) == ACHTTIEN


CONTEXT_TSV = f'?relatie\t?node\t?label\n"verwezen_door"\t<{ACHTTIEN}:lid:3>\t"Artikel 28, lid 3"\n'
ACHTTIEN_TSV = f'?lid\t?lidnummer\t?lidtekst\t?lidonderdelen\n<{ACHTTIEN}:lid:3>\t"3"\t"{ZIN_28}"\t"false"\n'


def _graaf_met_28(query: str) -> str:
    if "?relatie" in query:
        return CONTEXT_TSV
    return ACHTTIEN_TSV if ":artikel:28" in query or '"28"' in query else TIEN_TSV


def test_een_beurt_leest_het_genoemde_artikel_en_citeert_het_daarna():
    haal_beide = response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "10"}),
                           tool_block("t1b", "get_context", {"bwb_id": "BWBR0004770", "artikel": "10"})], "tool_use")
    met_28 = {**duiding(twijfel=["Of de rente meetelt, regelt artikel 28."]),
              "onderbouwing": [*duiding()["onderbouwing"],
                               {"bepaling": f"{ACHTTIEN}:lid:3", "van": "Over het bedrag", "tot": "invorderingsrente berekend.",
                                "waarom": "Over uitstel loopt rente."}]}
    llm = FakeLLM([KIES_DUIDING, haal_beide, _sluit_af(twijfel=["Of de rente meetelt, regelt artikel 28."]),
                   response([tool_block("t3", "antwoord_duiding", met_28)], "tool_use")])
    settings = make_settings(enable_planning=True, grounding_correct=True)

    async def alles():
        return [e async for e in answer_stream("Hoe werkt uitstel?", settings=settings, llm=llm, graph=FakeGraph(results=_graaf_met_28))]

    events = asyncio.run(alles())
    assert llm.index == 4, "één weigering, daarna rondt het model af zonder zelf nog een tool te roepen"
    gelezen = [e for e in events if e["type"] == "tool_execution" and e["phase"] == "start" and e["doel"].get("artikel") == "28"]
    assert [e["tool"] for e in gelezen] == ["get_artikel"], "de code las artikel 28, en de jurist ziet dat"
    assert ZIN_28 in json.dumps(llm.calls[3]["messages"][-1], ensure_ascii=False), "het model kreeg de tekst bij de weigering"
    citaten = _eerste(events, "antwoord")["antwoord"]["blokken"][1]["items"]
    assert [c["vindplaats"]["iri"] for c in citaten] == [TIEN_1, f"{ACHTTIEN}:lid:3"] and citaten[1]["tekst"] == ZIN_28
    assert _eerste(events, "grounding")["grounded"] is True


def test_een_jci_die_geen_rij_draagt_wordt_het_graafadres_uit_de_jci_zelf():
    """De leden van get_artikel dragen vaak geen eigen jci; het model gaf toch de jci van Iw 25 lid 1 op (eval 7 nov 2026)."""
    jci = "jci1.3:c:BWBR0004770&hoofdstuk=IV&artikel=10&lid=1&z=2026-10-01&g=2026-10-01"
    a = vul("antwoord_duiding", duiding(bepaling=jci), [tien()])
    assert a.blokken[1].items[0].vindplaats.iri == TIEN_1 and a.blokken[1].items[0].tekst == ZIN_1


def test_een_jci_van_een_bepaling_die_niet_is_opgehaald_blijft_onvulbaar():
    jci = "jci1.3:c:BWBR0004770&hoofdstuk=IV&artikel=11&lid=1"
    with pytest.raises(Onvulbaar, match="artikel:11:lid:1: de tekst is niet"):
        vul("antwoord_duiding", duiding(bepaling=jci), [tien()])
