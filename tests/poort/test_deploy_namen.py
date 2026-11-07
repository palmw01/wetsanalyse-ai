"""De uitrolstappen kennen elke resource die de bicep aanmaakt (B5, ROB-02 en ROB-13).

`opruimen` gooit weg wat niet op de lijst `hoort_erbij` staat. Een resource die er in de bicep bij komt en hier niet,
is bij de eerstvolgende opruimronde een wees en verdwijnt. En `afbreken` wist beide straten, dus mag alleen vanuit de
straat met de reviewer.
"""
from __future__ import annotations

import re
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[2]
WORKFLOW = WORTEL / ".github" / "workflows" / "azure-infra.yml"
BICEPS = [WORTEL / "deploy" / "azure" / "main.bicep", WORTEL / "deploy" / "azure" / "grafana.bicep"]


def _bicep_namen() -> set[str]:
    namen = set()
    for bicep in BICEPS:
        tekst = bicep.read_text(encoding="utf-8")
        variabelen = dict(re.findall(r"^(?:var|param) (\w+)(?: \w+)? = '([^']*)'", tekst, re.M))
        for kop, naam in re.findall(r"^resource \w+ '[^']+'( existing)?[^{]*\{\n\s+name: ('[^']*'|\w+)", tekst, re.M):
            if kop:  # een bestaande resource, niet door deze bicep gemaakt
                continue
            naam = naam.strip("'") if naam.startswith("'") else variabelen.get(naam, naam)
            if "${appName}" in naam:
                namen.add(naam.replace("${appName}", "$s"))
    return namen


def _hoort_erbij() -> set[str]:
    tekst = WORKFLOW.read_text(encoding="utf-8")
    return {w for regel in re.findall(r'hoort_erbij="\$hoort_erbij ([^"]*)"', tekst) for w in regel.split()}


def test_elke_resource_uit_de_bicep_staat_op_de_lijst_van_opruimen():
    namen = _bicep_namen()
    assert {"$s-db", "$s-api", "cae-$s"} <= namen, namen  # de parser vond de resources echt, ook via een param
    assert namen - _hoort_erbij() == set(), "voeg ze toe aan hoort_erbij in azure-infra.yml, anders ruimt opruimen ze op"


def test_afbreken_kan_alleen_vanuit_productie():
    tekst = WORKFLOW.read_text(encoding="utf-8")
    blok = tekst[tekst.index('if [ "${{ inputs.actie }}" = "afbreken" ]'):]
    blok = blok[: blok.index("exit 0")]
    assert '"${{ inputs.omgeving }}" != "productie"' in blok
