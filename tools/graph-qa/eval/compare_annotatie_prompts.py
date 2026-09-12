"""Begrensde directe promptvergelijking; geen juridische goldscore of volledige keteneval.

Uitvoeren vanuit tools/graph-qa: .venv/bin/python -m eval.compare_annotatie_prompts
Gebruikt de geconfigureerde modelprovider en verstuurt uitsluitend openbare casusteksten.
Beide varianten gebruiken dezelfde huidige klassedefinities; alleen promptbouw verschilt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import types
from pathlib import Path

from agent.adapters.anthropic_llm import AnthropicLLM
from agent.annotatie import _parse_elementen
from agent.annotatie_prompt import annotatie_systeemprompt, annotatie_userprompt
from agent.config import Settings
from eval.run_eval import _laad_env

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline-ref', default='HEAD')
    ap.add_argument('--cases', nargs='+', default=['IW01','AWB04','WZT01','RVV03'])
    ap.add_argument('--herhalingen', type=int, choices=range(1,4), default=3)
    ap.add_argument('--output', type=Path, required=True,
                    help='nieuw JSON-pad; bestaande meetresultaten worden niet overschreven')
    args = ap.parse_args()
    if args.output.exists():
        ap.error('uitvoer bestaat al; kies een nieuw pad')
    all_cases = json.loads((ROOT/'docs/wetsanalyse/referentieset/cases.json').read_text())
    selected = [c for c in all_cases if c['id'] in args.cases]
    if not selected or len(selected) != len(set(args.cases)):
        ap.error('onbekende casus')
    if any(c['split'] != 'ontwikkeling' for c in selected):
        ap.error('held-out casussen niet gebruiken voor promptontwikkeling')
    baseline = types.ModuleType('agent.baseline_prompt')
    baseline.__package__ = 'agent'
    code = subprocess.check_output(
        ['git','show',f'{args.baseline_ref}:tools/graph-qa/agent/annotatie_prompt.py'],
        cwd=ROOT, text=True,
    )
    exec(compile(code, '<baseline-prompt>', 'exec'), baseline.__dict__)
    prompts = {'oud':baseline.annotatie_systeemprompt(), 'nieuw':annotatie_systeemprompt()}
    _laad_env()
    settings = Settings.from_env().model_copy(update={'llm_timeout_seconds':45,'llm_max_retries':0})
    llm = AnthropicLLM(settings)
    report = {
        'status':'bezig', 'model':settings.llm_model,
        'baseline_commit':subprocess.check_output(['git','rev-parse',args.baseline_ref],cwd=ROOT,text=True).strip(),
        'scope':'directe annotator; gedeelde klassedefinities; geen critic, dossier of expertgold',
        'max_tokens':8192, 'temperature':'providerdefault, niet expliciet ingesteld',
        'herhalingen':args.herhalingen, 'prompts':prompts, 'resultaten':[],
    }
    def save():
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    save()
    for repeat in range(1,args.herhalingen+1):
        for case in selected:
            variants = list(prompts.items())
            if repeat % 2 == 0:
                variants.reverse()
            for variant, prompt in variants:
                try:
                    start = time.monotonic()
                    # Zelfde dossier-ID als in de eerste meting; geen bronretrieval in deze proef.
                    resp = llm.create(model=settings.llm_model,max_tokens=8192,system=prompt,tools=[],
                        messages=[{'role':'user','content':annotatie_userprompt(case['bron_id'],case['artikel'],case['tekst'])}])
                    raw = ''.join(b.text for b in resp.content if b.type=='text')
                    elements = _parse_elementen(raw)
                    report['resultaten'].append({
                        'casus':case['id'], 'ronde':repeat, 'variant':variant,
                        'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                        'bron_sha256':case['tekst_sha256'], 'analysetekst':case['tekst'],
                        'stop_reason':resp.stop_reason, 'seconden':time.monotonic()-start,
                        'elementen':elements, 'ruwe_uitvoer':raw,
                        'niet_letterlijk':sum(not e.get('tekst') or e['tekst'] not in case['tekst'] for e in elements),
                    })
                    save()
                    print(case['id'],repeat,variant,len(elements),'elementen',flush=True)
                except Exception as exc:
                    report.update(status='niet_volledig_gemeten',fout_type=type(exc).__name__,
                                  http_status=getattr(exc,'status_code',None))
                    save()
                    print('Gestopt:',type(exc).__name__,flush=True)
                    return 1
    report['status']='gemeten_nog_niet_juridisch_beoordeeld'
    save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
