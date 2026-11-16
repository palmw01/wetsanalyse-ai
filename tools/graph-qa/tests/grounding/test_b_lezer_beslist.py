"""De woordtoets wijst aan, de lezer beslist (plan centrale agent na A6, PR B; punt 4 en 5).

`gelezen.zonder_steun` toetst op woorden: een juiste samenvatting in eigen woorden kreeg "die de passages van dat stuk
niet dragen" (HR:2023:1371 in S01 en F01), en omdat de goedkopere toets iets vond, draaide de lezer (`stukcontrole`)
niet. Nu gaat zo'n melding naar de lezer, en zegt die bij elke zin `steunt`, dan vervalt ze. Plus de gerichte set
(`tests/data/stukcontrole_set.json`), met het script dat haar met het model draait (`eval/stukcontrole_set.py`)."""
from __future__ import annotations

import json
from pathlib import Path

from agent import stukcontrole
from eval import stukcontrole_set
from fakes import FakeLLM, make_settings, response, tool_block

ID = "ECLI:NL:HR:2099:105"
PASSAGE = ("Het doel van de meldingsplicht is dat de ontvanger in een vroeg stadium op de hoogte komt van "
           "betalingsmoeilijkheden, zodat hij zijn invorderingsbeleid daarop kan afstemmen.")
ZIN = "De melding moet de ontvanger vroeg laten weten dat er betalingsproblemen zijn, zodat hij kan bepalen hoe hij verder invordert."
TEKST = f"**{ID}**\n{ZIN}"
NIET_DRAGEN = f"duiding van {ID} die de passages van dat stuk niet dragen"


def _lezer(*oordelen: str) -> FakeLLM:
    return FakeLLM([response([tool_block("o", "oordelen", {"oordelen": [
        {"stuk": 1, "zin": z, "oordeel": o, "deel": "", "tegen": ""} for z, o in enumerate(oordelen, 1)]})], "tool_use")])


def test_de_lezer_geeft_zijn_oordelen_per_stuk_terug():
    oordelen: dict[str, set[str]] = {}
    assert stukcontrole.controleer(_lezer("steunt"), make_settings(), TEKST, {ID: PASSAGE}, [], oordelen=oordelen) == []
    assert oordelen == {ID: {"steunt"}}


def test_niet_dragen_vervalt_alleen_als_de_lezer_elke_zin_steunt():
    assert stukcontrole.vervalt_op_lezer([NIET_DRAGEN], {ID: {"steunt"}}) == [NIET_DRAGEN]
    assert stukcontrole.vervalt_op_lezer([NIET_DRAGEN], {ID: {"steunt", "niet_te_zien"}}) == []
    assert stukcontrole.vervalt_op_lezer([NIET_DRAGEN], {}) == [], "niet gelezen: de melding blijft"
    # "Zonder passage" valt erbuiten: daar valt niets te lezen.
    zonder = f"duiding van {ID} zonder passage van dat stuk in het rapport"
    assert stukcontrole.niet_dragen([zonder]) == {}
    assert stukcontrole.vervalt_op_lezer([zonder], {ID: {"steunt"}}) == []


def test_een_zin_zonder_oordeel_telt_als_niet_te_zien():
    """Gaf de lezer geen oordeel voor een zin, dan is er niets weerlegd."""
    tekst = f"**{ID}**\n{ZIN}\nDe ontvanger kan daardoor tijdig beslissen over zijn beleid tegenover de vennootschap."
    oordelen: dict[str, set[str]] = {}
    stukcontrole.controleer(_lezer("steunt"), make_settings(), tekst, {ID: PASSAGE}, [], oordelen=oordelen)
    assert oordelen[ID] == {"steunt", "niet_te_zien"}


def test_een_fout_van_de_lezer_laat_de_melding_staan():
    class Kapot:
        def create(self, **_):
            raise RuntimeError("weg")

    oordelen: dict[str, set[str]] = {}
    assert stukcontrole.controleer(Kapot(), make_settings(), TEKST, {ID: PASSAGE}, [], oordelen=oordelen) == []
    assert stukcontrole.vervalt_op_lezer([NIET_DRAGEN], oordelen) == []


def test_verify_laat_de_lezer_draaien_bij_alleen_niet_dragen():
    """De volgorde in `verify_node`: zijn de enige beweringen "niet dragen", dan draait de lezer toch."""
    import inspect

    from agent.nodes import antwoord

    bron = inspect.getsource(antwoord.verify_node)
    assert "andere = [x for x in report.beweringen if x not in niet_dragen(report.beweringen).values()]" in bron
    assert "vervalt_op_lezer(report.beweringen, oordelen)" in bron


def test_de_gerichte_set_heeft_de_vorm_van_het_plan():
    data = json.loads(Path(stukcontrole_set.SET).read_text(encoding="utf-8"))
    soorten = [g["soort"] for g in data["gevallen"]]
    assert soorten.count("tegen") == 4 and soorten.count("steunt") == 4
    assert soorten.count("verwijzing") == 2 and soorten.count("meer") == 2
    for g in data["gevallen"]:
        assert g["id"].startswith("ECLI:NL:") and ":2099:" in g["id"], "fictieve ids, geen echt arrest"
        assert g["passage"].strip() and g["zin"].strip()
        # Elk geval komt bij de lezer: de zin duidt het stuk (meer eigen woorden dan de grens).
        [stuk] = stukcontrole.te_controleren(stukcontrole_set.tekst_van(g), {g["id"]: g["passage"]}, [])
        assert stuk["zinnen"] == [g["zin"]], g["id"]


def test_het_script_telt_de_drempel_zonder_model():
    """`eval/stukcontrole_set.py` met een gescripte lezer: alles `steunt`, dus niets gevonden en niets vals."""
    uitslag = [stukcontrole_set.beoordeel(_lezer("steunt"), make_settings(), g) for g in stukcontrole_set.gevallen()]
    s = stukcontrole_set.samenvatting(uitslag)
    assert s["gevonden"] == 0 and s["vals"] == 0 and s["steunt_herkend"] == 4 and s["drempel"] is False
