#!/usr/bin/env python3
"""Genereer de gaten van een afleidingsregel (activiteit 3b) uit de wetsanalyse-skill naar de api.

De bron is `.claude/skills/wetsanalyse/regelgaten.json` (ADR-018 besluit 7.6, bijlage A §4.2). De volledigheidstoets in
de api (`api/app/regelskelet.gaten` voor het skelet, `api/app/regel_store` voor de regel en de keten) leest de codes en
meldingen uit een gegenereerde kopie, zoals de relatiecatalogus. Wie een gat wil wijzigen, bewerkt de JSON en draait dit
script; een met de hand bewerkte kopie faalt op `--check`. `tests/poort/test_regelgaten.py` toetst dat de skill
(`references/afleidingsregels.md`, *Wat een regel mist*) dezelfde codes noemt.

Alleen de standaardbibliotheek: `tests/poort` gebruikt `genereer()` ook. `scripts/genereer_jas_klassen.py` roept dit
script mee aan, zodat de bestaande `--check` in CI het ook dekt.

Gebruik: python3 scripts/genereer_regelgaten.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[3]
BRON = WORTEL / ".claude" / "skills" / "wetsanalyse" / "regelgaten.json"
API_DOEL = WORTEL / "api" / "app" / "jas_regelgaten.py"

PLEKKEN = ("skelet", "regel", "keten")
HERKOMSTEN = ("regelspecialist", "methode")
VELDEN = {"plek", "herkomst", "bron", "melding"}

_API_FUNCTIES = '''

def gat(code: str, **waarden) -> dict:
    """Eén gat met zijn melding ingevuld: `{code, plek, tekst}`. Een onbekende code is een programmeerfout."""
    g = GATEN[code]
    return {"code": code, "plek": g["plek"], "tekst": g["melding"].format(**waarden)}
'''


def lees(bron: Path = BRON) -> dict:
    data = json.loads(bron.read_text(encoding="utf-8"))
    if tuple(data["plekken"]) != PLEKKEN:
        raise ValueError(f"plekken moeten precies {PLEKKEN} zijn")
    for code, g in data["gaten"].items():
        if set(g) != VELDEN:
            raise ValueError(f"{code}: velden moeten precies {sorted(VELDEN)} zijn")
        if g["plek"] not in PLEKKEN or g["herkomst"] not in HERKOMSTEN or not g["bron"]:
            raise ValueError(f"{code}: onbekende plek of herkomst, of geen bron")
    return {"versie": hashlib.sha256(bron.read_bytes()).hexdigest()[:12],
            "gaten": {code: {"plek": g["plek"], "herkomst": g["herkomst"], "melding": g["melding"]}
                      for code, g in data["gaten"].items()}}


def api_bron(v: dict) -> str:
    def blok(naam: str, waarde, uitleg: str) -> str:
        return f"#: {uitleg}\n{naam} = " + pprint.pformat(waarde, width=110, sort_dicts=False) + "\n\n"
    return ("# Gegenereerd uit .claude/skills/wetsanalyse/regelgaten.json; niet handmatig bewerken.\n"
            "# Draai tools/graph-qa/scripts/genereer_regelgaten.py.\n"
            '"""De gaten van een afleidingsregel (activiteit 3b): code, plek, herkomst en melding."""\n'
            "from __future__ import annotations\n\n"
            + blok("REGELGATEN_VERSIE", v["versie"], "De eerste twaalf tekens van de sha256 van de bron.")
            + blok("PLEKKEN", PLEKKEN, "Waar een gat zit: het skelet, het regelobject of de keten.")
            + blok("GATEN", v["gaten"], "code → plek, herkomst en melding (met {velden} om in te vullen).").rstrip("\n")
            + "\n" + _API_FUNCTIES)


def genereer(bron: Path = BRON) -> dict[Path, str]:
    """Doelbestand → verwachte inhoud."""
    return {API_DOEL: api_bron(lees(bron))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="niets schrijven; exitcode 1 als een kopie niet bij de skill past")
    args = p.parse_args(argv)
    afwijkend = []
    for doel, inhoud in genereer().items():
        if args.check:
            if not doel.exists() or doel.read_text(encoding="utf-8") != inhoud:
                afwijkend.append(doel)
        else:
            doel.write_text(inhoud, encoding="utf-8")
    if afwijkend:
        for doel in afwijkend:
            print(f"{doel.relative_to(WORTEL)} loopt uit de pas met regelgaten.json.", file=sys.stderr)
        print("Draai: python3 tools/graph-qa/scripts/genereer_regelgaten.py", file=sys.stderr)
        return 1
    print("regelgaten " + ("komen overeen met de skill." if args.check else "bijgewerkt uit de skill."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
