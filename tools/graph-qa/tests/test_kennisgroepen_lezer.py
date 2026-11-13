"""De lezer van de kennisgroepstandpunten (`bronmodel.kennisgroepen`, plan-connector-kennisgroepen.md stap 2).

De fixtures in `tests/data/kennisgroepen/` zijn echte publicaties uit de REST API van de Belastingdienst (CC0, opgehaald
13 nov 2026): een standpunt dat een ouder standpunt intrekt (22819), een ingetrokken (4785) en een vervallen (586)
standpunt, een standpunt met tabel en voetnoten (8488), de drie titels met een afwijkend kenmerk (21497, 19538, 7012), een
standpunt met jci-links tot op het lid (14091), een standpunt met vaststellingsdatum (777), een met een bijlage (20766),
een met `h3`-koppen (5450) en een nieuwsbericht (22821).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bronmodel.extern import BRONTYPEN
from bronmodel.kennisgroepen import (STATUSSEN, item_url, kenmerk_uit_titel, lees_bericht, lees_publicatie, lijst_url,
                                     rijen_uit_html)
from bronmodel.connectors import METADATA_SLEUTELS

DATA = Path(__file__).parent / "data" / "kennisgroepen"


def _item(wp_id: int) -> dict:
    return json.loads((DATA / f"wp-{wp_id}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("titel,ident,status,onderwerp", [
    ("KG:013:2026:4 Aangifte BPM voor afronding onderzoek RDW", "kg:013:2026:4", "geldend",
     "Aangifte BPM voor afronding onderzoek RDW"),
    ("[INGETROKKEN]\xa0KG:023:2022:7 Aftrekbaarheid advieskosten", "kg:023:2022:7", "ingetrokken", "Aftrekbaarheid advieskosten"),
    ("[Ingetrokken] KG:211:2022:15 ANBI – commerciële tarieven", "kg:211:2022:15", "ingetrokken", "ANBI – commerciële tarieven"),
    ("INGETROKKEN KG:204:2022:46 Premie WGA-hiaatverzekering", "kg:204:2022:46", "ingetrokken", "Premie WGA-hiaatverzekering"),
    ("[VERVALLEN] KG:209:2022:2 Annuleringsvergoeding pakketreizen", "kg:209:2022:2", "vervallen", "Annuleringsvergoeding pakketreizen"),
    # De drie afwijkende titels bij de bron: omgedraaid, een spatie in plaats van een dubbele punt, een spatie in het nummer.
    ("KG:2026:211:19 ANBI - Vormt een aandelenbezit een investering?", "kg:211:2026:19", "geldend",
     "ANBI - Vormt een aandelenbezit een investering?"),
    ("KG 202:2025:26 Reiskosten vrijwilliger", "kg:202:2025:26", "geldend", "Reiskosten vrijwilliger"),
    ("KG:204:2023: 5 Renseigneringsverplichting leerlingenvervoer", "kg:204:2023:5", "geldend",
     "Renseigneringsverplichting leerlingenvervoer"),
    ("KG:013:2018:0173 Oud standpunt", "kg:013:2018:173", "geldend", "Oud standpunt"),
    ("Over de kennisgroepen", None, "geldend", "Over de kennisgroepen"),
])
def test_kenmerk_uit_titel(titel, ident, status, onderwerp):
    assert kenmerk_uit_titel(titel) == (ident, status, onderwerp)
    assert status in STATUSSEN


@pytest.mark.parametrize("wp_id,ident", [(21497, "kg:211:2026:19"), (19538, "kg:202:2025:26"), (7012, "kg:204:2023:5")])
def test_de_afwijkende_titels_bij_de_bron(wp_id, ident):
    assert lees_publicatie(_item(wp_id)).id == ident


def test_een_standpunt_dat_een_ander_intrekt():
    s = lees_publicatie(_item(22819))
    assert (s.id, s.kenmerk, s.status, s.wp_id) == ("kg:013:2026:4", "KG:013:2026:4", "geldend", 22819)
    assert s.link == "https://kennisgroepen.belastingdienst.nl/publicaties/kg01320264-aangifte-bpm-voor-afronding-onderzoek-rdw/"
    assert s.vervangt == ["kg:013:2018:173"]
    assert s.is_standpunt and s.label == "Kennisgroepstandpunt KG:013:2026:4"
    koppen = [r.kop.split(" › ")[0] for r in s.rijen]
    assert koppen[0] == "Aanleiding" and {"Vragen", "Antwoorden", "Beschouwing"} <= set(koppen)
    laatste = s.rijen[-1]
    assert laatste.kop.endswith("Let op! Intrekking") and "KG:013:2018:0173" in laatste.tekst
    # De ECLI staat als link in de tekst, en de link naar het Woo-besluit draagt het oude kenmerk.
    noemt = {(v.soort, v.doel, v.herkomst) for v in s.verwijzingen}
    assert ("uitspraak", "ECLI:NL:HR:2013:64", "link") in noemt
    assert ("standpunt", "kg:013:2018:173", "link") in noemt
    assert not any(v.doel == "kg:013:2026:4" for v in s.verwijzingen), "het eigen kenmerk telt niet"


def test_rijen_zijn_letterlijk_en_genummerd():
    s = lees_publicatie(_item(22819))
    assert [r.nr for r in s.rijen] == list(range(1, len(s.rijen) + 1))
    assert any(r.tekst == "Ja, de aangifte kan worden ingediend." for r in s.rijen)
    assert all("\xa0" not in r.tekst and "  " not in r.tekst for r in s.rijen)
    assert s.bron_hash == lees_publicatie(_item(22819)).bron_hash and len(s.bron_hash) == 64


def test_ingetrokken_en_vervallen():
    assert lees_publicatie(_item(4785)).status == "ingetrokken"
    assert lees_publicatie(_item(586)).status == "vervallen"


def test_tabel_en_voetnoten():
    s = lees_publicatie(_item(8488))
    tabel = [r for r in s.rijen if r.soort == "tabel"]
    assert len(tabel) == 1 and tabel[0].cellen == ("Vervreemdingsverbod", "Marginale afwaardering", "Cumulatieve afwaardering")
    rijen = [r for r in s.rijen if r.soort == "tabelrij"]
    assert rijen[0].cellen == ("1 volledig jaar", "5,5%", "5,5%") and all(r.tabel == 1 for r in rijen)
    voetnoten = [r for r in s.rijen if r.soort == "voetnoot"]
    assert len(voetnoten) == 3 and all(r.kop == "Voetnoten" for r in voetnoten)
    # Een jci in een voetnoot is een bepaling met de link als herkomst; z en g (de versie) vallen weg.
    bepaling = next(v for v in s.verwijzingen if v.soort == "bepaling" and v.bwb_id == "BWBR0002471"
                    and ("artikel", "13") in v.delen)
    assert bepaling.herkomst == "link" and bepaling.doel == "jci1.3:c:BWBR0002471&hoofdstuk=II&artikel=13"
    assert bepaling.rij == voetnoten[0].nr


def test_jci_tot_op_het_lid():
    s = lees_publicatie(_item(14091))
    leden = [v for v in s.verwijzingen if v.soort == "bepaling" and any(k == "lid" for k, _ in v.delen)]
    assert leden and all(v.doel.startswith("jci1.3:c:BWB") and "&lid=" in v.doel for v in leden)


def test_koppen_volgen_de_hierarchie():
    s = lees_publicatie(_item(5450))
    diep = [r.kop for r in s.rijen if r.kop.count(" › ") >= 1]
    assert diep, "een h3 hoort onder zijn h2"
    assert all(k.split(" › ")[0] in {"Aanleiding", "Vraag", "Vragen", "Antwoord", "Antwoorden", "Beschouwing", "Conclusie"}
               for k in diep)


def test_metadata_in_de_vaste_sleutels():
    s = lees_publicatie(_item(22819))
    m = s.metadata
    assert set(m) - {"bron"} <= set(METADATA_SLEUTELS), set(m) - set(METADATA_SLEUTELS)
    assert m["orgaan"] == "KG Auto (A)" and m["soort"] == "Standpunt"
    assert m["datum"] == m["gepubliceerd"] == "2026-11-12" and "vastgesteld" not in m
    assert "Belasting van personenauto's en motorrijwielen (BPM)" in m["rechtsgebied"]
    assert m["reeks"] == ["Aangiftebelastingen", "Afschrijving", "Belastingvermindering", "Waarde"]
    assert (m["nummer"], m["jaar"], m["status"], m["leesbaar"]) == ("4", "2026", "geldend", True)
    assert m["vervangt"] == ["kg:013:2018:173"]
    assert {"soort": "uitspraak", "id": "ECLI:NL:HR:2013:64", "herkomst": "link"} in [
        {k: n[k] for k in ("soort", "id", "herkomst")} for n in m["noemt"]]
    bron = m["bron"]
    assert bron["kennisgroepen"] == ["KG Auto (A)"] and bron["middelen"] == ["Autobelastingen"]
    assert bron["rubrieken"] and bron["subrubrieken"] == ["Waarde"] and bron["kennisgroep_ids"] == [155]
    for n in m["noemt"]:
        assert n["soort"] in BRONTYPEN or n["soort"] in {"bepaling", "regeling", "publicatie"}


def test_vaststellingsdatum_wint_van_de_publicatiedatum():
    m = lees_publicatie(_item(777)).metadata
    assert m["vastgesteld"] and m["datum"] == m["vastgesteld"] and m["gepubliceerd"] >= m["vastgesteld"]


def test_bijlagen():
    m = lees_publicatie(_item(20766)).metadata
    assert m["bijlagen"] and all(b.startswith("https://") for b in m["bijlagen"])


def test_een_nieuwsbericht_is_een_gebeurtenis():
    g = lees_bericht(json.loads((DATA / "bericht-22821.json").read_text(encoding="utf-8")))
    assert g.soort == "geactualiseerd" and g.datum == "2026-11-12"
    assert g.publicaties == ("kg01320264-aangifte-bpm-voor-afronding-onderzoek-rdw",)
    assert g.kenmerken == ("kg:013:2018:173",)


def test_urls():
    assert lijst_url(2).startswith("https://kennisgroepen.belastingdienst.nl/wp-json/wp/v2/wt_publication?_embed=1")
    assert "modified_after=2026-11-01T00%3A00%3A00" in lijst_url(1, gewijzigd_na="2026-11-01T00:00:00")
    assert "/posts?" in lijst_url(1, soort="posts")
    assert item_url(22819) == "https://kennisgroepen.belastingdienst.nl/wp-json/wp/v2/wt_publication/22819?_embed=1"


def test_lege_of_rare_html():
    assert rijen_uit_html("") == []
    rijen = rijen_uit_html("<h2>Vraag</h2><p>Een <b>vraag</b>?<br>Ja.</p><script>x()</script><ul><li><p>a</p></li></ul>")
    assert [(r.kop, r.tekst) for r in rijen] == [("Vraag", "Een vraag? Ja."), ("Vraag", "a")]
