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
    ("Hoofdelijk aansprakelijk is de bestuurder voor de loonbelasting.", "aansprakelijk"),  # rand: de inversie (Iw 36 lid 1)
    ("Een bestuurder is hoofdelijk aansprakelijk voor de belasting.", "aansprakelijk"),
    ("Geen kwijtschelding wordt verleend indien de aangifte ontbreekt.", ""),               # negatief: een beperking (b)
    ("Deze afdeling heeft betrekking op kwijtschelding van inkomstenbelasting.", ""),       # negatief: geen signaal
])
def test_het_signaal_van_bestaansrecht(zin, signaal):
    assert zv.bestaansrecht_signaal(zin) == signaal


def test_genoemd_is_het_woord_of_een_vervoeging_niet_een_gedeelde_korte_stam():
    """De vervoeging telt bij een specifieke stam: "waarop wordt uitbetaald" noemt de uitbetaling (werkgebied
    Rekeningafspraken, 4 nov 2026: de wet zegt uitbetaling, de analist bankrekening). Een korte stam ("betal") en het
    begin van een samenstelling ("belasti" in belastingrente en belastingschuldige) tellen niet."""
    assert zv.genoemd_in("kwijtschelding", "Kwijtschelding voor particulieren")
    assert zv.genoemd_in("uitbetaling", "een bankrekening waarop wordt uitbetaald")
    assert zv.genoemd_in("verrekening", "de teruggaaf is verrekend")
    assert not zv.genoemd_in("betaling", "Ze kan de aanslag niet betalen.")
    assert not zv.genoemd_in("belastingrente", "de belastingschuldige")
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


@pytest.mark.parametrize("tekst, zoekvraag, signaal", [
    ("De directeur beslist op het beroep bij uitspraak.", "c", "beroep"),
    ("Indien de directeur tegemoetkomt, stelt hij bij die uitspraak het bedrag van de kwijtschelding vast.", "c", "uitspraak"),
    ("Onder vermogen wordt verstaan de waarde in het economische verkeer van de bezittingen.", "d", "verstaan"),
    ("Geen kwijtschelding wordt verleend voor een voorlopige aanslag.", "b", "geen … wordt"),
    ("Het verzoek wordt ingediend op een formulier.", "b", "procedure"),
    ("Kwijtschelding wordt verleend indien geen vermogen aanwezig is.", "b", "jas.voorwaarde.voorwaardelijke_bijzin"),
    ("Deze afdeling heeft betrekking op kwijtschelding van inkomstenbelasting.", "a", "reikwijdte"),
    # overlap: een gevolg en een voorwaarde in één bepaling – het gevolg wint (de sterkste zoekvraag)
    ("Indien de belanghebbende niet tijdig betaalt, vervalt de regeling.", "c", "vervalt"),
    ("De ontvanger is de ambtenaar die belast is met de invordering.", "", ""),     # negatief: geen signaal
])
def test_de_zoekvraag_van_een_bepaling_uit_haar_tekst(tekst, zoekvraag, signaal):
    z, s, _ = zv.zoekvraag_van(tekst)
    assert (z, s) == (zoekvraag, signaal)


#: De omgeving van kwijtschelding in de lagere regeling (Uitv.reg. hoofdstuk II) en de beleidsregel (Leidraad 26).
OMGEVING = {
    f"urn:bwb:{UR}:artikel:7": [(f"urn:bwb:{UR}:artikel:7:lid:1", TEKSTEN[f"urn:bwb:{UR}:artikel:7:lid:1"][2])],
    f"urn:bwb:{UR}:artikel:8": [(f"urn:bwb:{UR}:artikel:8:lid:1", TEKSTEN[f"urn:bwb:{UR}:artikel:8:lid:1"][2])],
    f"urn:bwb:{UR}:artikel:12": [(f"urn:bwb:{UR}:artikel:12:lid:1", "Onder vermogen wordt verstaan de waarde van de "
                                  "bezittingen van de belastingschuldige.")],
    f"urn:bwb:{UR}:artikel:24": [(f"urn:bwb:{UR}:artikel:24", "Indien de belastingschuldige zich niet kan verenigen "
                                  "met de beschikking, kan hij een beroepschrift richten tot de directeur.")],
    f"urn:bwb:{UR}:artikel:25": [(f"urn:bwb:{UR}:artikel:25:lid:1", "De directeur beslist op het beroep bij uitspraak."),
                                 (f"urn:bwb:{UR}:artikel:25:lid:1:o:a", "een onderdeel van het eerste lid;")],
    f"urn:bwb:{UR}:artikel:26": [(f"urn:bwb:{UR}:artikel:26", "De Staatssecretaris is bevoegd tot vaststelling van "
                                  "modellen voor ondernemers.")],
}
SUB = f"urn:bwb:{LR}:id:{LR}%2FCirculaire.divisie26%2FCirculaire.divisie26.2%2FCirculaire.divisie26.2.3"


