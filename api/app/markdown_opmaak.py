"""De (stijl, tekst)-regels van een rapport als Markdown: de tegenhanger van `pdf_opmaak`.

Kopjes en lijsten, geen tabellen: de jurist neemt deze tekst over in een eigen document. De tekst wordt alleen geëscaped
waar Markdown de betekenis zou veranderen. Haal je de backslashes weg, dan staat de wettekst er letterlijk.
"""
from __future__ import annotations

import json
import re

from .pdf_opmaak import BEGRIP, BLOK_BEGIN, BLOK_EIND, DIAGRAM, DIAGRAM_BEGRIPPEN, INHOUD, MARKERING, PAGINA, PLAATS, SPANS, TITELBLAD, citaatbanen

_KOP = {"Title": "#", "Heading1": "##", "Heading2": "###", "Heading3": "####", BEGRIP: "####"}
_TEKENS = re.compile(r"([\\`*_\[\]<>])")
_BEGIN = re.compile(r"^(\s*)(#{1,6}\s|[-+]\s)")
_NUMMER = re.compile(r"^(\s*\d+)([.)]\s)")


def _ontsnapt(tekst: str) -> str:
    """De tekens die Markdown leest, met een backslash ervoor (een functie, geen backslash in een f-string: die kan
    pas vanaf Python 3.12, en de api vraagt 3.11)."""
    return _TEKENS.sub(r"\\\1", tekst)


def _veilig(tekst: str) -> str:
    """Eén regel: tekens die Markdown leest, en een begin dat een kop, lijst of citaat zou worden."""
    uit = _BEGIN.sub(lambda m: m[1] + "\\" + m[2], _ontsnapt(tekst))
    return _NUMMER.sub(lambda m: m[1] + "\\" + m[2], uit)


def _alinea(tekst: str, voor: str = "") -> str:
    return "\n".join(voor + _veilig(r).rstrip() for r in tekst.splitlines() if r.strip())


_SUPER = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _gemarkeerd(tekst: str, spans: list) -> str:
    """Het citaat met de markeringen (optie B, zonder kleur): een markering die niets omvat vet, een die andere omvat tussen
    ⸢ en ⸣, en het nummer als ⁽ⁿ⁾ waar een markering eindigt. Haal je `**`, de haken en de nummers weg, dan staat de
    wettekst er letterlijk."""
    banen = citaatbanen(tekst, spans)
    delen, vet = [], False
    for stuk in banen.stukken:
        open_ = [n for n, _b in sorted(stuk.banen, key=lambda x: -x[1]) if any(s == stuk.start and n2 == n for s, _e, n2, _k in spans)]
        moet_vet = stuk.vlak is not None
        if vet and (not moet_vet or open_):
            delen.append("**")
            vet = False
        delen += ["⸢"] * len(open_)
        if moet_vet and not vet:
            delen.append("**")
            vet = True
        delen.append(_ontsnapt(tekst[stuk.start:stuk.eind]))
        met_baan = {n for n, _b in stuk.banen}
        dicht = [n for n in stuk.eindigt if n in met_baan]
        delen += [f"⁽{str(n).translate(_SUPER)}⁾" for n in sorted(stuk.eindigt) if n not in met_baan]
        if dicht:
            if vet:
                delen.append("**")
                vet = False
            for n in sorted(dicht, key=lambda n: dict(stuk.banen)[n]):        # de binnenste eerst dicht
                delen.append(f"⸣⁽{str(n).translate(_SUPER)}⁾")
    if vet:
        delen.append("**")
    regels = "".join(delen).splitlines()
    return "\n>\n".join("> " + _NUMMER.sub(lambda m: m[1] + "\\" + m[2], _BEGIN.sub(lambda m: m[1] + "\\" + m[2], r)).rstrip()
                         for r in regels if r.strip())


def markdown(regels: list[tuple[str, str]]) -> str:
    uit: list[str] = []
    spans = None
    for stijl, tekst in regels:
        if stijl == SPANS:
            spans = [tuple(x) for x in json.loads(tekst)]
            continue
        if stijl in (BLOK_BEGIN, BLOK_EIND):
            continue
        if stijl in (DIAGRAM, DIAGRAM_BEGRIPPEN):
            from .diagram import Diagram
            from .diagram_teken import als_mermaid
            uit.append(als_mermaid(Diagram.model_validate_json(tekst),
                                   "begrippen" if stijl == DIAGRAM_BEGRIPPEN else "formuleringen"))
            continue
        if stijl.startswith(TITELBLAD):
            veld = stijl.removeprefix(TITELBLAD)
            if veld == "titel":
                uit.append(f"# {_ontsnapt(tekst)}")
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
            uit.append(f"{_KOP[stijl]} {_ontsnapt(tekst)}")
        elif stijl == "Citaat" and spans:
            uit.append(_gemarkeerd(tekst, spans))
            spans = None
        elif stijl == "Citaat":
            uit.append(_alinea(tekst, "> ").replace("\n", "\n>\n"))
        elif stijl == "Heading4" or stijl.startswith(MARKERING):
            uit.append(f"**{_veilig(tekst)}**")
        elif stijl == "Waarschuwing":
            uit.append(f"**Let op:** {_veilig(tekst)}")
        elif stijl == PLAATS:
            uit.append(f"*{_veilig(tekst)}*")
        elif stijl == "Voorstel":
            uit.append(f"*{_veilig(tekst)}*")
        else:
            uit.append(_alinea(tekst))
    return "\n\n".join(uit).strip() + "\n"
