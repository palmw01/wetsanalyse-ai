"""De index van de kennisgroepstandpunten komt mee met de connector, en alleen daar (plan-connector-kennisgroepen §2.3).

De connector `kennisgroepen` zoekt in een eigen named graph die `bwb-import --kennisgroepen` vult. Op acceptatie gaat hij
aan door één `azure-infra`-deploy: die geeft alle namen uit `bronmodel.connectors` mee als `connectoren`, zet daarmee
`CONNECTOR_KENNISGROEPEN` én `--kennisgroepen` op de import en de graafwacht, en start daarna de import-job. Deze tests
houden die keten vast, zodat de connector nooit aanstaat zonder dat iemand de index vult, en de index nooit wordt
opgehaald waar niemand hem leest (productie, waar `connectoren` leeg is).
"""
from __future__ import annotations

import re
import sys

from routeboek import WORTEL

BICEP = (WORTEL / "deploy" / "azure" / "main.bicep").read_text(encoding="utf-8")
INFRA = (WORTEL / ".github" / "workflows" / "azure-infra.yml").read_text(encoding="utf-8")


def _job_args() -> list[str]:
    return re.findall(r"^\s+args: (.+)$", BICEP, re.M)


def test_de_connector_staat_in_de_lijst_die_acceptatie_meekrijgt():
    sys.path.insert(0, str(WORTEL / "packages" / "bronmodel"))
    from bronmodel.connectors import CONNECTORS

    assert "kennisgroepen" in CONNECTORS
    assert "from bronmodel.connectors import CONNECTORS" in INFRA


def test_de_index_hangt_alleen_aan_de_connector():
    assert BICEP.count("'--kennisgroepen'") == 1, "`--kennisgroepen` hoort alleen in `kennisgroepenIndex`"
    assert re.search(
        r"^var kennisgroepenIndex = contains\(connectoren, 'kennisgroepen'\) \? \['--kennisgroepen'\] : \[\]$",
        BICEP, re.M), "de index alleen waar de connector in `connectoren` staat"


def test_de_import_en_de_graafwacht_verversen_de_index():
    args = _job_args()
    met_index = [a for a in args if "kennisgroepenIndex" in a]
    assert len(met_index) == 2, args
    import_job, graafwacht = sorted(met_index, key=lambda a: "--alleen-bij-verlies" in a)
    assert "--alleen-bij-verlies" not in import_job
    # De graafwacht peilt de wet en de index elk apart: een lege index is geen verlies van de wetgraaf (en andersom).
    assert "'--alleen-bij-verlies'" in graafwacht


def test_een_deploy_start_de_import_job():
    stap = INFRA.partition("- name: Graaf vullen (import-job)")[2].partition("\n      - name:")[0]
    assert "inputs.actie == 'deploy'" in stap
    assert 'JOB="$APP_NAME-bwb-import"' in stap and "az containerapp job start" in stap
