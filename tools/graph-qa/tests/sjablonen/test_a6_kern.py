"""De kern per stuk in `antwoord_extern` (plan centrale agent na A6, PR A; S01, P01 en de citaten bij uitspraken).

Het sjabloon had alleen een kort antwoord van twee tot vier zinnen. Een vraag "vat per uitspraak samen" eindigde dan op
twee manieren fout: het model schreef het overzicht per stuk naast de aanroep, en die tekst gooit de code weg (S01,
4.345 tekens `tekst_ernaast`), of het perste vier arresten in het korte antwoord (P01). De citaten kozen daarna uit dat
korte antwoord, en dat waren de trefwoorden. Nu draagt elke aanwijzing een `kern`, en kiest de code de passages op die
kern. Dezelfde nepbron als `test_a6_citaten.py`."""
from __future__ import annotations

import json

from bronmodel.antwoord import antwoord_tekst

from agent import sjablonen
from agent.gelezen import per_stuk, zonder_steun
from agent.sjablonen import extern
from test_a6_citaten import BRON, DRAGEND, HR, NR_DRAGEND, NR_PROCES, PROCES, TRACE

KORT = "De Hoge Raad legt uit waarom de melding van betalingsonmacht ertoe doet."
KERN = ("Het doel van de meldingsplicht is dat de ontvanger vroeg op de hoogte komt van betalingsmoeilijkheden. Bij een "
        "correcte melding draagt de ontvanger de bewijslast voor kennelijk onbehoorlijk bestuur; zonder correcte melding "
        "geldt een wettelijk vermoeden, waartegen de gewezen bestuurder tegenbewijs mag leveren.")


def _schema(naam: str) -> dict:
    [s] = [s for s in sjablonen.sjabloon_schemas(frozenset({naam}), extern=True)]
    return s["input_schema"]["properties"]["extern"]["items"]


def test_alleen_antwoord_extern_vraagt_een_kern_per_aanwijzing():
    """Het subsjabloon blijft byte-gelijk: het zit in elk sjabloon van de centrale agent, aan de grens van de strict
    schema's."""
    items = _schema("antwoord_extern")
    assert "kern" in items["properties"] and "kern" in items["required"]
    assert "kern" not in _schema("antwoord_duiding")["properties"]


def test_de_passages_volgen_de_kern_niet_het_korte_antwoord():
    """S01: het model wees het procesverloop aan, en het korte antwoord droeg geen punt. De kern wel."""
    items = [{"id": HR, "van_nr": NR_PROCES[0], "tot_nr": NR_PROCES[-1], "kern": KERN}]
    antwoord = sjablonen.vul("antwoord_extern", {"kort_antwoord": KORT, "extern": items, "stukken": [], "twijfel": []},
                             TRACE)
    [blok] = [b for b in antwoord.blokken if b.soort == "extern"]
    assert blok.kern == KERN
    getoond = {p.tekst for p in blok.passages}
    assert getoond and getoond <= set(DRAGEND) and not getoond & set(PROCES), getoond
    # De tekst zet de kern onder een kop met het stuk, zodat de toets per stuk weet waarover hij gaat, en de getoonde
    # passages dragen hem.
    tekst = antwoord_tekst(antwoord)
    assert any(HR in ids for zin, ids in per_stuk(tekst) if "meldingsplicht" in zin)
    assert not zonder_steun(tekst, {HR: " ".join(getoond)}, TRACE)


def test_een_kern_bij_meer_aanwijzingen_van_een_stuk_staat_er_een_keer():
    items = [{"id": HR, "van_nr": NR_DRAGEND[0], "tot_nr": NR_DRAGEND[0], "kern": KERN},
             {"id": HR, "van_nr": NR_DRAGEND[2], "tot_nr": NR_DRAGEND[2], "kern": ""},
             {"id": HR, "van_nr": NR_DRAGEND[3], "tot_nr": NR_DRAGEND[3], "kern": KERN}]
    assert extern.kernen(items) == {HR: KERN}
    antwoord = sjablonen.vul("antwoord_extern", {"kort_antwoord": KORT, "extern": items, "stukken": [], "twijfel": []},
                             TRACE)
    assert antwoord_tekst(antwoord).count(KERN) == 1


def test_zonder_kern_blijft_het_blok_zoals_het_was():
    """Een aanwijzing zonder kern (een ouder bericht, de code die een lijst omzet) toont geen kop en geen lege regel."""
    items = [{"id": HR, "van_nr": NR_DRAGEND[0], "tot_nr": NR_DRAGEND[-1]}]
    antwoord = sjablonen.vul("antwoord_extern", {"kort_antwoord": KORT, "extern": items, "stukken": [], "twijfel": []},
                             TRACE)
    [blok] = [b for b in antwoord.blokken if b.soort == "extern"]
    assert blok.kern == ""
    assert f"**{blok.label}**" not in antwoord_tekst(antwoord)


def test_door_de_hele_graaf_staat_de_kern_in_het_antwoord_en_meldt_de_toets_niets(monkeypatch):
    """Route → node → sjabloon → verify → finalize, met de kern per stuk: geen correctieronde op 'niet dragen'."""
    import asyncio

    from agent import tools as t
    from agent.agent import answer_stream
    from fakes import FakeGraph, FakeLLM, make_settings, response, tool_block

    monkeypatch.setattr(t.CONNECTORMODULES["rechtspraak"], "_bron", BRON)
    aanroep = {"kort_antwoord": KORT, "stukken": [], "twijfel": [],
               "extern": [{"id": HR, "van_nr": NR_PROCES[0], "tot_nr": NR_PROCES[-1], "kern": KERN}]}
    llm = FakeLLM([response([tool_block("s1", "antwoord_extern", aanroep)], "tool_use")] * 3)

    async def beurt():
        return [e async for e in answer_stream(f"Vat {HR} samen: wat zegt de Hoge Raad over de melding?",
                                               settings=make_settings(connector_rechtspraak=True),
                                               llm=llm, graph=FakeGraph(result=""), bronnen=["rechtspraak"])]

    events = asyncio.run(beurt())
    assert not [e for e in events if e.get("type") == "error"], events
    antwoord = next(e["antwoord"] for e in events if e.get("type") == "antwoord")
    [blok] = [b for b in antwoord["blokken"] if b["soort"] == "extern"]
    assert blok["kern"] == KERN
    grounding = next(e for e in events if e.get("type") == "grounding")
    assert "niet dragen" not in json.dumps(grounding, ensure_ascii=False), grounding
