"""A fresh process exports zero before its first failure for Prometheus rate()."""
import os
from pathlib import Path
import subprocess
import sys


def test_first_query_failure_and_early_rejection_are_observable():
    script = r'''
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from app import main
from app.llm import ModelUnavailable

class DownModel:
    async def generate(self, *args, **kwargs):
        raise ModelUnavailable('synthetic failure')

main.engine.model = DownModel()
headers={'Authorization':'Bearer synthetic_metrics_access'}
def count(client,status):
    response=client.get('/metrics',headers=headers)
    assert response.status_code==200
    matches=[sample.value for family in text_string_to_metric_families(response.text)
             for sample in family.samples if sample.name=='ponto_certo_http_requests_total'
             and sample.labels=={'route':'/api/ask','method':'POST','status':status}]
    assert len(matches)==1, 'A zero sample must exist before the first event'
    return matches[0]
with TestClient(main.app) as client:
    assert count(client,'503')==0
    assert count(client,'413')==0
    response=client.post('/api/ask',json={'question':'Previsão de chegada é garantia de horário?'})
    assert response.status_code==503
    assert count(client,'503')==1
    response=client.post('/api/ask',content=b'x'*8193,headers={'Content-Type':'application/json'})
    assert response.status_code==413
    assert count(client,'413')==1
'''
    result = subprocess.run([sys.executable, '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            env={'PATH': os.defpath, 'PYTHON_DOTENV_DISABLED': '1',
                                 'DATA_MODE': 'demo', 'METRICS_TOKEN': 'synthetic_metrics_access'},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
