"""Het kwaliteitsrapport (`scripts/kwaliteit.py`, job `kwaliteit` in de poort): een rapport dat niets tegenhoudt.

Wat stil mis kan gaan: `poort` die toch op het rapport wacht of een stap die faalt (dan wordt een meting een poort zonder
dat iemand dat besloot), of een testjob die zijn dekking onder een andere naam bewaart dan het script leest (dan staat
er "niet gemeten" terwijl er gemeten is). Daaronder de rekenregels van het script zelf. Alleen de standaardbibliotheek,
zoals de andere poorttests.
"""
from __future__ import annotations

import re
import sys
import tomllib

from routeboek import WORTEL

sys.path.insert(0, str(WORTEL / "scripts"))
import kwaliteit  # noqa: E402
from test_poort_parallel import JOBS, RAPPORT  # noqa: E402

JOB = JOBS["kwaliteit"]


def _stappen(job: str) -> list[str]:
    return re.split(r"^      - ", job.partition("\n    steps:\n")[2], flags=re.M)[1:]


def test_de_poort_wacht_niet_op_het_rapport():
    assert RAPPORT == {"kwaliteit"}
    assert "kwaliteit" not in re.search(r"^    needs: \[(.*)\]\s*$", JOBS["poort"], re.M).group(1)


def test_elke_stap_van_het_rapport_mag_falen():
    """Anders staat er een rode job op de PR, al houdt hij de merge niet tegen."""
    for stap in _stappen(JOB):
        if stap.startswith("uses: actions/checkout@"):
            continue
        assert "continue-on-error: true" in stap, f"deze stap kan rood worden:\n{stap}"


def test_het_rapport_draait_na_de_testjobs_en_alleen_bij_code():
    assert re.search(r"^    needs: \[raakt, frontend, graph-qa, api\]\s*$", JOB, re.M)
    assert "if: always() && needs.raakt.outputs.kruis == 'true'" in JOB
    assert "fetch-depth: 2" in JOB and "--basis HEAD^1" in JOB, "de eerste ouder van de merge-commit is de basis"
    assert "uv run scripts/kwaliteit.py" in JOB, "de versies van ruff en coverage staan in de kop van het script"


def test_de_testjobs_bewaren_hun_dekking_waar_het_script_zoekt():
    for naam in kwaliteit.PYTHON_DEKKING:
        job = JOBS[naam]
        assert f'COVERAGE_FILE="$GITHUB_WORKSPACE/dekking/{naam}/{naam}-${{{{ matrix.shard }}}}.coverage"' in job, naam
        assert "--cov --cov-report=" in job, naam
    assert "npm run test -- --coverage" in JOBS["frontend"]
    assert 'cp coverage/coverage-final.json "$GITHUB_WORKSPACE/dekking/frontend/"' in JOBS["frontend"]
    for naam in kwaliteit.DEKKING_ONDERDELEN:
        upload = next(s for s in _stappen(JOBS[naam]) if "name: dekking-" in s)
        assert re.search(r"^          path: dekking$", upload, re.M), f"{naam}: de artefactwortel moet `dekking/` zijn"
        assert "continue-on-error: true" in upload and "if: always()" in upload, naam
    assert "pattern: dekking-*" in JOB and "merge-multiple: true" in JOB


def test_de_dekking_meet_de_code_met_relatieve_paden():
    """Zonder `relative_files` staan er absolute paden van de shard in de data, en dan vindt de rapportjob niets."""
    for naam, map_ in kwaliteit.PYTHON_DEKKING.items():
        config = tomllib.loads((WORTEL / map_ / "pyproject.toml").read_text(encoding="utf-8"))
        run = config["tool"]["coverage"]["run"]
        assert run["relative_files"] is True, naam
        for bron in run["source"]:
            assert (WORTEL / map_ / bron).is_dir(), f"{naam}: de dekkingsbron {bron} bestaat niet"


# ── de rekenregels ──────────────────────────────────────────────────────────────────────────────────────────────────

DIFF = """\
diff --git a/api/app/x.py b/api/app/x.py
--- a/api/app/x.py
+++ b/api/app/x.py
@@ -3,0 +4,2 @@ def f():
+    a = 1
+    b = 2
@@ -10 +12 @@
-    oud
+    nieuw
@@ -20,3 +23,0 @@
-    weg
diff --git a/nieuw.py b/nieuw.py
--- /dev/null
+++ b/nieuw.py
@@ -0,0 +1,3 @@
+x
+y
+z
diff --git a/weg.py b/weg.py
--- a/weg.py
+++ /dev/null
@@ -1,2 +0,0 @@
-x
-y
"""


