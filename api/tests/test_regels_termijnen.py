"""De ontwikkelset van ADR-018 (R1 in het bouwplan): het 3b-resultaat van werkgebied Termijnen moet in het regelobject
passen, zonder vrije tekst voor skelet, parameters of keuzes. De regels komen uit het werk van het team op acceptatie
(`docs/architectuur/afleidingsregels-termijnen-team.md`), bijgesteld naar de methode: R8 is een beslisregel (M-3b-0).

De begrip-id's zijn de eerste tekens uit dat document. Waar het document nog geen begrip noemt (het regelbegrip van R8,
het operatorbegrip "gedeeld door" op "gelijke termijnen"), staat een id met `nog-` ervoor: dat begrip moet nog gemaakt
worden, op zijn formulering.
"""
from __future__ import annotations

import pytest

from app.regel_contracts import RegelInhoud
from app.regeltekst import genoemde_begrippen, regeltekst
from app.regel_store import keten

NAMEN = {
    "f87474ca": "bepalen van het aantal termijnen", "de1bae54": "aantal termijnen", "0337495b": "jaar",
    "11c714db": "dagtekening van het aanslagbiljet", "c25b97af": "bedrag van de belastingaanslag",
    "6bce8f07": "bepalen van de vervaldag bij betaling ineens", "08ffc11c": "vervaldag",
    "855cd256": "wettelijke betalingstermijn", "a9afb082": "bepalen van de vervaldag een maand na de dagtekening",
    "e48826ff": "betalingstermijn", "225d18a3": "bepalen van de vervaldagen van de termijnen",
    "f0a7053f": "laatste dag van de kalendermaand", "27426263": "bepalen van het termijnbedrag",
    "cbc694db": "termijnbedrag", "nog-gedeeld-door": "gedeeld door", "d23d063b": "bepalen van de wijze van uitbetaling",
    "ef13d661": "wijze van uitbetaling", "ca0b687b": "ten hoogste", "82165e28": "drempel voor uitbetaling in één keer",
    "420c5e40": "derdenbeslag", "ef9a1c46": "bepalen van het tijdstip van verrekening",
    "6334736f": "tijdstip van verrekening",
    "nog-r8": "bepalen van de bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn",
    "fb9f3866": "bevoegdheid tot verrekening vóór het verstrijken van de betalingstermijn",
}


def b(i: str) -> dict:
    return {"soort": "begrip", "begrip_id": i}


def op(i: str) -> dict:
    return {"soort": "operator", "begrip_id": i}


def t(tekst: str) -> dict:
    return {"soort": "tekst", "tekst": tekst}


def alle(*delen) -> dict:
    return {"verband": "alle", "delen": [d if isinstance(d, dict) else {"tekst": d} for d in delen]}


