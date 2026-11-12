"""De gedeelde vorm van een validatie (ADR-016 §B2, poort 1): bevindingen, de fout die ze draagt, en de frontmatter.

Een skill (`bronmodel.skill`) en een agentprofiel (`bronmodel.agentprofiel`) zijn allebei Markdown met YAML-frontmatter,
en worden op twee plekken getoetst: door de generator die ze in het image bundelt, en door de werkplaats bij elke
opslag. Die twee gebruiken dezelfde validator. Daarom werkt hij op tekst in het geheugen en niet op een map op schijf,
en geeft hij **alle** bevindingen terug in plaats van bij de eerste te stoppen: de editor toont ze naast elkaar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class Bevinding:
    """Eén reden waarom een onderdeel niet geldig is."""

    #: Stabiel en machineleesbaar (`naam`, `frontmatter`, `rol`, …): de editor en de tests leunen erop, niet op de tekst.
    code: str
    melding: str
    #: Het bestand waar het om gaat, relatief aan het onderdeel; leeg als het over het geheel gaat.
    bestand: str = ""

    def __str__(self) -> str:
        return f"{self.bestand}: {self.melding}" if self.bestand else self.melding


class ValidatieFout(ValueError):
    """Een onderdeel dat niet geldig is, met alle bevindingen."""

    def __init__(self, onderdeel: str, bevindingen: list[Bevinding]):
        self.onderdeel = onderdeel
        self.bevindingen = list(bevindingen)
        super().__init__(f"{onderdeel}: " + "; ".join(str(b) for b in self.bevindingen))


def frontmatter(tekst: str) -> tuple[dict[str, Any], str]:
    """De YAML-frontmatter en de tekst eronder. De frontmatter staat tussen twee regels `---`, bovenaan het bestand.

    Gooit `ValueError` als die vorm ontbreekt of de YAML geen afbeelding is. De tekst eronder komt terug zonder
    witregels eromheen."""
    regels = tekst.split("\n")
    if not regels or regels[0].rstrip() != "---":
        raise ValueError("het bestand begint niet met frontmatter (een regel ---)")
    try:
        einde = next(i for i, r in enumerate(regels[1:], 1) if r.rstrip() == "---")
    except StopIteration:
        raise ValueError("de frontmatter wordt niet afgesloten met een regel ---") from None
    try:
        kop = yaml.safe_load("\n".join(regels[1:einde]))
    except yaml.YAMLError as fout:
        raise ValueError(f"de frontmatter is geen geldige YAML: {fout}") from None
    if not isinstance(kop, dict) or not all(isinstance(k, str) for k in kop):
        raise ValueError("de frontmatter is geen lijst van velden")
    return kop, "\n".join(regels[einde + 1:]).strip()


def uniek(waarden: list[Any] | tuple[Any, ...]) -> bool:
    return len(waarden) == len(set(waarden))