def test_lees_diff():
    assert kwaliteit.lees_diff(DIFF) == {"api/app/x.py": {4, 5, 12}, "nieuw.py": {1, 2, 3}}


def _b(bestand, regel, code):
    return {"bestand": bestand, "regel": regel, "code": code, "melding": ""}


def test_nieuw_is_wat_de_wijziging_toevoegt():
    basis = [_b("a.py", 10, "F401"), _b("b.py", 5, "B905")]
    # a.py: één F401 erbij op een gewijzigde regel; de oude (verschoven naar 11) telt niet als nieuw.
    # b.py: niet gewijzigd, dus wat daar staat is nooit nieuw. c.py: een nieuw bestand, alles is nieuw.
    nu = [_b("a.py", 3, "F401"), _b("a.py", 11, "F401"), _b("b.py", 5, "B905"), _b("b.py", 9, "B905"),
          _b("c.py", 1, "S110")]
    gewijzigd = {"a.py": {1, 2, 3}, "c.py": {1}}
    assert kwaliteit.nieuwe_bevindingen(nu, basis, gewijzigd) == [_b("a.py", 3, "F401"), _b("c.py", 1, "S110")]


def test_een_verschoven_blok_toont_alle_van_die_soort():
    """Steeg het aantal, maar ligt er geen op een gewijzigde regel, dan weet het script niet welke nieuw is."""
    nu = [_b("a.py", 30, "B023"), _b("a.py", 40, "B023")]
    assert kwaliteit.nieuwe_bevindingen(nu, [_b("a.py", 10, "B023")], {"a.py": {1}}) == nu


def test_gelijk_gebleven_is_niets_nieuw():
    nu = [_b("a.py", 3, "F401")]
    assert kwaliteit.nieuwe_bevindingen(nu, [_b("a.py", 9, "F401")], {"a.py": {3}}) == []


def test_complexiteit_uit_de_melding():
    b = {"bestand": "a.py", "regel": 7, "code": "C901", "melding": "`zoek` is too complex (22 > 15)"}
    assert kwaliteit.complexiteit([b, _b("a.py", 1, "F401")]) == [
        {"bestand": "a.py", "regel": 7, "functie": "zoek", "complexiteit": 22}]


def test_ongedekte_wijzigingen_tellen_alleen_uitvoerbare_regels():
    per_bestand = {"a.py": {"regels": {1, 2, 3, 4}, "ongedekt": {3, 4}}, "b.py": {"regels": {1}, "ongedekt": set()}}
    gewijzigd = {"a.py": {2, 3, 9}, "b.py": {5}, "c.py": {1}}
    assert kwaliteit.ongedekte_wijzigingen(per_bestand, gewijzigd) == [
        {"bestand": "a.py", "gewijzigd": 2, "ongedekt": [3]}]


def test_bereiken():
    assert kwaliteit.bereiken([3, 4, 5, 9, 11, 12]) == "3-5, 9, 11-12"
    assert kwaliteit.bereiken([]) == ""


def test_onderdelen():
    assert kwaliteit.onderdeel("tools/graph-qa/agent/x.py") == "graph-qa"
    assert kwaliteit.onderdeel("packages/bronmodel/src/a.py") == "bronmodel"
    assert kwaliteit.onderdeel(".claude/skills/x.py") == "overig"


def test_het_rapport_noemt_wat_nieuw_is():
    rapport = {
        "basis": "abc", "gewijzigde_bestanden": ["a.py"], "meldingen": [],
        "ruff": {"totaal": 2, "totaal_basis": 1, "per_code": {"F401": 2}, "per_onderdeel": {"overig": 2},
                 "nieuw": [{"bestand": "a.py", "regel": 3, "code": "F401", "melding": "`os` imported but unused"}],
                 "in_gewijzigde_bestanden": []},
        "complexiteit": {"grens": 15, "aantal": 0, "aantal_basis": 0, "hoogste": [], "in_gewijzigde_bestanden": []},
        "dekking": {"api": {"regels": 10, "gedekt": 5, "procent": 50.0,
                            "gewijzigd_zonder_test": [{"bestand": "api/a.py", "gewijzigd": 2, "ongedekt": [3, 4]}]}},
    }
    tekst = kwaliteit.markdown(rapport)
    assert "| ruff-bevindingen | 2 | 1 | +1 |" in tekst
    assert "`a.py:3` **F401**" in tekst
    assert "| `api/a.py` | 2 | 2 | 3-4 |" in tekst
    assert "testdekking niet gemeten | graph-qa, frontend" in tekst
