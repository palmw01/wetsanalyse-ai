"""De gebeurtenis en de grondslag (zoekvraag a), zonder model: `agent/zoekvragen.py`. Een kleine kwijtscheldingswereld
als nepgraaf – een wet, een ministeriële regeling en een beleidsregel – met de valkuilen die de meting op de
ontwikkelset liet zien: een afbakening die de gebeurtenis zelf noemt, "vallen" in "gevallen", een stam die overal
staat, en de grondslag in de lagere regeling achter de leden van de wet."""
from __future__ import annotations

import json
import re

import pytest

from agent import regelingnamen, zoekvragen as zv
from agent.zoektermen import uitsluitstammen, buiten_uit_afbakening
from fakes import FakeGraph

IW, UR, LR = "BWBR0004770", "BWBR0004766", "BWBR0024096"
FTS_KOP = ["node", "score", "soort", "label", "tekst", "jci", "bwbId", "citeertitel"]

#: node → (soort, bwb, tekst)
TEKSTEN = {
    f"urn:bwb:{IW}:artikel:26:lid:1": ("Lid", IW, "Bij ministeriële regeling worden regels gesteld krachtens welke aan de "
                                       "belastingschuldige gehele of gedeeltelijke kwijtschelding kan worden verleend."),
    f"urn:bwb:{IW}:artikel:26a:lid:1": ("Lid", IW, "De ontvanger verleent ambtshalve kwijtschelding aan een persoon als "
                                        "bedoeld in de Wet hersteloperatie toeslagen."),
    f"urn:bwb:{IW}:artikel:70ba": ("Artikel", IW, "Indien het uitstel eindigt, kan volgens bij ministeriële regeling te "
                                   "stellen regels kwijtschelding worden verleend."),
    f"urn:bwb:{UR}:artikel:7:lid:1": ("Lid", UR, "De ontvanger verleent de belastingschuldige op diens schriftelijk "
                                      "verzoek kwijtschelding in andere gevallen dan die bedoeld in hoofdstuk IB."),
    f"urn:bwb:{UR}:artikel:8:lid:1": ("Lid", UR, "Geen kwijtschelding wordt verleend voor zover het niet betalen aan de "
                                      "belastingschuldige is toe te rekenen."),
    f"urn:bwb:{LR}:artikel:26": ("Divisie", LR, "De ontvanger kan kwijtschelding verlenen aan een particulier."),
    f"urn:bwb:{LR}:id:{LR}%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.3":
        ("Divisie", LR, "De auto van een particulier telt niet als vermogen bij kwijtschelding."),
}
#: bepaling (artikel of divisie) → de delen erboven: (deel, soort, label)
KOPPEN = {
    f"urn:bwb:{IW}:artikel:26": [(f"urn:bwb:{IW}:hoofdstuk:IV", "Hoofdstuk", "Hoofdstuk IV – Bijzondere bepalingen"),
                                 (f"urn:bwb:{IW}:hoofdstuk:IV:afdeling:3", "Afdeling",
                                  "Afdeling 3 – Uitstel van betaling, kwijtschelding en verjaring")],
    f"urn:bwb:{IW}:artikel:26a": [(f"urn:bwb:{IW}:hoofdstuk:IV:afdeling:3", "Afdeling",
                                   "Afdeling 3 – Uitstel van betaling, kwijtschelding en verjaring")],
    f"urn:bwb:{IW}:artikel:70ba": [(f"urn:bwb:{IW}:hoofdstuk:X", "Hoofdstuk", "Hoofdstuk X – Overgangsbepalingen")],
    f"urn:bwb:{UR}:artikel:7": [(f"urn:bwb:{UR}:hoofdstuk:II", "Hoofdstuk",
                                 "Hoofdstuk II – Kwijtschelding in andere gevallen en ontslag van betalingsverplichting")],
    f"urn:bwb:{UR}:artikel:8": [(f"urn:bwb:{UR}:hoofdstuk:II", "Hoofdstuk",
                                 "Hoofdstuk II – Kwijtschelding in andere gevallen en ontslag van betalingsverplichting")],
    f"urn:bwb:{LR}:id:{LR}%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.3":
        [(f"urn:bwb:{LR}:artikel:26", "Divisie", "Kwijtschelding"),
         (f"urn:bwb:{LR}:id:{LR}%2FCirculaire.divisie26%2FCirculaire.divisie26.2", "Divisie",
          "Kwijtschelding van rijksbelastingen voor particulieren")],
}
SOORT = {IW: "wet", UR: "ministeriele-regeling", LR: "beleidsregel"}
NAAM = {IW: "Invorderingswet 1990", UR: "Uitvoeringsregeling Invorderingswet 1990", LR: "Leidraad Invordering 2008"}


