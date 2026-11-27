"""Drift-guard: kan de agent in de uitgerolde omgeving zijn beurt wél vastleggen?

Waarom deze test bestaat. graph-qa legt de uitkomst van een annotatiebeurt zelf
vast, en daarvoor moet de Azure-bicep de juiste env-namen zetten. Ontbreken ze, dan
staat `legt_zelf_vast` op false en verdwijnt de uitkomst van elke annotatiebeurt:
de werkplek laat de hele beurt en alle elementen zien, en meldt pas aan het eind
dat er niets is vastgelegd.

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

WORTEL = Path(__file__).resolve().parents[4]
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


def test_probes_blijven_binnen_de_azure_limiet() -> None:
    """`initialDelaySeconds` mag bij Container Apps hoogstens 60 zijn.

    Waarom dit een test verdient: hoger wordt geweigerd met
    `ContainerAppProbeInitialDelaySecondsOutOfRange`, maar dat is een preflight-controle van de
    resource provider en `az deployment group what-if` voert die NIET uit. Een groene what-if
    bewijst hier dus niets — de fout valt pas bij een echte deploy.

    Omdat infra handmatig wordt uitgerold, kan een onuitrolbare template dagen in master staan
    zonder dat iemand het merkt; pas de eerstvolgende deploy loopt erop vast. Deze test kost niets
    en verplaatst die ontdekking naar de pull request.
    """
    tekst = BICEP.read_text(encoding="utf-8")
    te_hoog = [
        (nr, int(m.group(1)))
        for nr, regel in enumerate(tekst.splitlines(), 1)
        if (m := re.search(r"initialDelaySeconds:\s*(\d+)", regel)) and int(m.group(1)) > 60
    ]
    assert not te_hoog, (
        "initialDelaySeconds > 60 wordt door Azure geweigerd (what-if merkt het niet): "
        + ", ".join(f"main.bicep:{nr} = {v}" for nr, v in te_hoog)
        + ". Wil je meer speling? Verhoog failureThreshold – de totale marge is "
          "initialDelay + failureThreshold × periodSeconds."
    )


#: Hoe de image en de poort het NL-model installeren: met zijn hash, zonder iets te bouwen (SonarQube S8541/S8544).
TAALMODEL_INSTALL = "--no-deps --no-build --require-hashes -r taalmodel.txt"


def test_dockerfile_installeert_hetzelfde_taalmodel_als_de_poort() -> None:
    """Het NL-model staat niet in uv.lock; `taalmodel.txt` noemt URL en hash. De image en de poort installeren uit dat
    ene bestand, en spaCy zelf komt in beide uit de lock (de extra `nlp`). Loopt dat uit de pas, dan meet CI een ander
    model dan er draait."""
    taalmodel = (WORTEL / "tools/graph-qa/taalmodel.txt").read_text(encoding="utf-8")
    dockerfile = (WORTEL / "tools/graph-qa/Dockerfile").read_text(encoding="utf-8")
    poort = (WORTEL / ".github/workflows/poort.yml").read_text(encoding="utf-8")
    regels = [r for r in taalmodel.replace("\\\n", " ").splitlines() if r.strip() and not r.lstrip().startswith("#")]
    assert len(regels) == 1, regels
    assert regels[0].startswith("nl-core-news-md @ https://github.com/explosion/spacy-models/releases/download/")
    assert re.search(r"--hash=sha256:[0-9a-f]{64}$", regels[0]), "het model zonder hash: --require-hashes faalt"
    assert "COPY tools/graph-qa/pyproject.toml tools/graph-qa/uv.lock tools/graph-qa/taalmodel.txt" in dockerfile
    assert TAALMODEL_INSTALL in dockerfile and TAALMODEL_INSTALL in poort
    assert "--extra nlp" in dockerfile


def test_het_taalmodel_staat_niet_in_de_lock() -> None:
    """Een directe URL in uv.lock liet Dependabot elke update van graph-qa weigeren
    (private_source_authentication_failure, okt–nov 2026). Het model staat in [tool.graph-qa] en de poort installeert
    het uit `taalmodel.txt`."""
    lock = (WORTEL / "tools/graph-qa/uv.lock").read_text(encoding="utf-8")
    pyproject = (WORTEL / "tools/graph-qa/pyproject.toml").read_text(encoding="utf-8")
    assert "nl-core-news-md" not in lock
    assert "[tool.uv.sources]" not in pyproject or "spacy-models" not in pyproject.split("[tool.uv.sources]")[1].split("\n[")[0]
    poort = (WORTEL / ".github/workflows/poort.yml").read_text(encoding="utf-8")
    assert "taalmodel.txt" in poort, "de poort installeert het taalmodel niet meer: de parsertests slaan zich over"
