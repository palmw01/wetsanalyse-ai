#!/usr/bin/env python3
"""Genereer de begripverwachting per JAS-klasse (activiteit 3a) uit de wetsanalyse-skill naar de api en de werkplek.

De bron is `.claude/skills/wetsanalyse/begripverwachting.json`. Per klasse staat daar wat de methode van een
geclassificeerde formulering verwacht: een begrip, een omschrijving (de voorwaarde) of de wettelijke definitie van een
begrip (de brondefinitie). De dekking van een werkgebied (`api/app/begrip_onderhoud_store.dekking`) en de werkvoorraad in
de werkplek lezen het uit een gegenereerde kopie, zoals de relatiecatalogus. Wie het wil wijzigen, bewerkt de JSON en
draait dit script; een met de hand bewerkte kopie faalt op `--check`.

Alleen de standaardbibliotheek: `tests/poort` gebruikt `genereer()` ook. `scripts/genereer_jas_klassen.py` roept dit
script mee aan, zodat de bestaande `--check` in CI het ook dekt.

Gebruik: python3 scripts/genereer_begripverwachting.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parents[3]
BRON = WORTEL / ".claude" / "skills" / "wetsanalyse" / "begripverwachting.json"
API_DOEL = WORTEL / "api" / "app" / "jas_begripverwachting.py"
FRONTEND_DOEL = WORTEL / "frontend" / "lib" / "jasBegripverwachting.ts"

VERWACHTINGEN = ("begrip", "omschrijving", "definitie")

_API_FUNCTIES = '''

def verwacht(klasse: str) -> str:
    """Wat de methode van een formulering van deze klasse verwacht; een onbekende klasse verwacht een begrip."""
    return VERWACHTING.get(klasse, "begrip")
'''

_TS_FUNCTIES = """
/** Wat de methode van een formulering van deze klasse verwacht; een onbekende klasse verwacht een begrip. */
export function verwacht(klasse: string): Verwachting {
  return VERWACHTING[klasse] ?? "begrip";
}
"""


def lees(bron: Path = BRON) -> dict:
    data = json.loads(bron.read_text(encoding="utf-8"))
    if set(data["verwachtingen"]) != set(VERWACHTINGEN):
        raise ValueError(f"verwachtingen moeten precies {VERWACHTINGEN} zijn")
    for klasse, k in data["klassen"].items():
        if k["verwacht"] not in VERWACHTINGEN:
            raise ValueError(f"onbekende verwachting bij {klasse}: {k['verwacht']}")
        if set(k) - {"verwacht", "bron", "projectkeuze"}:
            raise ValueError(f"onbekend veld bij {klasse}: {sorted(set(k) - {'verwacht', 'bron', 'projectkeuze'})}")
    return {
        "versie": hashlib.sha256(bron.read_bytes()).hexdigest()[:12],
        "verwachting": {klasse: k["verwacht"] for klasse, k in data["klassen"].items()},
        "uitleg": data["verwachtingen"],
    }


def api_bron(v: dict) -> str:
    def blok(naam: str, waarde, uitleg: str) -> str:
        return f"#: {uitleg}\n{naam} = " + pprint.pformat(waarde, width=110, sort_dicts=False) + "\n\n"
    return ("# Gegenereerd uit .claude/skills/wetsanalyse/begripverwachting.json; niet handmatig bewerken.\n"
            "# Draai tools/graph-qa/scripts/genereer_begripverwachting.py.\n"
            '"""Wat de methode per JAS-klasse verwacht in activiteit 3a: een begrip, een omschrijving of een definitie."""\n'
            "from __future__ import annotations\n\n"
            + blok("VERWACHTING_VERSIE", v["versie"], "De eerste twaalf tekens van de sha256 van de bron.")
            + blok("VERWACHTINGEN", VERWACHTINGEN, "De drie verwachtingen.")
            + blok("VERWACHTING", v["verwachting"], "klasse → verwachting.")
            + blok("UITLEG", v["uitleg"], "verwachting → wat ze betekent.").rstrip("\n")
            + "\n" + _API_FUNCTIES)


def frontend_bron(v: dict) -> str:
    def j(waarde) -> str:
        return json.dumps(waarde, ensure_ascii=False, indent=2)
    return ("// Gegenereerd uit .claude/skills/wetsanalyse/begripverwachting.json; niet handmatig bewerken.\n"
            "// Draai tools/graph-qa/scripts/genereer_begripverwachting.py.\n\n"
            f"export type Verwachting = {' | '.join(json.dumps(x) for x in VERWACHTINGEN)};\n\n"
            f"export const VERWACHTING_VERSIE = {j(v['versie'])};\n\n"
            f"export const VERWACHTING: Record<string, Verwachting> = {j(v['verwachting'])};\n\n"
            f"export const UITLEG: Record<Verwachting, string> = {j(v['uitleg'])};\n"
            + _TS_FUNCTIES)


def genereer(bron: Path = BRON) -> dict[Path, str]:
    """Doelbestand → verwachte inhoud."""
    v = lees(bron)
    return {API_DOEL: api_bron(v), FRONTEND_DOEL: frontend_bron(v)}


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
            print(f"{doel.relative_to(WORTEL)} loopt uit de pas met begripverwachting.json.", file=sys.stderr)
        print("Draai: python3 tools/graph-qa/scripts/genereer_begripverwachting.py", file=sys.stderr)
        return 1
    print("begripverwachting " + ("komt overeen met de skill." if args.check else "bijgewerkt uit de skill."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
