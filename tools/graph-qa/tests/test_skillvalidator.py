"""De validator van een methode-skill (ADR-016 §B2, poort 1): de Agent Skills-specificatie plus de regels van Lex.

Eén validator voor de generator en de werkplaats, in `bronmodel.skill`. Hier staat wat hij weigert, per regel één geval,
en dat de skills in de repo hem halen. Dat het methodepakket er byte-gelijk uit komt, bewaakt `test_methodepakket.py`.
"""
from __future__ import annotations

import json

import pytest
from bronmodel import skill as sk
from bronmodel.validatie import ValidatieFout, frontmatter

from scripts.genereer_methodepakket import ROLLEN, SKILL, SKILLS, methode_skills

SECTIE = "nep-scenario"


def _skill(**anders) -> dict[str, str]:
    """Een kleinste geldige skill `nepmethode`, als afbeelding van pad naar tekst."""
    kop = {"name": "nepmethode", "description": "Een nepmethode voor de test.",
           "metadata": {"methode_versie": "0.1", "lex_soort": "methode", "lex_label": "Nepmethode",
                        "lex_herkomst": "eigen testtekst", "lex_licentie": "repo", "lex_letterlijk": "nee"}}
    kop |= anders.pop("kop", {})
    kop["metadata"] = kop["metadata"] | anders.pop("metadata", {})
    for weg in anders.pop("zonder", ()):
        kop.pop(weg, None), kop["metadata"].pop(weg, None)
    rollen = anders.pop("rollen", {"duiding": [SECTIE]})
    secties = anders.pop("secties", {SECTIE: {"bestand": "references/nep.md", "bronnen": ["NX1"]}})
    bestanden = {
        "SKILL.md": "---\n" + json.dumps(kop, indent=1) + "\n---\n\n# Nepmethode\n",
        "agentrollen.json": json.dumps({"secties": secties, "rollen": rollen}),
        "references/bronnen.md": "| code | bron |\n|---|---|\n| NX1 | testbron |\n",
        "references/nep.md": f"<!-- methode:{SECTIE}:begin -->\nNoem de bepaling.\n<!-- methode:{SECTIE}:end -->\n",
    }
    bestanden |= anders.pop("bestanden", {})
    for weg in anders.pop("zonder_bestand", ()):
        del bestanden[weg]
    assert not anders
    return bestanden


def _codes(bestanden, *, naam="nepmethode", basis=False) -> set[str]:
    skill, bevindingen = sk.toets(naam, bestanden, rollen=ROLLEN, basis=basis)
    assert (skill is None) == bool(bevindingen)
    return {b.code for b in bevindingen}


def test_de_skills_in_de_repo_halen_de_validator():
    for pad in [SKILL, *methode_skills()]:
        skill, bevindingen = sk.toets(pad.name, sk.lees_map(pad), rollen=ROLLEN, basis=pad == SKILL)
        assert not bevindingen, [str(b) for b in bevindingen]
        assert skill.naam == pad.name
    assert {p.name for p in methode_skills()} == {p.parent.name for p in SKILLS.glob("*/SKILL.md")} - {SKILL.name}


def test_een_geldige_skill_levert_wat_het_pakket_nodig_heeft():
    skill = sk.valideer("nepmethode", _skill(bestanden={"BRON.md": "bron"}), rollen=ROLLEN)
    assert skill.versie == "0.1" and skill.rollen == {"duiding": [SECTIE]}
    assert skill.lex == {"soort": "methode", "label": "Nepmethode", "herkomst": "eigen testtekst", "licentie": "repo",
                         "letterlijk": "nee", "beschrijving": "Een nepmethode voor de test."}
    assert skill.secties[SECTIE] == {"bestand": "references/nep.md", "bronnen": ["NX1"], "tekst": "Noem de bepaling.",
                                     "sha256": sk.sha("Noem de bepaling."), "skill": "nepmethode"}
    assert skill.bestanden == {"SKILL.md", "agentrollen.json", "references/bronnen.md", "references/nep.md", "BRON.md"}


