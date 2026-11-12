"""De toets op beweringen in de toelichting (`agent/beweringen.py`), en zijn herstelpad in `verify_node`.

Iteratie Rechtspraak ronde 4 (12 nov 2026): een feit in de toelichting dat niet in het opgehaalde staat, wordt gevangen,
voor elk sjabloon en vrije tekst, zonder lijst per connector. Eerst één correctieronde; staat het er dan nog, dan is het
onbevestigd.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from agent.agent import answer_stream
from agent.beweringen import beweringen
from agent.grounding import check_grounding
from fakes import FakeGraph, FakeLLM, make_settings, response, text_block, tool_block

ART_IRI = "urn:bwb:BWBR0004770:artikel:36"

ZOEK = json.dumps({"status": "ok", "volledig": False, "aantal": 2, "totaal": 75,
                   "per_instantie": {"Hoge Raad": 75},
                   "resultaten": [{"id": "ECLI:NL:HR:2023:563", "label": "Hoge Raad 14 april 2023, ECLI:NL:HR:2023:563",
                                   "datum": "2023-04-14", "orgaan": "Hoge Raad", "nummer": "20/02401"},
                                  {"id": "ECLI:NL:HR:2023:1371", "label": "Hoge Raad 6 oktober 2023",
                                   "datum": "2023-10-06", "orgaan": "Hoge Raad"}]})
TRACE = [("zoek_uitspraken", ZOEK)]


def _bron(trace=TRACE) -> str:
    from agent.resultaat import waarden
    return "\n".join(f"{waarden(t)}\n{t}" for _, t in trace)


# --- wat telt als feit --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tekst,feit", [
    ("De memorie van toelichting staat in dossier 20588.", "20588"),                     # een nummer (K16)
    ("Er zijn 104 uitspraken van de Hoge Raad.", "104 uitspraken"),                      # een telling
    ("De Hoge Raad besliste op 1 maart 2021.", "1 maart 2021"),                           # een datum
    ("Het gerechtshof: Gerechtshof Arnhem-Leeuwarden oordeelde anders.", "Gerechtshof Arnhem-Leeuwarden"),  # instantie
    ("De Eerste Kamer nam het voorstel aan.", "Eerste Kamer"),
    ("Het stuk verscheen in 1989.", "1989"),                                             # een jaar
])
def test_een_feit_zonder_bron_is_een_bewering(tekst, feit):
    assert feit in beweringen(tekst, _bron())


@pytest.mark.parametrize("tekst", [
    "De Hoge Raad heeft 75 uitspraken bij dit artikel.",                 # totaal en instantie uit het resultaat
    "Hoge Raad 14 april 2023, ECLI:NL:HR:2023:563, zaak 20/02401.",      # datum voluit uit de ISO-datum, het zaaknummer
    "Zie ECLI:NL:HR:2099:12345 en BWBR0004770.",                         # ids hebben hun eigen toets (`unsupported`)
    "Artikel 103 en lid 3 van artikel 36 regelen dit.",                  # vindplaatsen: `onbevestigd`
    'De wet zegt: "binnen 1234 dagen na de aanslag betalen".',           # een citaat: `niet_letterlijk`
    "Zie [de uitspraak](https://deeplink.rechtspraak.nl/uitspraak?id=ECLI:NL:HR:2023:9999).",
])
def test_wat_een_eigen_toets_heeft_of_in_de_bron_staat_is_geen_bewering(tekst):
    assert beweringen(tekst, _bron()) == []


def test_duizendtallen_tellen_in_beide_vormen():
    assert beweringen("Er zijn 6.772 uitspraken.", "totaal 6772") == []
    assert beweringen("Er zijn 6772 uitspraken.", "totaal: 6.772") == []


def test_wat_de_jurist_zelf_noemt_is_geen_bewering():
    """"Wat heeft de Hoge Raad gezegd over dossier 20588?" — het antwoord mag dat herhalen zonder bron."""
    vraag = "Wat zegt de Hoge Raad over dossier 20588 sinds 1 maart 2021?"
    assert beweringen("Over dossier 20588 vond ik bij de Hoge Raad sinds 1 maart 2021 niets.", "", bekend=vraag) == []


def test_parket_bij_de_hoge_raad_telt_niet_ook_als_hoge_raad():
    assert beweringen("Het Parket bij de Hoge Raad concludeerde.", "orgaan: Parket bij de Hoge Raad") == []


def test_een_bewering_maakt_het_rapport_onbepaald_maar_niet_ongegrond():
    rapport = check_grounding("Er zijn 104 uitspraken van de Hoge Raad.", TRACE)
    assert rapport.beweringen == ["104 uitspraken"] and rapport.grounded and rapport.niveau == "onbepaald"


def test_een_ecli_zonder_bron_staat_niet_dubbel():
    rapport = check_grounding("Zie ECLI:NL:HR:2099:12345.", TRACE)
    assert rapport.unsupported and rapport.beweringen == []


# --- het herstelpad --------------------------------------------------------------------------------------------------

def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_een_bewering_krijgt_eerst_een_correctieronde():
    settings = make_settings(enable_planning=False, grounding_correct=True)
    graph = FakeGraph(result=f"<{ART_IRI}> bwb:tekst 'Hoofdelijk aansprakelijk is ieder van de bestuurders.' .")
    llm = FakeLLM([
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "36"})], "tool_use"),
        response([text_block(f"Zie {ART_IRI}. De memorie van toelichting staat in dossier 20588.")], "end_turn"),
        response([text_block(f"Zie {ART_IRI}. Bestuurders zijn hoofdelijk aansprakelijk.")], "end_turn"),
    ])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert llm.index == 3, "de correctieronde hoort te zijn gedraaid"
    instructie = llm.calls[-1]["messages"][-1]["content"]
    assert "20588" in instructie and "eigen kennis" in instructie
    grounding = next(e for e in events if e["type"] == "grounding")
    assert grounding["grounded"] is True and not grounding.get("onbevestigd")


def test_blijft_de_bewering_staan_dan_is_ze_onbevestigd():
    settings = make_settings(enable_planning=False, grounding_correct=True)
    graph = FakeGraph(result=f"<{ART_IRI}> bwb:tekst 'Hoofdelijk aansprakelijk is ieder van de bestuurders.' .")
    fout = f"Zie {ART_IRI}. De memorie van toelichting staat in dossier 20588."
    llm = FakeLLM([
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "36"})], "tool_use"),
        response([text_block(fout)], "end_turn"),
        response([text_block(fout)], "end_turn"),
    ])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert llm.index == 3
    grounding = next(e for e in events if e["type"] == "grounding")
    assert grounding["grounded"] is True and grounding["niveau"] == "onbepaald" and "20588" in grounding["onbevestigd"]


def test_zonder_correctie_is_een_bewering_meteen_onbevestigd():
    settings = make_settings(enable_planning=False, grounding_correct=False)
    graph = FakeGraph(result=f"<{ART_IRI}> bwb:tekst 'x' .")
    llm = FakeLLM([
        response([tool_block("t1", "get_artikel", {"bwb_id": "BWBR0004770", "artikel": "36"})], "tool_use"),
        response([text_block(f"Zie {ART_IRI}. Dossier 20588.")], "end_turn"),
    ])
    events = _run(answer_stream("vraag", settings=settings, llm=llm, graph=graph))
    assert llm.index == 2
    assert "20588" in next(e for e in events if e["type"] == "grounding")["onbevestigd"]


def test_het_jaar_in_een_wetsnaam_is_geen_bewering():
    """Ronde 2, R28b: "artikel 36 Invorderingswet 1990" in de toelichting, en de uitspraak noemde de wet als "IW"."""
    for naam in ("Invorderingswet 1990", "Leidraad Invordering 2008", "Wet IB 2001", "de AWR 1959"):
        assert beweringen(f"Dit volgt uit de {naam}.", "") == [], naam
    assert beweringen("In 1989 verscheen de memorie.", "") == ["1989"]


def test_een_afkorting_van_een_gerecht_is_geen_bewering():
    """Ronde 2, R22: "CRvB en CBb" in de toelichting, de bron noemt ze voluit."""
    assert beweringen("De CRvB en het CBb komen weinig voor.", "Centrale Raad van Beroep") == []


def test_een_afgeleid_getal_is_een_bewering():
    """Ronde 2, R22 en K17-R22: "73 procent" en "samen: 166" rekende het model zelf uit; ze staan nergens in de bron."""
    bron = '{"per_instantie": {"Hoge Raad": 75, "Parket bij de Hoge Raad": 91}}'
    assert beweringen("Hoge Raad en Parket bij de Hoge Raad samen: 166.", bron) == ["166"]
