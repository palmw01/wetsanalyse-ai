"""Volledige expliciet-doelketen; vier devcasussen, één herhaling, vaste bronfixture.

Draai met --agent-dir voor een snapshot vóór import en de huidige package.
Bewaart openbare prompts/events; geen expertgoldscore of retrieval-LLM-evaluatie.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agent-dir', type=Path, required=True)
    p.add_argument('--variant', choices=['voor-import', 'na-import'], required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists(): p.error('uitvoer bestaat al')
    sys.path.insert(0, str(args.agent_dir.resolve()))
    from agent.adapters.anthropic_llm import AnthropicLLM
    from agent.agent import answer_stream
    from agent.config import Settings
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'tools/graph-qa/.env')
    sys.path.append(str(ROOT / 'tools/graph-qa'))  # achteraan: de snapshot-agent gaat voor
    from eval.keten_fixture import Capture, FixtureGraph, LegeAnnotaties, fixture_doel, ketensettings, laad_cases
    settings = ketensettings(Settings.from_env())
    cases = laad_cases(['IW01', 'AWB04', 'WZT01', 'RVV03'])
    report = {'variant': args.variant, 'status': 'bezig', 'model': settings.llm_model,
        'scope': 'expliciet doel → bronophaling → annotator → critic → eventuele patch/herziening/critic → emit; vaste bronfixture, geen router/retrieval-LLM',
        'herhalingen': 1, 'temperature': 'providerdefault',
        'settings': {'critic_max_rondes': 2, 'enable_kandidaat_splitsing': False,
                     'annotatie_prompt_kort': settings.annotatie_prompt_kort},
        'agentbestanden': {str(f.relative_to(args.agent_dir)): hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in sorted((args.agent_dir / 'agent').rglob('*.py'))}, 'resultaten': []}
    def save(): args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    async def run():
        for c in cases:
            llm = Capture(AnthropicLLM(settings)); start = time.monotonic()
            events = [e async for e in answer_stream('Annoteer de aangewezen bronpassage.', doel=fixture_doel(c),
                       settings=settings, llm=llm, graph=FixtureGraph(c['tekst']), annotaties=LegeAnnotaties(c['tekst']))]
            report['resultaten'].append({'casus': c['id'], 'bron_sha256': c['tekst_sha256'],
                'analysetekst': c['tekst'], 'seconden': time.monotonic()-start, 'calls': llm.calls, 'events': events})
            save(); print(args.variant, c['id'], len(llm.calls), 'modelcalls', flush=True)
            if any(e['type'] == 'error' for e in events): raise RuntimeError('error-event')
    save()
    try: asyncio.run(run())
    except Exception as exc:
        report.update(status='niet_volledig_gemeten', fout_type=type(exc).__name__); save(); return 1
    report['status'] = 'gemeten_nog_niet_juridisch_beoordeeld'; save(); return 0

if __name__ == '__main__': raise SystemExit(main())
