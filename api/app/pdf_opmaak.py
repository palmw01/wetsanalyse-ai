"""De opmaak van de PDF's: lettertypen, stijlen en het omzetten van (stijl, tekst)-regels in een bestand.

De exports leveren hun inhoud als regels (`annotatie_export.pdf_regels`, `werkgebied_export.pdf_regels`), zodat die
zonder reportlab te testen zijn; alles over de vorm staat hier.

**De lettertypen zijn ingesloten.** De standaardletters van een PDF kennen alleen cp1252: een `ā` of een harde
afbreekstreep werd stil een `■`, en dat mag niet in een letterlijk citaat. Fira Sans is de letter van de werkplek;
wat Fira niet heeft, tekent DejaVu per teken (`opgemaakt`). Beide staan in `app/fonts/` met hun licentie, zodat tests
en image hetzelfde tonen.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from .jas_klassen import JAS_KLASSE_KLEUREN, JAS_TEKSTKLEUR

_FONTS = Path(__file__).parent / "fonts"
_LETTERS = {"Fira": "FiraSans-Regular.ttf", "Fira-Italic": "FiraSans-Italic.ttf", "Fira-SemiBold": "FiraSans-SemiBold.ttf",
            "DejaVu": "DejaVuSans.ttf", "DejaVu-Mono": "DejaVuSansMono.ttf"}
_LINTBLAUW = "#154273"
_GRIJS = "#535353"
_ROOD = "#A1132B"

MARKERING = "Markering:"
"""Voorvoegsel van een stijl: `Markering:<JAS-klasse>` is de kop van een markering in de kleur van die klasse."""
PAGINA = "Pagina"
"""Een regel met deze stijl begint een nieuwe pagina."""
INHOUD = "Inhoud"
"""Een regel met deze stijl is de plek van de inhoudsopgave."""

_NIVEAU = {"Heading1": 0, "Heading2": 1, "Heading3": 2}
_IN_INHOUD = 2                                 # koppen tot dit niveau staan in de inhoudsopgave


def _registreer() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for naam, bestand in _LETTERS.items():
        if naam not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(naam, _FONTS / bestand))
    pdfmetrics.registerFontFamily("Fira", normal="Fira", bold="Fira-SemiBold", italic="Fira-Italic",
                                  boldItalic="Fira-SemiBold")


def opgemaakt(tekst: str, *, heeft=None) -> str:
    """De tekst als veilige Paragraph-opmaak: escaped, en wat Fira niet tekent per teken in DejaVu."""
    from reportlab.pdfbase import pdfmetrics
    _registreer()
    heeft = heeft or pdfmetrics.getFont("Fira").face.charToGlyph
    return re.sub(r"[^\x00-\x7f]+", lambda m: "".join(
        c if ord(c) in heeft else f'<font name="DejaVu">{c}</font>' for c in m[0]), escape(tekst))


def _stijlen() -> dict:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle

    basis = ParagraphStyle("BodyText", fontName="Fira", fontSize=10, leading=14, spaceAfter=5, textColor=HexColor("#1A1A1A"))
    meta = ParagraphStyle("Meta", parent=basis, fontSize=8.5, leading=11.5, textColor=HexColor(_GRIJS), spaceAfter=4)
    kop = dict(parent=basis, fontName="Fira-SemiBold", textColor=HexColor(_LINTBLAUW), keepWithNext=1)
    uit = {"BodyText": basis, "Meta": meta,
           "Title": ParagraphStyle("Title", **kop, fontSize=24, leading=29, spaceAfter=12),
           "Subtitle": ParagraphStyle("Subtitle", parent=basis, fontSize=13, leading=18, spaceAfter=14),
           "Heading1": ParagraphStyle("Heading1", **kop, fontSize=18, leading=23, spaceAfter=10),
           "Heading2": ParagraphStyle("Heading2", **kop, fontSize=13.5, leading=18, spaceBefore=13, spaceAfter=6),
           "Heading3": ParagraphStyle("Heading3", **kop, fontSize=11.5, leading=15, spaceBefore=11, spaceAfter=4),
           "Heading4": ParagraphStyle("Heading4", **kop, fontSize=10, leading=14, spaceBefore=7, spaceAfter=3),
           "Citaat": ParagraphStyle("Citaat", parent=basis, leftIndent=11, borderPadding=(0, 0, 0, 7),
                                    fontName="Fira", spaceAfter=5),
           "Waarschuwing": ParagraphStyle("Waarschuwing", parent=basis, fontName="Fira-SemiBold",
                                          textColor=HexColor(_ROOD)),
           "Voorstel": ParagraphStyle("Voorstel", parent=basis, fontName="Fira-Italic"),
           "Code": ParagraphStyle("Code", parent=basis, fontName="DejaVu-Mono", fontSize=7.5, leading=10),
           "Markering": ParagraphStyle("Markering", parent=basis, fontName="Fira-SemiBold", fontSize=9.5, leading=13,
                                       borderPadding=(2, 4, 2, 4), spaceBefore=7, spaceAfter=6, keepWithNext=1,
                                       textColor=HexColor(JAS_TEKSTKLEUR))}
    for klasse, (kleur, _rand) in JAS_KLASSE_KLEUREN.items():
        uit[MARKERING + klasse] = ParagraphStyle(klasse, parent=uit["Markering"], backColor=HexColor(kleur))
    return uit


def render(regels: list[tuple[str, str]], titel: str = "", voet: str = "") -> bytes:
    """De regels als PDF. Met een `INHOUD`-regel een inhoudsopgave; koppen worden altijd bladwijzers."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph
    from reportlab.platypus.tableofcontents import TableOfContents

    _registreer()
    stijlen = _stijlen()
    verhaal: list = []
    teller = {"kop": 0}

    class Kop(Paragraph):
        """Een kop die bij het zetten zijn plek doorgeeft aan bladwijzers en inhoudsopgave."""

        def __init__(self, tekst, stijl, platte_tekst, niveau):
            super().__init__(tekst, stijl)
            self.platte_tekst, self.niveau = platte_tekst, niveau
            teller["kop"] += 1
            self.sleutel = f"kop-{teller['kop']}"

    class Document(BaseDocTemplate):
        def afterFlowable(self, flowable):
            if not isinstance(flowable, Kop):
                return
            self.canv.bookmarkPage(flowable.sleutel)
            self.canv.addOutlineEntry(flowable.platte_tekst, flowable.sleutel, flowable.niveau, closed=flowable.niveau > 0)
            if flowable.niveau < _IN_INHOUD:
                self.notify("TOCEntry", (flowable.niveau, flowable.platte_tekst, self.page, flowable.sleutel))

    heeft_inhoud, laatste = False, -1
    for stijl, tekst in regels:
        if stijl == PAGINA:
            verhaal.append(PageBreak())
        elif stijl == INHOUD:
            heeft_inhoud = True
            inhoud = TableOfContents(dotsMinLevel=0)
            inhoud.levelStyles = [
                ParagraphStyle("Inhoud0", parent=stijlen["BodyText"], fontName="Fira-SemiBold", spaceBefore=6, spaceAfter=2),
                ParagraphStyle("Inhoud1", parent=stijlen["BodyText"], leftIndent=12, spaceAfter=1)]
            verhaal.append(inhoud)
        elif stijl in _NIVEAU:
            # Een bladwijzer mag maar één niveau dieper dan de vorige: een kop zonder bovenliggende kop schuift op.
            laatste = min(_NIVEAU[stijl], laatste + 1)
            verhaal.append(Kop(opgemaakt(tekst), stijlen[stijl], tekst, laatste))
        else:
            verhaal.append(Paragraph(opgemaakt(tekst), stijlen[stijl] if stijl in stijlen else stijlen["Markering"]))

    def voettekst(canvas, doc):
        canvas.saveState()
        canvas.setFont("Fira", 8)
        canvas.setFillColor(HexColor(_GRIJS))
        canvas.drawString(20 * mm, 11 * mm, voet[:110])
        canvas.drawRightString(A4[0] - 20 * mm, 11 * mm, f"Pagina {doc.page}")
        canvas.restoreState()

    output = io.BytesIO()
    doc = Document(output, pagesize=A4, title=titel, author="Lex", leftMargin=20 * mm, rightMargin=20 * mm,
                   topMargin=20 * mm, bottomMargin=20 * mm)
    doc.addPageTemplates(PageTemplate(id="pagina", onPage=voettekst, frames=[
        Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="tekst")]))
    if heeft_inhoud:
        doc.multiBuild(verhaal)
    else:
        doc.build(verhaal)
    return output.getvalue()


def aantal_paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))
