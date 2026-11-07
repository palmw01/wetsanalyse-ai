"""De (stijl, tekst)-regels van een rapport als Markdown: de tegenhanger van `pdf_opmaak`.

Kopjes en lijsten, geen tabellen: de jurist neemt deze tekst over in een eigen document. De tekst wordt alleen geëscaped
waar Markdown de betekenis zou veranderen. Haal je de backslashes weg, dan staat de wettekst er letterlijk.
"""
from __future__ import annotations

import re

from .pdf_opmaak import BEGRIP, BLOK_BEGIN, BLOK_EIND, INHOUD, MARKERING, PAGINA, TITELBLAD

_KOP = {"Title": "#", "Heading1": "##", "Heading2": "###", "Heading3": "####", BEGRIP: "####"}
_TEKENS = re.compile(r"([\\`*_\[\]<>])")
_BEGIN = re.compile(r"^(\s*)(#{1,6}\s|[-+]\s)")
_NUMMER = re.compile(r"^(\s*\d+)([.)]\s)")


def _veilig(tekst: str) -> str:
    """Eén regel: tekens die Markdown leest, en een begin dat een kop, lijst of citaat zou worden."""
    uit = _BEGIN.sub(lambda m: m[1] + "\\" + m[2], _TEKENS.sub(r"\\\1", tekst))
    return _NUMMER.sub(lambda m: m[1] + "\\" + m[2], uit)


def _alinea(tekst: str, voor: str = "") -> str:
    return "\n".join(voor + _veilig(r).rstrip() for r in tekst.splitlines() if r.strip())


def markdown(regels: list[tuple[str, str]]) -> str:
    uit: list[str] = []
    for stijl, tekst in regels:
        if stijl in (BLOK_BEGIN, BLOK_EIND):
            continue
        if stijl.startswith(TITELBLAD):
            veld = stijl.removeprefix(TITELBLAD)
            if veld == "titel":
                uit.append(f"# {_TEKENS.sub(r'\\\1', tekst)}")
            elif veld == "rij":
                label, _, waarde = tekst.partition(": ")
                rij = f"- **{_veilig(label)}:** {_veilig(waarde)}"
                # De rijen vormen samen één lijst.
                if uit and uit[-1].startswith("- **"):
                    uit[-1] += "\n" + rij
                else:
                    uit.append(rij)
            elif veld == "voetnoot":
                uit.append(f"*{_veilig(tekst)}*")
            else:
                uit.append(_alinea(tekst))
            continue
        if stijl == PAGINA:
            if uit and uit[-1] != "---":
                uit.append("---")
        elif stijl == INHOUD:
            uit.append("\n".join(f"- {_veilig(t)}" for s, t in regels if s == "Heading1"))
        elif stijl in _KOP:
            uit.append(f"{_KOP[stijl]} {_TEKENS.sub(r'\\\1', tekst)}")
        elif stijl == "Citaat":
            uit.append(_alinea(tekst, "> ").replace("\n", "\n>\n"))
        elif stijl == "Heading4" or stijl.startswith(MARKERING):
            uit.append(f"**{_veilig(tekst)}**")
        elif stijl == "Waarschuwing":
            uit.append(f"**Let op:** {_veilig(tekst)}")
        elif stijl == "Voorstel":
            uit.append(f"*{_veilig(tekst)}*")
        else:
            uit.append(_alinea(tekst))
    return "\n\n".join(uit).strip() + "\n"
