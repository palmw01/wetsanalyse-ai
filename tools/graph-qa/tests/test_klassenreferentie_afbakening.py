"""De afbakening tussen klassen staat in de skill én in de keten, en loopt gelijk (plan methodes scheiden, deel 2, W2,
test 7).

De klasseprofielen van de annotatieketen noemen per klasse de klassen waarmee zij verward wordt
(`confusable_classes`). De klassenreferentie in de skill legt hetzelfde onderscheid uit voor wie de skill leest. Deze
test eist dat elk paar uit een profiel bij die klasse in de referentie staat, zodat skill en keten niet uiteenlopen.
De drie bronvelden die naar de keten gaan, veranderen daar niet door: dat bewaakt `test_methode_drift.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from agent.jas_klassen import GELDIGE_JAS_KLASSEN
from agent.jas_pipeline.profielen import laad

REFERENTIE = (Path(__file__).resolve().parents[3] / ".claude" / "skills" / "wetsanalyse" / "references"
              / "jas-klassen-referentie.md").read_text(encoding="utf-8")
SECTIES = {s.split("\n", 1)[0].split(". ", 1)[1].strip(): s for s in re.split(r"\n## (?=\d+\. )", REFERENTIE)[1:]}
PROFIELEN = laad()


def _afbakening(klasse: str) -> str:
    m = re.search(r"\*\*Afbakening\*\*\n\n(.+?)(?=\n\n\*\*|\n---|\Z)", SECTIES[klasse], re.S)
    return m.group(1) if m else ""


def test_elke_klasse_heeft_een_sectie_met_samenhang_en_afbakening():
    assert set(SECTIES) == set(GELDIGE_JAS_KLASSEN)
    zonder = [k for k, s in SECTIES.items() if "**Samenhang**" not in s or not _afbakening(k)]
    assert zonder == []


@pytest.mark.parametrize("klasse", sorted(PROFIELEN))
def test_elk_paar_uit_het_profiel_staat_in_de_referentie(klasse):
    paren = [c["klasse"] for c in PROFIELEN[klasse].confusable_classes]
    assert paren, f"{klasse}: het profiel noemt geen verwarbare klassen"
    blok = _afbakening(klasse)
    assert [p for p in paren if f"*{p}*" not in blok] == []


def test_rechtsbetrekking_en_rechtsfeit_noemen_hun_subklassen():
    assert all(s in SECTIES["Rechtsbetrekking"] for s in ("Aanspraak tegenover verplichting",
               "Bevoegdheid tegenover gehoudenheid", "Immuniteit tegenover geen bevoegdheid", "Vrijheid tegenover geen aanspraak"))
    assert all(s in SECTIES["Rechtsfeit"] for s in ("Rechtshandeling", "Feitelijke handeling met rechtsgevolg",
               "Gebeurtenis met rechtsgevolg", "Tijdsverloop met rechtsgevolg"))
