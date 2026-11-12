"""Compileer de expliciete skillselectie van alle methode-skills (ADR-014 §7); geen runtime-bestandslezing nodig."""
from __future__ import annotations

import argparse
import hashlib
import json
import pprint
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / '.claude/skills/wetsanalyse'
DOEL = ROOT / 'tools/graph-qa/agent/methodepakket.py'
# Geen annotatierollen: de annotatieketen (ADR-001) gebruikt geen generatieve prompts met
# methodetekst.
# Een rol hoort hier alleen als een modelaanroep hem draagt (`llm_stap.Rol`, `tests/test_methoderollen.py`).
ROLLEN = frozenset({'supervisor', 'retrieval', 'definitie', 'duiding', 'algemeen', 'deelvragen'})
LEX_VELDEN = frozenset({'soort', 'label', 'herkomst', 'licentie', 'letterlijk'})


def sha(tekst: str) -> str:
    return hashlib.sha256(tekst.encode()).hexdigest()


SKILLS = ROOT / '.claude/skills'
AGENT = ROOT / 'tools/graph-qa/agent'
#: De ketens waarvoor een skill regels mag meebrengen (S6, achter de proefvlag `SKILL_REGELS`): per keten het id-voorvoegsel
#: en de verklaringen waarin elke bewijscode al moet staan. Een skillregel hergebruikt een bestaande code, zodat de
#: werkplek, de exports en de vocabulairegraaf hem al kunnen uitleggen.
REGELKETENS = {
    'jas': ('jas.{skill}.', AGENT / 'jas_pipeline/verklaringen.yaml', 'detectie'),
    'begrippen': ('begrip.{skill}.', AGENT / 'begrippen_pipeline/verklaringen.yaml', 'signalen'),
}
TESTSOORTEN = ('positief', 'negatief', 'rand', 'overlap')


def _regels(skill: Path) -> dict[str, dict[str, list]]:
    """De regelsets onder `regels/<keten>/<familie>.yaml`, per keten op `<skill>.<familie>`. De vorm toetst de lader in
    graph-qa (`Regel.van`, `patronen._regel`); hier de grenzen die een skill raken: het id-voorvoegsel, de vier
    testsoorten en een bewijscode die al een verklaring heeft."""
    uit: dict[str, dict[str, list]] = {}
    if not (skill / 'regels').exists():
        return uit
    for map_ in sorted((skill / 'regels').iterdir()):
        if map_.name not in REGELKETENS:
            raise ValueError(f'{skill.name}: regels/{map_.name} is geen keten ({sorted(REGELKETENS)})')
        voorvoegsel, verklaringen, sectie = REGELKETENS[map_.name]
        codes = set(yaml.safe_load(verklaringen.read_text())[sectie])
        for pad in sorted(map_.glob('*.yaml')):
            items = yaml.safe_load(pad.read_text())
            if not isinstance(items, list) or not items:
                raise ValueError(f'{skill.name}: {pad.name} is geen lijst regels')
            for d in items:
                if not str(d.get('id', '')).startswith(voorvoegsel.format(skill=skill.name)):
                    raise ValueError(f'{skill.name}: regel {d.get("id")} begint niet met {voorvoegsel.format(skill=skill.name)}')
                if ontbreekt := [s for s in TESTSOORTEN if not (d.get('tests') or {}).get(s)]:
                    raise ValueError(f'{skill.name}: regel {d["id"]} mist de tests {ontbreekt}')
                if d.get('code') not in codes:
                    raise ValueError(f'{skill.name}: regel {d["id"]}: code {d.get("code")} heeft geen verklaring ({sectie})')
            uit.setdefault(map_.name, {})[f'{skill.name}.{pad.stem}'] = items
    return uit


def methode_skills(basis: Path = SKILL) -> list[Path]:
    """De andere methode-skills naast de basis: elke map onder `.claude/skills/` met `lex_soort: "methode"`, op naam
    (ADR-014 §7). Een skill die alleen voor Claude Code is, telt niet mee."""
    return [p.parent for p in sorted(SKILLS.glob('*/SKILL.md'))
            if p.parent.resolve() != basis.resolve() and 'lex_soort: "methode"' in p.read_text()]


