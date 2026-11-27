"""Vrije tekst uit een handmatige trigger komt nooit als `${{ }}` in een script (SonarQube S7630).

GitHub vult `${{ inputs.x }}` in vóór de shell het script leest: een revisie `x"; curl … #` wordt dan code die met de
Azure-credentials van de straat draait. Via `env:` is het een gewone variabele. Keuzelijsten, booleans en getallen
kunnen geen code dragen; elke andere `workflow_dispatch`- of `workflow_call`-invoer wel.

Alleen stdlib, zoals alle poorttests: de workflows worden op hun inspringing gelezen, niet met een YAML-parser.
"""
from __future__ import annotations

import re

import pytest

from routeboek import WORTEL

WORKFLOWS = sorted((WORTEL / ".github" / "workflows").glob("*.yml"))
VEILIGE_TYPES = {"choice", "boolean", "number", "environment"}


def _inspringing(regel: str) -> int:
    return len(regel) - len(regel.lstrip(" "))


def _blok(regels: list[str], i: int) -> list[str]:
    """De regels onder regel `i` die dieper inspringen (lege regels horen erbij)."""
    diepte, uit = _inspringing(regels[i]), []
    for r in regels[i + 1:]:
        if r.strip() and _inspringing(r) <= diepte:
            break
        uit.append(r)
    return uit


def vrije_invoer(tekst: str) -> set[str]:
    """De invoer van een handmatige of aangeroepen workflow die vrije tekst is (zonder type is het `string`)."""
    regels, vrij = tekst.splitlines(), set()
    for i, r in enumerate(regels):
        if not re.fullmatch(r"\s*(workflow_dispatch|workflow_call):\s*", r):
            continue
        trigger = _blok(regels, i)
        for j, t in enumerate(trigger):
            if t.strip() != "inputs:":
                continue
            invoer = _blok(trigger, j)
            diepte = min(_inspringing(x) for x in invoer if x.strip())
            for k, x in enumerate(invoer):
                if x.strip() and _inspringing(x) == diepte and (m := re.fullmatch(r"\s*([\w-]+):\s*", x)):
                    soort = re.search(r"^\s*type:\s*(\w+)", "\n".join(_blok(invoer, k)), re.M)
                    if not soort or soort.group(1) not in VEILIGE_TYPES:
                        vrij.add(m.group(1))
    return vrij


def scripts(tekst: str) -> list[str]:
    """De tekst van elke `run:` (een regel, of een blok met `|` of `>`)."""
    regels, uit = tekst.splitlines(), []
    for i, r in enumerate(regels):
        if m := re.match(r"\s*(?:-\s+)?run:\s*(.*)$", r):
            uit.append(m.group(1) + "\n" + "\n".join(_blok(regels, i)) if m.group(1) in ("|", ">", "|-", ">-", "")
                       else m.group(1))
    return uit


def lekken(tekst: str) -> list[str]:
    vrij = vrije_invoer(tekst)
    return sorted({m.group(1) for s in scripts(tekst)
                   for m in re.finditer(r"\$\{\{[^}]*\b(?:inputs|github\.event\.inputs)\.([\w-]+)", s)
                   if m.group(1) in vrij})


@pytest.mark.parametrize("pad", WORKFLOWS, ids=lambda p: p.name)
def test_vrije_invoer_alleen_via_env(pad):
    assert not lekken(pad.read_text(encoding="utf-8")), (
        f"{pad.name}: zet deze invoer in `env:` en lees hem als $VARIABELE in het script")


VOORBEELD = """\
on:
  workflow_dispatch:
    inputs:
      omgeving:
        type: choice
        options: [acceptatie]
      revisie:
        description: vrije tekst
        default: ''
jobs:
  x:
    steps:
      - name: kies
        run: echo "${{ inputs.omgeving }}"
      - name: {naam}
        env:
          REVISIE: ${{ inputs.revisie }}
        run: |
          echo "{script}"
"""


def test_de_controle_vangt_het_lek_en_laat_env_door():
    lek = VOORBEELD.replace("{naam}", "lek").replace("{script}", "${{ inputs.revisie }}")
    goed = VOORBEELD.replace("{naam}", "goed").replace("{script}", "$REVISIE")
    assert vrije_invoer(lek) == {"revisie"}
    assert lekken(lek) == ["revisie"]
    assert lekken(goed) == []
