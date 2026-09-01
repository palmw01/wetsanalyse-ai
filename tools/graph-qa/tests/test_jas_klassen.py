"""JAS-klassen-referentie: 13 canonieke klassen, drift-guard, volledigheid."""
from __future__ import annotations

from agent.jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN, JAS_KLASSEN_VOLGORDE

# De canonieke JAS-namen + weergave-volgorde (docs/wetsanalyse/wa-table.png). Deze test is de drift-guard:
# wijzigen van een naam moet bewust gebeuren en gelijk blijven met de rest van het systeem
# (validation.JAS_KLASSEN_VOLGORDE in het api-/skill-spoor).
VERWACHT: tuple[str, ...] = (
    "Rechtssubject",
    "Rechtsobject",
    "Rechtsbetrekking",
    "Rechtsfeit",
    "Voorwaarde",
    "Afleidingsregel",
    "Variabele en variabelewaarde",
    "Parameter en parameterwaarde",
    "Operator",
    "Tijdsaanduiding",
    "Plaatsaanduiding",
    "Delegatiebevoegdheid en delegatie-invulling",
    "Brondefinitie",
)


def test_dertien_canonieke_klassen():
    assert JAS_KLASSEN_VOLGORDE == VERWACHT
    assert len(JAS_KLASSEN) == 13
    assert GELDIGE_JAS_KLASSEN == frozenset(VERWACHT)


def test_elke_klasse_volledig_geduid():
    for k in JAS_KLASSEN:
        assert k.naam and k.omschrijving and k.vraag and k.uitdrukkingswijze


def test_korte_promptvariant_is_kleiner_maar_volledig():
    """De meetknop `ANNOTATIE_PROMPT_KORT` mag inkorten, niet weglaten.

    Waarom deze test bestaat: de knop is er om te meten of de vólle brontekst in de prompt beter
    annoteert dan de verkorte referentie die er tot 1 sep 2026 stond. Die vergelijking is alleen
    geldig als de korte variant (a) fors kleiner is, en (b) nog steeds alle dertien klassen met hun
    exacte naam noemt — anders meet je "klasse ontbreekt" in plaats van "beschrijving is korter".
    """
    from agent.annotatie_prompt import _klassen_referentie

    vol, kort = _klassen_referentie(kort=False), _klassen_referentie(kort=True)
    assert len(kort) < len(vol) / 2, "de korte variant scheelt te weinig om iets te meten"
    for k in JAS_KLASSEN:
        assert k.naam in kort, f"{k.naam} ontbreekt in de korte variant"
    # Elke klasse houdt alle drie de rubrieken; alleen de tekst erachter is ingekort.
    assert kort.count("omschrijving:") == len(JAS_KLASSEN)
    assert kort.count("herken-vraag:") == len(JAS_KLASSEN)
    assert kort.count("uitdrukkingswijze:") == len(JAS_KLASSEN)
