"""Elke methodestap van de skill wetsanalyse wijst naar een bron (plan methodes scheiden, deel 2, W1, test 6).

"Volgt de bronnen aantoonbaar" is hiermee toetsbaar: elke reference begint met een regel *Grondslag* met codes die in
het register staan, en elke projectregel (P) noemt de bron met de plek erin, of zegt dat het een projectkeuze is.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "wetsanalyse"
REGISTER = (SKILL / "references" / "bronnen.md").read_text(encoding="utf-8")
CODE = re.compile(r"\b([MP]\d{2})\b")
RIJ = re.compile(r"^\| ([MP]\d{2}) \| (.*) \|$", re.M)
#: De bronnen met hoofdstukken, stappen of regels: wie ze noemt, zegt ook waar.
MET_PLEK = {"M01", "M02", "M03", "M04"}
PLEK = re.compile(r"h\.\s?\d|§|\bH[23]\b|\bstap\b|activiteit|tabel|p\.\s?\d")

CODES = {c for c, _ in RIJ.findall(REGISTER)}
REFERENCES = sorted(p for p in (SKILL / "references").glob("*.md") if p.name != "bronnen.md")


def _regels() -> dict[str, list[str]]:
    return {code: [k.strip() for k in rest.split(" | ")] for code, rest in RIJ.findall(REGISTER)}


def test_het_register_kent_bronnen_en_projectregels():
    assert {"M01", "M02", "M04", "P01", "P18"} <= CODES


@pytest.mark.parametrize("pad", REFERENCES, ids=lambda p: p.name)
def test_elke_reference_noemt_haar_grondslag(pad):
    regels = [r for r in pad.read_text(encoding="utf-8").splitlines() if r.startswith("Grondslag:")]
    assert regels, f"{pad.name} heeft geen regel 'Grondslag:'"
    codes = {c for r in regels for c in CODE.findall(r)}
    # Een bereik als "P01–P03" noemt zijn uiteinden; die moeten bestaan.
    assert codes and codes <= CODES, f"{pad.name}: onbekende codes {sorted(codes - CODES)}"


@pytest.mark.parametrize("code", sorted(c for c in CODES if c.startswith("P")))
def test_elke_projectregel_noemt_bron_en_plek_of_zegt_projectkeuze(code):
    basis = _regels()[code][1]
    delen = [d.strip() for d in basis.split(";")]
    assert CODE.search(basis) or "ADR-" in basis or "projectkeuze" in basis, f"{code}: geen bron en geen 'projectkeuze'"
    zonder_plek = [d for d in delen if set(CODE.findall(d)) & MET_PLEK and not PLEK.search(d)]
    assert zonder_plek == [], f"{code}: {zonder_plek} noemt de bron zonder hoofdstuk, stap, paragraaf of regel"


def test_elke_code_in_een_methodesectie_staat_in_het_register():
    import json
    rollen = json.loads((SKILL / "agentrollen.json").read_text(encoding="utf-8"))
    gebruikt = {c for s in rollen["secties"].values() for c in s["bronnen"]}
    assert gebruikt <= CODES


def test_de_versie_van_het_jas_staat_bij_de_bron():
    """De prompts van de annotatieketen noemen JAS 1.0.10; het register zegt waar dat nummer vandaan komt."""
    from agent.jas_pipeline.keten import JAS_VERSIE
    assert JAS_VERSIE in _regels()["M04"][0]