class Omgeving(Wereld):
    def _antwoord(self, q: str) -> str:
        if self.faal:
            raise RuntimeError("graaf hapert")
        if "?aantal" in q:                       # zoek_opbouw: de koppen met de gebeurtenis
            rijen = {UR: [[f"urn:bwb:{UR}:hoofdstuk:II", "Hoofdstuk II – Kwijtschelding in andere gevallen"]],
                     LR: [[f"urn:bwb:{LR}:artikel:26", "Kwijtschelding"]],
                     IW: [[f"urn:bwb:{IW}:hoofdstuk:IV", "Hoofdstuk IV – Bijzondere bepalingen"]]}
            bwb = next(b for b in SOORT if f"{b}:" in q or f"{b}\"" in q)
            return _tsv(["node", "score", "soort", "label"], [[n, "1.0", "Hoofdstuk", l] for n, l in rijen.get(bwb, [])])
        if "VALUES ?deel" in q:
            return _tsv(["deel", "bepaling", "nummer"], [[f"urn:bwb:{UR}:hoofdstuk:II", a, a.rsplit(":", 1)[1]]
                                                        for a in OMGEVING])
        if "?kern ?deel ?tekst" in q:
            return _tsv(["kern", "deel", "tekst"], [[a, d, t] for a, delen in OMGEVING.items() if f"<{a}>" in q
                                                   for d, t in delen])
        if "?kern ?doel ?bron" in q:
            return _tsv(["kern", "doel", "bron"], [[f"urn:bwb:{IW}:artikel:26", f"urn:bwb:{IW}:artikel:26",
                                                    f"urn:bwb:{LR}:artikel:26"]])
        if "?hoofd ?sub ?tekst" in q:
            return _tsv(["hoofd", "sub", "tekst"], [[f"urn:bwb:{LR}:artikel:26", SUB, TEKSTEN[SUB][2]]])
        if "definieertBegrip ?begrip" in q:
            return _tsv(["node", "begrip", "label"], [[f"urn:bwb:{UR}:artikel:1:o:b", "belastingschuldige", ""]])
        return super()._antwoord(q)


def test_de_pool_vanuit_de_grondslag_met_een_zoekvraag_per_kandidaat():
    """a de grondslag; in de omgeving (Uitv.reg. hoofdstuk II) per lid de zoekvraag uit de tekst – een beperking (b),
    een begrip (d), het beroep en de uitspraak (c) – en geen kandidaat zonder signaal (art. 26: een bevoegdheid buiten
    de gebeurtenis); een onderdeel telt voor zijn lid. d ook buiten de wet: de Leidraad die naar Iw 26 verwijst en
    de definitie van een term uit a–c. Volgorde a, b, c, d."""
    p = zv.pool(Omgeving(), gebeurtenis="kwijtschelding", regelingen=[IW, UR, LR])
    zoekvraag = {k["bron_iri"].split(":", 2)[2]: (k["zoekvraag"], k["via"]) for k in p["kandidaten"]}
    assert zoekvraag[f"{IW}:artikel:26:lid:1"] == ("a", "grondslag")
    assert zoekvraag[f"{UR}:artikel:7:lid:1"] == ("a", "grondslag")
    assert zoekvraag[f"{UR}:artikel:8:lid:1"] == ("b", "omgeving")
    assert zoekvraag[f"{UR}:artikel:12:lid:1"] == ("d", "omgeving")
    assert zoekvraag[f"{UR}:artikel:24"] == ("c", "omgeving") and zoekvraag[f"{UR}:artikel:25:lid:1"] == ("c", "omgeving")
    assert zoekvraag[SUB.split(":", 2)[2]] == ("d", "beleidsregel")
    assert zoekvraag[f"{UR}:artikel:1:o:b"] == ("d", "definitie")
    assert f"{UR}:artikel:26" not in zoekvraag and f"{UR}:artikel:25:lid:1:o:a" not in zoekvraag
    assert [k["zoekvraag"] for k in p["kandidaten"]] == sorted(k["zoekvraag"] for k in p["kandidaten"])
    assert p["volledig"] is True and f"urn:bwb:{UR}:hoofdstuk:II" in p["omgeving"]
    # Een haperende graaf: geen crash, wel onvolledig.
    assert zv.pool(Omgeving(faal=True), gebeurtenis="kwijtschelding", regelingen=[IW, UR])["volledig"] is False
