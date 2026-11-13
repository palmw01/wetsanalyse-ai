"""De testgevallen van de skill wetsanalyse (plan methodes scheiden, deel 2, W7, test 8).

Een voorbeeld in de skill is geen testgeval: wie de voorbeelden heeft gelezen, kent anders het antwoord al. En elke
werkstroom van de router heeft een testgeval, met de twee grenzen erbij.
"""
from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "wetsanalyse"
EVALS = sorted(p for p in (SKILL / "evals").iterdir() if p.is_dir())
BEPALING = re.compile(r"\*\*Bron\.\*\* (?P<regeling>[^,]+), artikel (?P<artikel>[\w:.]+)")
IN_PROMPT = re.compile(r"(?P<regeling>Invorderingswet 1990|Algemene wet bestuursrecht), artikel (?P<artikel>[\w:.]+)")


def _voorbeeldbepalingen() -> set[tuple[str, str]]:
    tekst = (SKILL / "references" / "voorbeelden.md").read_text(encoding="utf-8")
    return {(m["regeling"].strip(), m["artikel"]) for m in BEPALING.finditer(tekst)}


def test_de_voorbeelden_noemen_hun_bepalingen():
    assert len(_voorbeeldbepalingen()) >= 3


def test_geen_eval_gebruikt_een_bepaling_uit_de_voorbeelden():
    voorbeelden = _voorbeeldbepalingen()
    dubbel = {e.name: (m["regeling"], m["artikel"]) for e in EVALS
              for m in IN_PROMPT.finditer((e / "prompt.md").read_text(encoding="utf-8"))
              if (m["regeling"], m["artikel"]) in voorbeelden}
    assert dubbel == {}


def test_elke_eval_heeft_een_vraag_een_uitkomst_en_graders():
    for e in EVALS:
        assert (e / "prompt.md").read_text(encoding="utf-8").startswith("---\n"), e.name
        assert "expected_outcome:" in (e / "case.yaml").read_text(encoding="utf-8"), e.name
        assert len(list((e / "graders").glob("*.md"))) >= 3, e.name


def test_elke_werkstroom_en_beide_grenzen_hebben_een_eval():
    namen = " ".join(e.name for e in EVALS)
    for deel in ("werkgebied", "markeert", "samenhang", "begrip", "dossier", "grens-scenario", "grens-geen"):
        assert deel in namen, f"geen eval voor {deel}"
