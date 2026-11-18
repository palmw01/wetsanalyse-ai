"""De begripverwachting per klasse in de skill (activiteit 3a) tegen de klassen van de api en de bronnen van de methode.

Het bestand is een build-input: de api en de werkplek krijgen het gegenereerd (`genereer_begripverwachting.py`). Een
klasse die ontbreekt zou stil als "begrip" tellen; een bron die nergens staat maakt een methodeclaim onherleidbaar.
"""
from __future__ import annotations

import ast
import json
import re
import runpy

from routeboek import WORTEL

SKILL = WORTEL / ".claude" / "skills" / "wetsanalyse"
DATA = json.loads((SKILL / "begripverwachting.json").read_text(encoding="utf-8"))
REGISTER = (SKILL / "references" / "bronnen.md").read_text(encoding="utf-8")
UITLEG = (SKILL / "references" / "begrippen.md").read_text(encoding="utf-8")


def _klassen() -> list[str]:
    bron = (WORTEL / "api" / "app" / "jas_klassen.py").read_text(encoding="utf-8")
    for knoop in ast.parse(bron).body:
        if isinstance(knoop, ast.AnnAssign) and getattr(knoop.target, "id", "") == "JAS_KLASSEN_VOLGORDE":
            return list(ast.literal_eval(knoop.value))
    raise AssertionError("JAS_KLASSEN_VOLGORDE staat niet in api/app/jas_klassen.py")


def test_elke_klasse_heeft_precies_een_verwachting():
    assert list(DATA["klassen"]) == _klassen(), "dezelfde klassen in dezelfde volgorde als de api"


def test_elke_verwachting_rust_op_een_bron_uit_het_register():
    for klasse, k in DATA["klassen"].items():
        assert k["bron"], klasse
        for b in k["bron"]:
            code = re.match(r"(M\d\d)\b", b)
            assert code and f"| {code.group(1)} |" in REGISTER, f"{klasse}: {b} staat niet in bronnen.md"


def test_alleen_de_voorwaarde_en_de_brondefinitie_krijgen_geen_eigen_begrip():
    # M01 h.6–7: de voorwaarde krijgt een omschrijving "indien …"; M01 h.4 punt 16: de brondefinitie is de wettelijke
    # definitie van een begrip. Elke andere klasse krijgt een begrip (M01 h.3 stap 3a).
    anders = {k: v["verwacht"] for k, v in DATA["klassen"].items() if v["verwacht"] != "begrip"}
    assert anders == {"Voorwaarde": "omschrijving", "Brondefinitie": "definitie"}


def test_de_uitleg_in_de_skill_noemt_elke_klasse():
    sectie = UITLEG.split("## Welke formulering krijgt wat", 1)
    assert len(sectie) == 2, "references/begrippen.md mist de sectie *Welke formulering krijgt wat*"
    tekst = sectie[1].split("\n## ", 1)[0]
    for klasse in DATA["klassen"]:
        assert klasse in tekst, f"{klasse} ontbreekt in de uitleg"


def test_de_gegenereerde_kopieen_volgen_de_skill():
    script = runpy.run_path(str(WORTEL / "tools" / "graph-qa" / "scripts" / "genereer_begripverwachting.py"))
    for doel, inhoud in script["genereer"]().items():
        assert doel.read_text(encoding="utf-8") == inhoud, \
            f"{doel.relative_to(WORTEL)}: draai genereer_begripverwachting.py"
