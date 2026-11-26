"""De referentiedocumentatie van de ontologieën (`docs/ontologie/`) loopt niet achter op haar bronnen.

Bron: de T-Box (`tools/bwb-import/app/ontology.py`), de shapes (`bwb-graaf.ttl`, `jas-v2.ttl`, `begrippen-wa.ttl`,
`regels-wa.ttl`), de JAS-vocabulaire en de documentatievocabulaires `wa-vocabulaire.ttl` en `kg-vocabulaire.ttl`.
Een kruistest: hij leest buiten graph-qa en draait dus bij elke codewijziging (`scripts/kruistests.sh`).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts import genereer_ontologie_docs as gen

WORTEL = Path(__file__).resolve().parents[4]
DOCS = WORTEL / "docs" / "ontologie"


def test_de_documentatie_is_gegenereerd_uit_de_huidige_bronnen():
    assert gen.main(["--check"]) == 0, "draai: cd tools/graph-qa && uv run --extra dev python scripts/genereer_ontologie_docs.py"


def test_elke_geschreven_term_is_gedeclareerd_en_de_vocabulaires_hebben_geen_domain_of_range():
    assert gen.controleer_termen() == []


def test_de_check_bijt_op_een_niet_gedeclareerde_term(monkeypatch):
    monkeypatch.setattr(gen, "GEBRUIK", [("api/app/begrip_projectie.py", r"(nieuweTermZonderDeclaratie)", "urn:wa-ns:")])
    monkeypatch.setattr(gen, "lees", lambda pad: "nieuweTermZonderDeclaratie" if pad.endswith(".py") else
                        (WORTEL / pad).read_text(encoding="utf-8"))
    assert any("nieuweTermZonderDeclaratie" in f for f in gen.controleer_termen())


def test_een_bronwijziging_zonder_nieuwe_versie_wordt_geweigerd(monkeypatch):
    monkeypatch.setattr(gen, "bronhash", lambda o: "anders")
    versies = {o.sleutel: {"versie": "1.0.0", "historie": {"1.0.0": "oud"}} for o in gen.ONTOLOGIEEN}
    assert sum("verhoog" in f for f in gen.controleer_versies(versies, schrijven=True)) == len(gen.ONTOLOGIEEN)


def test_de_documentatievocabulaires_worden_nergens_geladen():
    """Een rdfs:range in de graaf zou rdfsplus triples laten afleiden; deze bestanden zijn alleen documentatie."""
    treffers = subprocess.run(
        ["git", "grep", "-l", "-E", r"wa-vocabulaire\.ttl|kg-vocabulaire\.ttl|docs/ontologie", "--",
         "api/app", "tools/bwb-import/app", "tools/graph-qa/agent", "deploy"],
        cwd=WORTEL, capture_output=True, text=True).stdout.split()
    assert treffers == [], treffers


def test_elke_ontologie_heeft_een_versie_in_de_changelog():
    log = (DOCS / "CHANGELOG.md").read_text(encoding="utf-8")
    for o in gen.ONTOLOGIEEN:
        assert re.search(rf"^## {o.sleutel} \d+\.\d+\.\d+", log, re.M), o.sleutel
