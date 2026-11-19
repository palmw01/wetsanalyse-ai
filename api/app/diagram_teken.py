"""Het diagram rond een centrale klasse getekend: een reportlab-tekening (PDF), SVG en Mermaid (Markdown).

Alle drie gaan uit van hetzelfde `diagram.Diagram`; de PDF en de SVG ook van dezelfde `diagram.plaats`, dus overal hetzelfde
plaatje. Mermaid kiest zijn eigen layout, met dezelfde knopen, teksten en labels. Kleur draagt nooit alleen: elke knop noemt
zijn klasse, elke lijn haar relatie.
"""
from __future__ import annotations

import math
from typing import Literal

from .diagram import KOP_H, MARGE, REGEL_H, Diagram, Geplaatst, labelregels, plaats
from .jas_klassen import JAS_KLASSE_KLEUREN, JAS_TEKSTKLEUR

Vorm = Literal["formuleringen", "begrippen"]

LIJNKLEUR = "#535353"
LABELKLEUR = "#535353"
RANDKLEUR_CENTRAAL = "#154273"
_GROOTTE = 7.5
_KOPGROOTTE = 6.5
_LABELGROOTTE = 6.0
_STANDAARD = ("#edefef", "#b8baba")


def _kleur(klasse: str) -> tuple[str, str]:
    return JAS_KLASSE_KLEUREN.get(klasse, _STANDAARD)


def _stukken(tekst: str, letter: str) -> list[tuple[str, str]]:
    """De tekst in stukken per letter: wat Fira niet tekent, tekent DejaVu (zoals `pdf_opmaak.opgemaakt`)."""
    from reportlab.pdfbase import pdfmetrics

    from .pdf_opmaak import _registreer
    _registreer()
    heeft = pdfmetrics.getFont("Fira").face.charToGlyph
    uit: list[tuple[str, str]] = []
    for c in tekst:
        f = letter if ord(c) < 128 or ord(c) in heeft else "DejaVu"
        if uit and uit[-1][1] == f:
            uit[-1] = (uit[-1][0] + c, f)
        else:
            uit.append((c, f))
    return uit


def _breedte(tekst: str, letter: str, grootte: float) -> float:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return sum(stringWidth(t, f, grootte) for t, f in _stukken(tekst, letter))


def _regel(g, x: float, y: float, tekst: str, letter: str, grootte: float, maximaal: float, kleur: str,
           midden: bool = False) -> None:
    """Eén regel tekst; past hij niet, dan iets kleiner (nooit afgekapt: de tekst is letterlijk)."""
    from reportlab.graphics.shapes import String
    from reportlab.lib.colors import HexColor
    b = _breedte(tekst, letter, grootte)
    if b > maximaal and b > 0:
        grootte, b = grootte * maximaal / b, maximaal
    if midden:
        x -= b / 2
    from reportlab.pdfbase.pdfmetrics import stringWidth
    for t, f in _stukken(tekst, letter):
        g.add(String(x, y, t, fontName=f, fontSize=grootte, fillColor=HexColor(kleur)))
        x += stringWidth(t, f, grootte)


def _rand(a: Geplaatst, dx: float, dy: float) -> tuple[float, float]:
    """Waar een lijn vanuit het midden van `a` in richting (dx, dy) de rand van `a` raakt."""
    tx = (a.b / 2) / abs(dx) if dx else math.inf
    ty = (a.h / 2) / abs(dy) if dy else math.inf
    t = min(tx, ty)
    return a.x + a.b / 2 + dx * t, a.y + a.h / 2 + dy * t


