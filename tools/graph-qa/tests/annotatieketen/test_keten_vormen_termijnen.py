"""Bundel 3 van het plan lessen E2E Termijnen (L-2-1, L-2-5, L-2-6): vormen die de keten niet herkende.

De zinnen komen uit de proef op Termijnen (IW 1990 art. 9, AWR art. 13), maar elke regel is een taalvorm die de methode
noemt: een telling ('zoveel … als'), een datum uit een duur ('invorderbaar zes weken na …'), een tijdstip als waarde
('de dagtekening van …') en een benoeming ('wordt aangeduid als'). Geen regel noemt een term uit de IW; daarom staat er
bij elke positieve toets een negatieve.
"""
from __future__ import annotations

import json

import pytest

from agent.jas_pipeline.detectoren import BronTekst
from agent.jas_pipeline.detectoren.functies import FunctieDetector
from agent.jas_pipeline.detectoren.structuur import DefinitieDetector
from agent.jas_pipeline.detectoren.syntactisch import GevolgDetector
from agent.jas_pipeline.taal import SpacyProvider

LID_1 = "Een belastingaanslag is invorderbaar zes weken na de dagtekening van het aanslagbiljet."
LID_2 = ("In afwijking van het eerste lid is een navorderingsaanslag, alsmede een conserverende navorderingsaanslag "
         "invorderbaar één maand na de dagtekening van het aanslagbiljet en een naheffingsaanslag invorderbaar veertien "
         "dagen na de dagtekening van het aanslagbiljet.")
LID_5 = ("In afwijking van het eerste lid is een voorlopige aanslag in de inkomstenbelasting of in de "
         "vennootschapsbelasting en een voorlopige conserverende aanslag in de inkomstenbelasting, waarvan het "
         "aanslagbiljet een dagtekening heeft die ligt in het jaar waarover deze is vastgesteld, invorderbaar in zoveel "
         "gelijke termijnen als er na de maand, die in de dagtekening van het aanslagbiljet is vermeld, nog maanden van "
         "het jaar overblijven.")
LID_7 = ("In afwijking van het eerste lid is een voorlopige aanslag waarvan het aanslagbiljet een dagtekening heeft "
         "die ligt voor het jaar waarover deze is vastgesteld, invorderbaar in zoveel gelijke termijnen als er "
         "maanden van het jaar zijn.")
AWR_13_2 = ("Een voorlopige aanslag tot een negatief bedrag die voor of in de loop van het tijdvak wordt vastgesteld, "
            "wordt aangeduid als voorlopige teruggaaf.")


@pytest.fixture(scope="module")
def parser():
    p = SpacyProvider("nl_core_news_md")
    if p.analyseer("Een synthetische controle.").gedegradeerd:
        pytest.skip("volledige parser vereist")
    return p


def _bron(tekst, parser):
    return BronTekst.van_tekst("urn:test", tekst, analyse=parser.analyseer(tekst))


def _met(detector, tekst, parser, code):
    return [k for k in detector.detecteer(_bron(tekst, parser)).kandidaten if any(e.code == code for e in k.evidence)]


# --- L-2-1: 'zoveel … als' met elke telbare bijzin -------------------------------------------------------------------

def test_zoveel_als_zonder_overblijven(parser):
    """Lid 7: 'als er maanden van het jaar zijn' is net zo goed een telling als '… overblijven'."""
    k, = _met(FunctieDetector(), LID_7, parser, "CALCULATION_QUANTITY")
    d = json.loads(k.evidence[0].detail)
    assert d["uitkomst"]["tekst"] == "gelijke termijnen"
    assert d["invoer"]["tekst"] == "er maanden van het jaar zijn"
    assert k.span.tekst == "zoveel gelijke termijnen als er maanden van het jaar zijn"


