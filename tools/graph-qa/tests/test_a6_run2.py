"""De fixes na A6 run 2 (15 nov 2026, `docs/architectuur/metingen/centrale-agent-2026-11-15-a6-run2/`), met de gevallen uit
die meting als test.

1. V02: de centrale agent koos zelf de bronselectie, die stil doorging bij deelvraag 3. Heeft het werkgebied geen deelvraag
   over het genoemde onderwerp, dan vraagt de code het de jurist, zonder model; de overdracht `werkgebied` weigert hetzelfde.
   V03 (wat de memorie van toelichting zegt, per deelvraag) gaat naar een subagent, en de centrale agent leest zelf
   hoogstens `MAX_STUKKEN_CENTRAAL` stukken naast de wet.
2. F01: de controle per stuk wees bij PHR:2025:435 een stukje slotsom aan dat hetzelfde zei als de zin. Een tegenspraak
   wijst nu ook het zinsdeel aan, en "zegt meer" is geen tegenspraak.
3. S03 en S04: na het rapport zei de weigering van het sjabloon "haal de bepaling op met get_artikel", en dat weigert
   `tools_node` na een subagent (11 en 9 geweigerde aanroepen). Die opdracht valt weg, en een tekstantwoord krijgt de
   citaten uit het rapport.
4. E03: "BW art. 3:239" in de uitleg is "artikel 239 van Boek 3" in de wettekst; de code vond het niet en weigerde twee
   keer met `genoemd_onbekend`.
5. F01: "Invorderingswet 1990 uitspraken gelezen" telde als 1990 gelezen uitspraken.
6. De meetset: M01 en M06 klikken de bevestiging, zodat de uitvoering van het plan gemeten wordt.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import overdracht, stukcontrole
from agent.beweringen import gelezen_aantallen
from agent.bronselectie import deelvraag_onderwerp, deelvragen_uit, geen_deelvraag_melding
from agent.nodes import antwoord as antwoordnodes
from agent.nodes import sjabloon as sjabloonnodes
from agent.nodes import subagent_route as route
from agent.nodes import supervisie
from agent.sjablonen.duiding import _zin_met
from bronmodel.antwoord import Citaat, Vindplaats
from bronmodel.connectors import CONNECTORS
from fakes import FakeLLM, make_settings, response, tool_block
from test_a6_run1 import PHR, PHR_PASSAGES, regelingen
from test_subagent import STATE

EVAL = Path(__file__).resolve().parents[1] / "eval"
AAN = {n: {"naam": n, "label": c.label, "aan": True, "reden": "aan"} for n, c in CONNECTORS.items()}


def _set(naam: str) -> dict[str, dict]:
    rijen = [json.loads(r) for r in (EVAL / naam).read_text().splitlines() if r.strip().startswith("{")]
    return {r["id"]: r for r in rijen if r.get("opdracht")}


AGENTSET = _set("golden_centrale_agent.jsonl")

#: Het meetwerkgebied van A6 (de deelvragen zoals `werkgebied_context.context_tekst` ze geeft): geen deelvraag over verjaring.
CONTEXT = ("Werkgebied: Meting centrale agent\nAnalysevraag: Hoe vordert de ontvanger een belastingaanslag in?\n"
           "Deelvragen:\n- Wanneer moet de belastingschuldige een aanslag betalen?\n"
           "- Welke stappen zet de ontvanger als de aanslag niet op tijd betaald is?\n"
           "- Wanneer kan de ontvanger betaling vorderen van een derde die de belastingschuldige iets verschuldigd is?\n"
           "Bronnen om te analyseren: Artikel 9; Artikel 11; Artikel 19")


# 1. V02 en V03 ---------------------------------------------------------------------------------------------------------

def test_v02_een_deelvraag_die_het_werkgebied_niet_heeft_wordt_een_vraag_aan_de_jurist():
    vraag = AGENTSET["V02"]["opdracht"]
    assert deelvraag_onderwerp(vraag) == "verjaring" and len(deelvragen_uit(CONTEXT)) == 3
    melding = geen_deelvraag_melding(vraag, CONTEXT)
    assert melding.startswith("Dit werkgebied heeft geen deelvraag over verjaring.")
    assert "3. Wanneer kan de ontvanger betaling vorderen" in melding and melding.rstrip().endswith("?")


@pytest.mark.parametrize("vraag, context", [
    ("Zoek de bronnen bij de deelvraag over de betaling door een derde.", CONTEXT),   # die deelvraag is er
    ("Zoek de bronnen bij de deelvraag over verjaring.", ""),                          # niets om tegen te toetsen
    ("Zoek de bronnen bij deelvraag 2", CONTEXT),                                     # bij nummer: de bronselectie
    ("Help mij de bronnen bij dit werkgebied te bepalen", CONTEXT),
    ("Wat zegt de deelvraag over verjaring?", CONTEXT),                               # geen verzoek om bronnen
])
def test_wat_de_deelvraagtoets_laat_gaan(vraag, context):
    assert geen_deelvraag_melding(vraag, context) == ""


def test_de_supervisor_vraagt_het_zonder_model_en_voor_beide_vormen(monkeypatch):
    monkeypatch.setattr(supervisie, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(settings=SimpleNamespace(centrale_agent="aan", legt_zelf_vast=True), graph=None, kinderen=None)
    for vorm in ("centraal", "supervisor"):
        state = {**STATE, "question": AGENTSET["V02"]["opdracht"], "modus": "auto", "agentvorm": vorm,
                 "werkgebied_id": "w1", "werkgebied_context": "\n\nWERKGEBIED (…):\n" + CONTEXT}
        upd = supervisie._kies(b, state)
        assert upd["afwijzen"] and upd["afwijs_melding"].startswith("Dit werkgebied heeft geen deelvraag over verjaring")


def test_de_overdracht_werkgebied_start_de_bronselectie_niet_bij_een_onbekende_deelvraag_of_een_connector(monkeypatch):
    monkeypatch.setattr(overdracht, "get_stream_writer", lambda: (lambda _e: None))
    state = {**STATE, "question": AGENTSET["V02"]["opdracht"], "werkgebied_id": "w1", "werkgebied_context": CONTEXT}
    uit = overdracht._werkgebied(None, state, {"taak": "bronselectie"})
    assert isinstance(uit, str) and "geen deelvraag over verjaring" in uit
    uit = overdracht._werkgebied(None, {**state, "question": AGENTSET["V03"]["opdracht"]}, {"taak": "bronselectie"})
    assert isinstance(uit, str) and "naast de wet" in uit


def test_v03_gaat_naar_een_subagent_met_de_deelvragen_als_oplevering():
    rij = AGENTSET["V03"]
    stand = {n: AAN[n] for n in rij["context"]["bronnen"]}
    [(profiel, opdracht)] = route.plan(rij["opdracht"], stand, regelingen)
    assert profiel == "wetsgeschiedenis_lezen" == rij["verwacht"]["profielen"][0] and opdracht.doel == rij["opdracht"]
    assert "Per deelvraag" in opdracht.oplevering
    assert not route.plan(rij["opdracht"], {}, regelingen), "zonder bron naast de wet aan doet de centrale agent het"


def _gelezen(ident: str) -> tuple[str, str]:
    return ("get_kamerstuk", json.dumps({"status": "ok", "volledig": True, "stuk": {"id": ident, "label": ident},
                                         "resultaten": [{"nr": 1, "tekst": "Tekst."}]}))


def _lees(ident: str, offset: int = 0) -> dict:
    return {"id": f"t-{ident}-{offset}", "name": "get_kamerstuk", "input": {"id": ident, "offset": offset}}


def test_de_centrale_agent_leest_zelf_hoogstens_zes_stukken_naast_de_wet():
    """V03: 17 keer `get_kamerstuk` in 14 rondes (690k), zonder subagent."""
    gelezen = [f"kst-3440{i}-3" for i in range(antwoordnodes.MAX_STUKKEN_CENTRAAL - 1)]
    state = {"specialist": "centraal", "source_trace": [_gelezen(i) for i in gelezen]}
    nieuw = [_lees("kst-33402-3"), _lees("kst-34786-3"), _lees(gelezen[0], 200)]
    weg = antwoordnodes.stukken_plafond(state, nieuw)
    # Het zesde stuk mag nog, het zevende niet; een volgende pagina van een gelezen stuk telt niet als nieuw.
    assert weg == {id(nieuw[1])}
    assert json.loads(antwoordnodes.STUKKEN_PLAFOND)["reden"] == "stukken_plafond"
    # Een subagent en een specialist van de supervisor vallen er niet onder.
    assert not antwoordnodes.stukken_plafond({**state, "opdracht": {"doel": "x"}}, nieuw)
    assert not antwoordnodes.stukken_plafond({**state, "specialist": "algemeen"}, nieuw)


def test_de_reden_van_het_plafond_heeft_een_zin_voor_de_jurist():
    from agent.resultaat import REDEN_ZIN

    assert REDEN_ZIN["stukken_plafond"]


# 2. De controle per stuk: PHR:2025:435 in F01 --------------------------------------------------------------------------

F01_ZIN = ("De A-G bespreekt vijf mogelijke verzachtingen van de regeling, maar concludeert dat geen ervan in de concrete "
           "zaak tot een andere uitkomst leidt.")
F01_ANTWOORD = f"**Conclusie A-G ({PHR})**\n{F01_ZIN}"
F01_PASSAGES = PHR_PASSAGES + " Ik meen dat belanghebbende niets opschiet met de lichtpuntjes."


from test_a6_run1 import _oordeel  # noqa: E402 – het oordeel en de tweede lezing


def test_een_stukje_passage_dat_hetzelfde_zegt_als_een_zin_die_meer_zegt_is_geen_tegenspraak():
    """F01: de slotsom (r.o. 1.5) stond letterlijk in de passages, dus de toets van run 1 liet de tegenspraak door. Het
    zinsdeel dat niet zou kloppen, moet nu ook letterlijk in de zin staan."""
    steun = {PHR: F01_PASSAGES}
    [stuk] = stukcontrole.te_controleren(F01_ANTWOORD, steun, [])
    assert stuk["zinnen"] == [F01_ZIN]
    slotsom = "Ik meen dat belanghebbende niets opschiet met de lichtpuntjes."
    for deel in ("", "vijf", "de A-G heeft het over vier lichtpuntjes"):   # leeg, één woord, niet uit de zin
        assert stukcontrole.controleer(_oordeel(oordeel="spreekt_tegen", deel=deel, tegen=slotsom), make_settings(),
                                       F01_ANTWOORD, steun, []) == [], deel
    [bewering] = stukcontrole.controleer(
        _oordeel(oordeel="spreekt_tegen", deel="geen ervan in de concrete zaak tot een andere uitkomst leidt",
                 tegen=slotsom), make_settings(), F01_ANTWOORD, steun, [])
    assert bewering.startswith(f"duiding van {PHR} die de passages van dat stuk tegenspreekt")


def test_de_instructie_zegt_dat_meer_zeggen_niet_te_zien_is_en_het_schema_vraagt_beide_kanten():
    assert "Zegt een zin méér dan de passages" in stukcontrole.SYSTEEM and "niet spreekt_tegen" in stukcontrole.SYSTEEM
    rij = stukcontrole.schema()["input_schema"]["properties"]["oordelen"]["items"]
    assert {"deel", "tegen"} <= set(rij["required"])
    # De uitleg komt vóór het oordeel: eerst aanwijzen, dan oordelen.
    assert list(rij["properties"]).index("deel") < list(rij["properties"]).index("oordeel")


# 3. S03 en S04: na het rapport -----------------------------------------------------------------------------------------

WEIGERING = ("Niet te tonen, dus er wordt niets getoond. urn:bwb:BWBR0004770:artikel:11: de tekst is niet (helemaal) "
             "opgehaald. Gebruik een iri uit een toolresultaat, en haal de bepaling op met get_artikel, get_lid of "
             "get_bepaling. Rond daarna opnieuw af.")


def test_na_een_rapport_zegt_de_weigering_niet_meer_dat_het_model_zelf_moet_ophalen():
    na = {"subagenten": [{"uitkomst": "klaar"}], "specialist": "centraal"}
    tekst = sjabloonnodes.na_subagent_weigering(na, WEIGERING)
    assert "haal de bepaling op" not in tekst.casefold() and "get_artikel" not in tekst
    assert "Gebruik een iri uit een toolresultaat." in tekst and "zelf lezen kan nu niet" in tekst
    # Zonder subagent blijft de weigering zoals ze was.
    assert sjabloonnodes.na_subagent_weigering({"specialist": "centraal"}, WEIGERING) == WEIGERING


CITAAT = Citaat(tekst="De ontvanger maant de belastingschuldige schriftelijk aan.",
                vindplaats=Vindplaats(iri="urn:bwb:BWBR0004770:artikel:11:lid:1", label="Artikel 11, lid 1"))
S03_TEKST = "**Artikel 11** – De ontvanger is verplicht de belastingschuldige schriftelijk aan te manen."


def _na_rapport(**extra) -> dict:
    return {"answer": S03_TEKST, "subagenten": [{"uitkomst": "klaar"}], "rapport_citaten": [CITAAT.model_dump()], **extra}


def test_een_tekstantwoord_na_een_rapport_krijgt_de_citaten_uit_het_rapport():
    met = antwoordnodes.met_rapportcitaten(_na_rapport(), S03_TEKST)
    assert [b.soort for b in met.blokken] == ["toelichting", "citaten"] and met.blokken[1].items == [CITAAT]


@pytest.mark.parametrize("extra, tekst", [
    ({"antwoord": {"blokken": []}}, S03_TEKST),                     # een sjabloon: die heeft zijn eigen blokken
    ({"opdracht": {"doel": "x"}}, S03_TEKST),                       # een subagent zelf
    ({"rapport_citaten": []}, S03_TEKST),                           # het rapport toonde niets
    ({"subagenten": [{"uitkomst": "afgesloten"}]}, S03_TEKST),      # geen rapport: de tekst is uit code
    ({}, S03_TEKST + "\n\n> De ontvanger maant aan."),              # Lex citeerde zelf
    ({}, antwoordnodes.VRAAG_VAN_SUBAGENT),
])
def test_wanneer_de_rapportcitaten_niet_onder_het_antwoord_komen(extra, tekst):
    assert antwoordnodes.met_rapportcitaten(_na_rapport(**extra), tekst) is None


def test_de_citaten_komen_uit_de_blokken_van_het_rapport_ontdubbeld():
    from agent.subagent import citaten_van

    kind = {"antwoord": {"blokken": [{"soort": "toelichting", "tekst": "x"},
                                     {"soort": "citaten", "items": [CITAAT.model_dump(), CITAAT.model_dump()]}]}}
    assert citaten_van([kind]) == [CITAAT.model_dump()]
    assert citaten_van([kind], [CITAAT.model_dump()]) == [CITAAT.model_dump()]


# 4. E03: artikel 3:239 -------------------------------------------------------------------------------------------------

IW24_LID3 = ("Verrekening is niet mogelijk indien een vordering onder bijzondere titel is overgegaan of indien daarop een "
             "pandrecht als bedoeld in artikel 239 van Boek 3 van het Burgerlijk Wetboek is gevestigd.")


def test_een_artikel_met_boeknummer_staat_in_de_wettekst_met_het_boek_erbij():
    assert _zin_met("artikel 3:239", IW24_LID3) == IW24_LID3
    assert _zin_met("artikel 239", IW24_LID3) == IW24_LID3
    assert _zin_met("artikel 4:239", IW24_LID3) == "" and _zin_met("artikel 3:240", IW24_LID3) == ""


# 5. Jaartallen als aantal ----------------------------------------------------------------------------------------------

def test_een_jaartal_in_een_wetsnaam_is_geen_aantal_gelezen_stukken():
    assert gelezen_aantallen("Bij artikel 36 van de Invorderingswet 1990 uitspraken gelezen.", 8) == []
    assert gelezen_aantallen("De subagent las 16 uitspraken.", 8) == ["16 uitspraken gelezen (gelezen: 8)"]


# 6. De meetset ---------------------------------------------------------------------------------------------------------

def test_m01_en_m06_klikken_de_bevestiging_en_de_groepen_blijven():
    for id in ("M01", "M06"):
        assert AGENTSET[id]["kaarten"] == {"start": True} and AGENTSET[id]["verwacht"]["bevestiging"]
    groepen = [r["groep"] for r in AGENTSET.values()]
    assert {g: groepen.count(g) for g in set(groepen)} == {"enkelvoudig": 10, "een_subagent": 5, "meer_subagents": 6,
                                                            "vraag_omhoog": 4, "vervolg": 5}
