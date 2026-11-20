"""Schakelbepalingen (L-1-1 uit de lessen van Termijnen): een regeling buiten het zoekbereik die een regeling erin van
toepassing verklaart, wordt een voorstel "regeling erbij?". Art. 72 Mijnbouwwet is het voorbeeld uit Termijnen; de
regel kent alleen de verwijzingsgraaf en de formule, geen regeling."""
from __future__ import annotations

import pytest

from agent import schakelbepalingen as sb

IW, AWR, MBW, AWB = "BWBR0004770", "BWBR0002320", "BWBR0014168", "BWBR0005537"
ART72 = ("Onverminderd het overigens bij of krachtens deze paragraaf bepaalde geschieden de heffing en de invordering van "
         "oppervlakterecht, cijns en winstaandeel met overeenkomstige toepassing van de Algemene wet inzake "
         "rijksbelastingen, de Invorderingswet 1990 en de Kostenwet invordering rijksbelastingen.")


@pytest.mark.parametrize("tekst, anker, verwacht", [
    (ART72, "Invorderingswet 1990", True),
    ("De Invorderingswet 1990 is van overeenkomstige toepassing op de terugvordering.", "Invorderingswet 1990", True),
    ("Op het besluit zijn de artikelen van de Algemene wet bestuursrecht van toepassing.", "Algemene wet bestuursrecht", True),
    ("De Algemene wet bestuursrecht is niet van toepassing op de in dit artikel bedoelde termijnen.",
     "Algemene wet bestuursrecht", False),
    ("Als belastingaanslag als bedoeld in de Invorderingswet 1990 geldt ook de naheffing.", "Invorderingswet 1990", False),
    # De formule staat in een andere zin dan de verwijzing: geen schakel.
    ("De ontvanger is bevoegd. Artikel 4 is van toepassing; zie de Invorderingswet 1990.", "Invorderingswet 1990", False),
    # Acceptatie, 20 nov 2026 (Leidraad 1.1.10 en 76.1): het anker "wet" binnen "Ambtenarenwet" telt niet, en een anker
    # dat niet in de tekst staat is geen bewijs.
    ("De rechten en plichten uit de Ambtenarenwet zijn op hem van toepassing.", "wet", False),
    ("De invordering vindt plaats met toepassing van verordeningen.", "wet", False),
])
def test_de_formule_rond_de_verwijzing(tekst, anker, verwacht):
    assert sb.is_schakel(tekst, anker) is verwacht


class _Graaf:
    def __init__(self, rijen):
        self.rijen = rijen


@pytest.fixture
def graaf(monkeypatch):
    def maak(rijen):
        monkeypatch.setattr(sb, "rijen", lambda g, q: rijen)
        return _Graaf(rijen)
    return maak


def _rij(bron, doel, tekst, anker, titel):
    return {"bron": f"urn:bwb:{bron}", "doel": f"urn:bwb:{doel}", "tekst": tekst, "anker": anker,
            "regeling": f"urn:bwb:{bron.split(':')[0]}", "titel": titel}


def test_schakelregelingen_buiten_het_zoekbereik_sterkste_eerst(graaf):
    g = graaf([
        _rij(f"{MBW}:artikel:72", AWR, ART72, "Algemene wet inzake rijksbelastingen", "Mijnbouwwet"),
        _rij(f"{MBW}:artikel:72", IW, ART72, "Invorderingswet 1990", "Mijnbouwwet"),
        _rij(f"{AWB}:artikel:1:3", IW, "De Invorderingswet 1990 is van overeenkomstige toepassing.",
             "Invorderingswet 1990", "Algemene wet bestuursrecht"),
        # binnen het zoekbereik, en een verwijzing zonder schakelformule: allebei geen voorstel
        _rij(f"{IW}:artikel:2", AWR, "De Algemene wet inzake rijksbelastingen is van toepassing.", "Algemene wet inzake rijksbelastingen", "IW"),
        _rij("BWBR0000001:artikel:1", IW, "Als bedoeld in de Invorderingswet 1990.", "Invorderingswet 1990", "Andere wet"),
    ])
    uit = sb.schakelregelingen(g, [IW, AWR])
    assert [p["bwb_id"] for p in uit] == [MBW, AWB]
    assert uit[0]["doelen"] == [AWR, IW] and uit[0]["bepalingen"] == [f"urn:bwb:{MBW}:artikel:72"]
    assert sb.omschrijving(uit[0], {IW: "Invorderingswet 1990", AWR: "AWR"}) == (
        "verklaart AWR en Invorderingswet 1990 van toepassing (artikel 72): regeling erbij?")


def test_zonder_zoekbereik_of_zonder_graaf_geen_voorstel(monkeypatch):
    assert sb.schakelregelingen(object(), []) == []

    def kapot(g, q):
        raise RuntimeError("graaf weg")
    monkeypatch.setattr(sb, "rijen", kapot)
    assert sb.schakelregelingen(object(), [IW]) == []


def test_de_vraagkaart_stelt_de_schakelregeling_voor_maar_kiest_haar_niet(monkeypatch):
    from agent import overzicht as ov
    from agent import werkgebied_intake as wi
    monkeypatch.setattr(ov, "regelingen_in_vraag", lambda g, v: [])
    monkeypatch.setattr(ov, "bouw_overzicht", lambda g, v, onderwerp=None, scope=None: {"regelingen": [
        {"bwb_id": IW, "citeertitel": "Invorderingswet 1990", "delen": []}]})
    monkeypatch.setattr(sb, "schakelregelingen", lambda g, bereik: [
        {"bwb_id": MBW, "titel": "Mijnbouwwet", "bepalingen": [f"urn:bwb:{MBW}:artikel:72"], "doelen": [IW]}]
        if IW in bereik else [])
    opties, voorop, _ = wi.regeling_opties(object(), "invordering")
    assert [o["waarde"] for o in opties] == [IW, MBW] and voorop == []
    assert opties[1]["omschrijving"] == "verklaart Invorderingswet 1990 van toepassing (artikel 72): regeling erbij?"


def test_de_zin_van_de_bronselectie():
    from agent.bronselectie import schakel_zin
    p = {"bwb_id": MBW, "titel": "Mijnbouwwet", "bepalingen": [f"urn:bwb:{MBW}:artikel:72"], "doelen": [IW]}
    assert schakel_zin([p], {IW: "Invorderingswet 1990"}) == (
        "Mijnbouwwet verklaart Invorderingswet 1990 van toepassing (artikel 72). Hoort die regeling erbij, neem haar dan "
        "op in het zoekbereik.")
    assert schakel_zin([], {}) == ""
