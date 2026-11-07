"""De opmaak van de PDF's: lettertypen, stijlen en het omzetten van (stijl, tekst)-regels in een bestand.

De exports leveren hun inhoud als regels (`annotatie_export.pdf_regels`, `werkgebied_rapport.rapport_regels`), zodat die
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
LINTBLAUW = "#154273"
TEKST = "#1A1A1A"
GRIJS = "#535353"
ROOD = "#A1132B"
LET_OP_VLAK = "#FBEAEC"
LET_OP_TEKST = "#6E0A1C"
HAARLIJN = "#B4C3D3"
KLEURPAREN = {"tekst": (TEKST, "#FFFFFF"), "meta": (GRIJS, "#FFFFFF"), "koppen": (LINTBLAUW, "#FFFFFF"),
              "let op": (LET_OP_TEKST, LET_OP_VLAK)}
"""Elke tekstkleur op haar achtergrond; een test eist WCAG AA (4,5:1). De JAS-kleuren toetst hij met `JAS_TEKSTKLEUR`."""

MARKERING = "Markering:"
"""Voorvoegsel van een stijl: `Markering:<JAS-klasse>` is de kop van een markering in de kleur van die klasse."""
PAGINA = "Pagina"
"""Een regel met deze stijl begint een nieuwe pagina. Staat de pagina nog leeg, dan gebeurt er niets: nooit een blanke pagina."""
INHOUD = "Inhoud"
"""Een regel met deze stijl is de plek van de inhoudsopgave."""
BLOK_BEGIN, BLOK_EIND = "BlokBegin", "BlokEind"
"""De regels ertussen blijven op één pagina, als dat past. Past het niet, dan lopen ze gewoon door."""
PLAATS = "Plaats"
"""De plaats in de opbouw ("Hoofdstuk 2 – … › § 3 – …") boven een artikel. Ook de kopregel toont hem, tot het volgende hoofdstuk."""
BEGRIP = "Begrip"
"""De kop van een begrip: die van `Heading3`, maar wel in de inhoudsopgave. Een begrip heeft een eigen pagina."""

TITELBLAD = "Titelblad:"
"""Voorvoegsel: `Titelblad:<veld>` is een veld van het titelblad (`soort`, `titel`, `vraag`, `rij`, `regelingen`, `voetnoot`).
Staan zulke regels vooraan, dan worden ze op pagina 1 getekend, zonder kop- en voetregel. Een `rij` is "Label: waarde"."""
TITELBLAD_VELDEN = ("soort", "titel", "vraag", "rij", "regelingen", "voetnoot")

MERK = (("vlak", 0, 0, 32, 32, LINTBLAUW), ("vorm", 6, 6, 20, 4, "#FFFFFF"), ("vorm", 6, 14, 6, 4, "#FFFFFF"),
        ("vorm", 6, 22, 14, 4, "#FFFFFF"), ("markering", 16, 14, 10, 4, "#FFD84D"))
"""Het Lex-beeldmerk op een raster van 32, zoals `frontend/merk/lex-merk.svg`; een test vergelijkt beide."""
STATUSVLAK = "#E8EEF5"

_NIVEAU = {"Heading1": 0, "Heading2": 1, "Heading3": 2, BEGRIP: 2}
_IN_INHOUD = 2                                 # koppen boven dit niveau staan in de inhoudsopgave, plus elk begrip


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

    basis = ParagraphStyle("BodyText", fontName="Fira", fontSize=10, leading=14, spaceAfter=5, textColor=HexColor(TEKST))
    meta = ParagraphStyle("Meta", parent=basis, fontSize=8.5, leading=11.5, textColor=HexColor(GRIJS), spaceAfter=4)
    kop = dict(parent=basis, fontName="Fira-SemiBold", textColor=HexColor(LINTBLAUW), keepWithNext=1)
    uit = {"BodyText": basis, "Meta": meta,
           "Title": ParagraphStyle("Title", **kop, fontSize=24, leading=29, spaceAfter=12),
           "Subtitle": ParagraphStyle("Subtitle", parent=basis, fontSize=13, leading=18, spaceAfter=14, textColor=HexColor(GRIJS)),
           "Heading1": ParagraphStyle("Heading1", **kop, fontSize=18, leading=23, spaceAfter=12),
           "Heading2": ParagraphStyle("Heading2", **kop, fontSize=13.5, leading=18, spaceBefore=14, spaceAfter=6),
           "Heading3": ParagraphStyle("Heading3", **kop, fontSize=11.5, leading=15, spaceBefore=12, spaceAfter=4),
           BEGRIP: ParagraphStyle(BEGRIP, **kop, fontSize=11.5, leading=15, spaceBefore=12, spaceAfter=4),
           "Heading4": ParagraphStyle("Heading4", **kop, fontSize=10, leading=14, spaceBefore=8, spaceAfter=3),
           # De lijn links tekent `_Lijn`; de inspringing maakt er ruimte voor.
           "Citaat": ParagraphStyle("Citaat", parent=basis, leftIndent=12, spaceBefore=2, spaceAfter=7),
           # Een kader in plaats van vette rode tekst: opvallend, maar het overheerst de pagina niet.
           "Waarschuwing": ParagraphStyle("Waarschuwing", parent=basis, fontSize=9.5, leading=13, textColor=HexColor(LET_OP_TEKST),
                                          backColor=HexColor(LET_OP_VLAK), borderColor=HexColor(ROOD), borderWidth=0.6,
                                          borderPadding=(5, 7, 5, 7), borderRadius=2, leftIndent=7, rightIndent=7,
                                          spaceBefore=9, spaceAfter=11),
           PLAATS: ParagraphStyle(PLAATS, parent=basis, fontName="Fira-SemiBold", fontSize=8.5, leading=11.5, textColor=HexColor(GRIJS),
                                  spaceBefore=12, spaceAfter=0, keepWithNext=1),
           "Voorstel": ParagraphStyle("Voorstel", parent=basis, fontName="Fira-Italic", textColor=HexColor(GRIJS)),
           "Code": ParagraphStyle("Code", parent=basis, fontName="DejaVu-Mono", fontSize=7.5, leading=10),
           "Markering": ParagraphStyle("Markering", parent=basis, fontName="Fira-SemiBold", fontSize=9.5, leading=13,
                                       borderPadding=(2, 4, 2, 4), spaceBefore=8, spaceAfter=6, keepWithNext=1,
                                       textColor=HexColor(JAS_TEKSTKLEUR))}
    for klasse, (kleur, _rand) in JAS_KLASSE_KLEUREN.items():
        uit[MARKERING + klasse] = ParagraphStyle(klasse, parent=uit["Markering"], backColor=HexColor(kleur))
    return uit


def render(regels: list[tuple[str, str]], titel: str = "", voet: str = "", spoor: list[dict] | None = None, *,
           onderwerp: str = "", auteur: str = "Lex", trefwoorden: str = "", paginas: list[dict] | None = None) -> bytes:
    """De regels als PDF. Met een `INHOUD`-regel een inhoudsopgave; koppen worden altijd bladwijzers.

    Elke pagina behalve de eerste krijgt een kopregel (`titel` links, het lopende hoofdstuk rechts) en elke pagina een
    voetregel (`voet` links, "Pagina n van N" rechts). Het document draagt taal en titel (`/Lang`, `DisplayDocTitle`).

    `spoor` krijgt per alinea `{pagina, stijl, tekst, bovenaan, inhoud}`, van de laatste zetronde: zo is de opbouw van de
    pagina's te toetsen zonder de PDF terug te lezen (`tekst` en `inhoud` alleen bij een kop). `paginas` krijgt per
    pagina `{pagina, kopregel, voetregel}`."""
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate, PageBreak, PageBreakIfNotEmpty,
                                    PageTemplate, Paragraph, TableStyle)
    from reportlab.platypus.tableofcontents import TableOfContents

    _registreer()
    stijlen = _stijlen()
    verhaal: list = []
    teller = {"kop": 0}
    links, rechts, boven, onder = 25 * mm, 20 * mm, 25 * mm, 20 * mm

    class Kop(Paragraph):
        """Een kop die bij het zetten zijn plek doorgeeft aan bladwijzers, inhoudsopgave en kopregel."""

        def __init__(self, tekst, stijl, platte_tekst, niveau, in_inhoud):
            super().__init__(tekst, stijl)
            self.platte_tekst, self.niveau, self.in_inhoud = platte_tekst, niveau, in_inhoud
            teller["kop"] += 1
            self.sleutel = f"kop-{teller['kop']}"

    class Lijn(Flowable):
        """Een citaat met een lintblauwe lijn links, ook als het over een pagina breekt."""

        def __init__(self, alinea):
            super().__init__()
            self.alinea = alinea
            self.style = alinea.style                    # voor het spoor en voor de ruimte ervoor en erna

        def wrap(self, breedte, hoogte):
            self.breedte, self.hoogte = self.alinea.wrap(breedte, hoogte)
            return self.breedte, self.hoogte

        def split(self, breedte, hoogte):
            return [Lijn(d) for d in self.alinea.split(breedte, hoogte)]

        def getSpaceBefore(self):
            return self.alinea.getSpaceBefore()

        def getSpaceAfter(self):
            return self.alinea.getSpaceAfter()

        def draw(self):
            self.canv.saveState()
            self.canv.setStrokeColor(HexColor(LINTBLAUW))
            self.canv.setLineWidth(2)
            self.canv.line(1, 0, 1, self.hoogte)
            self.canv.restoreState()
            self.alinea.drawOn(self.canv, 0, 0)

    blad = [(stijl.removeprefix(TITELBLAD), tekst) for stijl, tekst in regels if stijl.startswith(TITELBLAD)]
    regels = [(stijl, tekst) for stijl, tekst in regels if not stijl.startswith(TITELBLAD)]

    def titelblad(canvas, doc):
        """Pagina 1: merk, titel, vraag en een statusblok, op vaste plekken. Geen kop- of voetregel."""
        breedte, hoogte = A4
        canvas.saveState()
        canvas._zonder_voet = True
        canvas.setFillColor(HexColor(LINTBLAUW))
        canvas.rect(0, hoogte - 6 * mm, breedte, 6 * mm, stroke=0, fill=1)
        maat, x0, y0 = 13 * mm / 32, links, hoogte - 22 * mm
        for _rol, x, y, w, h, kleur in MERK:
            canvas.setFillColor(HexColor(kleur))
            if _rol == "vlak":
                canvas.roundRect(x0, y0 - 32 * maat, w * maat, h * maat, 7 * maat, stroke=0, fill=1)
            else:
                canvas.rect(x0 + x * maat, y0 - (y + h) * maat, w * maat, h * maat, stroke=0, fill=1)
        canvas.setFont("Fira-SemiBold", 11)
        canvas.setFillColor(HexColor(LINTBLAUW))
        canvas.drawString(x0 + 17 * mm, y0 - 8.5 * mm, "Lex · Wetsanalyse")

        tekstbreedte = breedte - links - rechts
        y = hoogte - 90 * mm
        velden: dict[str, list[str]] = {}
        for veld, tekst in blad:
            velden.setdefault(veld, []).append(tekst)

        def alinea(tekst, stijl, y):
            p = Paragraph(opgemaakt(tekst), stijl)
            _w, h = p.wrap(tekstbreedte, hoogte)
            p.drawOn(canvas, links, y - h)
            return y - h

        for t in velden.get("soort", []):
            y = alinea(t.upper(), ParagraphStyle("Soort", fontName="Fira-SemiBold", fontSize=9, leading=12,
                                                 textColor=HexColor(GRIJS)), y) - 4 * mm
        for t in velden.get("titel", []):
            y = alinea(t, ParagraphStyle("Titelbladtitel", fontName="Fira-SemiBold", fontSize=26, leading=31,
                                         textColor=HexColor(LINTBLAUW)), y) - 4 * mm
        canvas.setStrokeColor(HexColor(LINTBLAUW))
        canvas.setLineWidth(2)
        canvas.line(links, y, links + 20 * mm, y)
        y -= 8 * mm
        for t in velden.get("vraag", []):
            y = alinea(t, ParagraphStyle("Titelbladvraag", fontName="Fira", fontSize=11.5, leading=16,
                                         textColor=HexColor(GRIJS)), y) - 10 * mm

        rijen = [r.split(": ", 1) if ": " in r else (r, "") for r in velden.get("rij", [])]
        if rijen:
            regelhoogte = 6.2 * mm
            blokhoogte = len(rijen) * regelhoogte + 8 * mm
            y = min(y, 120 * mm)
            canvas.setFillColor(HexColor(STATUSVLAK))
            canvas.rect(links, y - blokhoogte, tekstbreedte, blokhoogte, stroke=0, fill=1)
            ry = y - 4 * mm - 4.2 * mm
            for label, waarde in rijen:
                canvas.setFillColor(HexColor(GRIJS))
                canvas.setFont("Fira-SemiBold", 9)
                canvas.drawString(links + 6 * mm, ry, opgemaakt_plat(label))
                canvas.setFillColor(HexColor(TEKST))
                canvas.setFont("Fira", 9.5)
                canvas.drawString(links + 36 * mm, ry, opgemaakt_plat(waarde)[:95])
                ry -= regelhoogte
            y -= blokhoogte + 8 * mm
        for t in velden.get("regelingen", []):
            y = alinea(t, ParagraphStyle("Titelbladregelingen", fontName="Fira", fontSize=9, leading=13,
                                         textColor=HexColor(GRIJS)), y) - 4 * mm
        for t in velden.get("voetnoot", []):
            p = Paragraph(opgemaakt(t), ParagraphStyle("Titelbladvoet", fontName="Fira", fontSize=8, leading=11,
                                                       textColor=HexColor(GRIJS)))
            _w, h = p.wrap(tekstbreedte, hoogte)
            p.drawOn(canvas, links, 18 * mm)
        canvas.restoreState()
        if paginas is not None:
            paginas.append({"pagina": doc.page, "kopregel": "", "voetregel": "", "titelblad": True})

    def kader(canvas, doc):
        """Kop- en voetregel; de voetregel krijgt zijn totaal pas bij het opslaan (`Teller`)."""
        canvas._zonder_voet = False
        canvas.saveState()
        kopregel = ""
        if doc.page > 1:
            kopregel = " · ".join(filter(None, [titel[:70], doc.hoofdstuk, doc.plaats]))
            canvas.setFont("Fira", 8)
            canvas.setFillColor(HexColor(GRIJS))
            # Met een plaats in de opbouw schuiven titel en hoofdstuk een regel omhoog; de plaats staat vlak boven de lijn.
            hoogte = A4[1] - (10.5 if doc.plaats else 14) * mm
            canvas.drawString(links, hoogte, opgemaakt_plat(titel[:70]))
            canvas.drawRightString(A4[0] - rechts, hoogte, opgemaakt_plat(doc.hoofdstuk[:70]))
            if doc.plaats:
                canvas.drawRightString(A4[0] - rechts, A4[1] - 14 * mm, opgemaakt_plat(doc.plaats[:110]))
            canvas.setStrokeColor(HexColor(HAARLIJN))
            canvas.setLineWidth(0.5)
            canvas.line(links, A4[1] - 16 * mm, A4[0] - rechts, A4[1] - 16 * mm)
        canvas.setStrokeColor(HexColor(HAARLIJN))
        canvas.setLineWidth(0.5)
        canvas.line(links, 14 * mm, A4[0] - rechts, 14 * mm)
        canvas.setFont("Fira", 8)
        canvas.setFillColor(HexColor(GRIJS))
        canvas.drawString(links, 10 * mm, opgemaakt_plat(voet[:100]))
        canvas.restoreState()
        if paginas is not None:
            paginas.append({"pagina": doc.page, "kopregel": kopregel, "voetregel": voet[:100], "titelblad": False})

    class Teller(Canvas):
        """Schrijft "Pagina n van N": het totaal is pas bekend als alle pagina's gezet zijn."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._standen: list[dict] = []

        def showPage(self):
            self._standen.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            totaal = len(self._standen)
            for p in paginas or []:
                p["totaal"] = totaal
            for stand in self._standen:
                self.__dict__.update(stand)
                if getattr(self, "_zonder_voet", False):
                    super().showPage()
                    continue
                self.saveState()
                self.setFont("Fira", 8)
                self.setFillColor(HexColor(GRIJS))
                self.drawRightString(A4[0] - rechts, 10 * mm, f"Pagina {self._pageNumber} van {totaal}")
                self.restoreState()
                super().showPage()
            super().save()

    class Document(BaseDocTemplate):
        def beforeDocument(self):                  # `multiBuild` zet meer dan eens: het spoor is van de laatste ronde
            self.hoofdstuk, self.plaats = "", ""
            if spoor is not None:
                spoor.clear()
            if paginas is not None:
                paginas.clear()

        def beforePage(self):
            self.leeg = True

        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph) and flowable.style.name == PLAATS:
                self.plaats = flowable.platte_plaats
            if spoor is not None and isinstance(flowable, (Paragraph, Lijn)):
                kop = isinstance(flowable, Kop)
                spoor.append({"pagina": self.page, "stijl": flowable.style.name, "bovenaan": self.leeg,
                              "tekst": flowable.platte_tekst if kop else "", "inhoud": kop and flowable.in_inhoud})
                self.leeg = False
            if not isinstance(flowable, Kop):
                return
            if flowable.niveau == 0:
                self.hoofdstuk, self.plaats = flowable.platte_tekst, ""
            elif flowable.niveau == 1:
                self.plaats = ""
            self.canv.bookmarkPage(flowable.sleutel)
            self.canv.addOutlineEntry(flowable.platte_tekst, flowable.sleutel, flowable.niveau, closed=flowable.niveau > 0)
            if flowable.in_inhoud:
                self.notify("TOCEntry", (flowable.niveau, flowable.platte_tekst, self.page, flowable.sleutel))

    class _Bladwijzer(Flowable):
        """Een bladwijzer zonder tekst op de pagina: het titelblad staat zo ook in het overzicht."""

        def __init__(self, naam):
            super().__init__()
            self.naam = naam

        def wrap(self, *_):
            return 0, 0

        def draw(self):
            self.canv.bookmarkPage("titelblad")
            self.canv.addOutlineEntry(self.naam, "titelblad", 0, closed=False)

    heeft_inhoud, laatste, blok = False, -1, None
    for stijl, tekst in regels:
        doel = verhaal if blok is None else blok
        if stijl == BLOK_BEGIN:
            blok = []
        elif stijl == BLOK_EIND:
            verhaal.append(KeepTogether(blok))
            blok = None
        elif stijl == PAGINA:
            doel.append(PageBreakIfNotEmpty())
        elif stijl == INHOUD:
            heeft_inhoud = True
            # De standaardtabelstijl zet Helvetica op elke cel: een niet-ingesloten letter in een verder ingesloten document.
            inhoud = TableOfContents(dotsMinLevel=0, tableStyle=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("FONTNAME", (0, 0), (-1, -1), "Fira")]))
            inhoud.levelStyles = [
                ParagraphStyle("Inhoud0", parent=stijlen["BodyText"], fontName="Fira-SemiBold", spaceBefore=7, spaceAfter=2,
                               textColor=HexColor(LINTBLAUW)),
                ParagraphStyle("Inhoud1", parent=stijlen["BodyText"], leftIndent=14, spaceAfter=1),
                ParagraphStyle("Inhoud2", parent=stijlen["BodyText"], leftIndent=28, spaceAfter=0, textColor=HexColor(GRIJS))]
            doel.append(inhoud)
        elif stijl in _NIVEAU:
            # Een bladwijzer mag maar één niveau dieper dan de vorige: een kop zonder bovenliggende kop schuift op.
            laatste = min(_NIVEAU[stijl], laatste + 1)
            doel.append(Kop(opgemaakt(tekst), stijlen[stijl], tekst, laatste, laatste < _IN_INHOUD or stijl == BEGRIP))
        elif stijl == PLAATS:
            alinea = Paragraph(opgemaakt(tekst), stijlen[PLAATS])
            alinea.platte_plaats = tekst
            doel.append(alinea)
        elif stijl == "Citaat":
            doel.append(Lijn(Paragraph(opgemaakt(tekst), stijlen["Citaat"])))
        elif stijl == "Waarschuwing":
            doel.append(Paragraph('<font name="Fira-SemiBold">Let op: </font>' + opgemaakt(tekst), stijlen["Waarschuwing"]))
        else:
            doel.append(Paragraph(opgemaakt(tekst), stijlen[stijl] if stijl in stijlen else stijlen["Markering"]))

    output = io.BytesIO()
    doc = Document(output, pagesize=A4, title=titel, author=auteur, subject=onderwerp, keywords=trefwoorden,
                   creator="Lex – wetsanalyseplatform", lang="nl-NL", displayDocTitle=True, initialFontName="Fira",
                   leftMargin=links, rightMargin=rechts, topMargin=boven, bottomMargin=onder)
    sjablonen = [PageTemplate(id="pagina", onPageEnd=kader, frames=[
        Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="tekst")])]
    if blad:
        # Het titelblad is een eigen sjabloon met een leeg kader: alles erop tekent `titelblad`.
        sjablonen.insert(0, PageTemplate(id="titelblad", onPage=titelblad, frames=[
            Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="blad")]))
        verhaal[:0] = [NextPageTemplate("pagina"), _Bladwijzer("Titelblad"), PageBreak()]
    doc.addPageTemplates(sjablonen)
    if heeft_inhoud:
        doc.multiBuild(verhaal, canvasmaker=Teller)
    else:
        doc.build(verhaal, canvasmaker=Teller)
    return output.getvalue()


def opgemaakt_plat(tekst: str) -> str:
    """Tekst voor het canvas (kop- en voetregel): geen opmaak, en wat Fira niet heeft wordt een spatie in plaats van een ■."""
    from reportlab.pdfbase import pdfmetrics
    _registreer()
    heeft = pdfmetrics.getFont("Fira").face.charToGlyph
    return "".join(c if ord(c) < 128 or ord(c) in heeft else " " for c in tekst)


def aantal_paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))