def test_zoveel_als_met_een_bijzin_in_de_invoer(parser):
    """Lid 5: de betrekkelijke bijzin in de invoer sluit haar niet af; de parser hangt 'als' daar aan 'maand'."""
    k, = _met(FunctieDetector(), LID_5, parser, "CALCULATION_QUANTITY")
    assert json.loads(k.evidence[0].detail)["invoer"]["tekst"].endswith("nog maanden van het jaar overblijven")


@pytest.mark.parametrize("tekst", ["De inspecteur doet zoveel als mogelijk is.",
                                   "Hij betaalt zoveel als hij kan."])
def test_zoveel_als_zonder_telbare_grootheid_is_geen_aantal(parser, tekst):
    assert not _met(FunctieDetector(), tekst, parser, "CALCULATION_QUANTITY")


# --- L-2-1: een rechtsgevolg als toestand met een moment --------------------------------------------------------------

def test_invorderbaar_na_een_duur_is_ook_een_afleidingsregel(parser):
    k, = _met(GevolgDetector(), LID_1, parser, "DATE_ASSIGNMENT")
    assert k.span.tekst == "invorderbaar zes weken na de dagtekening van het aanslagbiljet"
    assert k.possible_classes == ("Afleidingsregel",)
    # Het tijdstip is de invoer, zonder het voorzetsel (meting bundel 3: de regel kreeg geen invoer).
    assert json.loads(k.evidence[0].detail)["invoer"]["tekst"] == "de dagtekening van het aanslagbiljet"


def test_de_datumregel_stopt_voor_de_nevenschikking(parser):
    """Lid 2: de tijdregel pakt beide termijnen samen; de regel loopt tot het eind van de eigen tijdsbepaling."""
    spans = [k.span.tekst for k in _met(GevolgDetector(), LID_2, parser, "DATE_ASSIGNMENT")]
    assert "invorderbaar één maand na de dagtekening van het aanslagbiljet" in spans
    assert not any("naheffingsaanslag" in s for s in spans)


def test_de_datumregel_stopt_bij_het_moment(parser):
    """IW art. 63b lid 5 (meting 20 nov 2026): de parser hangt de nabepaling onder de tijdsbepaling; de regel eindigt
    bij het moment, niet bij het eind van de zin."""
    tekst = ("Een door de ontvanger opgelegde bestuurlijke boete is invorderbaar zes weken na de dagtekening van de "
             "beschikking waarbij deze is opgelegd, met overeenkomstige toepassing van de regels die gelden voor de "
             "invordering van de belastingaanslag in verband waarmee deze is opgelegd.")
    k, = _met(GevolgDetector(), tekst, parser, "DATE_ASSIGNMENT")
    assert k.span.tekst == "invorderbaar zes weken na de dagtekening van de beschikking waarbij deze is opgelegd"


@pytest.mark.parametrize("tekst", [
    "Een belastingaanslag die een bedrag behelst is niet invorderbaar zolang het adres ontbreekt.",
    "Het invorderbare bedrag wordt binnen zes weken na de dagtekening betaald.",
    "Een belastingaanslag is invorderbaar.",
])
def test_geen_datumregel_zonder_moment_of_met_ontkenning(parser, tekst):
    assert not [k for k in _met(GevolgDetector(), tekst, parser, "DATE_ASSIGNMENT")
                if k.span.tekst.lower().startswith("invorderba")]


# --- keten-termijnpatroon (24 nov 2026): de toestand van de datumregel is een Variabele ------------------------------

@pytest.mark.parametrize("tekst", [
    LID_1,
    "Het bedrag, vermeld in een beschikking, is invorderbaar zes weken na de dagtekening van de beschikking.",
    "Een door de ontvanger opgelegde bestuurlijke boete is invorderbaar zes weken na de dagtekening van de beschikking "
    "waarbij deze is opgelegd, met overeenkomstige toepassing van de regels die gelden voor de invordering.",
])
def test_de_toestand_van_een_datumregel_is_een_variabele(parser, tekst):
    """Voorbeelden.md E03: 'invorderbaar' is een booleaanse eigenschap van de aanslag, en de uitvoer van de regel. Op
    acceptatie (run 367e895d, art. 9 lid 1) had geen detector het woord: het ontbrak, ook als de regel bleef staan."""
    k, = _met(GevolgDetector(), tekst, parser, "STATE_PROPERTY")
    assert k.span.tekst == "invorderbaar"
    assert k.possible_classes == ("Variabele en variabelewaarde",)
    regel, = _met(GevolgDetector(), tekst, parser, "DATE_ASSIGNMENT")
    uitkomst = json.loads(regel.evidence[0].detail)["uitkomst"]
    assert (uitkomst["start"], uitkomst["eind"]) == (k.span.start, k.span.eind)