def _lees(skill: Path, *, basis: bool) -> tuple[str, dict, dict, dict, set[str]]:
    """Eén skill: versie, lex-metadata, de rollen die hij vult, zijn secties en zijn bronbestanden. De basis bepaalt
    alle rollen; een andere skill vult bestaande rollen aan (een nieuwe rol vraagt code en een meting, ADR-014 §5)."""
    hoofd = (skill / 'SKILL.md').read_text()
    versie = re.findall(r'^  methode_versie: "([^"\n]+)"$', hoofd.split('---', 2)[1], re.M)
    if len(versie) != 1:
        raise ValueError(f'{skill.name}: precies één methode_versie in skillmetadata vereist')
    # De beschrijving voor de catalogus (ADR-014): soort, label, herkomst, licentie en of de tekst letterlijk uit een
    # bron van derden mag komen. Het staat in de frontmatter, zodat de skill ook voor Claude Code één bestand blijft.
    lex = dict(re.findall(r'^  lex_([a-z]+): "([^"\n]+)"$', hoofd.split('---', 2)[1], re.M))
    beschrijving = re.search(r'^description: >-\n((?:  .+\n)+)', hoofd.split('---', 2)[1], re.M)
    if not beschrijving:
        raise ValueError(f'{skill.name}: skillmetadata: description (>-) vereist')
    lex['beschrijving'] = ' '.join(r.strip() for r in beschrijving[1].splitlines())
    if set(lex) - {'beschrijving'} != LEX_VELDEN or lex['soort'] != 'methode' or lex['letterlijk'] not in ('ja', 'nee'):
        raise ValueError(f'{skill.name}: skillmetadata lex_*: precies {sorted(LEX_VELDEN)} vereist')
    if lex['letterlijk'] == 'ja' and not (skill / 'BRON.md').exists():
        raise ValueError(f'{skill.name}: letterlijke tekst van derden vraagt een BRON.md met de licentie')
    mapping = json.loads((skill / 'agentrollen.json').read_text())
    if basis and set(mapping['rollen']) != ROLLEN:
        raise ValueError('onbekende of ontbrekende agentrollen')
    if not basis and (not mapping['rollen'] or not set(mapping['rollen']) <= ROLLEN):
        raise ValueError(f'{skill.name}: een skill vult alleen bestaande rollen aan ({sorted(ROLLEN)})')
    register = (skill / 'references/bronnen.md').read_text()
    bekend = set(re.findall(r'^\| ([A-Z]{1,3}\d+) \|', register, re.M))
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
        secties[key] = {**spec, 'tekst': inhoud, 'sha256': sha(inhoud), 'skill': skill.name}
    for rol, ids in mapping['rollen'].items():
        if not ids or len(ids) != len(set(ids)) or not set(ids) <= secties.keys():
            raise ValueError(f'ongeldige sectieselectie: {rol}')
    # Ook klassendefinities en bronregister vallen onder de identiteit van het pakket.
    bestanden = {'SKILL.md', 'agentrollen.json', 'references/bronnen.md'} | {s['bestand'] for s in secties.values()}
    if basis:
        bestanden.add('references/jas-klassen-referentie.md')
    bestanden |= {p.relative_to(skill).as_posix() for p in (skill / 'regels').glob('*/*.yaml')} \
        if (skill / 'regels').exists() else set()
    return versie[0], lex, mapping['rollen'], secties, bestanden | ({'BRON.md'} if (skill / 'BRON.md').exists() else set())


def compileer(skill: Path = SKILL, extra: list[Path] | None = None) -> dict:
    """Het methodepakket uit de basis-skill en de methode-skills ernaast. Een rol is de vereniging van de secties die de
    skills haar geven: eerst de basis, dan de andere skills op naam. Sectie-ids en broncodes zijn uniek over de skills."""
    versie, lex, rollen, secties, bestanden = _lees(skill, basis=True)
    rollen = {r: list(ids) for r, ids in rollen.items()}
    bronbestanden = {p: sha((skill / p).read_text()) for p in sorted(bestanden)}
    codes = {c: skill.name for s in secties.values() for c in s['bronnen']}
    skills = {skill.name: {'versie': versie, 'lex': lex, 'map': f'.claude/skills/{skill.name}'}}
    regels = _regels(skill)
    for ander in (methode_skills(skill) if extra is None else extra):
        v, l, r, s, b = _lees(ander, basis=False)
        if dubbel := secties.keys() & s.keys():
            raise ValueError(f'{ander.name}: sectie-id al in gebruik: {sorted(dubbel)}')
        for c in {c for x in s.values() for c in x['bronnen']}:
            if codes.get(c, ander.name) != ander.name:
                raise ValueError(f'{ander.name}: broncode {c} is al van {codes[c]}')
            codes[c] = ander.name
        secties |= s
        for rol, ids in r.items():
            rollen[rol] += ids
        bronbestanden |= {f'{ander.name}/{p}': sha((ander / p).read_text()) for p in sorted(b)}
        skills[ander.name] = {'versie': v, 'lex': l, 'map': f'.claude/skills/{ander.name}'}
        for keten, sets in _regels(ander).items():
            regels.setdefault(keten, {}).update(sets)
    pakket = {'versie': versie, 'lex': lex, 'rollen': rollen, 'secties': secties, 'bronbestanden': bronbestanden,
              'skills': skills, 'regels': regels}
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
