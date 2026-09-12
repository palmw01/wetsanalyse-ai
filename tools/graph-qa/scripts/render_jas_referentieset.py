"""Render de leesbare conceptdossiers uit cases.json; --check bewaakt synchronisatie."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAP = ROOT / 'docs/wetsanalyse/referentieset'


def render(cases: list[dict]) -> dict[str, str]:
    files = {}
    for family in dict.fromkeys(c['familie'] for c in cases):
        rows = [c for c in cases if c['familie'] == family]
        parts = [f'# Conceptanalyses {family}',
                 '<!-- Gegenereerd uit cases.json door render_jas_referentieset.py. -->',
                 'Status: concept; niet vastgesteld en geen volledige gold-annotaties. '
                 'Gebruik de reviewvragen om ontbrekende onderdelen en betwiste duidingen af te ronden. '
                 'Bron-ID’s verwijzen naar [het manifest](../bronnen/manifest.json). '
                 'Het analysedoel is methodetoetsing van de vastgelegde tekst, niet een individueel besluit.']
        for c in rows:
            parts += [f"## {c['id']} — {c['artikel']}",
                      f"Split: {c['split']} | Bron: {c['bron_id']} | Versie: {c['versie']}",
                      '### Ongewijzigde analysetekst',
                      '\n'.join('> '+line for line in c['tekst'].splitlines()),
                      '### Grammatica en normstructuur', c['grammatica'],
                      '### Conceptmarkeringen',
                      '| ID | Fragment | Klasse | Motivering |\n|---|---|---|---|']
            for e in c['annotaties']:
                parts.append(f"| {e['id']} | {e['tekst'].replace(chr(10), '<br>')} | {e['klasse']} | {e['motivatie']} |")
            parts += ['### Samenhang', c['samenhang'], '### Hypothetische toetsgevallen', c['scenario'],
                      '### Dekking en review', c['reviewvraag'],
                      'Menselijke beoordeling: **niet uitgevoerd**. Brondekking en volledige '
                      'annotatiedekking zijn nog niet vastgesteld. Geen kwaliteitsscore toekennen.']
        files[f'{family.lower()}.md'] = '\n\n'.join(parts)+'\n'
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    cases = json.loads((MAP/'cases.json').read_text())
    mismatches = []
    for name, content in render(cases).items():
        p = MAP/name
        if args.check:
            if not p.exists() or p.read_text() != content:
                mismatches.append(name)
        else:
            p.write_text(content, encoding='utf-8')
    if mismatches:
        print('Opnieuw genereren: '+', '.join(mismatches))
        return 1
    print('Conceptdossiers zijn gesynchroniseerd.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
