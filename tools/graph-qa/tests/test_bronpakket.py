"""Het bronpakket (ADR-016 §B1, stap B1-2a): wat er aan skills en agentprofielen in het image zit.

De werkplaats vergelijkt een versie met wat hier staat: dezelfde hash is *actief*. Dat werkt alleen als het pakket bij
de mappen past, als elk onderdeel erin een geldige versie is, en als de hash dezelfde rekenregel volgt als het register
van de api (`bronmodel.werkplaats.hash_van`).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

from bronmodel import werkplaats as wp
from bronmodel.skill import sha

from agent import bronpakket, profielen
from agent import catalogus as cat
from agent.methodepakket import PAKKET as METHODEPAKKET
from scripts.genereer_bronpakket import DOEL, PROFIELEN, compileer, genereer

PAKKET = bronpakket.pakket()
ONDERDELEN = PAKKET["onderdelen"]


def test_het_pakket_past_bij_de_mappen():
    assert DOEL.read_text(encoding="utf-8") == genereer()
    assert compileer() == PAKKET


def test_elke_methode_skill_en_elk_profiel_zit_erin():
    assert {k.split("/", 1)[1] for k in ONDERDELEN if k.startswith("skill/")} == set(METHODEPAKKET["skills"])
    assert {k.split("/", 1)[1] for k in ONDERDELEN if k.startswith("agentprofiel/")} == set(profielen.PROFIELEN)
    assert {p.stem for p in PROFIELEN.glob("*.md")} == set(profielen.PROFIELEN)
    for sleutel, o in ONDERDELEN.items():
        assert sleutel == f"{o['soort']}/{o['naam']}" and o["soort"] in wp.REGISTER


def test_elk_onderdeel_is_een_geldige_versie_met_de_hash_van_de_werkplaats():
    for sleutel, o in ONDERDELEN.items():
        assert wp.toets(o["soort"], o["naam"], o["bestanden"]) == [], sleutel
        assert o["hash"] == wp.hash_van(o["bestanden"]), sleutel
    assert PAKKET["sha256"] == sha(json.dumps({k: o["hash"] for k, o in ONDERDELEN.items()}, sort_keys=True))


def test_een_skill_draagt_zijn_hele_map_en_een_profiel_zijn_ene_bestand():
    skill = ONDERDELEN["skill/wetsanalyse"]["bestanden"]
    assert {"SKILL.md", "agentrollen.json", "references/bronnen.md"} <= set(skill)
    assert any(p.startswith("evals/") for p in skill), "ook wat geen rol krijgt, hoort bij de map"
    for naam in profielen.PROFIELEN:
        assert set(ONDERDELEN[f"agentprofiel/{naam}"]["bestanden"]) == {f"{naam}.md"}


def test_de_catalogus_toont_de_hash_van_het_pakket():
    """Een methode en een agentprofiel dragen hun `bronhash`; wat geen bronbestanden heeft, een lege."""
    alle = {o.id: o for o in cat.catalogus()}
    for naam in METHODEPAKKET["skills"]:
        assert alle[f"methode/{naam}"].bronhash == ONDERDELEN[f"skill/{naam}"]["hash"] != ""
    for naam in profielen.PROFIELEN:
        assert alle[f"agentprofiel/{naam}"].bronhash == ONDERDELEN[f"agentprofiel/{naam}"]["hash"] != ""
    assert all(o.bronhash == "" for o in alle.values() if o.soort not in ("methode", "agentprofiel"))
    assert "bronhash" in alle["methode/wetsanalyse"].als_dict()
    assert bronpakket.bronhash("skill", "bestaat-niet") == ""


def test_het_methodepakket_is_niet_geraakt():
    """Het bronpakket staat ernaast: geen sleutel van het methodepakket komt eruit, en omgekeerd."""
    assert "bronbestanden" in METHODEPAKKET and "onderdelen" not in METHODEPAKKET
    assert set(PAKKET) == {"onderdelen", "sha256"}


def test_het_image_leest_het_pakket_zonder_de_skillmap(tmp_path):
    """In het image staat alleen `agent/`: het pakket moet daar leesbaar zijn."""
    shutil.copytree(DOEL.parent, tmp_path / "agent", ignore=shutil.ignore_patterns("__pycache__"))
    code = ("import sys; sys.path.insert(0, " + repr(str(tmp_path)) + "); from agent import bronpakket; "
            "assert bronpakket.bronhash('skill', 'wetsanalyse') and len(bronpakket.pakket()['onderdelen']) >= 2")
    subprocess.run([sys.executable, "-I", "-c", code], cwd=tmp_path, check=True, capture_output=True)