def _tsv(kop: list[str], rijen: list[list[str]]) -> str:
    def cel(v: str) -> str:
        return f"<{v}>" if v.startswith("urn:") else json.dumps(v, ensure_ascii=False)
    return "\t".join(f"?{k}" for k in kop) + "\n" + "".join("\t".join(cel(v) for v in r) + "\n" for r in rijen)


class Wereld(FakeGraph):
    def __init__(self, faal: bool = False) -> None:
        super().__init__(results=self._antwoord)
        self.faal = faal

    def _antwoord(self, q: str) -> str:
        if self.faal:
            raise RuntimeError("graaf hapert")
        if "luc:query" in q:
            woorden = re.findall(r"\(([0-9a-zà-ÿ]+) OR", q)
            bwb = next((b for b in SOORT if b in q), "")
            return _tsv(FTS_KOP, [[n, "1.0", s, "", t, "", b, ""] for n, (s, b, t) in TEKSTEN.items()
                                  if b == bwb and woorden and all(w[:8] in t.casefold() for w in woorden)])
        if "bwb:soort" in q:
            return _tsv(["regeling", "soort"], [[f"urn:bwb:{b}", s] for b, s in SOORT.items() if b in q])
        if "bwb:citeertitel" in q:
            return _tsv(["r", "citeertitel", "opschrift"], [[f"urn:bwb:{b}", n, ""] for b, n in NAAM.items() if b in q])
        if "VALUES ?bepaling" in q:
            return _tsv(["bepaling", "deel", "soort", "label"],
                        [[b, d, s, l] for b, delen in KOPPEN.items() if f"<{b}>" in q for d, s, l in delen])
        raise AssertionError(f"onverwachte query: {q[:200]}")


@pytest.fixture(autouse=True)
def _schone_namen():
    regelingnamen._CACHE.clear()


@pytest.mark.parametrize("label, gebeurtenissen", [
    ("Afdeling 3 – Uitstel van betaling, kwijtschelding en verjaring", ["uitstel van betaling", "kwijtschelding", "verjaring"]),
    ("Hoofdstuk 6 – Algemene bepalingen over bezwaar en beroep", ["bezwaar", "beroep"]),     # rand: de aanhef weg
    ("Verrekening", ["verrekening"]),                                                       # een hoofddivisie
    ("Afdeling 1 – Algemeen", []),                                                          # negatief: geen gebeurtenis
    ("Hoofdstuk X – Overgangsbepalingen", []),
    ("Bijzonder verhaalsrecht op goederen van een derde waarin het vermogen een belang heeft van 5 percent of meer",
     []),                                                                                   # te lang, en niet knippen op "of"
    ("Uitstel- en betalingsregelingen", ["betalingsregelingen"]),                           # een afgebroken ellips telt niet
])
def test_de_gebeurtenissen_in_een_kop(label, gebeurtenissen):
    assert zv.kop_gebeurtenissen(label) == gebeurtenissen


@pytest.mark.parametrize("zin, signaal", [
    ("De ontvanger is ten aanzien van de belastingschuldige bevoegd te verrekenen.", "bevoegd"),
    ("… gehele of gedeeltelijke kwijtschelding kan worden verleend.", "kan worden"),
    ("De ontvanger verleent de belastingschuldige kwijtschelding.", "verleent"),
    ("Bij ministeriële regeling worden regels gesteld krachtens welke …", "regels gesteld"),
    ("Hoofdelijk aansprakelijk is de bestuurder voor de loonbelasting.", ""),               # rand: inversie zonder "is … aansprakelijk"
    ("Een bestuurder is hoofdelijk aansprakelijk voor de belasting.", "aansprakelijk"),
    ("Geen kwijtschelding wordt verleend indien de aangifte ontbreekt.", ""),               # negatief: een beperking (b)
    ("Deze afdeling heeft betrekking op kwijtschelding van inkomstenbelasting.", ""),       # negatief: geen signaal
])
def test_het_signaal_van_bestaansrecht(zin, signaal):
    assert zv.bestaansrecht_signaal(zin) == signaal


