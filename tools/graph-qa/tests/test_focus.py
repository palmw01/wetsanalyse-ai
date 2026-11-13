"""De focus: waar het gesprek over gaat, als toestand naast de berichten.

Zonder focus routeerde de supervisor een vervolgvraag op de kale tekst, en wist een specialist na
een annotatie niet welke bepaling en welke markering ("die markering") bedoeld werd: de historie
bevatte één regel zonder bronnode of element-id.
"""
from __future__ import annotations

import asyncio

from bron_fakes import answer_stream
from fakes import FakeGraph, FakeLLM, KetenLLM, make_settings, response, text_block
from test_annotatie_worker import LID_TSV, _aanloop, _alleen

from agent.focus import als_context, bij_advies, na_annotatie, na_antwoord

SNAPSHOT = {"doel": {"bron_iri": "urn:bwb:BWBR0004770:artikel:9:lid:1", "bwb_id": "BWBR0004770",
                     "citeertitel": "Invorderingswet 1990"}}


def _run(gen):
    async def collect():
        return [ev async for ev in gen]
    return asyncio.run(collect())


def test_annotatie_zet_de_focus_en_een_antwoord_behoudt_haar():
    focus = na_annotatie(SNAPSHOT, "artikel 9 lid 1", "IW 1990",
                         [{"id": "e1", "klasse": "Rechtssubject", "tekst": "De ontvanger", "aandacht": "geel"}])
    assert focus["bron_iri"].endswith(":lid:1") and focus["label"] == "artikel 9 lid 1 IW 1990"
    na = na_antwoord(focus, "duiding", ["urn:bwb:BWBR0004770:artikel:9"])
    assert na["elementen"] == focus["elementen"], "een uitleg verschuift het onderwerp niet"
    assert na["laatste_route"] == "duiding" and na["bronnen"] == ["urn:bwb:BWBR0004770:artikel:9"]
    tekst = als_context(na, [])
    assert "e1 · Rechtssubject · \"De ontvanger\" (geel)" in tekst
    assert "get_annotatie" in tekst and "urn:bwb:BWBR0004770:artikel:9:lid:1" in tekst


def test_advies_wijst_een_element_aan_dat_blijft_staan():
    focus = bij_advies({}, {"element_id": "e7", "klasse": "Voorwaarde", "fragment": "indien x",
                            "bron_iri": "urn:bwb:BWBR0004770:artikel:12:lid:1"})
    assert focus["element"] == {"id": "e7", "klasse": "Voorwaarde", "tekst": "indien x"}
    volgende = na_antwoord(focus, "duiding", [])
    assert volgende["element"]["id"] == "e7"
    assert "Aangewezen markering: e7" in als_context(volgende, [])


def test_open_markeringen_gaan_mee_bij_een_gewone_vraag():
    tekst = als_context({}, [], [{"klasse": "Rechtssubject", "tekst": "de ontvanger"}])
    assert "nu open heeft" in tekst and "de ontvanger" in tekst
    assert als_context({}, [], []) == ""


def test_vervolgvraag_na_annotatie_kent_bepaling_en_element_ids(tmp_path):
    settings = make_settings(checkpoint_db_path=str(tmp_path / "cp.db"))
    llm1 = KetenLLM(_aanloop(), kies=_alleen(**{"De ontvanger": "Rechtssubject"}))
    events = _run(answer_stream("annoteer artikel 9 lid 1 IW", "focus-1", settings=settings, llm=llm1,
                                graph=FakeGraph(result=LID_TSV)))
    element = next(e["element"] for e in events if e["type"] == "element")

    llm2 = FakeLLM([
        response([text_block("SPECIALIST: duiding\nPLAN: leg de markering uit")], "end_turn"),
        response([text_block("Omdat de ontvanger de handelende partij is.")], "end_turn"),
    ])
    _run(answer_stream("waarom die klasse?", "focus-1", settings=settings, llm=llm2, graph=FakeGraph(result="")))

    supervisor, specialist = llm2.prompts[:2]
    for systeem in (supervisor, specialist):
        assert "urn:bwb:BWBR0004770:artikel:9:lid:1" in systeem, "de bepaling staat in de context"
        assert element["id"] in systeem, "het element is bij id aan te spreken"
    historie = str(llm2.calls[1].get("messages"))
    assert element["id"] in historie and "bronnode urn:bwb:BWBR0004770:artikel:9:lid:1" in historie


def test_een_antwoord_over_een_andere_bepaling_laat_de_annotatiefocus_vallen():
    """Annotatie van art. 9 lid 1, dan een antwoord over art. 26: "en lid 2?" gaat dan niet meer over art. 9."""
    focus = na_annotatie(SNAPSHOT, "artikel 9 lid 1", "IW 1990", [{"id": "e1", "klasse": "Rechtssubject", "tekst": "x"}])
    na = na_antwoord(focus, "duiding", ["urn:bwb:BWBR0004770:artikel:26:lid:1"])
    assert "bron_iri" not in na and "elementen" not in na
    assert na["bronnen"] == ["urn:bwb:BWBR0004770:artikel:26:lid:1"]
    assert "Onderwerp:" not in als_context(na, [])


