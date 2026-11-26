"""De padcontrole (`padcontrole.py`, Sonar `pythonsecurity:S8707` en `S8705`): één helper, vier gelijke kopieën.

Een script dat een pad uit `argv` opent, kan voor wie het aanroept – ook een agent – overal lezen en schrijven.
`veilig_pad` laat alleen een pad binnen de werkmap, de thuismap of de tijdelijke map toe; `veilig_argument` alleen een
onschuldige waarde voor een extern commando. De kopieën staan in onderdelen zonder gedeeld pakket en moeten gelijk
blijven; daarna het gedrag, en per onderdeel dat het misbruik echt geweigerd wordt.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from routeboek import WORTEL

KOPIEEN = [
    WORTEL / "tools" / "graph-qa" / "eval" / "padcontrole.py",
    WORTEL / "tools" / "bwb-import" / "app" / "padcontrole.py",
    WORTEL / "deploy" / "azure" / "padcontrole.py",
    WORTEL / "scripts" / "padcontrole.py",
]


def _laad():
    spec = importlib.util.spec_from_file_location("padcontrole_poort", KOPIEEN[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pc = _laad()


def test_de_kopieen_zijn_gelijk():
    eerste = KOPIEEN[0].read_bytes()
    for kopie in KOPIEEN[1:]:
        assert kopie.read_bytes() == eerste, f"{kopie.relative_to(WORTEL)} wijkt af van {KOPIEEN[0].relative_to(WORTEL)}"


def test_een_pad_binnen_de_basis_komt_er_canoniek_uit(tmp_path):
    (tmp_path / "a").mkdir()
    assert pc.veilig_pad(tmp_path / "a" / ".." / "b.json", basis=[tmp_path]) == (tmp_path / "b.json").resolve()
    assert pc.veilig_pad(tmp_path, basis=[tmp_path]) == tmp_path.resolve()
    assert pc.veilig_pad(str(tmp_path / "nieuw" / "x.md"), basis=[tmp_path]) == (tmp_path / "nieuw" / "x.md").resolve()


@pytest.mark.parametrize("pad", ["../buiten.json", "/etc/passwd", "../../../../../../etc/passwd"])
def test_een_pad_buiten_de_basis_wordt_geweigerd(tmp_path, pad):
    basis = tmp_path / "basis"
    basis.mkdir()
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_pad(basis / pad if not pad.startswith("/") else pad, basis=[basis])


def test_een_naam_die_alleen_zo_begint_valt_erbuiten(tmp_path):
    """`/basis-geheim` begint met `/basis`, maar ligt er niet in (partial path traversal)."""
    (tmp_path / "basis").mkdir()
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_pad(tmp_path / "basis-geheim" / "x", basis=[tmp_path / "basis"])


def test_een_symlink_naar_buiten_wordt_geweigerd(tmp_path):
    basis, buiten = tmp_path / "basis", tmp_path / "buiten"
    basis.mkdir()
    buiten.mkdir()
    (basis / "link").symlink_to(buiten)
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_pad(basis / "link" / "geheim.txt", basis=[basis])


def test_de_standaardbasis_is_werkmap_thuismap_en_tijdelijke_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert pc.veilig_pad("uit.json") == (tmp_path / "uit.json").resolve()
    assert pc.veilig_pad("~/x.json") == Path(os.path.realpath(os.path.expanduser("~/x.json")))
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_pad("/etc/passwd")


def test_de_wortel_telt_nooit_als_basis(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", "/")
    monkeypatch.chdir(tmp_path)
    assert "/" not in pc.basismappen()
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_pad("/etc/passwd")


def test_de_fout_is_een_valueerror_en_argparse_toont_hem():
    import argparse
    assert issubclass(pc.OnveiligPad, ValueError)
    assert issubclass(pc.OnveiligPad, argparse.ArgumentTypeError)


@pytest.mark.parametrize("waarde", ["rg-wetsanalyse", "wetsanalyse-prd", "westeurope", "a.b_c:d/e@f=g+h"])
def test_een_gewoon_argument_mag(waarde):
    assert pc.veilig_argument(waarde) == waarde


@pytest.mark.parametrize("waarde", ["--subscription", "-x", "rg wetsanalyse", "rg;rm", "", "rg\n--debug", "$(id)"])
def test_een_argument_dat_een_optie_of_meer_kan_zijn_wordt_geweigerd(waarde):
    with pytest.raises(pc.OnveiligPad):
        pc.veilig_argument(waarde)


# --- De gebruikers ---------------------------------------------------------------------------------------------------

GEN_DEPLOY = WORTEL / "deploy" / "azure" / "gen-deploy.py"


def _gen_deploy(tmp_path, *extra):
    env = {**os.environ, "HOME": str(tmp_path), "AZURE_AI_KEY": "test-sleutel"}
    for naam in list(env):
        if naam.startswith("WA_"):
            del env[naam]
    return subprocess.run([sys.executable, str(GEN_DEPLOY), "--llm-api-base", "https://llm.example", *extra], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)


def test_gen_deploy_schrijft_het_parameterbestand_binnen_de_werkmap(tmp_path):
    r = _gen_deploy(tmp_path, "--params-file", "params.json")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "params.json").is_file()
    assert "--resource-group rg-wetsanalyse" in r.stderr


def test_gen_deploy_weigert_een_parameterbestand_buiten_de_basis(tmp_path):
    r = _gen_deploy(tmp_path, "--params-file", "/etc/wa-params.json")
    assert r.returncode == 2
    assert "valt buiten de toegestane mappen" in r.stderr


def test_gen_deploy_weigert_een_licentiebestand_buiten_de_basis(tmp_path):
    r = _gen_deploy(tmp_path, "--license-file", "/etc/hostname", "--params-file", "params.json")
    assert r.returncode == 2
    assert not (tmp_path / "params.json").exists()


def test_gen_deploy_weigert_een_resource_group_die_een_optie_is(tmp_path):
    r = _gen_deploy(tmp_path, "--resource-group=--subscription=x", "--params-file", "params.json")
    assert r.returncode == 2
    assert "geen toegestane vorm" in r.stderr
    assert not (tmp_path / "params.json").exists()


def test_kwaliteit_schrijft_zijn_rapport_niet_buiten_de_basis(monkeypatch, tmp_path):
    sys.path.insert(0, str(WORTEL / "scripts"))
    import kwaliteit
    monkeypatch.setattr(kwaliteit, "_git", lambda *a: "abc\n")
    monkeypatch.setattr(kwaliteit, "meet", lambda basis, dekking: {})
    monkeypatch.setattr(kwaliteit, "markdown", lambda rapport: "rapport")
    monkeypatch.chdir(tmp_path)
    kwaliteit.main(["--basis", "HEAD", "--uit", "rapport"])
    assert (tmp_path / "rapport" / "kwaliteit.md").read_text(encoding="utf-8") == "rapport"
    with pytest.raises(ValueError, match="buiten de toegestane mappen"):
        kwaliteit.main(["--basis", "HEAD", "--uit", "/etc/wa-kwaliteit"])
