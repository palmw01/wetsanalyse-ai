"""`jas_klasse_opvragen` geeft naast de bronvelden de toelichting uit de skill (plan methodes scheiden, deel 2, G2).

Wie twijfelt tussen twee klassen, heeft de afbakening nodig, niet alleen de omschrijving. De toelichting komt uit de
klassenreferentie van de skill (`agent/jas_toelichting.py`, gegenereerd), apart van `agent/jas_klassen.py`: de
annotatieketen krijgt dezelfde klasseduiding als voorheen.
"""
from __future__ import annotations

import json
import re

import pytest

from agent.jas_klassen import GELDIGE_JAS_KLASSEN, JAS_KLASSEN, methode_versie
from agent.jas_toelichting import TOELICHTING
from agent.tools.jas_tools import _jas_klasse_opvragen

#: Het resultaat staat in de context van de duidingsrol; het blijft klein.
MAX_TEKENS = 4_000


@pytest.mark.parametrize("klasse", sorted(GELDIGE_JAS_KLASSEN))
def test_elke_klasse_geeft_bronvelden_samenhang_en_afbakening(klasse):
    uit = json.loads(_jas_klasse_opvragen(klasse))
    assert {"omschrijving", "vraag", "uitdrukkingswijze", "samenhang", "afbakening"} <= set(uit)
    assert isinstance(uit["afbakening"], list) and uit["afbakening"]
    assert len(json.dumps(uit, ensure_ascii=False)) <= MAX_TEKENS


def test_de_bronvelden_zijn_die_van_de_annotatieketen():
    for k in JAS_KLASSEN:
        uit = json.loads(_jas_klasse_opvragen(k.naam))
        assert (uit["omschrijving"], uit["vraag"], uit["uitdrukkingswijze"]) == (k.omschrijving, k.vraag, k.uitdrukkingswijze)


def test_rechtsbetrekking_en_rechtsfeit_noemen_hun_subklassen():
    assert "Immuniteit" in json.loads(_jas_klasse_opvragen("Rechtsbetrekking"))["subklassen"]
    assert "Rechtshandeling" in json.loads(_jas_klasse_opvragen("Rechtsfeit"))["subklassen"]


def test_de_afbakening_noemt_de_verwarbare_klasse_vooraan():
    for naam, velden in TOELICHTING.items():
        for regel in velden["afbakening"]:
            assert any(regel.startswith(k) for k in GELDIGE_JAS_KLASSEN), (naam, regel[:60])


def test_een_onbekende_klasse_is_een_fout():
    assert "fout" in json.loads(_jas_klasse_opvragen("Rechtsgevolg"))


def test_de_toelichting_raakt_de_methodeversie_van_de_keten_niet():
    """`methode_versie()` gaat mee in de run van elke annotatie; de toelichting staat er los van."""
    import agent.jas_klassen as jk
    assert "TOELICHTING" not in vars(jk) and len(methode_versie()) == 12


# --- G2b (meting G2, 14 nov 2026) --------------------------------------------------------------------

#: Een verwijzing naar tekst die niet in het toolresultaat staat: het model kan haar niet nalezen.
_VERWIJZING = re.compile(r"hierboven|hieronder|\bzie §|\bzie daar\b|\]\(")


@pytest.mark.parametrize("klasse", sorted(GELDIGE_JAS_KLASSEN))
def test_de_toelichting_is_zelfstandig_leesbaar(klasse):
    for veld, waarde in TOELICHTING[klasse].items():
        for regel in waarde if isinstance(waarde, list) else [waarde]:
            assert not _VERWIJZING.search(regel), (klasse, veld, regel[:80])


def test_parameter_tegenover_variabele_noemt_de_toets_en_de_verbijzondering():
    """Meting G2, k-awb67: het model verwierp de parameter met de toets van een variabele ("verschilt niet per
    rechtssubject"). De afbakening zegt nu dat gelijk voor allen juist een parameter is, en hoe de tijdsaanduiding hem
    verbijzondert."""
    regels = TOELICHTING["Parameter en parameterwaarde"]["afbakening"]
    variabele = next(r for r in regels if r.startswith("Variabele"))
    assert "gelijk voor alle" in variabele and "pleit dus vóór een parameter" in variabele and "H2:89" in variabele
    tijd = next(r for r in regels if r.startswith("Tijdsaanduiding"))
    assert "verbijzondert" in tijd and "H2:107" in tijd
    assert "verbijzondert" in " ".join(TOELICHTING["Tijdsaanduiding"]["afbakening"])


@pytest.mark.parametrize("gevraagd,klasse", [
    ("Parameterwaarde", "Parameter en parameterwaarde"),
    ("parameter", "Parameter en parameterwaarde"),
    ("constante", "Parameter en parameterwaarde"),
    ("Variabele", "Variabele en variabelewaarde"),
    ("variabelewaarde", "Variabele en variabelewaarde"),
    ("Delegatie-invulling", "Delegatiebevoegdheid en delegatie-invulling"),
    ("rechtssubject", "Rechtssubject"),
    ("  TIJDSAANDUIDING ", "Tijdsaanduiding"),
    ("begripsbepaling", "Brondefinitie"),
])
def test_een_gangbare_naam_vindt_de_klasse(gevraagd, klasse):
    uit = json.loads(_jas_klasse_opvragen(gevraagd))
    assert uit["naam"] == klasse and uit["gevraagd"] == gevraagd.strip()


def test_de_exacte_naam_noemt_geen_gevraagd():
    assert "gevraagd" not in json.loads(_jas_klasse_opvragen("Rechtsfeit"))


def test_een_bijna_goede_naam_krijgt_de_naam_die_wel_bestaat():
    fout = json.loads(_jas_klasse_opvragen("Parameterwaardes"))["fout"]
    assert "Bedoel je 'Parameter en parameterwaarde'?" in fout


def test_elk_synoniem_wijst_een_bestaande_klasse_aan():
    from agent.tools.jas_tools import SYNONIEMEN
    assert set(SYNONIEMEN.values()) <= GELDIGE_JAS_KLASSEN