def test_een_antwoord_zonder_bronnen_laat_de_focus_staan():
    focus = na_annotatie(SNAPSHOT, "artikel 9 lid 1", "IW 1990", [])
    assert na_antwoord(focus, "duiding", [])["bron_iri"] == focus["bron_iri"]


def test_de_recentste_bronnen_blijven_in_een_lang_gesprek():
    gezien = [f"urn:bwb:BWBR0004770:artikel:{n}" for n in range(1, 20)]
    tekst = als_context({"bronnen": ["urn:bwb:BWBR0004770:artikel:99"]}, gezien)
    assert "artikel:99" in tekst and "artikel:1," not in tekst


# --- de volgorde van het vorige antwoord (ADR-016 ronde 3, F01) -------------------------------------------------------

from agent.focus import MAX_GENOEMD, MAX_GENOEMD_LABEL, genoemd_in_antwoord  # noqa: E402

#: Het overzicht van S01: het antwoord noemt de uitspraak uit 2023 eerst; Lex las die uit 2026 als eerste.
OVERZICHT = {"sjabloon": "antwoord_extern", "blokken": [
    {"soort": "stukken", "brontype": "uitspraak", "kop": "Uitspraken", "items": [
        {"id": "ECLI:NL:HR:2023:1371", "label": "Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371"},
        {"id": "ECLI:NL:HR:2026:586", "label": "Hoge Raad 10 april 2026, ECLI:NL:HR:2026:586"},
        {"id": "ECLI:NL:GHARL:2024:12", "label": "Gerechtshof Arnhem-Leeuwarden 9 januari 2024, ECLI:NL:GHARL:2024:12"}]}],
    "doelen": []}
GELEZEN = [{"uri": "ECLI:NL:HR:2026:586", "label": "Hoge Raad 10 april 2026"},
           {"uri": "ECLI:NL:HR:2023:1371", "label": "Hoge Raad 6 oktober 2023"}]


def test_de_eerste_uit_je_overzicht_is_de_eerste_van_het_antwoord_niet_de_eerst_gelezene():
    """F01: "Wat zei de eerste uitspraak uit je overzicht precies over de bewijslast?" ging over ECLI:NL:HR:2026:586 (de
    eerste die Lex las), niet over ECLI:NL:HR:2023:1371 (de eerste van het antwoord)."""
    genoemd = genoemd_in_antwoord(OVERZICHT, "", GELEZEN)
    assert [g["id"] for g in genoemd] == ["ECLI:NL:HR:2023:1371", "ECLI:NL:HR:2026:586", "ECLI:NL:GHARL:2024:12"]
    focus = na_antwoord({}, "algemeen", [b["uri"] for b in GELEZEN], genoemd)
    tekst = als_context(focus, [])
    regels = tekst.splitlines()
    kop = next(i for i, r in enumerate(regels) if r.startswith("In je vorige antwoord genoemd, in deze volgorde"))
    assert "'de eerste'" in regels[kop] and "niet op de volgorde waarin je las" in regels[kop]
    assert regels[kop + 1] == "1. Hoge Raad 6 oktober 2023, ECLI:NL:HR:2023:1371 (ECLI:NL:HR:2023:1371)"
    assert regels[kop + 2].startswith("2. Hoge Raad 10 april 2026") and regels[kop + 3].startswith("3. Gerechtshof")


def test_de_volgorde_bij_andere_vormen_van_een_antwoord():
    # Twee blokken met een gelezen stuk elk: de volgorde van de blokken.
    twee = {"blokken": [{"soort": "extern", "id": "kst-35496-3", "label": "Kamerstukken II 35496, nr. 3"},
                        {"soort": "wettekst"},
                        {"soort": "extern", "id": "stb-2010-176", "label": "Stb. 2010, 176"}], "doelen": []}
    assert [g["id"] for g in genoemd_in_antwoord(twee, "", [])] == ["kst-35496-3", "stb-2010-176"]
    # Een sjabloon over bepalingen: de doelen, met de regeling erbij.
    doelen = {"blokken": [{"soort": "wettekst"}], "doelen": [
        {"iri": "urn:bwb:BWBR0004770:artikel:25", "label": "Artikel 25", "regeling": "Invorderingswet 1990"},
        {"iri": "urn:bwb:BWBR0004770:artikel:9", "label": "Artikel 9", "regeling": "Invorderingswet 1990"}]}
    assert [g["label"] for g in genoemd_in_antwoord(doelen, "", [])] == ["Artikel 25 Invorderingswet 1990", "Artikel 9 Invorderingswet 1990"]
    # Vrije tekst: waar de tekst de bron voor het eerst noemt, niet de volgorde van de bronnenlijst.
    tekst = "De Hoge Raad oordeelde op 6 oktober 2023 anders dan in het arrest van Hoge Raad 10 april 2026."
    bronnen = [{"uri": "ECLI:NL:HR:2026:586", "label": "Hoge Raad 10 april 2026"},
               {"uri": "ECLI:NL:HR:2023:1371", "label": "6 oktober 2023"},
               {"uri": "ECLI:NL:HR:2020:1", "label": "Hoge Raad 1 januari 2020"}]   # gelezen, niet genoemd
    assert [g["id"] for g in genoemd_in_antwoord(None, tekst, bronnen)] == ["ECLI:NL:HR:2023:1371", "ECLI:NL:HR:2026:586"]


