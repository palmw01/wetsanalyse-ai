"""Het team van Lex Bench is blind door constructie (plan §4.2): het profiel krijgt een allowlist, geen verbodslijst.

Alleen de standaardbibliotheek, zoals de andere poorttests. De inhoud van het werk van een analist ziet de poort niet;
wel dat hij geen tool heeft om Lex of de repo te lezen.
"""
from __future__ import annotations

import json
import re

import pytest

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R15", laag=2)

AGENTS = WORTEL / ".claude" / "agents"
MCP = "mcp__wetsanalyse-acceptatie__"
TOEGESTAAN = {
    "bench-analist": {"Skill", *(MCP + t for t in ("bron_lezen", "graaf_lezen", "logboek_aanvullen", "logboek_lezen"))},
    "bench-reviewer": {"Skill", *(MCP + t for t in ("bron_lezen", "graaf_lezen", "logboek_aanvullen", "logboek_lezen"))},
}
NOOIT = re.compile(r"^(Read|Grep|Glob|Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch|Agent|Task)$|"
                   rf"^{MCP}(lex_|bff|werkgebied_lezen|annotatie_lezen|weergave_lezen|begrip_lezen|logs_zoek|opruimen)|"
                   r"^mcp__(graphdb|wetsanalyse-admin|vaultwarden)")


def _frontmatter(naam: str) -> dict[str, str]:
    tekst = (AGENTS / f"{naam}.md").read_text(encoding="utf-8")
    kop = re.match(r"^---\n(.*?)\n---\n", tekst, re.S)
    assert kop, f"{naam}: geen frontmatter"
    return dict(re.match(r"^(\w+):\s*(.*)$", r).groups() for r in kop.group(1).splitlines() if r.strip())


@pytest.mark.parametrize("naam", sorted(TOEGESTAAN))
def test_een_bench_profiel_heeft_precies_zijn_allowlist(naam):
    kop = _frontmatter(naam)
    assert kop["name"] == naam
    assert "disallowedTools" not in kop, "blind door constructie: een allowlist, geen verbodslijst"
    tools = {t.strip() for t in kop["tools"].split(",")}
    assert tools == TOEGESTAAN[naam]
    assert not [t for t in tools if NOOIT.search(t)]


@pytest.mark.parametrize("rol, formulier", [("analist", "lex-bench-formulier-1"), ("reviewer", "lex-bench-review-1")])
def test_het_formulier_en_de_briefing_staan_er(rol, formulier):
    schema = json.loads((WORTEL / "docs" / "lex-bench" / "bronselectie" / f"formulier-{rol}.json").read_text())
    assert schema["properties"]["formulier"]["const"] == formulier
    briefing = (WORTEL / "docs" / "lex-bench" / f"briefing-{rol}.md").read_text(encoding="utf-8")
    assert f"## Voor de {rol}" in briefing and "## Voor de coördinator" in briefing
