"""Compileer de expliciete skillselectie van alle methode-skills (ADR-014 §7); geen runtime-bestandslezing nodig."""
from __future__ import annotations

import argparse
import json
import pprint
from pathlib import Path

import yaml
from bronmodel.skill import Skill, is_methode, lees_map, sha, toets_samen, valideer
from bronmodel.validatie import ValidatieFout

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / '.claude/skills/wetsanalyse'
DOEL = ROOT / 'tools/graph-qa/agent/methodepakket.py'
# Geen annotatierollen: de annotatieketen (ADR-001) gebruikt geen generatieve prompts met
# methodetekst.
# Een rol hoort hier alleen als een modelaanroep hem draagt (`llm_stap.Rol`, `tests/test_methoderollen.py`).
ROLLEN = frozenset({'supervisor', 'retrieval', 'definitie', 'duiding', 'algemeen', 'deelvragen'})

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
            if p.parent.resolve() != basis.resolve() and is_methode(p.read_text())]


def _lees(skill: Path, *, basis: bool) -> tuple[Skill, set[str]]:
    """Eén skill, gevalideerd, met zijn bronbestanden. De toets is die van de werkplaats (`bronmodel.skill`, ADR-016
    §B2): de specificatie en de regels van Lex. De basis bepaalt alle rollen; een andere skill vult bestaande rollen aan
    (een nieuwe rol vraagt code en een meting, ADR-014 §5)."""
    s = valideer(skill.name, lees_map(skill), rollen=ROLLEN, basis=basis)
    # Ook klassendefinities en regels vallen onder de identiteit van het pakket.
    bestanden = set(s.bestanden)
    if basis:
        bestanden.add('references/jas-klassen-referentie.md')
    if (skill / 'regels').exists():
        bestanden |= {p.relative_to(skill).as_posix() for p in (skill / 'regels').glob('*/*.yaml')}
    return s, bestanden


def compileer(skill: Path = SKILL, extra: list[Path] | None = None) -> dict:
    """Het methodepakket uit de basis-skill en de methode-skills ernaast. Een rol is de vereniging van de secties die de
    skills haar geven: eerst de basis, dan de andere skills op naam. Sectie-ids en broncodes zijn uniek over de skills."""
    paden = [skill, *(methode_skills(skill) if extra is None else extra)]
    gelezen = [_lees(p, basis=p is skill) for p in paden]
    if botsingen := toets_samen([s for s, _ in gelezen]):
        raise ValidatieFout('methodepakket', botsingen)
    basis = gelezen[0][0]
    rollen = {r: list(ids) for r, ids in basis.rollen.items()}
    secties: dict = {}
    bronbestanden: dict = {}
    skills: dict = {}
    regels: dict = {}
    for pad, (s, bestanden) in zip(paden, gelezen, strict=True):
        secties |= s.secties
        if pad is not skill:
            for rol, ids in s.rollen.items():
                rollen[rol] += ids
        voorvoegsel = '' if pad is skill else f'{s.naam}/'
        bronbestanden |= {f'{voorvoegsel}{p}': sha((pad / p).read_text()) for p in sorted(bestanden)}
        skills[s.naam] = {'versie': s.versie, 'lex': s.lex, 'map': f'.claude/skills/{s.naam}'}
        for keten, sets in _regels(pad).items():
            regels.setdefault(keten, {}).update(sets)
    pakket = {'versie': basis.versie, 'lex': basis.lex, 'rollen': rollen, 'secties': secties,
              'bronbestanden': bronbestanden, 'skills': skills, 'regels': regels}
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
