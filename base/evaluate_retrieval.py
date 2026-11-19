"""Run from repository root: python -m base.evaluate_retrieval.
Calibrates on dev only, then reports frozen test exactly once per invocation.
"""
import hashlib
import json
from pathlib import Path
from app.retrieval import Retriever

ROOT = Path(__file__).resolve().parent


def load(split):
    return [json.loads(line) for line in (ROOT / f'retrieval_{split}.jsonl').read_text().splitlines()]


def evaluate(cases, threshold):
    retriever = Retriever(threshold=threshold)
    details = []
    for case in cases:
        ranked = retriever.rank(case['question'], 3)
        relevant = set(case['relevant_ids'])
        accepted = [r for r in ranked if r['score'] >= threshold and r['score'] > 0]
        details.append(dict(case,ranked=[{'id':r['id'],'score':r['score']} for r in ranked],accepted_ids=[r['id'] for r in accepted],
            recall_at_1=(len(relevant & {r['id'] for r in ranked[:1]}) / len(relevant)) if relevant else None,
            recall_at_3=(len(relevant & {r['id'] for r in ranked[:3]}) / len(relevant)) if relevant else None,
            accepted_recall_at_3=(len(relevant & {r['id'] for r in accepted[:3]}) / len(relevant)) if relevant else None))
    positives = [d for d in details if d['answerable']]
    negatives = [d for d in details if not d['answerable']]
    tp = sum(bool(d['accepted_ids']) for d in positives)
    tn = sum(not d['accepted_ids'] for d in negatives)
    tpr = tp / len(positives) if positives else 0
    tnr = tn / len(negatives) if negatives else 0
    return {'threshold':threshold,'n':len(details),'n_answerable':len(positives),'n_unanswerable':len(negatives),
            'recall_at_1':sum(d['recall_at_1'] for d in positives)/len(positives),
            'recall_at_3':sum(d['recall_at_3'] for d in positives)/len(positives),
            'accepted_recall_at_3':sum(d['accepted_recall_at_3'] for d in positives)/len(positives),
            'answerability_tpr':tpr,'unanswerable_rejection_rate':tnr,'answerability_balanced_accuracy':(tpr+tnr)/2,
            'details':details}


def main():
    candidates = [round(i/100,2) for i in range(5,51)]
    dev = load('dev')
    sweeps = [evaluate(dev,t) for t in candidates]
    # Declared tie rule: maximize answerability balanced accuracy, then relevant
    # recall after threshold; finally choose smallest threshold to retain evidence.
    selected = max(sweeps,key=lambda x:(x['answerability_balanced_accuracy'],x['accepted_recall_at_3'],-x['threshold']))
    test = evaluate(load('test'),selected['threshold'])
    result={'method':'TF-IDF sublinear term frequency, smoothed idf, cosine; title + body; lowercase/accent removal and stopwords; ties by id.',
            'metric_definition':'Macro recall@k = mean(|relevant_ids intersect top-k|/|relevant_ids|), only answerable questions, before threshold. All cases have one relevant chunk, so this equals hit rate. Also report recall after threshold and rejection on unanswerable questions.',
            'selection':'Threshold selected using dev only, maximizing balanced accuracy of nonempty retrieval vs answerable label; tie: higher accepted recall@3, then smaller threshold. Grid 0.05..0.50 step 0.01. Scores are not confidence probabilities.',
            'limitations':'Small authored corpus and curated questions; no multilingual or population-level validation. A high cosine score does not establish answerability. No held-out test tuning.',
            'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'chunks.jsonl',ROOT/'retrieval_dev.jsonl',ROOT/'retrieval_test.jsonl']},
            'selected_threshold':selected['threshold'],
            'dev_sweep':[{k:v for k,v in x.items() if k!='details'} for x in sweeps],
            'dev':selected,'test':test}
    (ROOT/'retrieval_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in test.items() if k!='details'},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
