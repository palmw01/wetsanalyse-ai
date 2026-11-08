"""De live-proef van de bronconnectors draait op een schema, nooit in de poort (ADR-013).

Een live-test in `poort.yml` maakt elke PR afhankelijk van een externe dienst. De bronnenwacht meet daarom op een
schema en faalt zichtbaar, zoals `bouwwacht.yml`. Deze tests houden die vorm vast.
"""
from __future__ import annotations

import re

from routeboek import WORTEL

WORKFLOWS = WORTEL / ".github" / "workflows"
WACHT = WORKFLOWS / "bronnenwacht.yml"


def _trigger(tekst: str) -> str:
    return tekst.partition("\non:\n")[2].partition("\npermissions:")[0]


def test_de_wacht_draait_op_een_schema_en_niet_bij_een_pr():
    tekst = WACHT.read_text(encoding="utf-8")
    trigger = _trigger(tekst)
    assert "schedule:" in trigger and "cron:" in trigger, "de bronnenwacht hoort op een schema te draaien"
    assert "workflow_dispatch:" in trigger, "de bronnenwacht hoort ook met de hand te starten"
    assert not re.search(r"^\s+(pull_request|push)\b", trigger, re.M), "de bronnenwacht hangt niet aan een PR of push"


def test_de_wacht_draait_de_live_proef_zonder_het_spacy_wiel():
    tekst = WACHT.read_text(encoding="utf-8")
    assert "BRONNEN_LIVE" in tekst and "-m live" in tekst
    assert "uv sync --frozen" in tekst, "zonder --frozen haalt uv het spaCy-wiel van GitHub om de lock te controleren"
    assert "nlp" not in re.sub(r"#.*", "", tekst), "de live-proef heeft de taalanalyse niet nodig"


def test_geen_andere_workflow_draait_de_live_proef():
    for pad in WORKFLOWS.glob("*.yml"):
        if pad != WACHT:
            tekst = re.sub(r"#.*", "", pad.read_text(encoding="utf-8"))
            assert "BRONNEN_LIVE" not in tekst and "-m live" not in tekst, f"{pad.name} draait de live-proef"
