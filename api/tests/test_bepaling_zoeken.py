"""Bepaling toevoegen: een getypte vindplaats lezen en in de echte boom vinden (3 nov 2026)."""
from __future__ import annotations

import pytest
from bronmodel import bouw_snapshot

from app import bepaling_zoeken as zoeken

IW, LR = "BWBR0004770", "BWBR0024096"


def rij(bwb, suffix, soort, ouder="", nummer="", tekst="", label="", vindplaats=""):
    root = f"urn:bwb:{bwb}"
    return {"node": root + suffix, "type": "urn:bwb-ns:" + soort, "parent": (root + ouder) if ouder != "-" else "",
            "nummer": nummer, "tekst": tekst, "label": label, "vindplaats": vindplaats}


def iw():
    return bouw_snapshot([
        rij(IW, "", "Regeling", "-"),
        rij(IW, ":artikel:9", "Artikel", "", "9", label="Artikel 9", vindplaats="Artikel 9"),
        rij(IW, ":artikel:9:lid:1", "Lid", ":artikel:9", "1", "Een belastingaanslag is invorderbaar zes weken na de dagtekening.",
            vindplaats="Artikel 9, lid 1"),
        rij(IW, ":artikel:9:lid:2", "Lid", ":artikel:9", "2", "Een navorderingsaanslag is invorderbaar een maand na de dagtekening.",
            vindplaats="Artikel 9, lid 2"),
        rij(IW, ":artikel:9:lid:2:o:a", "Onderdeel", ":artikel:9:lid:2", "a.", "bij een naheffingsaanslag;",
            vindplaats="Artikel 9, lid 2, onderdeel a"),
        rij(IW, ":artikel:9:lid:2:o:b", "Onderdeel", ":artikel:9:lid:2", "b.", "bij een navorderingsaanslag.",
            vindplaats="Artikel 9, lid 2, onderdeel b"),
        rij(IW, ":artikel:9a", "Artikel", "", "9a", "Een voorlopige aanslag …", label="Artikel 9a"),
        rij(IW, ":artikel:36", "Artikel", "", "36", label="Artikel 36"),
        rij(IW, ":artikel:36:lid:5", "Lid", ":artikel:36", "5", "Onder bestuurder wordt mede verstaan:"),
        rij(IW, ":artikel:36:lid:5:o:a", "Onderdeel", ":artikel:36:lid:5", "a.", "de gewezen bestuurder;"),
    ], bwb_id=IW)["nodes"]


def leidraad():
    d = ":id:BWBR0024096%2FCirculaire.divisie9%2FCirculaire.divisie9.2"
    return bouw_snapshot([
        rij(LR, "", "Regeling", "-"),
        rij(LR, ":artikel:9", "Divisie", "", "9", "In aansluiting op artikel 9 …", label="Invorderbaarheid"),
        rij(LR, d, "Divisie", ":artikel:9", "9.2", "Wanneer een aanslag is gedagtekend:", label="Dagtekening",
            vindplaats="Artikel 9.2"),
        # Het onderdeel heet in zijn IRI naar artikel 9, maar hangt onder divisie 9.2.
        rij(LR, ":artikel:9:o:d", "Onderdeel", d, "d.", "de dagtekening van het aanslagbiljet;",
            vindplaats="Artikel 9.2, onderdeel d"),
        rij(LR, ":id:BWBR0024096%2FCirculaire.divisie21", "Divisie", "", "21.1", "Onder bodemzaken wordt verstaan …",
            label="Begrippen bodemzaken"),
        rij(LR, ":id:BWBR0024096%2FCirculaire.divisie21b", "Divisie", "", "21.5", "De tijdsduur …", label="Tijdsduur voorrecht"),
    ], bwb_id=LR)["nodes"]


@pytest.mark.parametrize("invoer, verwacht", [
    ("9 lid 2", ("9", "2", "")),
    ("artikel 9, tweede lid", ("9", "2", "")),
    ("art. 9 lid 2 onderdeel b", ("9", "2", "b")),
    ("9 lid 2 b", ("9", "2", "b")),
    ("36 lid 5 sub a", ("36", "5", "a")),
    ("21.1", ("21.1", "", "")),
    ("25.4 onderdeel b", ("25.4", "", "b")),
    ("4:86", ("4:86", "", "")),
    ("Artikel 9a", ("9a", "", "")),
    ("kennelijk onbehoorlijk", ("", "", "")),
])
def test_lees_de_vindplaats_zoals_de_jurist_hem_typt(invoer, verwacht):
    v = zoeken.lees(invoer)
    assert (v.artikel, v.lid, v.onderdeel) == verwacht


def iris(treffers):
    return [t["bron_iri"].removeprefix("urn:bwb:") for t in treffers]


def test_een_lid_precies_en_dan_zijn_onderdelen():
    t = zoeken.zoek(iw(), "9 lid 2")
    assert iris(t) == [f"{IW}:artikel:9:lid:2", f"{IW}:artikel:9:lid:2:o:a", f"{IW}:artikel:9:lid:2:o:b"]
    assert t[0]["vindplaats"] == "Artikel 9, lid 2" and t[0]["soort"] == "lid"
    assert t[0]["fragment"].startswith("Een navorderingsaanslag")


def test_een_artikel_dan_zijn_leden_dan_artikelen_die_ermee_beginnen():
    assert iris(zoeken.zoek(iw(), "9")) == [f"{IW}:artikel:9", f"{IW}:artikel:9:lid:1", f"{IW}:artikel:9:lid:2",
                                             f"{IW}:artikel:9a"]


def test_een_onderdeel_met_en_zonder_naam_uit_de_importer():
    assert iris(zoeken.zoek(iw(), "art. 9, tweede lid, onderdeel b")) == [f"{IW}:artikel:9:lid:2:o:b"]
    t = zoeken.zoek(iw(), "36 lid 5 sub a")
    assert iris(t) == [f"{IW}:artikel:36:lid:5:o:a"] and t[0]["vindplaats"] == "Artikel 36, lid 5, onderdeel a"


def test_de_leidraad_divisies_en_een_onderdeel_zonder_lid():
    lr = leidraad()
    t = zoeken.zoek(lr, "9.2 onderdeel d")
    assert iris(t) == [f"{LR}:artikel:9:o:d"] and t[0]["vindplaats"] == "Artikel 9.2, onderdeel d"
    # "9 lid 2" bij een beleidsregel is de subdivisie 9.2.
    assert iris(zoeken.zoek(lr, "9 lid 2"))[0].endswith("Circulaire.divisie9.2")
    t = zoeken.zoek(lr, "21")
    assert [x["vindplaats"] for x in t] == ["Artikel 21.1", "Artikel 21.5"]
    assert t[0]["titel"] == "Begrippen bodemzaken"


def test_zoeken_op_de_kop_zonder_nummer():
    assert [t["titel"] for t in zoeken.zoek(leidraad(), "bodemzaken")] == ["Begrippen bodemzaken"]


def test_niets_dat_niet_bestaat():
    assert zoeken.zoek(iw(), "9 lid 7") == []
    assert zoeken.zoek(iw(), "123") == []
    assert zoeken.zoek(iw(), "") == []
