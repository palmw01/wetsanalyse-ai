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
import json
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
SPANS = "Spans"
"""De markeringen in het citaat dat erop volgt: JSON `[[start, eind, nr, klasse], …]`, offsets in codepoints. Geen eigen alinea."""
TOELICHTING = "Toelichting"
"""De toelichting bij een markering: kleiner en ingesprongen, onder haar kop."""
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
           TOELICHTING: ParagraphStyle(TOELICHTING, parent=basis, fontSize=9, leading=12.5, leftIndent=8, spaceAfter=3),
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
    from reportlab.pdfbase.pdfmetrics import stringWidth
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
        velden: dict[str, list[str]] = {}
        for veld, tekst in blad:
            velden.setdefault(veld, []).append(tekst)
        getekend: list[dict] = []

        def stijl(naam, letter, grootte, regel, kleur):
            return ParagraphStyle(naam, fontName=letter, fontSize=grootte, leading=regel, textColor=HexColor(kleur))

        def teken(tekst, st, x, y, w, max_regels=None, waar=""):
            """Een alinea met echte afbreking binnen `w`, de bovenkant op `y`. Past ze niet in `max_regels`, dan wordt ze op
            een woordgrens ingekort met een ellips, en zegt een noot waar de volledige tekst staat: niets verdwijnt stil."""
            tekst, afgekapt = passend(tekst, st, w, max_regels)
            p = Paragraph(opgemaakt(tekst), st)
            _w, h = p.wrap(w, hoogte)
            p.drawOn(canvas, x, y - h)
            getekend.append({"tekst": tekst, "x": x, "y": y - h, "breedte": w, "hoogte": h, "afgekapt": afgekapt})
            if afgekapt and waar:
                n = Paragraph(opgemaakt(waar), stijl("Noot", "Fira-Italic", 8, 11, GRIJS))
                _w, nh = n.wrap(w, hoogte)
                n.drawOn(canvas, x, y - h - nh)
                getekend.append({"tekst": waar, "x": x, "y": y - h - nh, "breedte": w, "hoogte": nh, "afgekapt": False})
                h += nh
            return y - h

        # Onderaan staat de voetnoot; alles erboven moet daarboven blijven.
        ondergrens = 18 * mm
        voetstijl = stijl("Titelbladvoet", "Fira", 8, 11, GRIJS)
        for t in velden.get("voetnoot", []):
            h = _hoogte(passend(t, voetstijl, tekstbreedte, 4)[0], voetstijl, tekstbreedte)
            teken(t, voetstijl, links, ondergrens + h, tekstbreedte, max_regels=4)
            ondergrens += h + 6 * mm

        y = hoogte - 90 * mm
        for t in velden.get("soort", []):
            y = teken(t.upper(), stijl("Soort", "Fira-SemiBold", 9, 12, GRIJS), links, y, tekstbreedte, max_regels=2) - 4 * mm
        for t in velden.get("titel", []):
            y = teken(t, stijl("Titelbladtitel", "Fira-SemiBold", 26, 31, LINTBLAUW), links, y, tekstbreedte, max_regels=4,
                      waar="De volledige titel staat in het colofon.") - 4 * mm
        canvas.setStrokeColor(HexColor(LINTBLAUW))
        canvas.setLineWidth(2)
        canvas.line(links, y, links + 20 * mm, y)
        y -= 8 * mm

        # Het statusblok en de regelingen hebben een vaste plek nodig; de vraag krijgt wat er daarboven over is.
        labelbreedte, binnen = 36 * mm, 6 * mm
        waardestijl = stijl("Statuswaarde", "Fira", 9.5, 12.5, TEKST)
        rijen = [r.split(": ", 1) if ": " in r else (r, "") for r in velden.get("rij", [])]
        waardebreedte = tekstbreedte - labelbreedte - 2 * binnen
        notenhoogte = _hoogte("Volledig in het colofon.", stijl("Noot", "Fira-Italic", 8, 11, GRIJS), waardebreedte)

        def rijhoogte(w):
            """Een rij is zo hoog als haar gezette waarde, plus de noot als ze is ingekort: de volgende rij begint eronder."""
            tekst, af = passend(w, waardestijl, waardebreedte, 3)
            return max(_hoogte(tekst, waardestijl, waardebreedte), 12.5) + (notenhoogte if af else 0) + 5

        rijhoogtes = [rijhoogte(w) for _l, w in rijen]
        blokhoogte = sum(rijhoogtes) + 8 * mm if rijen else 0
        regstijl = stijl("Titelbladregelingen", "Fira", 9, 13, GRIJS)
        reghoogte = sum(_hoogte(passend(t, regstijl, tekstbreedte, 3)[0], regstijl, tekstbreedte) + 4 * mm + 11
                        for t in velden.get("regelingen", []))
        vraagstijl = stijl("Titelbladvraag", "Fira", 11.5, 16, GRIJS)
        ruimte = y - ondergrens - blokhoogte - reghoogte - 18 * mm
        for t in velden.get("vraag", []):
            y = teken(t, vraagstijl, links, y, tekstbreedte, max_regels=max(2, int(ruimte // 16) - 1),
                      waar="De volledige analysevraag staat in de samenvatting.") - 10 * mm

        if rijen:
            y = min(y, max(120 * mm, ondergrens + blokhoogte + reghoogte + 8 * mm))
            canvas.setFillColor(HexColor(STATUSVLAK))
            canvas.rect(links, y - blokhoogte, tekstbreedte, blokhoogte, stroke=0, fill=1)
            getekend.append({"tekst": "statusblok", "x": links, "y": y - blokhoogte, "breedte": tekstbreedte, "hoogte": blokhoogte,
                             "afgekapt": False, "vlak": True})
            ry = y - 4 * mm
            labelstijl = stijl("Statuslabel", "Fira-SemiBold", 9, 12.5, GRIJS)
            for (label, waarde), rh in zip(rijen, rijhoogtes):
                teken(label, labelstijl, links + binnen, ry, labelbreedte - 2 * mm, max_regels=2)
                teken(waarde, waardestijl, links + binnen + labelbreedte, ry, waardebreedte, max_regels=3,
                      waar="Volledig in het colofon.")
                ry -= rh
            y -= blokhoogte + 8 * mm
        for t in velden.get("regelingen", []):
            y = teken(t, regstijl, links, y, tekstbreedte, max_regels=3, waar="Alle regelingen staan in het colofon.") - 4 * mm
        canvas.restoreState()
        if paginas is not None:
            paginas.append({"pagina": doc.page, "kopregel": "", "voetregel": "", "titelblad": True, "getekend": getekend})

    def kader(canvas, doc):
        """Kop- en voetregel; de voetregel krijgt zijn totaal pas bij het opslaan (`Teller`)."""
        canvas._zonder_voet = False
        canvas.saveState()
        kopregel = ""
        getekend: list[dict] = []
        tekstbreedte = A4[0] - links - rechts

        def schrijf(tekst, x, y, max_breedte, rechts_uitgelijnd=False):
            tekst = op_breedte(opgemaakt_plat(tekst), "Fira", 8, max_breedte)
            w = stringWidth(tekst, "Fira", 8)
            (canvas.drawRightString if rechts_uitgelijnd else canvas.drawString)(x, y, tekst)
            getekend.append({"tekst": tekst, "x": x - w if rechts_uitgelijnd else x, "breedte": w})
            return tekst

        if doc.page > 1:
            canvas.setFont("Fira", 8)
            canvas.setFillColor(HexColor(GRIJS))
            # Met een plaats in de opbouw schuiven titel en hoofdstuk een regel omhoog; de plaats staat vlak boven de lijn.
            # Titel links en hoofdstuk rechts delen de breedte; wat niet past, krijgt een ellips op breedte.
            hoogte = A4[1] - (10.5 if doc.plaats else 14) * mm
            rechts_deel = min(stringWidth(opgemaakt_plat(doc.hoofdstuk), "Fira", 8), tekstbreedte * 0.45)
            links_tekst = schrijf(titel, links, hoogte, tekstbreedte - rechts_deel - 6 * mm)
            rechts_tekst = schrijf(doc.hoofdstuk, A4[0] - rechts, hoogte, rechts_deel, rechts_uitgelijnd=True) if doc.hoofdstuk else ""
            plaats_tekst = schrijf(doc.plaats, A4[0] - rechts, A4[1] - 14 * mm, tekstbreedte, rechts_uitgelijnd=True) if doc.plaats else ""
            kopregel = " · ".join(filter(None, [links_tekst, rechts_tekst, plaats_tekst]))
            canvas.setStrokeColor(HexColor(HAARLIJN))
            canvas.setLineWidth(0.5)
            canvas.line(links, A4[1] - 16 * mm, A4[0] - rechts, A4[1] - 16 * mm)
        canvas.setStrokeColor(HexColor(HAARLIJN))
        canvas.setLineWidth(0.5)
        canvas.line(links, 14 * mm, A4[0] - rechts, 14 * mm)
        canvas.setFont("Fira", 8)
        canvas.setFillColor(HexColor(GRIJS))
        # Rechts staat "Pagina n van N" (`Teller`): daar blijft ruimte voor.
        voetregel = schrijf(voet, links, 10 * mm, tekstbreedte - stringWidth("Pagina 999 van 999", "Fira", 8) - 6 * mm)
        canvas.restoreState()
        if paginas is not None:
            paginas.append({"pagina": doc.page, "kopregel": kopregel, "voetregel": voetregel, "titelblad": False, "getekend": getekend})

    # Het totaal van de vorige zetronde. Een pagina wordt meteen aan het document toegevoegd: een uitgestelde `showPage`
    # (de bekende "NumberedCanvas") koppelt elke bladwijzer en elke link in de inhoudsopgave aan pagina 1, want ReportLab
    # bindt een bestemming aan de pagina die op dat moment in het document staat (ADR-009, review 8 nov 2026).
    totaal: dict = {"n": None, "juist": False}

    class Teller(Canvas):
        """Schrijft "Pagina n van N" met het totaal van de vorige ronde; `render` zet zo nodig een ronde extra."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._gebruikt = totaal["n"]

        def showPage(self):
            if not getattr(self, "_zonder_voet", False):
                self.saveState()
                self.setFont("Fira", 8)
                self.setFillColor(HexColor(GRIJS))
                n = self._gebruikt if self._gebruikt is not None else "…"
                nummer = f"Pagina {self._pageNumber} van {n}"
                self.drawRightString(A4[0] - rechts, 10 * mm, nummer)
                self.restoreState()
                if paginas and paginas[-1]["pagina"] == self._pageNumber:
                    paginas[-1]["nummer"] = nummer
            self._zonder_voet = False
            super().showPage()

        def save(self):
            aantal = self._pageNumber - 1
            totaal["juist"] = self._gebruikt == aantal
            totaal["n"] = aantal
            for p in paginas or []:
                p["totaal"] = aantal
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

    def bouw() -> bytes:
        """Eén zetronde: het verhaal en het document vers, zodat een tweede ronde niets van de eerste erft."""
        verhaal.clear()
        teller["kop"] = 0
        heeft_inhoud, laatste, blok, spans = False, -1, None, None
        for stijl, tekst in regels:
            if stijl == SPANS:
                spans = [tuple(x) for x in json.loads(tekst)]
                continue
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
                doel.append(Lijn(Paragraph(gemarkeerd(tekst, spans) if spans else opgemaakt(tekst), stijlen["Citaat"])))
                spans = None
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

    pdf = bouw()
    if not totaal["juist"]:
        pdf = bouw()       # het totaal is nu bekend; de opmaak verandert er niet door
    return pdf


def _segmenten(tekst: str, spans: list[tuple[int, int, int, str]]):
    """De tekst in stukken met de markeringen die elk stuk dekken, en de nummers die na het stuk eindigen. Deterministisch."""
    grenzen = sorted({0, len(tekst), *(s for s, _e, _n, _k in spans), *(e for _s, e, _n, _k in spans)})
    for a, b in zip(grenzen, grenzen[1:]):
        dekking = sorted((x for x in spans if x[0] <= a and x[1] >= b), key=lambda x: (x[0], -x[1], x[2]))
        eindigt = sorted({x[2] for x in spans if x[1] == b})
        yield tekst[a:b], dekking, eindigt


def gemarkeerd(tekst: str, spans: list[tuple[int, int, int, str]]) -> str:
    """Het citaat met de markeringen erin: de achtergrond in de kleur van de buitenste klasse, een onderstreping waar er meer
    overlappen, en het nummer in superscript waar een markering eindigt. De woorden zelf blijven letterlijk."""
    uit = []
    for stuk, dekking, eindigt in _segmenten(tekst, spans):
        deel = opgemaakt(stuk)
        if dekking:
            kleur = JAS_KLASSE_KLEUREN.get(dekking[0][3], ("#E6E6E6", ""))[0]
            deel = f'<span backColor="{kleur}">{deel}</span>'
            if len(dekking) > 1:
                deel = f"<u>{deel}</u>"
        uit.append(deel)
        if eindigt:                              # meer nummers op één plek: met komma's, anders leest "2" en "4" als 24
            uit.append(f'<super><font size="6.5">{",".join(map(str, eindigt))}</font></super>')
    return "".join(uit)


def _hoogte(tekst: str, stijl, breedte: float) -> float:
    from reportlab.platypus import Paragraph
    return Paragraph(opgemaakt(tekst), stijl).wrap(breedte, 10 ** 6)[1]


def passend(tekst: str, stijl, breedte: float, max_regels: int | None) -> tuple[str, bool]:
    """De tekst zo dat hij, echt gezet, in `max_regels` regels van `breedte` past: anders ingekort op een woordgrens met een ellips.
    Geeft (tekst, afgekapt). Gemeten met dezelfde zetter als de PDF, dus ook met de DejaVu-terugval."""
    if max_regels is None or _hoogte(tekst, stijl, breedte) <= max_regels * stijl.leading + 0.5:
        return tekst, False
    woorden = tekst.split()
    laag, hoog = 0, len(woorden)
    while laag < hoog:                                   # het grootste aantal woorden dat met "…" nog past
        midden = (laag + hoog + 1) // 2
        if _hoogte(" ".join(woorden[:midden]) + " …", stijl, breedte) <= max_regels * stijl.leading + 0.5:
            laag = midden
        else:
            hoog = midden - 1
    return (" ".join(woorden[:laag]) + " …").strip(), True


def op_breedte(tekst: str, letter: str, grootte: float, breedte: float) -> str:
    """Eén regel die in `breedte` past: anders afgekapt op breedte, met een ellips."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if stringWidth(tekst, letter, grootte) <= breedte:
        return tekst
    while tekst and stringWidth(tekst.rstrip() + "…", letter, grootte) > breedte:
        tekst = tekst[:-1]
    return tekst.rstrip() + "…"


def opgemaakt_plat(tekst: str) -> str:
    """Tekst voor het canvas (kop- en voetregel): geen opmaak, en wat Fira niet heeft wordt een spatie in plaats van een ■."""
    from reportlab.pdfbase import pdfmetrics
    _registreer()
    heeft = pdfmetrics.getFont("Fira").face.charToGlyph
    return "".join(c if ord(c) < 128 or ord(c) in heeft else " " for c in tekst)


def aantal_paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))
