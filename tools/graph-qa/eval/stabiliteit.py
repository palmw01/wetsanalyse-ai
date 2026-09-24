"""Stabiliteitsmeting: dezelfde passage N keer door de volledige annotatieketen.

Uitvoeren vanuit tools/graph-qa:
    .venv/bin/python -m eval.stabiliteit --output /pad/rapport.json [--cases IW01 ...] [--herhalingen 5]
Daarna: .venv/bin/python -m eval.stabiliteit_analyse /pad/rapport.json

Meet reproduceerbaarheid, geen juistheid: er is nog geen juridisch goedgekeurde gold. Per run
bewaart het rapport de ruwe annoteerder-elementen (vóór de Critic) en de uitgestuurde elementen
(ná de keten), zodat de analyse ook laat zien wat de Critic met de spreiding doet.
Gebruikt de geconfigureerde modelprovider en verstuurt uitsluitend openbare casusteksten.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from agent.adapters.anthropic_llm import AnthropicLLM
from agent.agent import answer_stream
from agent.annotatie import _parse_elementen
from agent.annotatie_prompt import annotatie_systeemprompt
from agent.config import Settings
from eval.keten_fixture import (
    ROOT, TOKENVELDEN, Capture, FixtureGraph, LegeAnnotaties, fixture_doel, ketensettings, laad_cases, ontwikkelcases,
)
from eval.run_eval import _laad_env


def _systeemtekst(system: Any) -> str:
    if isinstance(system, str):
        return system
    return ''.join(b.get('text', '') for b in system if isinstance(b, dict))


def ruwe_annotatie(calls: list[dict[str, Any]], kort: bool) -> list[dict[str, Any]]:
    """De elementen uit de eerste annoteerder-call, zoals het model ze gaf (vóór validatie)."""
    prefix = annotatie_systeemprompt(kort)
    for call in calls:
        if 'antwoord' in call and _systeemtekst(call.get('system', '')).startswith(prefix):
            return [{'tekst': e.get('tekst', ''), 'klasse': e.get('klasse', '')}
                    for e in _parse_elementen(call['antwoord'])]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cases', nargs='+', default=None, help='standaard: alle ontwikkelcasussen')
    ap.add_argument('--herhalingen', type=int, default=5)
    ap.add_argument('--max-tokens-totaal', type=int, default=6_000_000,
                    help='stop zodra alle tokens (incl. cache) over alle calls dit overschrijden')
    ap.add_argument('--output', type=Path, required=True,
                    help='nieuw JSON-pad; bestaande meetresultaten worden niet overschreven')
    args = ap.parse_args()
    if args.output.exists():
        ap.error('uitvoer bestaat al; kies een nieuw pad')
    if args.herhalingen < 2:
        ap.error('stabiliteit vraagt minimaal twee herhalingen')
    try:
        cases = laad_cases(args.cases or ontwikkelcases())
    except ValueError as exc:
        ap.error(str(exc))

    _laad_env()
    settings = ketensettings(Settings.from_env())
    agentdir = ROOT / 'tools/graph-qa/agent'
    report: dict[str, Any] = {
        'status': 'bezig', 'model': settings.llm_model,
        'scope': 'expliciet doel → annotator → critic → eventuele patch/herziening/critic → emit; '
                 'vaste bronfixture; meet reproduceerbaarheid, geen juridische juistheid',
        'herhalingen': args.herhalingen, 'temperature': 'providerdefault, niet expliciet ingesteld',
        'settings': {'critic_max_rondes': settings.critic_max_rondes,
                     'enable_kandidaat_splitsing': settings.enable_kandidaat_splitsing,
                     'annotatie_prompt_kort': settings.annotatie_prompt_kort},
        'agentbestanden': {str(f.relative_to(agentdir.parent)): hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in sorted(agentdir.rglob('*.py'))},
        'casussen': [{'id': c['id'], 'tekst': c['tekst'], 'tekst_sha256': c['tekst_sha256']} for c in cases],
        'runs': [], 'tokens_totaal': 0,
    }

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    async def run():
        # Herhaling buiten, casus binnen: een tijdelijke providerstoring raakt dan niet alle
        # herhalingen van één casus tegelijk.
        for ronde in range(1, args.herhalingen + 1):
            for c in cases:
                llm = Capture(AnthropicLLM(settings))
                start = time.monotonic()
                events = [e async for e in answer_stream(
                    'Annoteer de aangewezen bronpassage.', doel=fixture_doel(c),
                    settings=settings, llm=llm, graph=FixtureGraph(c['tekst']), annotaties=LegeAnnotaties(c['tekst']))]
                tokens = sum(k.get(v, 0) for k in llm.calls for v in TOKENVELDEN)
                per_soort = {v: sum(k.get(v, 0) for k in llm.calls) for v in TOKENVELDEN}
                report['tokens_totaal'] += tokens
                report['runs'].append({
                    'casus': c['id'], 'ronde': ronde, 'seconden': round(time.monotonic() - start, 1),
                    'modelcalls': len(llm.calls), 'tokens': tokens, 'tokens_per_soort': per_soort,
                    'fout': any(e.get('type') == 'error' for e in events),
                    'provenance': next((e['run'] for e in events if e.get('type') == 'run'), None),
                    'annoteerder': ruwe_annotatie(llm.calls, settings.annotatie_prompt_kort),
                    'na_keten': [e['element'] for e in events if e.get('type') == 'element'],
                    'ontbrekend': next((e['items'] for e in events if e.get('type') == 'ontbrekend'), []),
                })
                save()
                print(f"{c['id']} ronde {ronde}: {len(report['runs'][-1]['na_keten'])} elementen, "
                      f"{len(llm.calls)} calls, {tokens} tokens", flush=True)
                if report['tokens_totaal'] > args.max_tokens_totaal:
                    raise RuntimeError('tokenbudget overschreden')

    save()
    try:
        asyncio.run(run())
    except Exception as exc:
        report.update(status='niet_volledig_gemeten', fout_type=type(exc).__name__, fout=str(exc)[:300])
        save()
        print('Gestopt:', type(exc).__name__, exc, flush=True)
        return 1
    report['status'] = 'gemeten_nog_niet_juridisch_beoordeeld'
    save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
