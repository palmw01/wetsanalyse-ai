"""De parallelle `poort`: één verplichte check bovenop parallelle jobs, en shards die niets verliezen.

`poort.yml` draait sinds 12 nov 2026 per onderdeel een eigen job, de trage in shards. Wat daarbij stil mis kan gaan:
een shard die een testbestand of browsertest laat vallen, een nieuwe job die de aggregaatjob niet afwacht (dan mergt
een PR terwijl die job nog rood wordt), een `paths`-filter (dan blijft de check op "expected" staan), of een
aggregaatjob zonder `if: always()` (die wordt dan overgeslagen bij een fout, en overgeslagen telt als geslaagd).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys

import pytest

from routeboek import WORTEL

POORT = WORTEL / ".github" / "workflows" / "poort.yml"
TEKST = POORT.read_text(encoding="utf-8")

sys.path.insert(0, str(WORTEL / "scripts"))
import pytest_shard  # noqa: E402


def _jobs() -> dict[str, str]:
    _, _, rest = TEKST.partition("\njobs:\n")
    delen = re.split(r"^  ([A-Za-z0-9_-]+):\s*$", rest, flags=re.M)
    return dict(zip(delen[1::2], delen[2::2]))


JOBS = _jobs()


def test_geen_paths_filter():
    kop = TEKST.partition("\njobs:\n")[0]
    assert not re.search(r"^\s*paths(-ignore)?:", kop, re.M), "een paths-filter laat de verplichte check op expected staan"


def test_de_verplichte_check_heet_poort_en_wacht_op_alles():
    job = JOBS.get("poort")
    assert job, "de aggregaatjob `poort` ontbreekt; branch protection staat op die naam"
    assert re.search(r"^    name: poort\s*$", job, re.M), "de check moet exact `poort` heten"
    assert re.search(r"^    if: always\(\)\s*$", job, re.M), "zonder if: always() wordt `poort` overgeslagen = geslaagd"
    m = re.search(r"^    needs: \[(.*)\]\s*$", job, re.M)
    assert m, "`poort` mist zijn needs-lijst"
    nodig = {n.strip() for n in m.group(1).split(",")}
    assert nodig == set(JOBS) - {"poort"}, f"`poort` wacht niet op alle jobs: mist {set(JOBS) - {'poort'} - nodig}"
    assert '"raakt", "guards"' in job, "raakt en guards moeten echt slagen, niet overgeslagen"


def test_alleen_de_detectie_heeft_de_volle_historie():
    """fetch-depth 0 kost tijd; alleen `raakt` rekent een merge-base."""
    for naam, job in JOBS.items():
        if "fetch-depth: 0" in job:
            assert naam == "raakt", f"job `{naam}` haalt de volle historie op"


def test_postgres_alleen_waar_een_dsn_is():
    for naam, job in JOBS.items():
        heeft_dsn = "_TEST_DSN:" in job
        heeft_service = "image: postgres:" in job
        assert heeft_dsn == heeft_service, f"job `{naam}`: DSN={heeft_dsn} maar postgres-service={heeft_service}"


@pytest.mark.parametrize("naam", ["graph-qa", "api", "frontend-browser"])
def test_de_shards_tellen_kloppen(naam):
    """Het aantal shards staat in de matrix én in de aanroep; lopen die uiteen, dan valt een deel weg."""
    job = JOBS[naam]
    shards = re.search(r"shard: \[([\d, ]+)\]", job).group(1)
    n = len(shards.split(","))
    assert [int(s) for s in shards.split(",")] == list(range(1, n + 1)), f"{naam}: shards zijn geen 1..{n}"
    noemers = set(re.findall(r"\$\{\{ matrix\.shard \}\}/(\d+)", job))
    assert noemers == {str(n)}, f"{naam}: matrix heeft {n} shards, de aanroep deelt door {noemers}"


@pytest.mark.parametrize("naam", ["graph-qa", "api"])
def test_python_shards_gebruiken_de_plugin(naam):
    job = JOBS[naam]
    assert "-p pytest_shard" in job and "PYTEST_SHARD:" in job and "/scripts" in job


@pytest.mark.parametrize("totaal", [1, 2, 3, 5])
def test_pytest_shard_verliest_niets(totaal):
    aantallen = {f"tests/test_{i}.py": (i * 7) % 13 + 1 for i in range(40)}
    shards = pytest_shard.verdeel(aantallen, totaal)
    alles = [p for s in shards for p in s]
    assert sorted(alles) == sorted(aantallen), "een bestand zit in geen of in twee shards"
    assert pytest_shard.verdeel(aantallen, totaal) == shards, "de verdeling is niet deterministisch"


def test_pytest_shard_zonder_env_doet_niets(monkeypatch):
    monkeypatch.delenv("PYTEST_SHARD", raising=False)
    items = [object()]
    pytest_shard.pytest_collection_modifyitems(None, items)
    assert len(items) == 1


@pytest.mark.skipif(not shutil.which("node"), reason="node ontbreekt")
def test_browsershards_dekken_test_browser():
    pakket = json.loads((WORTEL / "frontend" / "package.json").read_text(encoding="utf-8"))
    verwacht = re.findall(r"node (scripts/[\w-]+\.mjs)", pakket["scripts"]["test:browser"])
    uit = subprocess.run(["node", "scripts/browsertests.mjs", "--lijst", "4"], cwd=WORTEL,
                         capture_output=True, text=True, check=True).stdout
    gevonden = [t for regel in uit.splitlines() for t in regel.partition(": ")[2].split()]
    assert sorted(gevonden) == sorted(verwacht), "een browsertest valt buiten de shards of staat er dubbel in"
    assert len(uit.splitlines()) == 4