@pytest.mark.parametrize("tekst", [
    "Een belastingaanslag die een bedrag behelst is niet invorderbaar zolang het adres ontbreekt.",
    "Het invorderbare bedrag wordt binnen zes weken na de dagtekening betaald.",
    "Een belastingaanslag is invorderbaar.",
    LID_7,
])
def test_geen_toestandsvariabele_zonder_datumregel(parser, tekst):
    """Alleen naast een datumregel: zonder moment, ontkend, als bijvoeglijk naamwoord of bij een telling niet."""
    assert not _met(GevolgDetector(), tekst, parser, "STATE_PROPERTY")


def test_de_toestandsvariabele_krijgt_het_subtype_variabele(parser):
    from agent.jas_pipeline.subtype import bepaal, codes_van
    k, = _met(GevolgDetector(), LID_1, parser, "STATE_PROPERTY")
    assert bepaal("Variabele en variabelewaarde", codes_van(k.evidence)) == "variabele"


# --- L-2-5: een tijdstip als waarde ----------------------------------------------------------------------------------

def test_de_dagtekening_van_iets_is_een_waarde(parser):
    ks = _met(FunctieDetector(), LID_1, parser, "TEMPORAL_VALUE")
    assert [k.span.tekst for k in ks] == ["de dagtekening van het aanslagbiljet"]
    assert set(ks[0].possible_classes) == {"Variabele en variabelewaarde", "Tijdsaanduiding"}


def test_een_tijdstip_als_waarde_zonder_nevenschikking(parser):
    spans = [k.span.tekst for k in _met(FunctieDetector(), LID_2, parser, "TEMPORAL_VALUE")]
    assert spans and all(s == "de dagtekening van het aanslagbiljet" for s in spans)


@pytest.mark.parametrize("tekst", ["Hij betaalt binnen veertien dagen.",
                                   "De datum wordt later bepaald.",
                                   "De data van de aanslagen worden bewaard."])
def test_geen_waarde_zonder_van_bepaling_of_in_het_meervoud(parser, tekst):
    assert not _met(FunctieDetector(), tekst, parser, "TEMPORAL_VALUE")


# --- L-2-6: de benoemende definitieformule ---------------------------------------------------------------------------

def test_wordt_aangeduid_als_is_een_brondefinitie(parser):
    k, = _met(DefinitieDetector(), AWR_13_2, parser, "DEFINITION_DESIGNATION")
    assert k.span.tekst == AWR_13_2
    assert k.possible_classes == ("Brondefinitie",)


def test_kan_worden_aangeduid_als_kwalificeert_en_benoemt_niet(parser):
    assert not _met(DefinitieDetector(), "Het terrein kan worden aangeduid als gevaarlijk.", parser,
                    "DEFINITION_DESIGNATION")


def test_de_benoeming_begint_bij_de_zin(parser):
    tekst = "Dit geldt voor elke aanslag. Een aanslag tot nul wordt hierna aangeduid als nulaanslag."
    k, = _met(DefinitieDetector(), tekst, parser, "DEFINITION_DESIGNATION")
    assert k.span.tekst == "Een aanslag tot nul wordt hierna aangeduid als nulaanslag."


# --- L-2-6: een lijst onder het opschrift 'Definities' (Leidraad Invordering 2008, 1.1.2) ---------------------------
# De divisie heeft geen tekst en geen aanhef, alleen het opschrift; elk onderdeel '– term: omschrijving' is een eigen
# bronnode. Het opschrift bereikt de detector via de context (`keten._bronteksten`).

