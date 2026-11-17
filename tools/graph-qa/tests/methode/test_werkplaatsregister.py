"""Het register van de soorten in de werkplaats (ADR-016 deel B, `bronmodel.werkplaats`), gezien vanaf graph-qa.

De api toetst een concept met dezelfde code als de generator hier. Deze tests leggen vast dat de twee kanten het eens
zijn: wat in de repo staat en door de generator komt, haalt ook poort 1 van de werkplaats, en de hash van een map is één
rekenregel. Het register zelf (versies, rechten, audit) test de api (`api/tests/test_werkplaats.py`).
"""
from __future__ import annotations

from bronmodel import skill
from bronmodel import werkplaats as wp

from agent import profielen
from scripts.genereer_agentprofielen import PROFIELEN as PROFIELMAP
from scripts.genereer_methodepakket import ROLLEN, SKILL, methode_skills


def test_elke_skill_in_de_repo_haalt_poort_1_van_de_werkplaats():
    for pad in [SKILL, *methode_skills()]:
        bestanden = skill.lees_map(pad)
        assert wp.toets("skill", pad.name, bestanden) == [], pad.name
        assert not wp.weiger(bestanden)


def test_elk_profiel_in_de_repo_haalt_poort_1_van_de_werkplaats():
    assert {p.stem for p in PROFIELMAP.glob("*.md")} == set(profielen.PROFIELEN)
    for pad in PROFIELMAP.glob("*.md"):
        assert wp.toets("agentprofiel", pad.stem, {pad.name: pad.read_text(encoding="utf-8")}) == [], pad.stem


def test_de_generator_en_de_werkplaats_delen_een_lijst_van_rollen():
    assert ROLLEN is skill.ROLLEN and SKILL.name == skill.BASIS


def test_de_hash_van_een_map_is_een_rekenregel():
    bestanden = skill.lees_map(SKILL)
    omgekeerd = dict(reversed(list(bestanden.items())))
    assert wp.hash_van(bestanden) == wp.hash_van(omgekeerd) and len(wp.hash_van(bestanden)) == 64
    assert wp.hash_van({**bestanden, "SKILL.md": bestanden["SKILL.md"] + " "}) != wp.hash_van(bestanden)
