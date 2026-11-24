"""Klasse, waardebereik en eigenaar op het begrip en de regel (plan lessen Termijnen-bibliotheek, V2–V4; besluit gebruiker
24 nov 2026: P15 bijgesteld). De klasse rekent de api uit de passages, de analist kan afwijken met een reden; het
waardebereik is optioneel en gestructureerd; een waarde in een voorbeeld die er niet in past, is een signaal."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.begrip_contracts import BegripInhoud, KlasseKeuze, Waardebereik
from app.regel_store import past_in
from gedeelde_bron import ART, _bron, _nieuw, client, database, graaf  # noqa: F401
from test_regels import _annoteer, _begrip, _inhoud, _url


def test_een_waardebereik_heeft_een_vorm():
    assert Waardebereik(soort="bedrag", eenheid="euro", decimalen=0, minimum="0").decimalen == 0
    with pytest.raises(ValidationError):
        Waardebereik(soort="opsomming")                       # een opsomming noemt haar waarden
    with pytest.raises(ValidationError):
        Waardebereik(soort="datum", waarden=["1-1-2026"])     # waarden alleen bij een opsomming
    with pytest.raises(ValidationError):
        Waardebereik(soort="opsomming", waarden=["a", "A"])
    with pytest.raises(ValidationError):
        Waardebereik(soort="kleur")


def test_een_klassekeuze_is_een_jas_klasse_met_een_reden():
    assert KlasseKeuze(klasse="Variabele en variabelewaarde", reden="ja/nee-kenmerk").reden == "ja/nee-kenmerk"
    with pytest.raises(ValidationError):
        KlasseKeuze(klasse="Kenmerk", reden="x")
    with pytest.raises(ValidationError):
        KlasseKeuze(klasse="Rechtsobject", reden="  ")
    assert BegripInhoud(naam="x").waardebereik is None


@pytest.mark.parametrize("waarde, bereik, past", [
    ("WAAR", {"soort": "ja_nee"}, True),
    ("misschien", {"soort": "ja_nee"}, False),
    ("15-03-2026", {"soort": "datum"}, True),
    ("2026-03-15", {"soort": "datum"}, True),
    ("31-02-2026", {"soort": "datum"}, False),
    ("1200", {"soort": "bedrag", "decimalen": 0}, True),
    ("€ 1.200,50", {"soort": "bedrag", "decimalen": 0}, False),
    ("3,5", {"soort": "aantal"}, False),
    ("April", {"soort": "opsomming", "waarden": ["april", "mei"]}, True),
    ("6 weken", {"soort": "duur"}, None),
])
def test_past_een_waarde_in_het_bereik(waarde, bereik, past):
    assert past_in(waarde, bereik) is past


async def test_de_klasse_komt_uit_de_passages_en_de_keuze_wint(client):
    ids = await _annoteer()
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    b = await _begrip(client, wg, "dagtekening", ids["var"])
    assert b["klasse"] == {"klasse": "Variabele en variabelewaarde", "afgeleid": "Variabele en variabelewaarde",
                           "uit_passages": {"Variabele en variabelewaarde": 1}, "gekozen": "", "reden": ""}
    url = f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}"
    r = await client.patch(url, json={"verwachte_revisie": b["revisie"], "inhoud": {
        "klasse_keuze": {"klasse": "Parameter en parameterwaarde", "reden": "De waarde verandert per tijdvak."},
        "waardebereik": {"soort": "duur", "eenheid": "weken"}, "eigenaar": "Inning"}})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["klasse"]["klasse"] == "Parameter en parameterwaarde"
    assert b["klasse"]["afgeleid"] == "Variabele en variabelewaarde"
    assert b["inhoud"]["waardebereik"]["soort"] == "duur" and b["inhoud"]["eigenaar"] == "Inning"
    r = await client.patch(url, json={"verwachte_revisie": b["revisie"], "inhoud": {"waardebereik": {"soort": "x"}}})
    assert r.status_code == 422


async def test_een_lege_patch_op_een_oud_begrip_geeft_geen_revisie(client):
    """Leeg en afwezig zijn hetzelfde: de nieuwe velden leeg meesturen maakt geen revisie."""
    ids = await _annoteer()
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    b = await _begrip(client, wg, "dagtekening", ids["var"])
    r = await client.patch(f"/v1/werkgebieden/{wg['id']}/begrippen/{b['id']}", json={
        "verwachte_revisie": b["revisie"], "inhoud": {"eigenaar": "", "waardebereik": None, "klasse_keuze": None}})
    assert r.status_code == 200, r.text
    assert r.json()["revisie"] == b["revisie"]


async def test_een_waarde_buiten_het_bereik_is_een_signaal_en_een_regel_heeft_een_eigenaar(client):
    ids = await _annoteer()
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    begrippen = {"regel": await _begrip(client, wg, "bepalen van het termijnbedrag", ids["ar"]),
                 "uit": await _begrip(client, wg, "termijnbedrag", ids["var"]),
                 "in": await _begrip(client, wg, "aantal termijnen", ids["rs"])}
    url = f"/v1/werkgebieden/{wg['id']}/begrippen/{begrippen['in']['id']}"
    r = await client.patch(url, json={"verwachte_revisie": begrippen["in"]["revisie"],
                                      "inhoud": {"waardebereik": {"soort": "aantal", "minimum": "1"}}})
    assert r.status_code == 200, r.text
    invoer = begrippen["in"]["id"]
    regel = (await client.post(_url(wg), json={"inhoud": _inhoud(begrippen, eigenaar="Inning", voorbeelden=[
        {"invoer": "drie termijnen", "uitkomst": "x", "waarden": [{"begrip_id": invoer, "waarde": "drie"}]},
        {"invoer": "12", "uitkomst": "100", "waarden": [{"begrip_id": invoer, "waarde": "12"}]},
    ]), "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    assert regel["inhoud"]["eigenaar"] == "Inning"
    melding = [s for s in regel["signalen"] if "buiten" in s or "noemt voor" in s]
    assert melding == ['Voorbeeld 1 noemt voor aantal termijnen de waarde "drie", maar dat begrip is een aantal.']
    # Een regel zonder eigenaar bewaart het veld niet (geen nieuwe revisie bij een gelijke PATCH van een oude regel).
    regel2 = (await client.post(_url(wg), json={"inhoud": _inhoud(begrippen),
                                                 "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})).json()
    assert "eigenaar" not in regel2["inhoud"]


async def test_de_lijst_zegt_welk_begrip_een_regel_benoemt(client):
    """V11: de begrippenlijst toont een regelbegrip bij de regels; de api zegt welke dat zijn."""
    ids = await _annoteer()
    wg = (await _bron(client, await _nieuw(client), bron_iri=ART))["werkgebied"]
    begrippen = {"regel": await _begrip(client, wg, "bepalen van het termijnbedrag", ids["ar"]),
                 "uit": await _begrip(client, wg, "termijnbedrag", ids["var"]),
                 "in": await _begrip(client, wg, "aantal termijnen", ids["rs"])}
    r = await client.post(_url(wg), json={"inhoud": _inhoud(begrippen),
                                          "dragers": [{"element_id": ids["ar"], "rol": "grondslag"}]})
    assert r.status_code == 201, r.text
    lijst = (await client.get(f"/v1/werkgebieden/{wg['id']}/begrippen")).json()["begrippen"]
    assert {b["inhoud"]["naam"]: b["regelbegrip"] for b in lijst} == {
        "bepalen van het termijnbedrag": True, "termijnbedrag": False, "aantal termijnen": False}
