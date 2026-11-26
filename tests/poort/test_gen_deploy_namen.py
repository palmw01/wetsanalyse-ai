"""`gen-deploy.py` laat alleen een Azure-naam het `az`-commando in (SonarQube S8705).

Een resource group `--subscription=…` of `-h` zou `az` anders als eigen optie lezen.
"""
from __future__ import annotations

import argparse
import importlib.util

import pytest

from routeboek import WORTEL

_spec = importlib.util.spec_from_file_location("gen_deploy", WORTEL / "deploy" / "azure" / "gen-deploy.py")
gen_deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen_deploy)


@pytest.mark.parametrize("naam", ["rg-wetsanalyse", "wetsanalyse-prd", "westeurope", "rg_test.(1)"])
def test_echte_namen_mogen(naam):
    assert gen_deploy.azure_naam(naam) == naam


@pytest.mark.parametrize("naam", ["", "--subscription=x", "-h", "rg wetsanalyse", "rg;rm", "a" * 91, "rg\n--debug"])
def test_wat_az_als_optie_of_meer_kan_lezen_mag_niet(naam):
    with pytest.raises(argparse.ArgumentTypeError):
        gen_deploy.azure_naam(naam)
