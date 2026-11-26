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
    "bench-analist": {"Skill", *(MCP + t for t in ("bron_lezen", "graaf_lezen", "logboek_aanvullen", "logboek_lezen", "bench_opdracht_lezen", "bench_inleveren"))},
    "bench-reviewer": {"Skill", *(MCP + t for t in ("bron_lezen", "graaf_lezen", "logboek_aanvullen", "logboek_lezen", "bench_opdracht_lezen", "bench_inleveren"))},
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


# --- de pilot (LB3, §9): drie nieuwe ontwikkelcasussen, één per niveau, zonder verwachting ---

PILOT = WORTEL / "docs" / "lex-bench" / "bronselectie" / "pilot"
#: De regelingen in de graaf op Azure (`bwbIds` in `deploy/azure/main.bicep`).
IN_DE_GRAAF = set(re.findall(r"'(BWBR\d{7})'", re.search(r"(?s)param bwbIds array = \[(.*?)\]", (
    WORTEL / "deploy" / "azure" / "main.bicep").read_text(encoding="utf-8")).group(1)))
VERWACHTING = {"verwacht", "uitgesloten", "buiten_graaf", "onenig", "open_punten", "verwachting"}


def _pilot() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PILOT.glob("*/set.json"))]


def test_de_pilot_heeft_een_casus_per_niveau_buiten_het_manifest():
    pilot = _pilot()
    assert sorted(s["niveau"] for s in pilot) == ["gemiddeld", "makkelijk", "moeilijk"]
    manifest = json.loads((WORTEL / "docs" / "lex-bench" / "bronselectie" / "manifest.json").read_text(encoding="utf-8"))
    bekend = {c["casus_id"] for c in manifest["casussen"]}
    for s in pilot:
        assert re.fullmatch(r"LB-\d{2}", s["casus_id"]) and s["casus_id"] not in bekend, (
            f"{s['casus_id']}: een pilotcasus komt pas in het manifest met haar bevroren teamverwachting")
        assert s["gebruik"] == "ontwikkeling" and s["status"] == "concept"


@pytest.mark.parametrize("s", _pilot(), ids=lambda s: s["casus_id"])
def test_een_pilotdossier_draagt_geen_verwachting(s):
    assert not VERWACHTING & set(s), f"{s['casus_id']}: de verwachting komt van het team, blind (§4.2)"
    assert "urn:bwb" not in json.dumps(s), f"{s['casus_id']}: het dossier noemt geen bepaling"
    assert not re.search(r"\bartikel(en)?\s+\d", json.dumps(s, ensure_ascii=False), re.I), (
        f"{s['casus_id']}: het dossier noemt geen artikelnummer")
    assert s["regelingen"] and set(s["regelingen"]) <= IN_DE_GRAAF, f"{s['casus_id']}: een regeling buiten de graaf"
    assert len(s["deelvragen"]) <= (3 if s["niveau"] == "makkelijk" else 6)
