"""Drift-guard: kan de agent in de uitgerolde omgeving zijn beurt wél vastleggen?

Waarom deze test bestaat. Op 19 aug 2026 verhuisde het schrijfpad van de werkplek
naar graph-qa zelf (commit 98eef5a, "één schrijfpad"). Die commit richtte de
dev-compose en de toenmalige Portainer-stack netjes in, maar raakte de Azure-bicep
niet. Daardoor stond `legt_zelf_vast` daar op false en verdween de uitkomst van
elke annotatiebeurt: de werkplek liet supervisor, Critic en vier elementen zien,
en meldde pas aan het eind dat er niets was vastgelegd.

Dat is precies het faalgedrag waar geen compiler tegen beschermt. De agent leest
env-namen, de bicep schrijft ze, en die twee leven in verschillende talen. Zelfde
idioom als `test_namespace_drift.py`: de deploy-bestanden worden als **tekst**
gelezen, niet uitgevoerd – we toetsen dat de namen op elkaar aansluiten, niet wat
er in een draaiende omgeving staat.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

WORTEL = Path(__file__).resolve().parents[3]
BICEP = WORTEL / "deploy" / "azure" / "main.bicep"
GEN_DEPLOY = WORTEL / "deploy" / "azure" / "gen-deploy.py"

# De twee waarden waar `Settings.legt_zelf_vast` op staat of valt (agent/config.py).
VEREIST = ("WETSANALYSE_API_URL", "WETSANALYSE_API_TOKEN")


@pytest.mark.skipif(not BICEP.is_file(), reason="deploy/azure/main.bicep niet aanwezig")
def test_bicep_zet_het_schrijfpad_voor_graph_qa() -> None:
    tekst = BICEP.read_text(encoding="utf-8")
    for naam in VEREIST:
        # `<NAAM>` of `<NAAM>_FILE` – `_read_secret` accepteert allebei.
        assert re.search(rf"'{naam}(_FILE)?'", tekst), (
            f"{naam} ontbreekt in main.bicep. Zonder deze env-var is `legt_zelf_vast` false en "
            f"legt graph-qa de uitkomst van een annotatiebeurt niet vast – zichtbaar pas aan het "
            f"eind van een beurt, als foutmelding aan de gebruiker."
        )


@pytest.mark.skipif(not GEN_DEPLOY.is_file(), reason="deploy/azure/gen-deploy.py niet aanwezig")
def test_api_tokenlijst_kent_graph_qa_als_eigen_client() -> None:
    tekst = GEN_DEPLOY.read_text(encoding="utf-8")
    treffer = re.search(r'"apiTokens":\s*\{"value":\s*f?"([^"]+)"', tekst)
    assert treffer, "apiTokens niet gevonden in gen-deploy.py"
    lijst = treffer.group(1)
    assert "graph-qa:" in lijst, (
        f"de api-tokenlijst kent geen client `graph-qa` (nu: {lijst!r}). Dan wijst graph-qa zich af "
        f"bij de api en landt een annotatie alsnog nergens. Een eigen token per client houdt "
        f"bovendien het auditspoor eerlijk."
    )
