"""Het dashboard van Lex Bench in de stijl van Lex (plan §6): de overgenomen tokens en het beeldmerk blijven gelijk aan
de frontend, en de pagina leest alleen het gegevensbestand.

De tokens worden overgenomen, niet geïmporteerd: de pagina hangt niet aan de build van de frontend. Deze toets is de
drift-test erop, net als die van de JAS-kleuren. Alleen de standaardbibliotheek.
"""
from __future__ import annotations

import re

import pytest

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R15", laag=2)

PAGINA = WORTEL / "tools" / "lex-bench" / "index.html"
GLOBALS = WORTEL / "frontend" / "app" / "globals.css"
MERK = WORTEL / "frontend" / "merk" / "lex-merk.svg"
TOKEN = re.compile(r"--([a-z0-9-]+):\s*([0-9]+ [0-9]+ [0-9]+);")


def _tokens(tekst: str) -> dict[str, str]:
    return dict(TOKEN.findall(tekst))


def _blok() -> str:
    tekst = PAGINA.read_text(encoding="utf-8")
    m = re.search(r"/\* tokens:.*?\*/(.*?)/\* einde tokens \*/", tekst, re.S)
    assert m, "het tokenblok ontbreekt in tools/lex-bench/index.html"
    return m.group(1)


def test_de_tokens_zijn_die_van_de_frontend():
    pagina, frontend = _tokens(_blok()), _tokens(GLOBALS.read_text(encoding="utf-8"))
    assert {"paper", "surface", "ink", "lint", "muted", "line", "succes", "gold", "fout"} <= set(pagina)
    afwijkend = {k: (v, frontend.get(k)) for k, v in pagina.items() if frontend.get(k) != v}
    assert not afwijkend, f"de tokens van het dashboard wijken af van globals.css: {afwijkend}"


def test_het_beeldmerk_is_dat_van_lex():
    def rechthoeken(tekst: str) -> list[tuple]:
        return sorted(tuple(sorted(re.findall(r'(\w+)="([^"]*)"', r))) for r in re.findall(r"<rect\b([^>]*)/>", tekst))
    assert rechthoeken(PAGINA.read_text(encoding="utf-8")) == rechthoeken(MERK.read_text(encoding="utf-8"))


def test_de_pagina_haalt_geen_code_van_buiten():
    tekst = PAGINA.read_text(encoding="utf-8")
    assert re.findall(r'<script[^>]*src="([^"]+)"', tekst) == ["data.js"], "alleen het gegevensbestand, geen bibliotheek"
    assert not re.search(r"\bfetch\(|XMLHttpRequest", tekst), "file:// mag niets ophalen: de gegevens komen uit data.js"
    for href in re.findall(r'<link[^>]*href="([^"]+)"', tekst):
        assert href.startswith("https://fonts.g"), f"alleen het lettertype mag van buiten komen: {href}"
