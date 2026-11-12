"""Een methode-skill toevoegen zonder code (ADR-014 §7): een map met `SKILL.md`, `agentrollen.json` en een bronregister.

Het bewijs, zoals de nep-connector in `test_connectorbeschrijving.py`. Een nep-skill vult de bestaande rol `duiding` aan.
Zonder één regel code buiten zijn map:
- staat hij in het pakket en in de catalogus;
- draagt de specialist `duiding` zijn sectie, en een andere specialist niet (contextisolatie);
- verandert de vingerafdruk van die ene rol.
Een nieuwe rol, een sectie-id of broncode die al bestaat, en letterlijke tekst zonder `BRON.md` worden geweigerd.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from bronmodel import catalogus as bc

from agent import catalogus as cat
from agent import methode, specialists
from agent.methodepakket import PAKKET
from scripts.genereer_methodepakket import SKILL, compileer

TEKST = "Een scenario beschrijft wat een burger doorloopt; noem bij elke stap de bepaling die hem draagt."


def _nep_skill(map_: Path, *, rollen: dict | None = None, sectie: str = "nep-scenario", code: str = "NX1",
               letterlijk: str = "nee") -> Path:
    skill = map_ / "nepmethode"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: nepmethode\ndescription: >-\n  Een nepmethode voor de test.\nmetadata:\n"
        '  methode_versie: "0.1"\n  lex_soort: "methode"\n  lex_label: "Nepmethode"\n'
        '  lex_herkomst: "eigen testtekst"\n  lex_licentie: "repo"\n'
        f'  lex_letterlijk: "{letterlijk}"\n---\n\n# Nepmethode\n')
    (skill / "references/bronnen.md").write_text(f"| code | bron |\n|---|---|\n| {code} | testbron |\n")
    (skill / "references/nep.md").write_text(f"<!-- methode:{sectie}:begin -->\n{TEKST}\n<!-- methode:{sectie}:end -->\n")
    (skill / "agentrollen.json").write_text(json.dumps({
        "secties": {sectie: {"bestand": "references/nep.md", "bronnen": [code]}},
        "rollen": rollen if rollen is not None else {"duiding": [sectie]}}))
    return skill


@pytest.fixture
def met_nep_skill(tmp_path, monkeypatch):
    pakket = compileer(SKILL, extra=[_nep_skill(tmp_path)])
    monkeypatch.setattr(methode, "PAKKET", pakket)
    monkeypatch.setattr(cat, "PAKKET", pakket)
    cat.catalogus.cache_clear()
    yield pakket
    cat.catalogus.cache_clear()


def test_de_skill_vult_alleen_zijn_eigen_rol_aan(met_nep_skill):
    assert met_nep_skill["rollen"]["duiding"] == [*PAKKET["rollen"]["duiding"], "nep-scenario"]
    assert all(met_nep_skill["rollen"][r] == PAKKET["rollen"][r] for r in PAKKET["rollen"] if r != "duiding")
    assert TEKST in specialists.get("duiding").system
    assert TEKST not in specialists.get("definitie").system


def test_de_vingerafdruk_van_alleen_die_rol_verandert(met_nep_skill, monkeypatch):
    nieuw = {r: methode.vingerafdruk(r) for r in PAKKET["rollen"]}
    monkeypatch.setattr(methode, "PAKKET", PAKKET)
    oud = {r: methode.vingerafdruk(r) for r in PAKKET["rollen"]}
    assert {r for r in oud if oud[r] != nieuw[r]} == {"duiding"}


def test_de_catalogus_toont_de_skill_en_volgt_de_regels(met_nep_skill):
    alle = {o.id: o for o in cat.catalogus()}
    nep = alle["methode/nepmethode"]
    assert nep.inhoud["rollen"] == {"duiding": ["nep-scenario"]}
    assert nep.herkomst.verwijzing == ("NX1",)
    assert nep.bewerkbaar == ("nep-scenario",)
    secties = alle["rol/duiding"].inhoud["secties"]
    assert secties[-1]["skill"] == "nepmethode" and secties[-1]["tekst"] == TEKST
    assert alle["rol/duiding"].versie == methode.vingerafdruk("duiding")
    for o in alle.values():
        for d in o.hangt_af_van:
            assert alle[d].concept in bc.MAG_GEBRUIKEN[o.concept], (o.id, d)


@pytest.mark.parametrize("fout", ["nieuwe_rol", "sectie_bestaat", "code_bestaat", "letterlijk_zonder_bron"])
def test_wat_code_vraagt_of_botst_wordt_geweigerd(tmp_path, fout):
    kwargs = {"nieuwe_rol": {"rollen": {"scenario": ["nep-scenario"]}},
              "sectie_bestaat": {"sectie": "basis"},
              "code_bestaat": {"code": next(iter(PAKKET["secties"]["basis"]["bronnen"]))},
              "letterlijk_zonder_bron": {"letterlijk": "ja"}}[fout]
    with pytest.raises(ValueError):
        compileer(SKILL, extra=[_nep_skill(tmp_path, **kwargs)])