TERMIJNEN = {
    "R1": {"soort": "rekenregel", "regelbegrip_id": "f87474ca", "uitvoer_begrip_id": "de1bae54",
           "invoer": [{"begrip_id": "0337495b"}, {"begrip_id": "11c714db"}, {"begrip_id": "c25b97af"}],
           "gevallen": [
               {"label": "lid 5", "voorwaarden": alle(
                   "de aanslag is een voorlopige aanslag in de inkomstenbelasting of de vennootschapsbelasting, een "
                   "voorlopige conserverende aanslag, of via art. 72 Mbw een voorlopige aanslag winstaandeel (lezing C)",
                   "de dagtekening ligt in het jaar", "het bedrag van de belastingaanslag is niet negatief"),
                "uitkomst": [t("het aantal maanden van het"), b("0337495b"), t("dat overblijft na de maand van de"),
                             b("11c714db")]},
               {"label": "lid 6", "voorwaarden": alle("een aanslag als bedoeld in lid 5 die een uit te betalen bedrag "
                                                      "behelst", "de dagtekening ligt in het jaar"),
                "uitkomst": [t("het aantal maanden van het"), b("0337495b"),
                             t("dat overblijft, met inbegrip van de maand van de"), b("11c714db")]},
               {"label": "lid 7", "voorwaarden": alle("de dagtekening ligt vóór het jaar"),
                "uitkomst": [t("het aantal maanden van het"), b("0337495b")]}]},
    "R2": {"soort": "rekenregel", "regelbegrip_id": "6bce8f07", "uitvoer_begrip_id": "08ffc11c",
           "invoer": [{"begrip_id": "11c714db"}, {"begrip_id": "855cd256", "rol": "parameter"}],
           "gevallen": [{"voorwaarden": {"verband": "een_van", "delen": [
               {"tekst": "de aanslag is niet in termijnen invorderbaar"},
               {"tekst": "de termijnregeling leidt niet tot meer dan één termijn"}]},
               "uitkomst": [t("het tijdstip dat de"), b("855cd256"), t("na de"), b("11c714db"), t("ligt")]}]},
    "R3": {"soort": "rekenregel", "regelbegrip_id": "a9afb082", "uitvoer_begrip_id": "08ffc11c", "brontype": "beleid",
           "invoer": [{"begrip_id": "11c714db"}, {"begrip_id": "e48826ff", "rol": "parameter"}],
           "gevallen": [{"voorwaarden": alle({"tekst": "de dagtekening valt op de laatste dag van de kalendermaand",
                                               "niet": True}),
                         "uitkomst": [t("het tijdstip dat de"), b("e48826ff"), t("na de"), b("11c714db"), t("ligt")]}]},
    "R4": {"soort": "rekenregel", "regelbegrip_id": "225d18a3", "uitvoer_begrip_id": "08ffc11c",
           "invoer": [{"begrip_id": "11c714db"}, {"begrip_id": "0337495b"}, {"begrip_id": "de1bae54"}],
           "gevallen": [
               {"label": "lid 5", "voorwaarden": alle("de aanslag valt onder lid 5 van R1"),
                "uitkomst": [t("eerst de vervaldag volgens R3, daarna telkens een maand later, tot het"), b("de1bae54")]},
               {"label": "lid 6", "voorwaarden": alle("de aanslag valt onder lid 6 van R1"),
                "uitkomst": [t("eerst de"), b("f0a7053f"), t("van de"), b("11c714db"),
                             t(", daarna telkens een maand later, tot het"), b("de1bae54")]},
               {"label": "lid 7", "voorwaarden": alle("de dagtekening ligt vóór het jaar"),
                "uitkomst": [t("eerst de"), b("f0a7053f"), t("van de eerste maand van het"), b("0337495b"),
                             t(", daarna telkens een maand later, tot het"), b("de1bae54")]}]},
    "R5": {"soort": "rekenregel", "regelbegrip_id": "27426263", "uitvoer_begrip_id": "cbc694db", "lidwoord": "het",
           "invoer": [{"begrip_id": "c25b97af"}, {"begrip_id": "de1bae54"}],
           "gevallen": [{"label": f"lid {n}", "voorwaarden": alle(f"de aanslag valt onder lid {n} van R1"),
                         "uitkomst": [b("c25b97af"), t("zonder teken"), op("nog-gedeeld-door"), b("de1bae54")]}
                        for n in (5, 6, 7)]},
    "R6": {"soort": "beslisregel", "regelbegrip_id": "d23d063b", "uitvoer_begrip_id": "ef13d661", "brontype": "beleid",
           "invoer": [{"begrip_id": "cbc694db"}, {"begrip_id": "82165e28", "rol": "parameter"}],
           "gevallen": [
               {"label": "in één keer", "voorrang": 1, "voorwaarden": alle(
                   "het gaat om een voorlopige teruggaaf",
                   "het termijnbedrag is ten hoogste de drempel voor uitbetaling in één keer",
                   {"tekst": "er ligt derdenbeslag", "niet": True}),
                "uitkomst": [t("in één keer")]},
               {"label": "anders", "uitkomst": [t("in maandelijkse termijnen")]}]},
    "R7": {"soort": "rekenregel", "regelbegrip_id": "ef9a1c46", "uitvoer_begrip_id": "6334736f",
           "invoer": [{"begrip_id": "08ffc11c"}, {"begrip_id": "11c714db"}],
           "gevallen": [
               {"label": "rij 2", "voorrang": 1, "voorwaarden": alle(
                   "een termijn van een voorlopige aanslag als bedoeld in art. 9 lid 6 of 7, ook een positieve aanslag "
                   "van lid 7"),
                "uitkomst": [t("de"), b("08ffc11c"), t("van die termijn")]},
               {"label": "rij 1", "uitkomst": [t("de"), b("11c714db"), t("van de aanslag waaruit het te betalen bedrag "
                                                                        "blijkt")]}]},
    "R8": {"soort": "beslisregel", "regelbegrip_id": "nog-r8", "uitvoer_begrip_id": "fb9f3866",
           "gevallen": [{"voorwaarden": alle("het gaat om dezelfde belasting (winstaandeel met winstaandeel, lezing C)",
                                             "de aanslag is een aanslag als bedoeld in art. 9 lid 5, ook lid 6",
                                             "het tijdvak is het jaar waarover de aanslag is vastgesteld"),
                         "uitkomst": [t("van toepassing")]}]},
}


