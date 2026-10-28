"""De B1-toetsen op een uitleg (spoor I2): elke toets met en zonder treffer, met en zonder parser."""
from __future__ import annotations

import pytest

from agent.begrippen_pipeline import begrip_b1, kaartacties as ka
from agent.jas_pipeline.taal.provider import NullProvider

GEWOON = "Een termijn is de tijd die je hebt om te betalen. Je betaalt binnen zes weken."
DEFINITIE = "Het tijdvak waarbinnen de belastingschuldige de belastingaanslag moet betalen."


@pytest.fixture(params=["spacy", "null"])
def provider(request):
    return begrip_b1.standaard_provider() if request.param == "spacy" else NullProvider()


def test_een_eenvoudige_uitleg_heeft_geen_aandachtspunten(provider):
    assert begrip_b1.toets(GEWOON, DEFINITIE, provider) == []


@pytest.mark.parametrize("zin", ["De aanslag wordt door de inspecteur vastgesteld.",
                                 "De belasting werd binnen de termijn betaald."])
def test_lijdende_vorm(provider, zin):
    assert "B1_LIJDENDE_VORM" in begrip_b1.toets(zin, "", provider)


def test_actief_is_geen_lijdende_vorm(provider):
    assert "B1_LIJDENDE_VORM" not in begrip_b1.toets("De inspecteur stelt de aanslag vast.", "", provider)


def test_lange_zin_en_te_veel_zinnen(provider):
    lang = ("Als je de aanslag niet op tijd betaalt omdat je het geld nog niet hebt of de brief niet kreeg "
            "stuurt de ontvanger je eerst een aanmaning.")
    assert "B1_LANGE_ZIN" in begrip_b1.toets(lang, "", provider)
    zes = " ".join(f"Dit is zin {i}." for i in range(6))
    codes = begrip_b1.toets(zes, "", provider)
    assert "B1_TE_LANG" in codes and "B1_LANGE_ZIN" not in codes


def test_moeilijk_woord_met_vervanger(provider):
    assert begrip_b1.moeilijke_woorden("Indien je reeds betaalde, ten aanzien van de aanslag.") == [
        ("indien", "als"), ("reeds", "al"), ("ten aanzien van", "over")]
    assert "B1_MOEILIJK_WOORD" in begrip_b1.toets("Indien je niet betaalt, volgt een aanmaning.", "", provider)


def test_vakterm_uit_de_definitie_moet_uitgelegd(provider):
    kaal = "De belastingschuldige betaalt binnen de termijn."
    assert "B1_VAKTERM_ONVERKLAARD" in begrip_b1.toets(kaal, DEFINITIE, provider)
    uitgelegd = "De belastingschuldige betaalt binnen de termijn. Een belastingschuldige is wie de belasting moet betalen."
    assert "B1_VAKTERM_ONVERKLAARD" not in begrip_b1.toets(uitgelegd, DEFINITIE, provider)


def test_herhaalde_definitie(provider):
    assert "B1_HERHAALT_DEFINITIE" in begrip_b1.toets(DEFINITIE, DEFINITIE, provider)
    assert "B1_HERHAALT_DEFINITIE" not in begrip_b1.toets(GEWOON, DEFINITIE, provider)


def test_elke_code_heeft_een_tekst_bij_de_kaartacties():
    assert set(begrip_b1.CODES) <= set(ka.TEKST)


def test_de_uitleg_actie_geeft_een_geel_voorstel_met_de_toetsen():
    k = ka.Kant(id="b1", inhoud={"naam": "termijn", "definitie": DEFINITIE}, leden=())
    uit = ka.valideer_uitleg(k, [], {"uitleg": "Indien je niet betaalt, wordt er een aanmaning gestuurd.",
                                     "fragmenten": [""], "motivatie": "Kort."}, NullProvider())
    [v] = uit.voorstellen
    assert (v["veld"], v["aandacht"], v["fragmenten"]) == ("uitleg", "geel", [])
    assert v["aandachtspunten"][:1] == ["DOOR_LEX_UITLEG"]
    assert {"B1_MOEILIJK_WOORD", "B1_LIJDENDE_VORM"} <= set(v["aandachtspunten"])


def test_geen_uitleg_zonder_definitie():
    k = ka.Kant(id="b1", inhoud={"naam": "termijn"}, leden=())
    assert ka.uitleg(None, "m", None, k).voorstellen == []        # geen model, geen manifest nodig