@pytest.mark.parametrize(("anders", "code"), [
    # De Agent Skills-specificatie.
    ({"kop": {"name": "Nep_Methode"}}, "naam"),
    ({"kop": {"name": "nep--methode"}}, "naam"),
    ({"kop": {"name": "n" * 65}}, "naam"),
    ({"kop": {"name": "anders"}}, "naam"),
    ({"zonder": ["description"]}, "beschrijving"),
    ({"kop": {"description": "x" * 1025}}, "beschrijving"),
    ({"kop": {"model": "zwaar"}}, "frontmatter"),
    ({"kop": {"compatibility": "x" * 501}}, "frontmatter"),
    ({"metadata": {"methode_versie": 2.1}}, "metadata"),
    ({"bestanden": {"SKILL.md": "# Zonder frontmatter\n"}}, "frontmatter"),
    ({"bestanden": {"SKILL.md": "---\nname: [\n---\n"}}, "frontmatter"),
    ({"zonder_bestand": ["SKILL.md"]}, "frontmatter"),
    # De regels van Lex.
    ({"zonder": ["methode_versie"]}, "versie"),
    ({"zonder": ["lex_licentie"]}, "lex"),
    ({"metadata": {"lex_extra": "x"}}, "lex"),
    ({"metadata": {"lex_herkomst": " "}}, "lex"),
    ({"metadata": {"lex_soort": "anders"}}, "lex"),
    ({"metadata": {"lex_letterlijk": "misschien"}}, "lex"),
    ({"metadata": {"lex_letterlijk": "ja"}}, "licentie"),
    ({"kop": {"allowed-tools": "Bash"}}, "tools"),
    ({"zonder_bestand": ["agentrollen.json"]}, "rolbestand"),
    ({"bestanden": {"agentrollen.json": "{"}}, "rolbestand"),
    ({"bestanden": {"agentrollen.json": '{"secties": {}}'}}, "rolbestand"),
    ({"zonder_bestand": ["references/bronnen.md"]}, "bronregister"),
    ({"rollen": {"scenario": [SECTIE]}}, "rol"),
    ({"rollen": {"duiding": []}}, "rol"),
    ({"rollen": {"duiding": [SECTIE, SECTIE]}}, "rol"),
    ({"rollen": {"duiding": ["onbekend"]}}, "rol"),
    ({"secties": {SECTIE: {"bestand": "../buiten.md", "bronnen": ["NX1"]}}}, "pad"),
    ({"secties": {SECTIE: {"bestand": "/etc/passwd", "bronnen": ["NX1"]}}}, "pad"),
    ({"secties": {SECTIE: {"bestand": "references/weg.md", "bronnen": ["NX1"]}}}, "pad"),
    ({"secties": {SECTIE: {"bestand": "references/nep.md", "bronnen": ["NX1"], "extra": 1}}}, "sectie"),
    ({"secties": {SECTIE: {"bestand": "references/nep.md", "bronnen": ["M99"]}}}, "broncode"),
    ({"secties": {SECTIE: {"bestand": "references/nep.md", "bronnen": []}}}, "broncode"),
    ({"bestanden": {"references/nep.md": "geen markers"}}, "sectie"),
    # De omvang.
    ({"bestanden": {"references/groot.md": "x" * (sk.MAX_TEKENS_BESTAND + 1)}}, "omvang"),
    ({"bestanden": {f"references/{i}.md": "x" for i in range(sk.MAX_BESTANDEN)}}, "omvang"),
    ({"bestanden": {"references/nep.md": f"<!-- methode:{SECTIE}:begin -->\n{'x' * 6001}\n<!-- methode:{SECTIE}:end -->"}},
     "omvang"),
])
def test_wat_de_validator_weigert(anders, code):
    assert code in _codes(_skill(**anders))


def test_de_validator_meldt_alles_tegelijk():
    """De editor toont de bevindingen naast elkaar; de generator gooit ze in één fout."""
    bestanden = _skill(kop={"name": "Fout"}, zonder=["methode_versie"], rollen={"scenario": [SECTIE]})
    assert {"naam", "versie", "rol"} <= _codes(bestanden)
    with pytest.raises(ValidatieFout) as fout:
        sk.valideer("nepmethode", bestanden, rollen=ROLLEN)
    assert len(fout.value.bevindingen) >= 3 and isinstance(fout.value, ValueError)


def test_de_basis_vult_alle_rollen_en_een_andere_skill_een_deel():
    assert _codes(_skill(), basis=True) == {"rol"}
    assert not _codes(_skill(rollen={}))


def test_sectie_ids_en_broncodes_zijn_van_een_skill():
    een = sk.valideer("nepmethode", _skill(), rollen=ROLLEN)
    ander = lambda **a: sk.valideer("tweede", _skill(kop={"name": "tweede"}, **a), rollen=ROLLEN)  # noqa: E731
    assert {b.code for b in sk.toets_samen([een, ander()])} == {"sectie", "broncode"}
    assert not sk.toets_samen([een, een])
    los = ander(secties={"eigen": {"bestand": "references/nep.md", "bronnen": ["NY1"]}}, rollen={},
                bestanden={"references/bronnen.md": "| NY1 | bron |\n",
                           "references/nep.md": "<!-- methode:eigen:begin -->\nx\n<!-- methode:eigen:end -->"})
    assert not sk.toets_samen([een, los])


def test_een_map_met_iets_anders_dan_tekst_wordt_geweigerd(tmp_path):
    (tmp_path / "SKILL.md").write_text("x")
    (tmp_path / "beeld.png").write_bytes(b"\x89PNG\xff\xfe")
    with pytest.raises(ValidatieFout):
        sk.lees_map(tmp_path)


def test_methode_of_alleen_voor_claude_code():
    assert sk.is_methode(_skill()["SKILL.md"])
    assert not sk.is_methode("---\nname: iets\ndescription: Alleen voor Claude Code.\n---\n")
    # Een kapotte frontmatter laat een methode-skill niet stil uit het pakket vallen: de toets meldt hem.
    assert sk.is_methode('---\nmetadata: [\n  lex_soort: "methode"\n---\n')


def test_frontmatter_en_tekst():
    assert frontmatter("---\nname: a\n---\n\nTekst.\n\nMeer.\n") == ({"name": "a"}, "Tekst.\n\nMeer.")
    for kapot in ["name: a\n", "---\nname: a\n", "---\n- a\n---\n"]:
        with pytest.raises(ValueError):
            frontmatter(kapot)
