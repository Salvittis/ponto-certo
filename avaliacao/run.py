"""Experimento A/B/C. Requer o mesmo servidor/modelo local usado pela aplicação.

python -m avaliacao.run --split dev --output avaliacao/runs/dev-v1
python -m avaliacao.run --split test --output avaliacao/runs/test-v1
Não sobrescreve uma execução. Valida hash do conjunto congelado.
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import unicodedata
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
CONFIGURATIONS=('baseline','rag','agent')
STATUSES={'ok','not_found','clarification','unavailable'}

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c)!='Mn')

def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def code_manifest():
    paths=sorted([*ROOT.glob('app/**/*.py'),*ROOT.glob('base/*.json*'),*ROOT.glob('avaliacao/*.py')])
    return {str(p.relative_to(ROOT)):sha256(p) for p in paths}

def raw_model_metadata(result):
    meta=result.get('metadata',result.get('_evaluation',{}))
    raw=meta.get('model_raw',result.get('model_raw'))
    called=meta.get('model_called',raw is not None)
    try:
        obj=json.loads(raw) if isinstance(raw,str) else raw
        valid=isinstance(obj,dict) and isinstance(obj.get('answer'),str) and obj.get('status') in STATUSES and isinstance(obj.get('source_ids'),list)
    except (ValueError,TypeError):
        obj=None;valid=False
    return dict(called=called,raw=raw,json_schema_valid=valid,parsed=obj)

def score(case,result):
    answer=normalized(result.get('answer',''))
    status_ok=result.get('status') in case['expected_status']
    missing=[group for group in case.get('required_groups',[]) if not any(normalized(term) in answer for term in group)]
    suspicious=[]
    for pattern in case.get('forbidden_patterns',[]):
        for match in re.finditer(pattern,answer):
            # Avoid marking "não garante" or quoted forbidden content as proof of a hallucination.
            prefix=answer[max(0,match.start()-32):match.start()]
            if re.search(r'\b(?:nao|nem|sem|nunca)\b',prefix): continue
            suspicious.append(match.group())
    final_schema=(isinstance(result.get('answer'),str) and result.get('status') in STATUSES and isinstance(result.get('sources'),list))
    sources=result.get('sources',[])
    sources_well_formed=bool(sources) and all(isinstance(s,dict) and bool(s.get('id')) and bool(s.get('url')) for s in sources)
    supported_source=any(case.get('evidence','').startswith('http') and s.get('url')==case['evidence'] for s in sources if isinstance(s,dict))
    source_required=(case['category'] in {'documental','contexto_historico','dinamico_demo'})
    source_ok=(sources_well_formed if source_required else True)
    abstention_needed=all(x!='ok' for x in case['expected_status'])
    # Property accuracy intentionally does not claim full semantic correctness.
    property_correct=final_schema and status_ok and not missing and not suspicious and source_ok
    return {'property_correct':property_correct,'status_correct':status_ok,'missing_required_groups':missing,
            'forbidden_claim_candidates':suspicious,'final_json_schema_valid':final_schema,
            'source_required':source_required,'sources_present_valid':sources_well_formed,
            'expected_source_url_found':supported_source,'abstention_needed':abstention_needed,
            'abstention_correct':status_ok if abstention_needed else None}

async def run(args):
    from app.engine import Engine
    data_path=ROOT/'avaliacao'/f'{args.split}.jsonl'
    frozen=json.loads((ROOT/'avaliacao/freeze.json').read_text())
    if sha256(data_path)!=frozen['files'][data_path.name]:
        raise SystemExit('Hash do conjunto mudou; crie versão e registre a mudança antes de avaliar.')
    out=Path(args.output).resolve()
    if out.exists(): raise SystemExit('Diretório de execução já existe. Escolha uma nova versão para preservar evidências.')
    out.mkdir(parents=True)
    cases=load_jsonl(data_path)
    selected=cases[:args.limit] if args.limit else cases
    engine=Engine()
    signature=inspect.signature(engine.answer)
    start=datetime.now(timezone.utc).isoformat()
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: revision=None
    manifest={'started_at':start,'split':args.split,'dataset_sha256':sha256(data_path),'configurations':list(CONFIGURATIONS),
        'n_cases':len(selected),'platform':platform.platform(),'python':platform.python_version(),'git_revision':revision,
        'code_sha256':code_manifest(),'data_condition':'same versioned synthetic fixture in A/B/C; A receives no evidence, B documented retrieval, C retrieval plus tools',
        'model_condition':'same local model and runtime; record server/version/hash in app evidence',
        'environment':{k:os.environ[k] for k in ['LLM_MODEL','LLM_BASE_URL','DATA_MODE','RETRIEVAL_THRESHOLD','MAX_DATA_AGE_SECONDS'] if k in os.environ},
        'notes':['Fixed A/B/C order per case; sequential runs avoid inference contention.','Question and structured fields shared across configurations.','Cold-start/warm-cache effects can affect latency; not a cloud latency benchmark.','Test set never passed to generation except individual question and allowed request fields.']}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    with (out/'responses.jsonl').open('w') as stream:
        for case in selected:
            for config in CONFIGURATIONS:
                kw={k:case[k] for k in ['line_code','stop_code','direction','scenario'] if k in case}
                kw['configuration']=config
                if 'evaluation' in signature.parameters: kw['evaluation']=True
                t=time.perf_counter()
                error=None
                try:
                    result=await engine.answer(case['question'],**kw)
                    if hasattr(result,'model_dump'): result=result.model_dump(mode='json')
                except Exception as exc:
                    error=type(exc).__name__
                    result={'status':'unavailable','answer':'Falha do runner/inferência. Consulte error_type.','sources':[],'metadata':{'model_called':False}}
                elapsed=time.perf_counter()-t
                row={'case_id':case['id'],'configuration':config,'question':case['question'],'category':case['category'],
                    'inputs':kw,'expected_status':case['expected_status'],'expected_evidence':case['evidence'],
                    'elapsed_seconds':round(elapsed,4),'error_type':error,'result':result,
                    'automatic':score(case,result),'model':raw_model_metadata(result)}
                rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                print(f"{case['id']} {config}: status={result.get('status')} property={row['automatic']['property_correct']} {elapsed:.2f}s",flush=True)
    finish=datetime.now(timezone.utc).isoformat()
    manifest['finished_at']=finish
    manifest['code_unchanged_during_run']=(manifest['code_sha256']==code_manifest())
    manifest['models_observed']=sorted({r['result'].get('model','not-recorded') for r in rows})
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    write_scoreboard(out,rows)
    if not manifest['code_unchanged_during_run']: print('ATENÇÃO: código/base mudou durante experimento; não usar comparação como resultado final.')

def write_scoreboard(out, rows):
    scores=[]
    for config in CONFIGURATIONS:
        subset=[r for r in rows if r['configuration']==config];n=len(subset)
        if not n: continue
        need_source=[r for r in subset if r['automatic']['source_required']]
        abstentions=[r for r in subset if r['automatic']['abstention_needed']]
        model_calls=[r for r in subset if r['model']['called']]
        s={'configuration':config,'n':n,'property_correct':sum(r['automatic']['property_correct'] for r in subset),
            'status_correct':sum(r['automatic']['status_correct'] for r in subset),
            'final_json_valid':sum(r['automatic']['final_json_schema_valid'] for r in subset),
            'source_n':len(need_source),'sources_present':sum(r['automatic']['sources_present_valid'] for r in need_source),
            'refusal_n':len(abstentions),'refusal_correct':sum(r['automatic']['abstention_correct'] for r in abstentions),
            'model_calls':len(model_calls),'model_json_valid':sum(r['model']['json_schema_valid'] for r in model_calls),
            'forbidden_claim_candidates':sum(bool(r['automatic']['forbidden_claim_candidates']) for r in subset),
            'mean_latency_seconds':round(sum(r['elapsed_seconds'] for r in subset)/n,3),
            'errors':sum(bool(r['error_type']) for r in subset)}
        scores.append(s)
    payload={'warning':'Acerto por propriedades é proxy automático, não acurácia semântica plena. Candidatos a afirmação proibida exigem auditoria. JSON final pode refletir validação/fallback do servidor; JSON bruto mede geração.','scores':scores}
    (out/'scoreboard.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['# Placar automático','',payload['warning'],'','| Configuração | Casos | Acerto por propriedades | Status | JSON final | Fontes exigidas presentes | Recusa/status negativo | JSON bruto / chamadas LLM | Latência média (s) |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in scores:
        lines.append(f"| {s['configuration']} | {s['n']} | {s['property_correct']}/{s['n']} | {s['status_correct']}/{s['n']} | {s['final_json_valid']}/{s['n']} | {s['sources_present']}/{s['source_n']} | {s['refusal_correct']}/{s['refusal_n']} | {s['model_json_valid']}/{s['model_calls']} | {s['mean_latency_seconds']} |")
    (out/'scoreboard.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--split',choices=['dev','test'],default='test')
    parser.add_argument('--output',required=True)
    parser.add_argument('--limit',type=int,default=0,help='Smoke test only; partial runs are not final evaluation.')
    asyncio.run(run(parser.parse_args()))
