"""De gedeelde PDF-opmaak: kop- en voetregel, metadata en kleurcontrast. De inhoud van de exports toetsen hun eigen tests."""
from __future__ import annotations

import re

import pytest

from app import pdf_opmaak
from app.jas_klassen import JAS_KLASSE_KLEUREN, JAS_TEKSTKLEUR


def _luminantie(kleur: str) -> float:
    def kanaal(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(kleur.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * kanaal(r) + 0.7152 * kanaal(g) + 0.0722 * kanaal(b)


def _contrast(voor: str, achter: str) -> float:
    a, b = sorted((_luminantie(voor), _luminantie(achter)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@pytest.mark.parametrize("naam", sorted(pdf_opmaak.KLEURPAREN))
def test_elke_tekstkleur_haalt_wcag_aa_op_haar_achtergrond(naam):
    voor, achter = pdf_opmaak.KLEURPAREN[naam]
    assert _contrast(voor, achter) >= 4.5, naam


@pytest.mark.parametrize("klasse", sorted(JAS_KLASSE_KLEUREN))
def test_de_kop_van_een_markering_is_leesbaar_op_haar_klassekleur(klasse):
    assert _contrast(JAS_TEKSTKLEUR, JAS_KLASSE_KLEUREN[klasse][0]) >= 4.5, klasse


def _regels(n: int = 60) -> list[tuple[str, str]]:
    return [("Title", "Rapport"), (pdf_opmaak.PAGINA, ""), (pdf_opmaak.INHOUD, ""), (pdf_opmaak.PAGINA, ""),
            ("Heading1", "1. Eerste"), *[("BodyText", f"Alinea {i} " + "tekst " * 60) for i in range(n)],
            (pdf_opmaak.PAGINA, ""), ("Heading1", "2. Tweede"), ("Citaat", "Een citaat"), ("Waarschuwing", "Pas op")]


def test_kopregel_vanaf_pagina_twee_met_het_lopende_hoofdstuk_en_een_voetregel_op_elke_pagina():
    paginas: list[dict] = []
    pdf = pdf_opmaak.render(_regels(), titel="Mijn werkgebied", voet="Werkgebiedrapport", paginas=paginas)
    assert paginas[0]["kopregel"] == ""                            # de eerste pagina heeft geen kopregel
    assert all(p["kopregel"].startswith("Mijn werkgebied") for p in paginas[1:])
    assert paginas[-1]["kopregel"] == "Mijn werkgebied · 2. Tweede"
    assert any(p["kopregel"] == "Mijn werkgebied · 1. Eerste" for p in paginas)
    assert all(p["voetregel"] == "Werkgebiedrapport" for p in paginas)
    assert len(paginas) == pdf_opmaak.aantal_paginas(pdf)


def test_de_voetregel_noemt_het_totaal():
    paginas: list[dict] = []
    pdf = pdf_opmaak.render(_regels(), titel="T", voet="V", paginas=paginas)
    assert {p["totaal"] for p in paginas} == {pdf_opmaak.aantal_paginas(pdf)}


def test_het_document_draagt_taal_titel_en_metadata():
    pdf = pdf_opmaak.render(_regels(3), titel="Mijn werkgebied", voet="V", onderwerp="Wetsanalyse", auteur="jurist-a",
                            trefwoorden="BWBR0004770")
    assert b"/Lang (nl-NL)" in pdf
    assert re.search(rb"/DisplayDocTitle\s+true", pdf)
    assert b"/Outlines" in pdf
    assert b"/Title (Mijn werkgebied)" in pdf and b"/Author (jurist-a)" in pdf and b"/Subject (Wetsanalyse)" in pdf
    assert b"/Keywords (BWBR0004770)" in pdf
    assert not re.search(rb"/BaseFont\s*/(Helvetica|Times|Courier)", pdf)   # alleen ingesloten letters


def test_een_lang_citaat_breekt_over_een_pagina_en_houdt_zijn_lijn():
    spoor: list[dict] = []
    pdf_opmaak.render([("Citaat", "woord " * 3000)], spoor=spoor)
    citaten = [r for r in spoor if r["stijl"] == "Citaat"]
    assert len({r["pagina"] for r in citaten}) > 1


def test_een_kop_of_voetregel_met_een_teken_buiten_fira_geeft_geen_blokje():
    assert pdf_opmaak.opgemaakt_plat("a b") in ("a b", "a b")
    assert "■" not in pdf_opmaak.opgemaakt_plat("ā – ő")


def test_het_merk_op_het_titelblad_is_het_beeldmerk_uit_de_frontend():
    import xml.etree.ElementTree as ET
    from pathlib import Path
    svg = ET.parse(Path(__file__).parents[2] / "frontend" / "merk" / "lex-merk.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    rechthoeken = []
    for el in svg.iter():
        if el.tag != ns + "rect":
            continue
        groep = next((g for g in svg.iter(ns + "g") if el in list(g)), None)
        rol = (el.get("class") or (groep.get("class") if groep is not None else "")).strip()
        kleur = el.get("fill") or (groep.get("fill") if groep is not None else "")
        rechthoeken.append((rol, int(el.get("x", 0)), int(el.get("y", 0)), int(el.get("width")), int(el.get("height")), kleur.upper()))
    assert sorted(rechthoeken) == sorted((r, x, y, w, h, k.upper()) for r, x, y, w, h, k in pdf_opmaak.MERK)


def _met_titelblad(n: int = 3) -> list[tuple[str, str]]:
    T = pdf_opmaak.TITELBLAD
    return [(T + "titel", "Mijn werkgebied"), (T + "soort", "Wetsanalyse"), (T + "vraag", "Wat mag de ontvanger?"),
            (T + "rij", "Status: Actief"), (T + "rij", "Kenmerk: WG-1"), (T + "regelingen", "Regelingen: Iw 1990"),
            (T + "voetnoot", "Geen oordeel."), (pdf_opmaak.PAGINA, ""), ("Heading4", "Colofon"),
            (pdf_opmaak.PAGINA, ""), ("Heading1", "1. Eerste"), *[("BodyText", "tekst " * 80) for _ in range(n)]]


def test_het_titelblad_is_pagina_een_zonder_kop_en_voetregel():
    paginas: list[dict] = []
    spoor: list[dict] = []
    pdf_opmaak.render(_met_titelblad(), titel="Mijn werkgebied", voet="Werkgebiedrapport", paginas=paginas, spoor=spoor)
    assert paginas[0] == {"pagina": 1, "kopregel": "", "voetregel": "", "titelblad": True, "totaal": len(paginas)}
    assert not any(p["titelblad"] for p in paginas[1:]) and all(p["voetregel"] == "Werkgebiedrapport" for p in paginas[1:])
    # Niets van de lopende tekst staat op het titelblad: het colofon begint bovenaan pagina 2.
    assert min(r["pagina"] for r in spoor) == 2 and spoor[0]["bovenaan"]


def test_het_titelblad_staat_in_de_bladwijzers():
    pdf = pdf_opmaak.render(_met_titelblad(1), titel="T")
    assert b"(Titelblad)" in pdf


def test_zonder_titelblad_blijft_de_eerste_pagina_gewone_tekst():
    paginas: list[dict] = []
    pdf_opmaak.render([("Heading1", "Een")], paginas=paginas)
    assert paginas == [{"pagina": 1, "kopregel": "", "voetregel": "", "titelblad": False, "totaal": 1}]