@pytest.mark.parametrize("naam", sorted(TERMIJNEN))
def test_elke_regel_van_termijnen_past_zonder_vrije_tekst(naam):
    inhoud = RegelInhoud.model_validate(TERMIJNEN[naam]).model_dump(mode="json")
    assert set(genoemde_begrippen(inhoud)) <= set(NAMEN), "elk genoemd begrip heeft een naam"
    tekst = regeltekst(inhoud, NAMEN)
    assert "(onbekend begrip)" not in tekst["tekst"]
    assert "|" not in tekst["markdown"], "kopieertekst heeft lijsten, geen tabellen"


def test_een_rekenregel_volgt_het_taalpatroon_van_de_methode():
    r5 = {**TERMIJNEN["R5"], "gevallen": [TERMIJNEN["R5"]["gevallen"][0] | {"label": "", "voorwaarden": None}]}
    tekst = regeltekst(RegelInhoud.model_validate(r5).model_dump(mode="json"), NAMEN)
    assert tekst["tekst"] == ("Het termijnbedrag moet berekend worden als bedrag van de belastingaanslag zonder teken "
                              "gedeeld door aantal termijnen.")
    assert "**gedeeld door**" in tekst["markdown"] and "_aantal termijnen_" in tekst["markdown"]


def test_een_beslistabel_noemt_elk_geval_en_wat_voorgaat():
    tekst = regeltekst(RegelInhoud.model_validate(TERMIJNEN["R6"]).model_dump(mode="json"), NAMEN)["tekst"]
    assert tekst.splitlines()[0] == "De wijze van uitbetaling moet bepaald worden volgens het geval dat geldt:"
    assert "Geval in één keer (gaat voor): indien aan alle volgende voorwaarden is voldaan:" in tekst
    assert "niet: er ligt derdenbeslag" in tekst
    assert "Geval anders: in maandelijkse termijnen." in tekst


def test_een_genest_verband_staat_als_lijst_onder_de_zin():
    tekst = regeltekst(RegelInhoud.model_validate(TERMIJNEN["R2"]).model_dump(mode="json"), NAMEN)["tekst"]
    assert "indien aan ten minste één van de volgende voorwaarden is voldaan:" in tekst
    assert "• de termijnregeling leidt niet tot meer dan één termijn" in tekst


def test_de_keten_van_termijnen_loopt_van_onder_naar_boven():
    regels = []
    for naam, data in TERMIJNEN.items():
        inhoud = RegelInhoud.model_validate(data).model_dump(mode="json")
        regels.append({"id": naam, "status": "concept", "inhoud": inhoud, "naam": NAMEN[inhoud["regelbegrip_id"]],
                       "uitvoer": NAMEN[inhoud["uitvoer_begrip_id"]],
                       "begrippen": {i: {"naam": NAMEN[i]} for i in genoemde_begrippen(inhoud)}})
    k = keten(regels)
    v = k["volgorde"]
    assert v.index("R1") < v.index("R4") < v.index("R7")
    assert v.index("R5") < v.index("R6")
    assert {"van": "R1", "naar": "R5", "begrip_id": "de1bae54", "via": "invoer"} in k["pijlen"]
    # R2, R3 en R4 leiden alle drie de vervaldag af: hun gevallen moeten elkaar uitsluiten.
    [zelfde] = [s for s in k["signalen"] if s["soort"] == "zelfde_uitvoer"]
    assert set(zelfde["regel_ids"]) == {"R2", "R3", "R4"} and zelfde["begrip_id"] == "08ffc11c"
    assert {"begrip_id": "11c714db", "naam": "dagtekening van het aanslagbiljet"} in k["basisgegevens"]
    assert not [s for s in k["signalen"] if s["soort"] == "kring"]


def test_een_kring_is_een_signaal():
    def r(i, uit, inv):
        return {"id": i, "status": "concept", "naam": i, "uitvoer": uit, "begrippen": {},
                "inhoud": {"soort": "rekenregel", "regelbegrip_id": i, "uitvoer_begrip_id": uit,
                           "invoer": [{"begrip_id": inv, "rol": "invoer"}], "gevallen": [{"uitkomst": []}]}}
    k = keten([r("A", "x", "y"), r("B", "y", "x")])
    assert [s["soort"] for s in k["signalen"]] == ["kring"]


def test_meer_gevallen_vragen_een_uniek_label():
    with pytest.raises(ValueError):
        RegelInhoud.model_validate({**TERMIJNEN["R4"], "gevallen": [g | {"label": "x"} for g in TERMIJNEN["R4"]["gevallen"]]})
    with pytest.raises(ValueError):
        RegelInhoud.model_validate({**TERMIJNEN["R5"], "invoer": [{"begrip_id": "cbc694db"}]})
