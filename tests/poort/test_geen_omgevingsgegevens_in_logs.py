"""Een adres van een omgeving staat nooit leesbaar in een runlog.

GitHub zet de waarde van een var leesbaar in het env-blok van elke stap, en de runlogs van deze publieke repo kan iedereen
lezen. Een secret maskeert GitHub overal. Op 17 nov 2026 stond het endpoint van Azure AI Foundry (`LLM_API_BASE`, een
var) zo in elke run van `azure-infra`. Een endpoint, url, host of adres komt daarom alleen uit `secrets.`, nooit uit
`vars.`. Alleen stdlib."""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
VAR = re.compile(r"\$\{\{\s*vars\.([A-Za-z0-9_]+)")
ADRES = re.compile(r"(URL|URI|BASE|HOST|ENDPOINT|ADRES|DOMEIN|DOMAIN|IP)(_|$)")


def _vars() -> dict[str, list[str]]:
    gevonden: dict[str, list[str]] = {}
    for p in sorted(WORKFLOWS.glob("*.y*ml")):
        for naam in VAR.findall(p.read_text(encoding="utf-8")):
            gevonden.setdefault(naam, []).append(p.name)
    return gevonden


def test_er_zijn_vars_om_te_toetsen():
    assert "APP_NAME" in _vars()


def test_geen_adres_uit_een_var():
    fout = {n: w for n, w in _vars().items() if ADRES.search(n)}
    assert not fout, f"een adres hoort in een secret, niet in een var (leesbaar in de runlog): {fout}"


def test_het_endpoint_van_het_model_is_een_secret():
    tekst = (WORKFLOWS / "azure-infra.yml").read_text(encoding="utf-8")
    assert "LLM_API_BASE: ${{ secrets.LLM_API_BASE }}" in tekst
