"""De build-inputs van graph-qa buiten zijn eigen map: de skills en de agentprofielen (ADR-016 §B1).

`agent/methodepakket.py`, `agent/agentprofielen.py` en `agent/bronpakket.json` worden gegenereerd uit `.claude/skills/`
en `.claude/lex-agents/`. Een wijziging daar is dus een wijziging van graph-qa, ook als ze alleen Markdown raakt. Drie
plekken moeten dat weten, en ze moeten het alle drie weten: de poort (anders draait de drift-guard niet en mergt een PR
groen terwijl het gegenereerde bestand achterloopt), de pre-push-hook, en de publish-workflow (anders komt er geen
image). Alleen de standaardbibliotheek, zoals de andere poorttests.
"""
from __future__ import annotations

import re
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[2]
#: De mappen waaruit graph-qa genereert. Elke methode-skill telt: het bronpakket bundelt ze allemaal.
INPUTS = (".claude/skills/", ".claude/lex-agents/")


def _lees(pad: str) -> str:
    return (WORTEL / pad).read_text(encoding="utf-8")


def test_de_poort_draait_graph_qa_bij_een_wijziging_van_een_skill_of_profiel():
    """Ook als de PR alleen Markdown raakt: de regel staat los van het filter op `.md`."""
    poort = _lees(".github/workflows/poort.yml")
    m = re.search(r"skill=\$\(echo \"\$gewijzigd\" \| grep -E '([^']+)'", poort)
    assert m, "de regel die een skill- of profielwijziging herkent, is niet gevonden"
    patroon = re.compile(m.group(1))
    for pad in (".claude/skills/wetsanalyse/SKILL.md", ".claude/skills/wetsuitvoering/references/scenario.md",
                ".claude/skills/nieuwe-skill/agentrollen.json", ".claude/lex-agents/duiding.md"):
        assert patroon.search(pad), f"{pad} start de graph-qa-suite niet"
    for pad in (".claude/agents/agent-jurist.md", "docs/architectuur/catalogus.md", "frontend/lib/jas.ts"):
        assert not patroon.search(pad), f"{pad} hoort de graph-qa-suite niet te starten"
    assert re.search(r'if \[ -n "\$skill" \]; then\s+echo [^\n]+\s+graph_qa=true', poort)


def test_de_hook_en_de_publish_kennen_dezelfde_mappen():
    hook = _lees(".githooks/pre-push")
    publish = _lees(".github/workflows/graph-qa-docker-publish.yml")
    for map_ in INPUTS:
        assert f'raakt "{map_}"' in hook, f"de pre-push-hook draait graph-qa niet bij {map_}"
        assert f'- "{map_}**"' in publish, f"de publish-workflow bouwt graph-qa niet bij {map_}"
