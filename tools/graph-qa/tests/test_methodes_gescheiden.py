"""Geen JRM in de skill wetsanalyse (plan methodes scheiden, S5, test 1).

Wetsanalyse (JAS) en wetsuitvoering (JRM) zijn zuiver gescheiden. De skill wetsanalyse noemt het JRM, het juridische
scenario, de akte en het juridisch relevante feit alleen in een alinea die naar de skill wetsuitvoering verwijst: zo'n
alinea zegt waar de grens ligt. Woorden die het JAS zelf gebruikt ("rechtsgevolg", "juridische toestand") vallen er
niet onder.

De methodetekst per rol (tussen de methodemarkers) telt hier nog niet mee: die verandert in een eigen stap met een
meting (S6). Tot dan toetst `MODELTEKST_MEE = False` alleen de leestekst.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "wetsanalyse"

#: Zet op True in S6, als de methodetekst van `duiding` en `supervisor` geen JRM meer noemt.
MODELTEKST_MEE = False

VERBODEN = re.compile(r"\bjrm|juridisch relevante? feit|juridische? scenario|\baktes?\b", re.I)
VERWIJST = re.compile(r"wetsuitvoering", re.I)
MARKER = re.compile(r"<!-- methode:(?P<id>[a-z0-9-]+):begin -->.*?<!-- methode:(?P=id):end -->", re.S)

#: Wat mag blijven zonder verwijzing, met de reden. De relatiecatalogus wordt niet herzien (ADR-011, besluit 4).
UITZONDERINGEN = {
    ("relaties.json", "rechtsgevolg en juridisch relevant feit als eigen element (JRM 2-werkversie)"),
}


def _bestanden() -> list[Path]:
    return sorted(p for p in SKILL.rglob("*") if p.is_file() and p.suffix in {".md", ".json", ".yaml"})


def _alineas(tekst: str) -> list[str]:
    """Een alinea is een blok tot de volgende lege regel; een tabelrij telt op zichzelf, want een tabel is geen betoog."""
    uit: list[str] = []
    for blok in re.split(r"\n\s*\n", tekst):
        rijen = [r for r in blok.splitlines() if r.lstrip().startswith("|")]
        rest = "\n".join(r for r in blok.splitlines() if not r.lstrip().startswith("|"))
        uit += rijen + ([rest] if rest.strip() else [])
    return uit


def _vondsten(pad: Path) -> list[str]:
    tekst = pad.read_text(encoding="utf-8")
    if not MODELTEKST_MEE:
        tekst = MARKER.sub("", tekst)
    rel = pad.relative_to(SKILL).as_posix()
    for bestand, zin in UITZONDERINGEN:
        if bestand == rel:
            tekst = tekst.replace(zin, "")
    return [a.strip()[:160] for a in _alineas(tekst) if VERBODEN.search(a) and not VERWIJST.search(a)]


@pytest.mark.parametrize("pad", _bestanden(), ids=lambda p: p.relative_to(SKILL).as_posix())
def test_de_skill_wetsanalyse_noemt_het_jrm_alleen_als_verwijzing(pad):
    assert _vondsten(pad) == []


def test_de_jrm_verrijking_bestaat_niet_meer_in_wetsanalyse():
    assert not (SKILL / "references" / "jrm-verrijking.md").exists()
    # Geen link meer naar het bestand; de historie in het bronregister mag zeggen dat het vervallen is.
    assert not [p for p in _bestanden() if "(jrm-verrijking.md)" in p.read_text(encoding="utf-8")]


def test_het_label_is_wetsanalyse_jas():
    assert 'lex_label: "Wetsanalyse: JAS"' in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_het_dossier_van_wetsanalyse_kent_geen_scenario_of_gevolg_als_identiteit():
    dossier = (SKILL / "assets" / "analysedossier.md").read_text(encoding="utf-8")
    protocol = (SKILL / "references" / "analyseprotocol.md").read_text(encoding="utf-8")
    for tekst in (dossier, protocol):
        assert not re.search(r"\bS-ID|\bG-ID|Scenario-ID|\bG01\b|\bS01\b", tekst)


def test_elke_uitzondering_bestaat_nog():
    """Een uitzondering die nergens meer op slaat, hoort weg."""
    for bestand, zin in UITZONDERINGEN:
        assert zin in (SKILL / bestand).read_text(encoding="utf-8")


def test_de_toets_vindt_een_vermenging():
    """De toets zelf: een alinea met JRM zonder verwijzing valt, een verwijzende alinea niet."""
    assert VERBODEN.search("Leg het rechtsgevolg vast volgens JRM 2.") and not VERWIJST.search("volgens JRM 2")
    assert _alineas("a\n\n| x | JRM |\n| y | z |\n\nb") == ["a", "| x | JRM |", "| y | z |", "b"]
    assert not VERBODEN.search("Aan een rechtsfeit zijn rechtsgevolgen verbonden; de juridische toestand wijzigt.")
