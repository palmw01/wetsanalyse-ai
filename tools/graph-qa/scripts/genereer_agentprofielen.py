"""Bundel de agentprofielen uit `.claude/lex-agents/` in het image (ADR-016 §A2 en §B1); geen runtime-bestandslezing.

Een profiel is een Markdown-bestand `<naam>.md`: frontmatter met de velden van §A2 en de instructie eronder. Dit script
leest ze met de validator van de werkplaats (`bronmodel.agentprofiel`) en schrijft `agent/agentprofielen.py`. De vorm
toetst het hier; de grenzen (bestaat de tool, de skill, de connector, het sjabloon, de methoderol) toetst het register
bij het laden (`agent/profielen.py`), tegen de registers van graph-qa zelf. `genereer_jas_klassen.py` draait dit script
mee, dus die ene `--check` in CI dekt het.
"""
from __future__ import annotations

import argparse
import json
import pprint
from pathlib import Path

from bronmodel.agentprofiel import uit_markdown
from bronmodel.skill import sha

ROOT = Path(__file__).resolve().parents[3]
PROFIELEN = ROOT / '.claude/lex-agents'
DOEL = ROOT / 'tools/graph-qa/agent/agentprofielen.py'


def compileer(map_: Path = PROFIELEN) -> dict:
    """De profielen op naam, elk als de velden van `Agentprofiel`, met één hash over het geheel."""
    profielen = {p.stem: uit_markdown(p.stem, p.read_text(encoding='utf-8')).model_dump() for p in sorted(map_.glob('*.md'))}
    if not profielen:
        raise ValueError(f'geen profielen in {map_}')
    return {'profielen': profielen, 'sha256': sha(json.dumps(profielen, sort_keys=True, ensure_ascii=False))}


def genereer(map_: Path = PROFIELEN) -> str:
    return ('# Gegenereerd uit .claude/lex-agents/; niet handmatig bewerken.\n'
            '# Draai scripts/genereer_jas_klassen.py.\nREGISTER = '
            + pprint.pformat(compileer(map_), width=100, sort_dicts=True) + '\n')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    verwacht = genereer()
    if args.check:
        if not DOEL.exists() or DOEL.read_text(encoding='utf-8') != verwacht:
            print('agentprofielen.py wijkt af: draai scripts/genereer_jas_klassen.py')
            return 1
        print('agentprofielen.py komt overeen met .claude/lex-agents.')
    else:
        DOEL.write_text(verwacht, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
