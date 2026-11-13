"""Twee toetsen op de naam van een begrip (plan methodes scheiden, deel 2, G3).

Uit de richtlijnen van de methode (skill wetsanalyse, `references/begrippen.md`): geen ontkenning in de naam, zo min
mogelijk afkortingen. Een aandachtspunt, nooit een weigering, en niet bij een letterlijke definitie: dan is de naam de
term van de wet.
"""
from __future__ import annotations

import pytest

from agent.begrippen_pipeline import toetsen
from agent.begrippen_pipeline.model import Fragment, Herkomst, Kaart, fragment_id


def _kaart(naam: str, herkomst: Herkomst | None = Herkomst.GEFORMULEERD) -> Kaart:
    velden = {"groep_id": "G1", "naam": naam}
    if herkomst is Herkomst.LETTERLIJK:
        velden |= {"definitie": "een omschrijving", "herkomst": herkomst, "definitie_bron_iri": "urn:bwb:x"}
    elif herkomst is not None:
        velden |= {"definitie": "een omschrijving", "herkomst": herkomst,
                   "fragmenten": (Fragment(id=fragment_id("urn:bwb:x", 0, 3), bron_iri="urn:bwb:x", start=0, eind=3, tekst="een"),)}
    return Kaart(**velden)


@pytest.mark.parametrize("naam", ["niet-ingezetene", "aanslag zonder bezwaar", "geen aangifte gedaan",
                                  "Niet tijdig betaalde aanslag"])
def test_een_ontkenning_in_de_naam_is_een_aandachtspunt(naam):
    assert "NAAM_MET_ONTKENNING" in toetsen.signalen(_kaart(naam), [])


@pytest.mark.parametrize("naam", ["WOZ-waarde", "aanslag IB", "bedrag art. 9", "uitstel o.g.v. lid 1"])
def test_een_afkorting_in_de_naam_is_een_aandachtspunt(naam):
    assert "NAAM_MET_AFKORTING" in toetsen.signalen(_kaart(naam), [])


@pytest.mark.parametrize("naam", ["belastingaanslag", "uitstel van betaling", "onroerende zaak", "nietigheid",
                                  "geenszins vaststaande schuld", "aanslag 2025", "Belastingdienst"])
def test_een_gewone_naam_geeft_geen_signaal(naam):
    s = toetsen.signalen(_kaart(naam), [])
    assert "NAAM_MET_ONTKENNING" not in s and "NAAM_MET_AFKORTING" not in s


def test_niet_bij_een_letterlijke_definitie_want_dan_is_de_naam_de_term_van_de_wet():
    s = toetsen.signalen(_kaart("WOZ-waarde van een niet-woning", Herkomst.LETTERLIJK), [])
    assert "NAAM_MET_ONTKENNING" not in s and "NAAM_MET_AFKORTING" not in s


def test_ook_zonder_definitie_telt_de_naam():
    assert "NAAM_MET_AFKORTING" in toetsen.signalen(_kaart("AWR-termijn", None), [])


def test_elke_code_heeft_een_tekst():
    assert {"NAAM_MET_ONTKENNING", "NAAM_MET_AFKORTING"} <= set(toetsen.TEKST)