def test_zonder_lijst_geen_blok_en_een_nieuw_antwoord_vervangt_de_vorige_lijst():
    """Tegenvoorbeelden: één ding heeft geen volgorde, en een gewoon antwoord laat geen oude lijst staan."""
    een = {"blokken": [{"soort": "extern", "id": "kst-35496-3", "label": "x"}], "doelen": []}
    assert genoemd_in_antwoord(een, "", []) == [] and genoemd_in_antwoord(None, "Een antwoord zonder bronnen.", []) == []
    assert genoemd_in_antwoord(None, "Artikel 9 regelt dit.", [{"uri": "urn:bwb:BWBR0004770:artikel:9", "label": "Artikel 9"}]) == []
    met = na_antwoord({}, "algemeen", [], genoemd_in_antwoord(OVERZICHT, "", []))
    assert "In je vorige antwoord genoemd" in als_context(met, [])
    daarna = na_antwoord(met, "duiding", ["urn:bwb:BWBR0004770:artikel:9"], [])
    assert "genoemd" not in daarna and "In je vorige antwoord genoemd" not in als_context(daarna, [])
    # Zonder lijst is de context byte-gelijk aan voorheen.
    assert als_context(na_antwoord({}, "duiding", ["urn:bwb:BWBR0004770:artikel:9"]), []) == \
        als_context(na_antwoord({}, "duiding", ["urn:bwb:BWBR0004770:artikel:9"], []), [])


def test_het_blok_is_klein_en_vast_van_vorm():
    """Hoogstens twaalf regels met een afgekapt label: wat de lijst in de context kost, heeft een bovengrens."""
    veel = {"blokken": [{"soort": "stukken", "items": [
        {"id": f"ECLI:NL:HR:2024:{i}", "label": f"Hoge Raad {i} januari 2024, ECLI:NL:HR:2024:{i}, " + "een heel lange titel " * 20}
        for i in range(1, 31)]}], "doelen": []}
    genoemd = genoemd_in_antwoord(veel, "", [])
    assert len(genoemd) == MAX_GENOEMD and all(len(g["label"]) <= MAX_GENOEMD_LABEL for g in genoemd)
    zonder = als_context(na_antwoord({}, "algemeen", []), [])
    met = als_context(na_antwoord({}, "algemeen", [], genoemd), [])
    # De bovengrens in tekens; met 0,354 token per teken (de ijking van de contextopbouw) is dat hoogstens zo'n 600 tokens.
    assert 0 < len(met) - len(zonder) <= 1700
    gewoon = als_context(na_antwoord({}, "algemeen", [], genoemd_in_antwoord(OVERZICHT, "", [])), [])
    assert len(gewoon) - len(zonder) <= 450


def test_het_vervolg_krijgt_de_volgorde_na_de_historie_en_het_voorvoegsel_blijft_gelijk(tmp_path):
    """In de keten: na een antwoord dat twee bepalingen noemt, staat de lijst in de context van de volgende beurt. Die
    context staat in de vraag van de beurt, na de historie (ADR-015); de systeemprompt is dezelfde als zonder lijst."""
    settings = make_settings(checkpoint_db_path=str(tmp_path / "cp.db"), enable_planning=False)
    rijen = ("?node\t?tekst\n<urn:bwb:BWBR0004770:artikel:25>\tUitstel van betaling.\n"
             "<urn:bwb:BWBR0004770:artikel:9>\tDe betalingstermijn.\n")
    from fakes import tool_block
    llm1 = FakeLLM([response([tool_block("t1", "search_wetgeving", {"query": "betaling"})], "tool_use"),
                    response([text_block("Zie urn:bwb:BWBR0004770:artikel:25 over uitstel en urn:bwb:BWBR0004770:artikel:9 over de termijn.")], "end_turn")])
    _run(answer_stream("welke artikelen gaan over betaling?", "volgorde-1", settings=settings, llm=llm1, graph=FakeGraph(result=rijen)))
    llm2 = FakeLLM([response([text_block("Het eerste artikel regelt uitstel.")], "end_turn")])
    _run(answer_stream("wat regelt de eerste precies?", "volgorde-1", settings=settings, llm=llm2, graph=FakeGraph(result=rijen)))
    aanroep = llm2.calls[0]
    berichten = str(aanroep.get("messages"))
    assert "In je vorige antwoord genoemd, in deze volgorde" in berichten
    assert berichten.index("urn:bwb:BWBR0004770:artikel:25") < berichten.index("In je vorige antwoord genoemd")
    assert "In je vorige antwoord genoemd" not in str(aanroep.get("system")), "niet in het voorvoegsel"
    assert str(aanroep.get("system")) == str(llm1.calls[0].get("system")), "het voorvoegsel beweegt niet"