def test_genoemd_is_het_woord_zelf_niet_een_gedeelde_stam():
    assert zv.genoemd_in("kwijtschelding", "Kwijtschelding voor particulieren")
    assert not zv.genoemd_in("betaling", "Ze kan de aanslag niet betalen.")
    assert zv._raakt_woord("vallen", "Wat vallen buiten") and not zv._raakt_woord("vallen", "in andere gevallen")


def test_de_gebeurtenis_komt_uit_de_koppen_wat_het_dossier_noemt_eerst():
    dossier = {"naam": "Kwijtschelding voor particulieren", "analysevraag": "Wanneer vervalt de schuld van een particulier?",
               "praktijkvoorbeeld": "Een particulier met een auto vraagt kwijtschelding."}
    opties = zv.gebeurtenis_opties(Wereld(), regelingen=[IW, UR, LR], dossier=dossier)
    eerste = opties[0]
    assert (eerste["gebeurtenis"], eerste["genoemd"]) == ("kwijtschelding", True)
    # De koppen zijn het bewijs, met de naam van de regeling; de afgekapte vorm ("Kwijtschelding in andere gevallen")
    # valt samen met de korte.
    assert any("Leidraad Invordering 2008" in k for k in eerste["koppen"])
    assert [o["gebeurtenis"] for o in opties].count("kwijtschelding") == 1
    assert "overgangsbepalingen" not in [o["gebeurtenis"] for o in opties]
    # Dezelfde vraag, hetzelfde voorstel; zonder regeling of zonder dossier niets, en een haperende graaf ook niets.
    assert zv.gebeurtenis_opties(Wereld(), regelingen=[IW, UR, LR], dossier=dossier) == opties
    assert zv.gebeurtenis_opties(Wereld(), regelingen=[], dossier=dossier) == []
    assert zv.gebeurtenis_opties(Wereld(faal=True), regelingen=[IW], dossier=dossier) == []


def test_de_grondslag_onder_de_kop_de_wet_en_de_lagere_regeling_om_de_beurt():
    """Iw 26 lid 1 en Uitv.reg. 7 lid 1 staan onder een kop met de gebeurtenis, dus vooraan, om de beurt per regeling.
    De afbakening noemt kwijtschelding zelf ("voor ondernemers"): dat haalt niets weg, de hersteloperatie wel. Een
    zin die met "Geen" begint en de beleidsregel tellen niet, en 70ba (geen kop met de gebeurtenis) komt achteraan."""
    buiten = uitsluitstammen(buiten_uit_afbakening(
        "Buiten de afbakening: kwijtschelding voor ondernemers en de hersteloperatie toeslagen."))
    assert "kwijtsch" in buiten
    uit = zv.grondslag(Wereld(), gebeurtenis="kwijtschelding", regelingen=[IW, UR, LR], buiten=buiten)
    assert [k["bron_iri"].split(":", 2)[2] for k in uit] == [f"{IW}:artikel:26:lid:1", f"{UR}:artikel:7:lid:1",
                                                            f"{IW}:artikel:70ba"]
    assert (uit[0]["signaal"], uit[0]["onder_kop"]) == ("kan worden",
                                                       "Afdeling 3 – Uitstel van betaling, kwijtschelding en verjaring")
    assert uit[1]["zin"].startswith("De ontvanger verleent") and uit[2]["onder_kop"] == ""
    assert zv.grondslag(Wereld(faal=True), gebeurtenis="kwijtschelding", regelingen=[IW]) == []
    assert zv.grondslag(Wereld(), gebeurtenis="", regelingen=[IW]) == []
