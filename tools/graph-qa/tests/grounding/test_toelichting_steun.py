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


def test_de_logregel_noemt_de_soort_bewering_zonder_de_tekst():
    from agent.nodes.antwoord import bewering_soorten

    assert bewering_soorten(["toelichting zonder steun in wat gelezen is: “Derdenbeslag is …”",
                             "toelichting zonder steun in wat gelezen is: “Een bank …”", "samenvatting van kst-1-2 (x)"]) == {
        "toelichting zonder steun in wat gelezen is": 2, "samenvatting van kst-1-2": 1}


# --- meting 2 na #1756: bij een begrip met een definitie of een bepaling is de steuntoets een signaal ---------------

INLENER_LID_1 = (
    "Ingeval een werknemer met instandhouding van de dienstbetrekking tot zijn inhoudingsplichtige, de uitlener, door deze "
    "ter beschikking is gesteld aan een derde, de inlener, om onder diens toezicht of leiding werkzaam te zijn, is de "
    "inlener hoofdelijk aansprakelijk voor de loonbelasting welke de uitlener verschuldigd is in verband met het verrichten "
    "van die werkzaamheden door die werknemer alsmede voor de omzetbelasting welke de uitlener, dan wel – in geval "
    "doorlening plaatsvindt – de in het tweede lid bedoelde doorlener verschuldigd is in verband met dat ter beschikking "
    "stellen.")
INLENER_LID_2 = (
    "Onder inlener wordt mede verstaan: de doorlener, zijnde degene aan wie een werknemer ter beschikking is gesteld en die "
    "deze werknemer vervolgens ter beschikking stelt aan een derde om onder diens toezicht of leiding werkzaam te zijn; de "
    "in onderdeel a bedoelde derde, aan wie door een doorlener een werknemer ter beschikking is gesteld om onder toezicht "
    "of leiding van die derde werkzaam te zijn.")
INLENER_ZIN = ("In lid 2 worden de doorlener en de uiteindelijke opdrachtgever bij doorlening ook als inlener aangemerkt, "
               "zodat de hoofdelijke aansprakelijkheid in de hele inleenketen geldt.")
VERHAAL_DEFINITIE = ("verhaalsconstructie: handeling of samenstel van handelingen die, onderscheidenlijk dat, in "
                     "overwegende mate is verricht met als doel om de ontvanger te benadelen in zijn verhaalsmogelijkheden.")
VERHAAL_TOELICHTING = ("De definitie staat in artikel 33a, lid 3, onderdeel g, van de Invorderingswet 1990. Het gaat niet "
                       "om elke transactie die dat effect heeft, maar om een transactie waarvoor dat doel de voornaamste "
                       "beweegreden was.")


def test_verbindingswoorden_zijn_geen_eigen_woorden():
    """Inlener: "zodat" en "hele" telden mee, en een inhoudelijk juiste zin viel af op 4 van 10."""
    assert toelichting_zonder_steun(INLENER_ZIN, INLENER_LID_1 + INLENER_LID_2, "wat betekent het begrip inlener") == []


def test_de_melding_toont_de_zin_zoals_lex_hem_schreef():
    zin = ("Volgens artikel 34, lid 2, is het een vorm van executoriaal beslag bij een werkgever die loon uitbetaalt "
           "aan een werknemer, of bij een bank.")
    uit = toelichting_zonder_steun(zin, gelezen_tekst(TRACE), VRAAG)
    assert uit == [f"toelichting zonder steun in wat gelezen is: “{zin[:90].rsplit(' ', 1)[0]} …”"]
    assert "artikel 34, lid 2" in uit[0]


def _verify(monkeypatch, antwoord: dict, trace: list, vraag: str) -> dict:
    from types import SimpleNamespace

    from agent.nodes import antwoord as antwoordnodes
    from fakes import FakeGraph, FakeLLM, make_settings

    monkeypatch.setattr(antwoordnodes, "get_stream_writer", lambda: (lambda _e: None))
    b = SimpleNamespace(llm=FakeLLM([]), settings=make_settings(grounding_correct=True), graph=FakeGraph(result=""))
    tekst = next(x["tekst"] for x in antwoord["blokken"] if x["soort"] == "toelichting")
    return antwoordnodes.verify_node(b, {"answer": tekst, "antwoord": antwoord, "question": vraag, "messages": [],
                                         "source_trace": trace, "run_id": "r", "specialist": "centraal"})


def _toelichting(tekst: str) -> dict:
    return {"soort": "toelichting", "door": "lex", "kop": "Toelichting van Lex", "tekst": tekst}


def test_bij_een_wettelijke_definitie_geen_correctieronde_maar_een_signaal(monkeypatch):
    """Verhaalsconstructie: een juiste parafrase van "in overwegende mate verricht met als doel" kreeg een correctieronde."""
    node = "urn:bwb:BWBR0004770:artikel:33a:lid:3:o:g"
    vp = {"iri": node, "label": "Artikel 33a, lid 3, onderdeel g", "jci": "", "regeling": "Invorderingswet 1990"}
    trace = [("zoek_definitie", json.dumps({"status": "ok", "volledig": True, "aantal": 1, "term": "verhaalsconstructie",
                                            "resultaten": [{"node": node, "begrip": "verhaalsconstructie", "tekst": VERHAAL_DEFINITIE,
                                                           "citeertitel": "Invorderingswet 1990"}]}))]
    antwoord = {"sjabloon": "begrip", "versie": 1, "doelen": [vp], "blokken": [
        {"soort": "definities", "door": "bron", "items": [{"term": "verhaalsconstructie", "tekst": VERHAAL_DEFINITIE, "vindplaats": vp}]},
        _toelichting(VERHAAL_TOELICHTING)]}
    uit = _verify(monkeypatch, antwoord, trace, "wat betekent het begrip verhaalsconstructie")
    assert uit["grounded"] is True, "geen correctieronde"
    assert any(x.startswith("toelichting zonder steun") for x in uit["onbevestigd"]), "wel zichtbaar als signaal"


def test_bij_een_begrip_zonder_definitie_blijft_de_correctieronde(monkeypatch):
    """Derdenbeslag: het bronblok `wettekst` toont een bepaling die de term gebruikt, geen definitie."""
    vp = {"iri": "urn:bwb:BWBR0024096:id:y", "label": "artikel 14.4.1", "jci": "", "regeling": "Leidraad Invordering 2008"}
    antwoord = {"sjabloon": "begrip", "versie": 1, "doelen": [], "blokken": [
        {"soort": "leemte", "door": "bron", "tekst": "Geen wettelijke definitie in de graaf bij de term “derdenbeslag”."},
        {"soort": "wettekst", "door": "bron", "items": [{"tekst": LEIDRAAD, "vindplaats": vp}]},
        _toelichting(UIT_EIGEN_KENNIS)]}
    uit = _verify(monkeypatch, antwoord, TRACE, VRAAG)
    assert uit["grounded"] is False and any(x.startswith("toelichting zonder steun") for x in uit["beweringen"])