LEIDRAAD_10 = "negatieve voorlopige aanslag: de aanslag als bedoeld in artikel 13, eerste lid, AWR tot een negatief bedrag;"


def _onderdelen(tekst: str, context: str):
    return DefinitieDetector().detecteer(BronTekst.van_tekst("urn:bwb:BWBR0000000:id:x", tekst, context=context)).kandidaten


@pytest.mark.parametrize("kop", ["Definities", "Begripsbepalingen", "begripsbepaling", "Begrippen"])
def test_een_onderdeel_onder_een_kop_die_de_lijst_benoemt_is_een_brondefinitie(kop):
    k, = _onderdelen(LEIDRAAD_10, kop)
    assert k.possible_classes == ("Brondefinitie",)
    assert k.span.tekst == LEIDRAAD_10
    assert [(e.code, e.regel) for e in k.evidence] == [("DEFINITION_ITEM", DefinitieDetector.REGEL_KOP)]


def test_een_term_met_lidwoord_tussen_haakjes_onder_de_kop():
    k, = _onderdelen("wet (de): de wet van 30 mei 1990 op de invordering van rijksbelastingen.", "Definities")
    assert k.evidence[0].detail == "wet (de)"


@pytest.mark.parametrize("kop", ["Definitieve aanslag", "Begrippen en afkortingen", "Invordering", ""])
def test_een_andere_kop_maakt_er_geen_definitie_van(kop):
    assert not _onderdelen(LEIDRAAD_10, kop)


def test_de_aanhef_van_de_ouder_gaat_voor_de_kop():
    """Een artikel 'Begripsbepalingen' met de aanhef in zijn tekst houdt de regel van de aanhef."""
    k, = _onderdelen("a. ontvanger: de ambtenaar die belast is met de invordering;",
                     "Begripsbepalingen\nIn deze wet wordt verstaan onder:")
    assert k.evidence[0].regel == DefinitieDetector.REGEL_ONDERDEEL


def test_de_kop_in_de_eigen_tekst_telt_niet():
    """Alleen het opschrift van de ouder benoemt de lijst; een regel 'Definities' in de tekst zelf niet."""
    assert not _onderdelen("Definities\nnegatieve voorlopige aanslag: de aanslag tot een negatief bedrag;", "")


def test_de_keten_geeft_het_opschrift_van_de_ouder_als_context():
    from agent.jas_pipeline.keten import _bronteksten
    ouder = {"bron_iri": "urn:bwb:BWBR0000000:id:d", "tekst": "", "titel": "Definities"}
    lid = {"bron_iri": "urn:bwb:BWBR0000000:id:l", "tekst": "", "titel": "",
           "parent_iri": ""}
    met_aanhef = {"bron_iri": "urn:bwb:BWBR0000000:id:a", "tekst": "In deze wet wordt verstaan onder:",
                  "titel": "Begripsbepalingen"}
    segmenten = [{"bron_iri": "urn:bwb:BWBR0000000:id:o", "tekst": LEIDRAAD_10, "bron_hash": "h",
                  "parent_iri": ouder["bron_iri"]},
                 {"bron_iri": "urn:bwb:BWBR0000000:id:p", "tekst": "a. x: y;", "bron_hash": "h",
                  "parent_iri": met_aanhef["bron_iri"]},
                 {"bron_iri": "urn:bwb:BWBR0000000:id:q", "tekst": "Tekst.", "bron_hash": "h",
                  "parent_iri": lid["bron_iri"]}]
    a, b, c = _bronteksten(segmenten, [ouder, met_aanhef, lid], "null")
    assert a.context == "Definities"
    # het opschrift staat vooraan: 'eindigt de aanhef op een dubbele punt' blijft gelijk
    assert b.context == "Begripsbepalingen\nIn deze wet wordt verstaan onder:" and b.context.rstrip().endswith(":")
    assert c.context == ""
