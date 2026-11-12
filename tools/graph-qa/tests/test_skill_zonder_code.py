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
import yaml
from bronmodel import catalogus as bc

from agent import catalogus as cat
from agent import methode, methodepakket, specialists
from agent.begrippen_pipeline import patronen
from agent.jas_pipeline.detectoren import BronTekst
from agent.jas_pipeline.detectoren.regels import RegelDetector, alle_regels
from agent.methodepakket import PAKKET
from scripts.genereer_methodepakket import SKILL, compileer

TEKST = "Een scenario beschrijft wat een burger doorloopt; noem bij elke stap de bepaling die hem draagt."


JAS_REGEL = {
    "id": "jas.nepmethode.redelijke_termijn", "klassen": ["Tijdsaanduiding"], "code": "TEMPORAL_DURATION",
    "bewijs": "zwak", "bron": "nepbron", "versie": 1, "patroon": r"\bbinnen een redelijke termijn\b",
    "tests": {"positief": [{"tekst": "De inspecteur beslist binnen een redelijke termijn.", "span": "binnen een redelijke termijn"}],
              "negatief": [{"tekst": "De termijn is redelijk."}],
              "rand": [{"tekst": "Binnen een redelijke termijn.", "span": "Binnen een redelijke termijn"}],
              "overlap": [{"tekst": "binnen een redelijke termijn", "spans": ["binnen een redelijke termijn"]}]}}
BEGRIP_REGEL = {
    "id": "begrip.nepmethode.telt_als", "hypothese": "kwalificatie", "code": "KWALIFICATIE", "polariteit": "steun",
    "sterkte": "middel", "bron": "nepbron", "versie": 1, "patroon": r"\b(?P<van>[\w-]+)\s+telt\s+als\s+(?P<naar>[\w-]+)",
    "tests": {"positief": [{"tekst": "Een eenheid telt als belastingplichtige.", "van": "eenheid", "naar": "belastingplichtige"}],
              "negatief": [{"tekst": "Een eenheid geldt niet."}],
              "rand": [{"tekst": "eenheid telt als plichtige", "van": "eenheid", "naar": "plichtige"}],
              "overlap": [{"tekst": "Een eenheid telt als belastingplichtige.", "van": "eenheid", "naar": "belastingplichtige"}]}}


def _nep_skill(map_: Path, *, rollen: dict | None = None, sectie: str = "nep-scenario", code: str = "NX1",
               letterlijk: str = "nee", regels: dict[str, list[dict]] | None = None) -> Path:
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
    for keten, items in (regels or {}).items():
        (skill / "regels" / keten).mkdir(parents=True)
        (skill / "regels" / keten / "nep.yaml").write_text(yaml.safe_dump(items, allow_unicode=True))
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



# --- regels uit een skill, achter de proefvlag SKILL_REGELS (S6) -----------------------------------------------------

@pytest.fixture
def met_regels(tmp_path, monkeypatch):
    pakket = compileer(SKILL, extra=[_nep_skill(tmp_path, regels={"jas": [JAS_REGEL], "begrippen": [BEGRIP_REGEL]})])
    for mod in (methodepakket, methode, cat):
        monkeypatch.setattr(mod, "PAKKET", pakket)

    def wis():
        cat.catalogus.cache_clear()
        alle_regels.cache_clear()
        patronen.alle_regels.cache_clear()
    wis()
    yield pakket
    monkeypatch.undo()
    wis()


def test_het_pakket_bundelt_de_regels_van_de_skill(met_regels):
    assert met_regels["regels"] == {"jas": {"nepmethode.nep": [JAS_REGEL]}, "begrippen": {"nepmethode.nep": [BEGRIP_REGEL]}}


def test_zonder_vlag_doen_ze_niet_mee(met_regels, monkeypatch):
    monkeypatch.delenv("SKILL_REGELS", raising=False)
    assert JAS_REGEL["id"] not in {r.id for r in alle_regels()}
    assert BEGRIP_REGEL["id"] not in {r.id for r in patronen.alle_regels()}


def test_met_vlag_vuren_ze_op_hun_eigen_tests(met_regels, monkeypatch):
    monkeypatch.setenv("SKILL_REGELS", "true")
    regel = next(r for r in alle_regels() if r.id == JAS_REGEL["id"])
    assert regel.detector == "nepmethode.nep"
    vind = lambda t: {k.span.tekst for k in RegelDetector(regel.detector, (regel,)).detecteer(BronTekst.van_tekst("urn:t", t)).kandidaten}
    for g in (*JAS_REGEL["tests"]["positief"], *JAS_REGEL["tests"]["rand"]):
        assert g["span"] in vind(g["tekst"])
    for g in JAS_REGEL["tests"]["negatief"]:
        assert not vind(g["tekst"])
    patroon = next(r for r in patronen.alle_regels() if r.id == BEGRIP_REGEL["id"]).patroon
    for g in BEGRIP_REGEL["tests"]["positief"]:
        m = patroon.search(g["tekst"])
        assert (m.group("van"), m.group("naar")) == (g["van"], g["naar"])


def test_de_catalogus_toont_ze_als_deel_van_de_skill_achter_de_vlag(met_regels):
    alle = {o.id: o for o in cat.catalogus()}
    jas = alle["regelset/jas.nepmethode.nep"]
    assert jas.straat == "SKILL_REGELS" and jas.deel_van == "methode/nepmethode"
    assert jas.inhoud["regels"][0]["id"] == JAS_REGEL["id"]
    assert "regelset/jas.nepmethode.nep" in alle["workflow/annotatieketen"].hangt_af_van
    assert "regelset/begrippen.nepmethode.nep" in alle["workflow/begrippenketen"].hangt_af_van


@pytest.mark.parametrize("fout", ["code_zonder_verklaring", "verkeerd_voorvoegsel", "zonder_tests", "onbekende_keten"])
def test_een_ongeldige_skillregel_wordt_geweigerd(tmp_path, fout):
    regel = dict(JAS_REGEL)
    keten = "jas"
    if fout == "code_zonder_verklaring":
        regel["code"] = "NIET_BESTAAND"
    if fout == "verkeerd_voorvoegsel":
        regel["id"] = "jas.tijd.redelijke_termijn"
    if fout == "zonder_tests":
        regel["tests"] = {"positief": JAS_REGEL["tests"]["positief"]}
    if fout == "onbekende_keten":
        keten = "onzin"
    with pytest.raises(ValueError):
        compileer(SKILL, extra=[_nep_skill(tmp_path, regels={keten: [regel]})])
