"""Spoor I5: wat Lex zegt, heet *verwijderen*, niet weghalen.

De frontend heeft dezelfde toets (`frontend/app/verwijderenNietWeghalen.test.ts`). Hier gaat het om de
strings in `agent/` die bij de jurist kunnen landen: berichten, prompts, het methodepakket. Docstrings en
commentaar tellen niet mee; die leest alleen een ontwikkelaar.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

AGENT = Path(__file__).resolve().parents[1] / "agent"

WEGHALEN = re.compile(r"weg\s*-?hal|weggehaald|wegklik|\bhaalt?\s+(?:\S+\s+){0,5}weg\b", re.IGNORECASE)


def _docstrings(boom: ast.AST) -> set[int]:
    """De id's van de Constant-nodes die een docstring zijn (module, klasse, functie)."""
    uit: set[int] = set()
    for node in ast.walk(boom):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            eerste = node.body[0]
            if isinstance(eerste, ast.Expr) and isinstance(eerste.value, ast.Constant):
                uit.add(id(eerste.value))
    return uit


def _treffers(bron: str) -> list[str]:
    boom = ast.parse(bron)
    docs = _docstrings(boom)
    return [n.value for n in ast.walk(boom)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
            and WEGHALEN.search(n.value)]


def test_de_toets_vindt_de_vormen_en_slaat_docstrings_over():
    assert _treffers('MELDING = "Relatie weggehaald."')
    assert _treffers('f(tekst="Haal de deelvraag weg")')
    assert not _treffers('"""Weghalen gebeurt in de api."""\nx = 1')
    assert not _treffers('def f():\n    """Een weggehaalde selectie."""\n    return "verwijderd"')


def test_geen_tekst_van_lex_zegt_weghalen():
    gevonden = [f"{pad.relative_to(AGENT)}: {tekst[:80]!r}"
                for pad in sorted(AGENT.rglob("*.py"))
                for tekst in _treffers(pad.read_text(encoding="utf-8"))]
    assert gevonden == []
