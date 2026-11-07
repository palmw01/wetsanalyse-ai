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
    assert {k: paginas[0][k] for k in ("pagina", "kopregel", "voetregel", "titelblad", "totaal")} == {
        "pagina": 1, "kopregel": "", "voetregel": "", "titelblad": True, "totaal": len(paginas)}
    assert not any(p["titelblad"] for p in paginas[1:]) and all(p["voetregel"] == "Werkgebiedrapport" for p in paginas[1:])
    # Niets van de lopende tekst staat op het titelblad: het colofon begint bovenaan pagina 2.
    assert min(r["pagina"] for r in spoor) == 2 and spoor[0]["bovenaan"]


def test_het_titelblad_staat_in_de_bladwijzers():
    pdf = pdf_opmaak.render(_met_titelblad(1), titel="T")
    assert b"(Titelblad)" in pdf


def test_zonder_titelblad_blijft_de_eerste_pagina_gewone_tekst():
    paginas: list[dict] = []
    pdf_opmaak.render([("Heading1", "Een")], paginas=paginas)
    assert [{k: p[k] for k in ("pagina", "kopregel", "voetregel", "titelblad", "totaal")} for p in paginas] == [
        {"pagina": 1, "kopregel": "", "voetregel": "", "titelblad": False, "totaal": 1}]



_LANG = ("Wet " + "bijzonder-lange-samenstelling-zonder-spaties-" * 4 + " en nog " + "heel veel woorden " * 40).strip()


def _extreem() -> list[tuple[str, str]]:
    T = pdf_opmaak.TITELBLAD
    return [(T + "titel", "Een uitzonderlijk lange titel van een werkgebied " * 8), (T + "soort", "Wetsanalyse · rapport " * 6),
            (T + "vraag", "Wat zijn de rechten en plichten van alle betrokkenen? " * 40),
            (T + "rij", "Status: In voorbereiding · concept"), (T + "rij", "Peildatum: 5 november 2026 " + "(een lange toelichting) " * 12),
            (T + "rij", "Thema: " + _LANG), (T + "rij", "Inhoudscode: 0123456789ab"),
            (T + "regelingen", "Regelingen: " + " · ".join(f"Een lange citeertitel van regeling {i}" for i in range(30))),
            (T + "voetnoot", "Een analyse-uitkomst, geen juridisch oordeel."),
            (pdf_opmaak.PAGINA, ""), ("Heading1", "1. " + "Een heel lang hoofdstuk " * 10),
            (pdf_opmaak.PLAATS, "Hoofdstuk 2 – " + "Een lange titel " * 20), ("BodyText", "tekst")]


def test_niets_op_het_titelblad_valt_buiten_de_marges_of_over_elkaar_en_wat_inkort_zegt_waar_het_staat():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    paginas: list[dict] = []
    pdf_opmaak.render(_extreem(), titel="Een uitzonderlijk lange titel " * 6, voet="Werkgebiedrapport · " * 12, paginas=paginas)
    items = paginas[0]["getekend"]
    links, rechts = 25 * mm, A4[0] - 20 * mm
    for i in items:
        assert i["x"] >= links - 0.5 and i["x"] + i["breedte"] <= rechts + 0.5, i["tekst"][:40]
        assert i["y"] >= 15 * mm and i["y"] + i["hoogte"] <= A4[1] - 6 * mm, i["tekst"][:40]
    # Geen overlap: tekstblokken (buiten het statusvlak, waarin de rijen staan) lopen van boven naar onder zonder elkaar te raken.
    vlak = next(i for i in items if i.get("vlak"))
    los = sorted((i for i in items if not i.get("vlak") and not (vlak["y"] <= i["y"] <= vlak["y"] + vlak["hoogte"])),
                 key=lambda i: -i["y"])
    for boven, onder in zip(los, los[1:]):
        assert onder["y"] + onder["hoogte"] <= boven["y"] + 0.5, (boven["tekst"][:30], onder["tekst"][:30])
    rijen = [i for i in items if not i.get("vlak") and vlak["y"] <= i["y"] <= vlak["y"] + vlak["hoogte"]]
    assert all(vlak["y"] - 0.5 <= i["y"] and i["y"] + i["hoogte"] <= vlak["y"] + vlak["hoogte"] + 0.5 for i in rijen)
    # Ook binnen het vlak: per kolom (labels, waarden met hun noten) raakt niets elkaar.
    for kolom in {round(i["x"]) for i in rijen}:
        stapel = sorted((i for i in rijen if round(i["x"]) == kolom), key=lambda i: -i["y"])
        for boven, onder in zip(stapel, stapel[1:]):
            assert onder["y"] + onder["hoogte"] <= boven["y"] + 0.5, (boven["tekst"][:30], onder["tekst"][:30])
    # Wat is ingekort, eindigt op een ellips en heeft een noot die zegt waar de volledige tekst staat.
    teksten = [i["tekst"] for i in items]
    for n, i in enumerate(items):
        if i["afgekapt"]:
            assert i["tekst"].endswith("…") and items[n + 1]["tekst"].startswith(("De volledige", "Volledig", "Alle regelingen"))
    assert "De volledige titel staat in het colofon." in teksten and "De volledige analysevraag staat in de samenvatting." in teksten
    assert any(t.startswith("In voorbereiding") for t in teksten) and "0123456789ab" in teksten     # korte waarden heel


def test_kop_en_voetregel_kappen_af_op_breedte_met_een_ellips():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    paginas: list[dict] = []
    pdf_opmaak.render(_extreem(), titel="Een uitzonderlijk lange titel " * 6, voet="Werkgebiedrapport · " * 12, paginas=paginas)
    for p in paginas[1:]:
        for i in p["getekend"]:
            assert i["x"] >= 25 * mm - 0.5 and i["x"] + i["breedte"] <= A4[0] - 20 * mm + 0.5, i["tekst"][:40]
        assert p["voetregel"].endswith("…") and p["kopregel"].split(" · ")[0].endswith("…")
    # De voetregel laat ruimte voor "Pagina n van N".
    from reportlab.pdfbase.pdfmetrics import stringWidth
    voet = next(i for i in paginas[1]["getekend"] if i["tekst"] == paginas[1]["voetregel"])
    assert voet["x"] + voet["breedte"] <= A4[0] - 20 * mm - stringWidth("Pagina 999 van 999", "Fira", 8)


def test_een_gewone_titel_wordt_niet_ingekort():
    paginas: list[dict] = []
    pdf_opmaak.render(_met_titelblad(1), titel="Kort", voet="V", paginas=paginas)
    assert not any(i["afgekapt"] for i in paginas[0]["getekend"])
    assert paginas[1]["voetregel"] == "V" and paginas[1]["kopregel"].startswith("Kort")


def test_passend_kort_in_op_een_woordgrens():
    from reportlab.lib.styles import ParagraphStyle
    st = ParagraphStyle("t", fontName="Fira", fontSize=10, leading=14)
    tekst, af = pdf_opmaak.passend("woord " * 200, st, 200, 2)
    assert af and tekst.endswith(" …") and set(tekst[:-2].split()) == {"woord"}
    assert pdf_opmaak.passend("kort", st, 200, 2) == ("kort", False)
