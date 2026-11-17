"""De vorm van Lex Bench (plan §3.3, §4.5, §6): het manifest, de meetmappen en het gegevensbestand van het dashboard.

Geen model en geen score: alleen of het manifest klopt met de sets, of een meetmap de vorm van een run heeft, en of
het dashboard alleen toont wat vastgelegd is, zonder de bepalingen van een blinde casus. Alleen de standaardbibliotheek,
zoals de andere poorttests.
"""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from routeboek import WORTEL

pytestmark = pytest.mark.risico("R15", laag=2)

BENCH = WORTEL / "docs" / "lex-bench" / "bronselectie"
MANIFEST = BENCH / "manifest.json"
SCHEMA = BENCH / "casus-schema-4.json"
DATA = WORTEL / "tools" / "lex-bench" / "data.js"
METINGEN = WORTEL / "docs" / "architectuur" / "metingen"
NIVEAUS = {"makkelijk", "gemiddeld", "moeilijk"}
GEBRUIK = {"ontwikkeling", "blind"}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _sha(pad) -> str:
    return hashlib.sha256(pad.read_bytes()).hexdigest()


def test_het_manifest_heeft_de_vorm_van_plan_3_3():
    m = _manifest()
    assert m["meetas"] == "bronselectie" and re.fullmatch(r"bench-bronselectie-v\d+", m["versie"])
    ids = [c["casus_id"] for c in m["casussen"]]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"LB-\d{2}", i) for i in ids)
    for c in m["casussen"]:
        assert c["niveau"] in NIVEAUS and c["gebruik"] in GEBRUIK, c["casus_id"]
        assert c["verwachting"]["status"] in {"concept", "vastgesteld"}
        assert (c["verwachting"]["status"] == "vastgesteld") == bool(c["verwachting"]["vastgesteld_door"]), (
            f"{c['casus_id']}: vastgesteld zonder jurist, of een jurist zonder vaststelling")
        if c["gebruik"] == "blind":
            assert "pad" not in c and "naam" not in c, f"{c['casus_id']}: een blinde casus noemt alleen zijn hash"


def test_de_hashes_kloppen_met_de_sets():
    m = _manifest()
    regels = sorted(f"{c['casus_id']} {c['sha256']}" for c in m["casussen"])
    assert m["hash"] == hashlib.sha256("\n".join(regels).encode()).hexdigest(), "de versiehash klopt niet"
    for c in m["casussen"]:
        if c["gebruik"] == "ontwikkeling":
            assert _sha(WORTEL / c["pad"] / "set.json") == c["sha256"], (
                f"{c['casus_id']}: de set veranderde; een wijziging is een nieuwe versie van het manifest")
            assert _sha(WORTEL / c["opname"]["pad"]) == c["opname"]["sha256"], f"{c['casus_id']}: andere opname"


def test_verrekening_staat_niet_in_de_casusset():
    assert not any("verrekening" in c.get("pad", "") for c in _manifest()["casussen"])


def test_het_schema_4_noemt_de_velden_van_plan_3_1():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    eigen = schema["properties"]
    assert {"casus_id", "niveau", "gebruik", "verwachting"} <= set(eigen)
    assert set(eigen["niveau"]["enum"]) == NIVEAUS and set(eigen["gebruik"]["enum"]) == GEBRUIK
    assert "nagekomen" in json.dumps(eigen["verwacht"])


def _runs():
    return sorted(p for p in METINGEN.glob("lex-bench-*") if (p / "run.json").exists())


def test_elke_meetmap_heeft_de_vorm_van_een_run():
    assert _runs(), "er is nog geen run: het nulpunt van LB1 ontbreekt"
    for map_ in _runs():
        run = json.loads((map_ / "run.json").read_text(encoding="utf-8"))
        rapport = json.loads((map_ / "rapport.json").read_text(encoding="utf-8"))
        assert (map_ / "README.md").exists(), map_.name
        assert {"datum", "arm", "code", "zoekversie", "casusset", "graaftoestand", "verwachting", "verbruik"} <= set(run)
        assert run["arm"] != "L1" or run["verbruik"] == {"L1": 0}, f"{map_.name}: L1 kost geen tokens"
        for rij in rapport["per_niveau"]:
            assert rij["gebruik"] in GEBRUIK, "geen rij over blind en ontwikkeling heen"
        for k in rapport["casussen"]:
            for maat in k["maten"].values():
                assert {"teller", "noemer"} <= set(maat), f"{map_.name}: een maat zonder aantallen"
            if k["gebruik"] == "blind":
                assert "verschillen" not in k and "urn:bwb" not in json.dumps(k), f"{map_.name}: blinde bepalingen"


def test_een_meetmap_staat_in_het_meetlogboek():
    logboek = (METINGEN / "README.md").read_text(encoding="utf-8")
    for map_ in _runs():
        assert map_.name in logboek, f"{map_.name} staat niet in het meetlogboek"



def test_het_dashboard_toont_precies_de_vastgelegde_runs():
    tekst = DATA.read_text(encoding="utf-8")
    m = re.fullmatch(r"(?s)//[^\n]*\nwindow\.LEX_BENCH = (\{.*\});\n", tekst)
    assert m, "data.js heeft de vorm `window.LEX_BENCH = {…};` (een gewone <script>, ook als lokaal bestand)"
    data = json.loads(m.group(1))
    assert [r["map"] for r in data["runs"]] == [p.name for p in sorted(_runs(), key=lambda p: (
        json.loads((p / "run.json").read_text(encoding="utf-8"))["datum"], p.name))], (
        "data.js loopt achter op de meetmappen: draai `python -m eval.lex_bench --dashboard`")
    for r in data["runs"]:
        for k in r["rapport"]["casussen"]:
            if k["gebruik"] == "blind":
                assert "verschillen" not in k
    assert data["risicos"]["risicos"], "de risicomatrix staat erbij"
