"""De relatiecatalogus in de skill (ADR-011) tegen de klassen van de api en de bronnen van de methode.

De catalogus is een build-input: api en werkplek krijgen hem gegenereerd. Een klassenaam die niet bestaat, een subtype
dat het contract niet kent of een bron die nergens staat, zou daar stil een relatie onmogelijk maken. Daarom toetsen we
hem hier, aan de bron van elk gegeven, zonder de onderdelen te importeren.
"""
from __future__ import annotations

import ast
import json
import re

import pytest

from routeboek import WORTEL

SKILL = WORTEL / ".claude" / "skills" / "wetsanalyse"
CATALOGUS = json.loads((SKILL / "relaties.json").read_text(encoding="utf-8"))
TYPEN = CATALOGUS["typen"]
H2 = (WORTEL / "docs" / "wetsanalyse" / "wetsanalyse-rijk" / "H2-JAS.md").read_text(encoding="utf-8").splitlines()
REGISTER = (SKILL / "references" / "bronnen.md").read_text(encoding="utf-8")


def _klassen() -> set[str]:
    bron = (WORTEL / "api" / "app" / "jas_klassen.py").read_text(encoding="utf-8")
    for knoop in ast.parse(bron).body:
        if isinstance(knoop, ast.AnnAssign) and getattr(knoop.target, "id", "") == "JAS_KLASSEN_VOLGORDE":
            return set(ast.literal_eval(knoop.value))
    raise AssertionError("JAS_KLASSEN_VOLGORDE staat niet in api/app/jas_klassen.py")


def _subtypes() -> set[str]:
    bron = (WORTEL / "api" / "app" / "annotatie_v2_contracts.py").read_text(encoding="utf-8")
    patroon = re.search(r'jas_subtype: str = Field\(default="", pattern=r"\^\(\|([^)]*)\)\$"\)', bron)
    assert patroon, "het subtypepatroon van jas_subtype is niet te lezen"
    return set(patroon.group(1).split("|"))


KLASSEN = _klassen()


def test_de_lijsten_bovenaan_noemen_bestaande_klassen():
    assert set(CATALOGUS["centrale_klassen"]) <= KLASSEN
    # Besluit gebruiker (7 nov 2026): een impliciete partij is alleen een rechtssubject.
    assert CATALOGUS["impliciet_toegestaan"] == ["Rechtssubject"]


@pytest.mark.parametrize("code", sorted(TYPEN))
def test_een_type_is_volledig_en_noemt_alleen_bestaande_klassen(code):
    t = TYPEN[code]
    assert re.fullmatch(r"[a-z]+(_[a-z]+)*", code), code
    assert t["leesvorm"] and t["invers"] and t["leesvorm"] != t["invers"]
    assert t["van"] and t["naar"] and set(t["van"]) | set(t["naar"]) <= KLASSEN, code
    assert len(set(t["van"])) == len(t["van"]) and len(set(t["naar"])) == len(t["naar"])
    assert t["drager"] in ("van", "naar")
    assert isinstance(t["methodisch"], bool)
    assert set(t) <= {"leesvorm", "invers", "van", "naar", "paren", "drager", "volgorde", "tekstueel",
                      "methodisch", "bron"}, code


@pytest.mark.parametrize("code", sorted(TYPEN))
def test_elke_bron_bestaat(code):
    """Een H2-verwijzing valt binnen de rijksspecificatie, een M- of P-code staat in het bronregister."""
    bronnen = TYPEN[code]["bron"]
    assert bronnen
    for ref in bronnen:
        if m := re.fullmatch(r"H2:(\d+)", ref):
            assert 1 <= int(m.group(1)) <= len(H2) and H2[int(m.group(1)) - 1].strip(), ref
        else:
            assert re.fullmatch(r"[MP]\d+", ref) and re.search(rf"^\| {ref} \|", REGISTER, re.M), ref
    # Een projectkeuze draagt de projectbron; een methodisch type draagt een bron uit de methode.
    if not TYPEN[code]["methodisch"]:
        assert "P18" in bronnen, code
    else:
        assert any(r.startswith(("H2:", "M")) for r in bronnen), code


def test_een_tekstueel_type_is_een_projectkeuze():
    for code, t in TYPEN.items():
        if t.get("tekstueel"):
            assert t["methodisch"] is False, code


def test_volgorde_bestaat_alleen_waar_de_bewerking_hem_vraagt():
    """Zonder volgorde is "A verminderd met B" niet te onderscheiden van "B verminderd met A" (ADR-011)."""
    assert {c for c, t in TYPEN.items() if t.get("volgorde")} == {"invoer", "operand"}


def test_uitvoer_kan_ook_een_moment_of_een_subject_of_object_zijn():
    assert set(TYPEN["uitvoer"]["naar"]) == {"Variabele en variabelewaarde", "Rechtssubject", "Rechtsobject",
                                            "Tijdsaanduiding"}


def test_de_paren_van_waarde_vallen_binnen_het_type_en_het_contract():
    t = TYPEN["waarde"]
    subtypes = _subtypes()
    for paar in t["paren"]:
        assert paar["van"] in t["van"] and paar["naar"] in t["naar"], paar
        for kant in ("van_subtype", "naar_subtype"):
            if kant in paar:
                assert paar[kant] in subtypes, paar
    assert all("paren" not in TYPEN[c] for c in TYPEN if c != "waarde")


def test_kardinaliteit_gaat_over_typen_die_de_klasse_raken():
    for klasse, regels in CATALOGUS["kardinaliteit"].items():
        assert klasse in KLASSEN
        for code, grens in regels.items():
            assert klasse in TYPEN[code]["van"] + TYPEN[code]["naar"], (klasse, code)
            assert grens.get("min", 0) <= grens.get("max", grens.get("min", 0)), (klasse, code)


def test_de_uitleg_verwijst_naar_de_catalogus():
    """De typen staan in de catalogus; de uitleg verwijst ernaar en naar zijn bron."""
    uitleg = (SKILL / "references" / "relaties.md").read_text(encoding="utf-8")
    assert "relaties.json" in uitleg and "P18" in uitleg


def test_de_gegenereerde_kopieen_volgen_de_catalogus():
    """api en werkplek dragen een gegenereerde kopie (`genereer_jas_relaties.py`). Een kopie die met de hand is
    bewerkt, of een catalogus die veranderde zonder het script te draaien, loopt hier vast – ook bij een PR die
    alleen de api of de frontend raakt."""
    import runpy

    script = runpy.run_path(str(WORTEL / "tools" / "graph-qa" / "scripts" / "genereer_jas_relaties.py"))
    for doel, inhoud in script["genereer"]().items():
        assert doel.read_text(encoding="utf-8") == inhoud, f"{doel.relative_to(WORTEL)}: draai genereer_jas_relaties.py"
