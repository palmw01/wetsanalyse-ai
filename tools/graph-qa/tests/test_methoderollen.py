"""Elke methoderol uit de skill heeft een modelaanroep, en elke modelaanroep loopt via de gedeelde stap (H5e).

De rol `begrippen` stond in de skill en in `CLAUDE.md`, maar geen model kreeg hem ooit (bevinding S-01). Niets faalde:
`instructies` werd voor die rol nergens aangeroepen. Deze tests maken zo'n stille drift rood, in beide richtingen.
"""
from __future__ import annotations

import re
from pathlib import Path

from agent.llm_stap import Rol
from agent.methodepakket import PAKKET
from agent.specialists import SPECIALISTS, methoderol

AGENT = Path(__file__).resolve().parents[1] / "agent"


def _gedragen() -> set[str]:
    """De methoderollen die een modelaanroep draagt: die van een `Rol`, plus die van elke specialist (de antwoordlus
    geeft de methoderol van de specialist mee aan `stroom`)."""
    return {r.methoderol for r in Rol if r.methoderol} | {methoderol(s) for s in SPECIALISTS}


def test_elke_methoderol_heeft_een_aanroeper():
    zonder = set(PAKKET["rollen"]) - _gedragen()
    assert not zonder, f"methoderollen die geen model krijgt: {sorted(zonder)} – schrap ze of geef ze een aanroep"


def test_elke_gedragen_methoderol_staat_in_de_skill():
    onbekend = _gedragen() - set(PAKKET["rollen"])
    assert not onbekend, f"een aanroep draagt een methoderol die de skill niet kent: {sorted(onbekend)}"


def _bronnen() -> dict[Path, str]:
    return {p: p.read_text(encoding="utf-8") for p in AGENT.rglob("*.py")}


def test_elke_rol_wordt_gebruikt():
    code = "\n".join(t for p, t in _bronnen().items() if p.name != "llm_stap.py")
    ongebruikt = [r.name for r in Rol if not re.search(rf"\bRol\.{r.name}\b", code)]
    assert not ongebruikt, f"rollen zonder aanroep: {ongebruikt}"


def test_niemand_roept_het_model_buiten_de_stap_aan():
    """Een nieuwe modelaanroep gaat via `llm_stap` (rol, stopreden, logregel) en krijgt een scenario in
    `test_modelverzoeken.py`. Alleen de adapter en de stap zelf spreken `create`/`stream` aan."""
    patroon = re.compile(r"\bllm\.(create|stream)\(")
    buiten = [f"{p.relative_to(AGENT)}:{t[:m.start()].count(chr(10)) + 1}"
              for p, t in _bronnen().items()
              if p.name != "llm_stap.py" and "adapters" not in p.parts
              for m in patroon.finditer(t)]
    assert not buiten, f"modelaanroepen buiten llm_stap: {buiten}"