def als_drawing(d: Diagram, breedte: float = 480.0, vorm: Vorm = "formuleringen", max_hoogte: float | None = None):
    """Een reportlab-`Drawing`: een flowable voor het rapport, en de bron van de SVG."""
    from reportlab.graphics.shapes import Drawing, Group, Polygon, Line, Rect
    from reportlab.lib.colors import HexColor, white

    p = plaats(d, breedte, vorm)
    hoogte = p.hoogte
    tekening = Drawing(breedte, hoogte)
    g = Group()
    omhoog = lambda y: hoogte - y                                                  # noqa: E731 – van boven gemeten
    per_id = {(k.knoop.soort, k.knoop.id): k for k in p.knopen}

    def knoop(id_: str) -> Geplaatst | None:
        return per_id.get(("element", id_)) or per_id.get(("impliciet", id_))

    labels = []
    for lijn in d.lijnen:
        a, b = knoop(lijn.van), knoop(lijn.naar)
        if a is None or b is None:
            continue
        dx, dy = (b.x + b.b / 2) - (a.x + a.b / 2), (b.y + b.h / 2) - (a.y + a.h / 2)
        if not dx and not dy:
            continue
        x1, y1 = _rand(a, dx, dy)
        x2, y2 = _rand(b, -dx, -dy)
        voorstel = lijn.lifecycle == "voorgesteld"
        g.add(Line(x1, omhoog(y1), x2, omhoog(y2), strokeColor=HexColor(LIJNKLEUR), strokeWidth=0.7,
                   strokeDashArray=[3, 2] if voorstel else None))
        lengte = math.hypot(x2 - x1, y2 - y1) or 1
        ux, uy = (x2 - x1) / lengte, (y2 - y1) / lengte
        punt = [(x2, y2), (x2 - 5 * ux + 2.4 * uy, y2 - 5 * uy - 2.4 * ux), (x2 - 5 * ux - 2.4 * uy, y2 - 5 * uy + 2.4 * ux)]
        g.add(Polygon([c for x, y in punt for c in (x, omhoog(y))], fillColor=HexColor(LIJNKLEUR), strokeColor=None))
        tekst = lijn.leesvorm + (f" ({lijn.volgorde})" if lijn.volgorde is not None else "")
        labels.append(((x1 + x2) / 2, (y1 + y2) / 2, tekst))

    for k in p.knopen:
        vlak, rand = _kleur(k.knoop.klasse)
        centraal = k.knoop.id == d.centraal and k.knoop.soort == "element"
        onder = omhoog(k.y + k.h)
        g.add(Rect(k.x, onder, k.b, k.h, rx=2, ry=2, fillColor=white,
                   strokeColor=HexColor(RANDKLEUR_CENTRAAL if centraal else rand), strokeWidth=1.6 if centraal else 0.8,
                   strokeDashArray=[2, 2] if k.knoop.soort == "impliciet" else None))
        g.add(Rect(k.x + 0.4, omhoog(k.y + KOP_H), k.b - 0.8, KOP_H - 0.4, fillColor=HexColor(vlak), strokeColor=None))
        _regel(g, k.x + 4, omhoog(k.y + KOP_H) + 3, k.kop, "Fira-SemiBold", _KOPGROOTTE, k.b - 8, JAS_TEKSTKLEUR)
        for i, r in enumerate(k.regels):
            _regel(g, k.x + 4, omhoog(k.y + KOP_H + MARGE + (i + 1) * REGEL_H) + 2, r, "Fira", _GROOTTE, k.b - 8, JAS_TEKSTKLEUR)

    for x, y, tekst in labels:
        regels = labelregels(tekst)
        w = max(_breedte(r, "Fira-Italic", _LABELGROOTTE) for r in regels) + 4
        h = 7.5 * len(regels) + 1.5
        g.add(Rect(x - w / 2, omhoog(y) - h / 2, w, h, fillColor=white, strokeColor=None))
        for i, r in enumerate(regels):
            _regel(g, x, omhoog(y) + h / 2 - 7.5 * (i + 1) + 1.2, r, "Fira-Italic", _LABELGROOTTE, 120, LABELKLEUR, midden=True)

    tekening.add(g)
    if max_hoogte and hoogte > max_hoogte:
        f = max_hoogte / hoogte
        g.scale(f, f)
        tekening.width, tekening.height = breedte * f, max_hoogte
    return tekening


def als_svg(d: Diagram, breedte: float = 480.0, vorm: Vorm = "formuleringen") -> str:
    """Dezelfde tekening als SVG, voor de werkplek en elke andere plek die een plaatje wil."""
    from reportlab.graphics import renderSVG
    return renderSVG.drawToString(als_drawing(d, breedte, vorm))


def _mermaid_tekst(tekst: str) -> str:
    return (tekst.replace("&", "#amp;").replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;")
            .replace("[", "#91;").replace("]", "#93;"))


def als_mermaid(d: Diagram, vorm: Vorm = "formuleringen") -> str:
    """Een ```mermaid-blok: in GitHub, Obsidian en Confluence een plaatje, elders leesbare tekst."""
    from .diagram import knooptekst
    namen = {}
    uit = ["```mermaid", "flowchart TB"]
    stijlen: dict[str, str] = {}
    for i, k in enumerate(d.knopen):
        n = f"n{i}"
        namen[(k.soort, k.id)] = n
        kop, regels = knooptekst(k, vorm)
        uit.append(f'  {n}["<b>{_mermaid_tekst(kop)}</b><br/>{"<br/>".join(_mermaid_tekst(r) for r in regels)}"]')
        stijlen.setdefault(k.klasse, f"k{len(stijlen)}")
    per_id = {i: n for (s, i), n in namen.items() if s == "element"} | {i: n for (s, i), n in namen.items() if s == "impliciet"}
    for lijn in d.lijnen:
        a, b = per_id.get(lijn.van), per_id.get(lijn.naar)
        if a and b:
            pijl = "-.->" if lijn.lifecycle == "voorgesteld" else "-->"
            label = lijn.leesvorm + (f" ({lijn.volgorde})" if lijn.volgorde is not None else "")
            uit.append(f'  {a} {pijl}|"{_mermaid_tekst(label)}"| {b}')
    for klasse, s in stijlen.items():
        vlak, rand = _kleur(klasse)
        uit.append(f"  classDef {s} fill:{vlak},stroke:{rand},color:{JAS_TEKSTKLEUR}")
    for k in d.knopen:
        uit.append(f"  class {namen[(k.soort, k.id)]} {stijlen[k.klasse]}")
    centraal = namen.get(("element", d.centraal))
    if centraal:
        uit.append(f"  style {centraal} stroke:{RANDKLEUR_CENTRAAL},stroke-width:2px")
    uit.append("```")
    return "\n".join(uit)
