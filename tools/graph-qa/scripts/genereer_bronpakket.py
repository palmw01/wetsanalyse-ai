"""Bundel de bronbestanden van elke skill en elk agentprofiel in het image (ADR-016 §B1, stap B1-2).

De werkplaats moet weten wat er draait: welke versie van een skill of profiel in dit image zit, en met welke bestanden
een jurist begint als hij er een bewerkt. Het methodepakket draagt alleen de secties die een rol krijgt; dit pakket
draagt de hele map, als afbeelding van pad naar tekst, met de hash van `bronmodel.werkplaats`: dezelfde rekenregel als
een versie in het register. Daaraan is te zien of een versie *actief* is.

- Skills: elke methode-skill onder `.claude/skills/` (`lex_soort: "methode"`), de hele map.
- Profielen: elk bestand in `.claude/lex-agents/`, met zijn commentaar.

Een eigen bestand (`agent/bronpakket.json`, gelezen door `agent/bronpakket.py`), niet in het methodepakket: de
vingerafdrukken per rol en de pakkethash bewegen niet. JSON en geen Python: het is alleen tekst, en als Python-literal
werd het acht keer zo groot. Elk onderdeel haalt poort 1 van de werkplaats (`bronmodel.werkplaats.toets`): wat in het image zit, is een
geldige versie. `genereer_jas_klassen.py` draait dit script mee, dus die ene `--check` in CI dekt het.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bronmodel import werkplaats as wp
from bronmodel.skill import is_methode, lees_map
from bronmodel.validatie import ValidatieFout

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / '.claude/skills'
PROFIELEN = ROOT / '.claude/lex-agents'
DOEL = ROOT / 'tools/graph-qa/agent/bronpakket.json'


def _onderdeel(soort: str, naam: str, bestanden: dict[str, str]) -> dict:
    if bevindingen := wp.toets(soort, naam, bestanden):
        raise ValidatieFout(f'{soort}/{naam}', bevindingen)
    return {'soort': soort, 'naam': naam, 'hash': wp.hash_van(bestanden), 'bestanden': bestanden}


def compileer(skills: Path = SKILLS, profielen: Path = PROFIELEN) -> dict:
    """De onderdelen op `<soort>/<naam>`, elk met zijn bestanden en zijn hash, en één hash over het geheel."""
    onderdelen: dict[str, dict] = {}
    for hoofd in sorted(skills.glob('*/SKILL.md')):
        if is_methode(hoofd.read_text(encoding='utf-8')):
            onderdelen[f'skill/{hoofd.parent.name}'] = _onderdeel('skill', hoofd.parent.name, lees_map(hoofd.parent))
    for pad in sorted(profielen.glob('*.md')):
        onderdelen[f'agentprofiel/{pad.stem}'] = _onderdeel('agentprofiel', pad.stem,
                                                           {pad.name: pad.read_text(encoding='utf-8')})
    # De identiteit van het pakket: verandert één bestand, dan verandert deze hash. De melding aan de api is er
    # idempotent op.
    hashes = {sleutel: o['hash'] for sleutel, o in onderdelen.items()}
    return {'onderdelen': onderdelen, 'sha256': wp.pakkethash(hashes)}


def genereer() -> str:
    """Het pakket als JSON: gesorteerd en met één sleutel per regel, zodat een wijziging in één bestand één regel is."""
    return json.dumps(compileer(), ensure_ascii=False, sort_keys=True, indent=1) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    verwacht = genereer()
    if args.check:
        if not DOEL.exists() or DOEL.read_text(encoding='utf-8') != verwacht:
            print('bronpakket.json wijkt af: draai scripts/genereer_jas_klassen.py')
            return 1
        print('bronpakket.json komt overeen met .claude/skills en .claude/lex-agents.')
    else:
        DOEL.write_text(verwacht, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
