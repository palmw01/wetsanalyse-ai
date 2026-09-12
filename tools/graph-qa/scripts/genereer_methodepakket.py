"""Compileer de expliciete skillselectie; geen runtime-bestandslezing nodig."""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / '.claude/skills/wetsanalyse'
DOEL = ROOT / 'tools/graph-qa/agent/methodepakket.py'
ROLLEN = frozenset({'supervisor', 'retrieval', 'definitie', 'duiding', 'algemeen',
                    'decompositie', 'synthese', 'kandidaten', 'annotator',
                    'classificatie', 'critic', 'herziening'})


def sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()


def compileer(skill: Path = SKILL) -> dict:
    hoofd = (skill / 'SKILL.md').read_text()
    versie = re.findall(r'^  methode_versie: "([^"\n]+)"$', hoofd.split('---', 2)[1], re.M)
    if len(versie) != 1:
        raise ValueError('precies één methode_versie in skillmetadata vereist')
    mapping = json.loads((skill / 'agentrollen.json').read_text())
    if set(mapping['rollen']) != ROLLEN:
        raise ValueError('onbekende of ontbrekende agentrollen')
    register = (skill / 'references/bronnen.md').read_text()
    bekend = set(re.findall(r'^\| ([MP]\d+) \|', register, re.M))
    secties = {}
    for key, spec in mapping['secties'].items():
        if not re.fullmatch(r'[a-z][a-z-]*', key):
            raise ValueError(f'ongeldig sectie-ID: {key}')
        pad = (skill / spec['bestand']).resolve()
        if not pad.is_relative_to(skill.resolve()):
            raise ValueError('bronpad buiten skill')
        tekst = pad.read_text()
        start, einde = f'<!-- methode:{key}:begin -->', f'<!-- methode:{key}:end -->'
        if tekst.count(start) != 1 or tekst.count(einde) != 1:
            raise ValueError(f'ontbrekende of dubbele sectie: {key}')
        if tekst.index(einde) < tekst.index(start):
            raise ValueError(f'omgekeerde sectie: {key}')
        inhoud = tekst.split(start)[1].split(einde)[0].strip()
        if not inhoud or not spec['bronnen'] or not set(spec['bronnen']) <= bekend:
            raise ValueError(f'lege sectie of ongeldige broncodes: {key}')
        secties[key] = {**spec, 'tekst': inhoud, 'sha256': sha(inhoud)}
    for rol, ids in mapping['rollen'].items():
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= secties.keys():
            raise ValueError(f'ongeldige sectieselectie: {rol}')
    # Ook klassendefinities en bronregister vallen onder de identiteit van het pakket.
    bestanden = {'SKILL.md', 'agentrollen.json', 'references/bronnen.md',
                 'references/jas-klassen-referentie.md'} | {s['bestand'] for s in secties.values()}
    pakket = {'versie': versie[0], 'rollen': mapping['rollen'], 'secties': secties,
              'bronbestanden': {p: sha((skill / p).read_text()) for p in sorted(bestanden)}}
    pakket['sha256'] = sha(json.dumps(pakket, sort_keys=True, ensure_ascii=False))
    return pakket


def genereer(skill: Path = SKILL) -> str:
    return ('# Gegenereerd uit de wetsanalyse-skill; niet handmatig bewerken.\n'
            '# Draai scripts/genereer_jas_klassen.py.\nPAKKET = '
            + pprint.pformat(compileer(skill), width=100, sort_dicts=True) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    verwacht = genereer()
    if args.check:
        if not DOEL.exists() or DOEL.read_text() != verwacht:
            print('methodepakket.py wijkt af: draai scripts/genereer_jas_klassen.py')
            return 1
    else:
        DOEL.write_text(verwacht)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
