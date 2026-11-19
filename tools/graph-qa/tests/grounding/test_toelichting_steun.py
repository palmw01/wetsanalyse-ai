"""De toelichting van een sjabloon van de graaf rust op wat gelezen is (acceptatie 19 nov 2026, "derdenbeslag").

Het antwoord zei "Geen wettelijke definitie", toonde het vastgelegde begrip en liet een toelichting volgen met een bank,
een werkgever die loon uitbetaalt en executoriaal beslag. De gelezen Leidraad-passage (14.4.1) en het begrip zeiden daar
niets over, en de controle zag het niet: ze toetste alleen getallen, namen en citaten.
"""
from __future__ import annotations

import json

from agent.gelezen import gelezen_tekst, toelichting_zonder_steun
from agent.grounding import check_grounding
from agent.nodes.antwoord import _toelichting_van_lex

LEIDRAAD = (
    "In artikel 475 Rv en volgende is de mogelijkheid gegeven ten laste van de belastingschuldige beslag te leggen onder "
    "een derde. Als blijkt dat – na het afleggen van de buitengerechtelijke verklaring – de derde geen gelden of zaken onder "
    "zich heeft, dan blijkt het beslag nooit te hebben gelegen. De ontvanger stelt de derde hiervan op de hoogte. Een "
    "belastingaanslag kan ook worden verhaald door het leggen van derdenbeslag op een vordering die formeel aan een ander "
    "dan de belastingschuldige toebehoort, dan wel op naam van die ander – bijvoorbeeld door een bank – wordt "
    "geadministreerd.")
BEGRIP = ("Beslag dat een schuldeiser van de belastingschuldige legt op een vordering van de belastingschuldige op een derde, "
          "zoals een voorlopige teruggaaf.")
#: De zoektreffers die de beurt ook vond: de woorden van de toelichting staan er deels in, maar gevonden is niet gelezen.
TREFFER = "Samenloop derdenbeslag en ketenaansprakelijkheid. De werkgever betaalt het loon uit aan de werknemer."
TRACE = [
    ("zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 0, "term": "derdenbeslag", "resultaten": []})),
    ("search_wetgeving", json.dumps({"status": "ok", "resultaten": [{"node": "urn:bwb:BWBR0024096:id:x", "tekst": TREFFER}]})),
    ("get_bepaling", json.dumps({"status": "ok", "resultaten": [], "bepaling": {"iri": "urn:bwb:BWBR0024096:id:y", "tekst": LEIDRAAD}})),
    ("search_begrippen", json.dumps({"status": "ok", "resultaten": [{"id": "b1", "naam": "derdenbeslag", "definitie": BEGRIP}]})),
]
VRAAG = "wat betekend het begrip derdenbeslag"
UIT_EIGEN_KENNIS = (
    "Derdenbeslag is een vorm van executoriaal beslag waarbij de schuldeiser (in het invorderingsrecht: de ontvanger) "
    "beslag legt niet bij de schuldenaar zelf, maar bij een derde die iets aan de schuldenaar verschuldigd is of voor hem "
    "onder zich heeft — zoals een bank die een rekening aanhoudt of een werkgever die loon uitbetaalt.")


def test_een_zin_uit_eigen_kennis_is_een_bewering():
    uit = toelichting_zonder_steun(UIT_EIGEN_KENNIS, gelezen_tekst(TRACE), VRAAG)
    assert len(uit) == 1 and uit[0].startswith("toelichting zonder steun in wat gelezen is: “Derdenbeslag is een vorm")


def test_een_zoektreffer_is_geen_steun():
    gelezen = gelezen_tekst(TRACE).casefold()
    assert "werkgever" not in gelezen and "buitengerechtelijke" in gelezen and "teruggaaf" in gelezen


def test_wat_de_gelezen_tekst_zegt_in_eigen_woorden_is_geen_bewering():
    tekst = (
        "De Leidraad beschrijft derdenbeslag als beslag ten laste van de belastingschuldige onder een derde, op grond van "
        "artikel 475 Rv. Heeft de derde na zijn buitengerechtelijke verklaring geen gelden of zaken onder zich, dan heeft "
        "het beslag nooit gelegen. Het vastgelegde begrip gaat over een schuldeiser die beslag legt op een vordering van de "
        "belastingschuldige, zoals een voorlopige teruggaaf.")
    assert toelichting_zonder_steun(tekst, gelezen_tekst(TRACE), VRAAG) == []


def test_een_naam_of_een_korte_zin_telt_niet():
    # Het Wetboek van Burgerlijke Rechtsvordering heet in de bron "Rv"; een naam heeft een eigen toets.
    tekst = ("De wettelijke grondslag staat in artikel 475 van het Wetboek van Burgerlijke Rechtsvordering en verder. "
             "De Leidraad Invordering 2008 werkt dit uit.")
    assert toelichting_zonder_steun(tekst, gelezen_tekst(TRACE), VRAAG) == []


def test_check_grounding_zet_het_in_de_beweringen():
    report = check_grounding(UIT_EIGEN_KENNIS, TRACE, vraag=VRAAG, toelichting=UIT_EIGEN_KENNIS)
    assert any(b.startswith("toelichting zonder steun") for b in report.beweringen) and report.niveau == "onbepaald"
    # Zonder `toelichting` (vrije tekst, of een sjabloon met eigen toetsen) geldt de toets niet.
    assert not any(b.startswith("toelichting zonder steun") for b in check_grounding(UIT_EIGEN_KENNIS, TRACE, vraag=VRAAG).beweringen)


def test_alleen_de_toelichting_van_lex_in_een_sjabloon_van_de_graaf():
    blokken = [{"soort": "leemte", "door": "bron", "tekst": "Geen wettelijke definitie."},
               {"soort": "toelichting", "door": "lex", "kop": "Toelichting van Lex", "tekst": "Uitleg."}]
    assert _toelichting_van_lex({"antwoord": {"sjabloon": "begrip", "blokken": blokken}}) == "Uitleg."
    assert _toelichting_van_lex({"antwoord": {"sjabloon": "bepaling", "blokken": blokken}}) == "Uitleg."
    assert _toelichting_van_lex({"antwoord": {"sjabloon": "duiding", "blokken": blokken}}) is None
    assert _toelichting_van_lex({"antwoord": {"sjabloon": "begrip", "blokken": blokken[:1]}}) is None
    assert _toelichting_van_lex({"answer": "vrije tekst"}) is None
