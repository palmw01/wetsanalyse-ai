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
    settings = Settings.from_env().model_copy(update={
        'checkpoint_db_path': None, 'checkpoint_db_url': None,
        'llm_timeout_seconds': 60, 'llm_max_retries': 0,
        'enable_kandidaat_splitsing': False, 'critic_max_rondes': 2,
        'enable_planning': True, 'enable_decomposition': False,
    })
    class Graph:
        def __init__(self, text): self.text = text
        def initialize(self): return {}
        def close(self): pass
        def sparql(self, query):
            literal = json.dumps(self.text, ensure_ascii=False) + '@nl'
            return json.dumps('?tekst\t?jci\t?lid\t?lidnummer\t?lidtekst\t?onderdeel\t?onderdeeltekst\n'
                              + '\t"jci"\t"lid-1"\t"1"\t' + literal + '\t\t')
        def semantic_search(self, query, limit=10): raise AssertionError('onverwachte zoekroute')
    class Capture:
        def __init__(self): self.llm = AnthropicLLM(settings); self.calls = []
        def create(self, **kw): self.calls.append(kw); return self.llm.create(**kw)
        def stream(self, **kw): self.calls.append(kw); return self.llm.stream(**kw)
    cases = json.loads((ROOT / 'docs/wetsanalyse/referentieset/cases.json').read_text())
    cases = [c for c in cases if c['id'] in ['IW01','AWB04','WZT01','RVV03']]
    assert len(cases) == 4 and all(c['split'] == 'ontwikkeling' for c in cases)
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
            llm = Capture(); start = time.monotonic()
            # Alleen technische fixture-identiteit; de werkelijke passage staat in het rapport.
            doel = {'bwbId': 'BWBR0004770', 'artikel': '9', 'lid': '1', 'citeertitel': c['id']}
            events = [e async for e in answer_stream('Annoteer de aangewezen bronpassage.', doel=doel,
                       settings=settings, llm=llm, graph=Graph(c['tekst']))]
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
