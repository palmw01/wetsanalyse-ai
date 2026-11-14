"""De actie `2fa-herstel` van azure-infra (README §*2FA voor beheerders*).

Ze wist een tweede factor, met een job die de verbindingsstring van de database draagt, in een repo met openbare
run-logs. Daarom vier vaste vormen: de userid komt nooit via `env:` of `${{ inputs.… }}` in een stap (GitHub zet
de env in de log vóór een `add-mask` werkt), de groepsnaam is de bevestiging, de job verdwijnt altijd weer, en
`opruimen` beschermt hem niet.
"""
from __future__ import annotations

import re
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[2]
WORKFLOW = (WORTEL / ".github" / "workflows" / "azure-infra.yml").read_text(encoding="utf-8")
BICEP = (WORTEL / "deploy" / "azure" / "herstel-2fa.bicep").read_text(encoding="utf-8")


def _stap(naam: str) -> str:
    begin = WORKFLOW.index(f"      - name: {naam}")
    rest = WORKFLOW[begin + 1:]
    volgende = rest.find("\n      - name: ")
    return WORKFLOW[begin: begin + 1 + volgende] if volgende >= 0 else WORKFLOW[begin:]


def test_de_userid_komt_nooit_via_env_of_een_expressie_binnen():
    regels = [r for r in WORKFLOW.splitlines() if "herstel_userid" in r]
    assert regels, "de invoer herstel_userid ontbreekt"
    for regel in regels:
        assert "${{" not in regel, f"lees de userid uit $GITHUB_EVENT_PATH, niet via een expressie: {regel.strip()}"
    for regel in regels:
        if "jq" in regel:
            assert "GITHUB_EVENT_PATH" in regel
    assert not re.search(r"^\s+\w+:\s*\$\{\{\s*inputs\.herstel_userid", WORKFLOW, re.M)


def test_de_userid_wordt_gemaskeerd_voor_hij_ergens_staat():
    for naam in ("Preflight", "2FA herstellen"):
        stap = _stap(naam)
        lezen = stap.index("herstel_userid")
        assert "::add-mask::$userid" in stap[lezen:], naam
        assert stap.index("::add-mask::$userid", lezen) < stap.index("grep -Eq", lezen), naam


def test_bevestiging_met_de_groepsnaam():
    blok = WORKFLOW[WORKFLOW.index('if [ "${{ inputs.actie }}" = "2fa-herstel" ]'):]
    blok = blok[: blok.index("exit 0")]
    assert '"$INVOER_BEVESTIGING" != "$RESOURCE_GROUP"' in blok


def test_de_samenvatting_noemt_het_account_niet():
    stap = _stap("2FA herstellen")
    samenvatting = stap[stap.index("{\n", stap.index("2FA-noodherstel")): stap.index("GITHUB_STEP_SUMMARY")]
    assert "$userid" not in samenvatting


def test_de_job_verdwijnt_altijd_en_staat_niet_op_de_lijst_van_opruimen():
    opruim = _stap("2FA-herstel-job verwijderen")
    assert "always()" in opruim and "job delete" in opruim
    assert "2fa-herstel" not in " ".join(re.findall(r'hoort_erbij="\$hoort_erbij ([^"]*)"', WORKFLOW))


def test_de_job_draagt_het_secret_als_bestand_en_draait_de_module():
    assert "name: '${appName}-2fa-herstel'" in BICEP
    assert "@secure()\n@description('De database-url" in BICEP
    assert "DATABASE_URL_FILE" in BICEP and "storageType: 'Secret'" in BICEP
    assert "'app.herstel_2fa'" in BICEP
    assert "replicaRetryLimit: 0" in BICEP
    assert (WORTEL / "api" / "app" / "herstel_2fa.py").exists()
