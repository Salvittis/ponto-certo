"""Verify the canonical retrieval experiment without recalibration or overwriting it.
Run: python -m avaliacao.retrieval
"""
from pathlib import Path
import hashlib
import json
from base.evaluate_retrieval import evaluate, load
ROOT=Path(__file__).resolve().parents[1]

def main():
    recorded=json.loads((ROOT/'base/retrieval_results.json').read_text())
    for name, expected in recorded['sha256'].items():
        assert hashlib.sha256((ROOT/'base'/name).read_bytes()).hexdigest()==expected, f'Input changed: {name}'
    measured=evaluate(load('test'),recorded['selected_threshold'])
    assert measured==recorded['test'], 'Recorded test is not reproducible'
    audit={'canonical_results':'base/retrieval_results.json','reproduced':True,
        'selection':'No recalibration; replay frozen selected threshold.',
        'threshold':recorded['selected_threshold'],
        'test':{k:v for k,v in measured.items() if k!='details'}}
    (ROOT/'avaliacao/retrieval-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
