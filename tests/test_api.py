"""Contract, input and exposure checks; no model download or SPTrans access required."""
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.llm import ModelUnavailable


class FakeModel:
    """Only substitutes the transport to the local model, not the application."""
    def __init__(self):
        self.calls = 0
        self.is_ready = True
        self.failure = False

    async def ready(self):
        return self.is_ready

    async def generate(self, question, evidence, instruction=''):
        self.calls += 1
        if self.failure:
            raise ModelUnavailable('PRIVATE_DETAIL_MUST_NOT_ESCAPE')
        evidence_list = evidence if isinstance(evidence, list) else []
        source_ids = [item['id'] for item in evidence_list if isinstance(item, dict) and isinstance(item.get('id'), str)]
        body = {
            'status': 'ok',
            'answer': 'A previsão é uma estimativa; não é garantia de horário.',
            'source_ids': source_ids[:1],
        }
        return body, {
            'model_raw': json.dumps(body, ensure_ascii=False),
            'model_json_valid': True,
            'model_called': True,
            'model_seconds': 0.001,
            'usage': {},
        }


@pytest.fixture
def model(monkeypatch):
    fake = FakeModel()
    monkeypatch.setattr(main.engine, 'model', fake)
    return fake


@pytest.fixture
def client(model):
    with TestClient(main.app) as client:
        yield client


@pytest.mark.parametrize('payload', [
    {},
    {'question': ''},
    {'question': ' '},
    {'question': 'x' * 5001},
    {'question': 'Quando chega?', 'line_code': 0},
    {'question': 'Quando chega?', 'stop_code': -1},
    {'question': 'Quando chega?', 'direction': 3},
    {'question': 'Quando chega?', 'scenario': 'normal'},
])
def test_invalid_input_never_calls_model(client, model, payload):
    response = client.post('/api/ask', json=payload)
    assert response.status_code == 422
    assert model.calls == 0


def test_health_and_model_readiness_are_distinct(client, model):
    assert client.get('/healthz').status_code == 200
    assert client.get('/readyz').status_code == 200
    model.is_ready = False
    assert client.get('/healthz').status_code == 200
    assert client.get('/readyz').status_code == 503
    assert model.calls == 0


def test_public_metadata_does_not_expose_credentials(client, monkeypatch):
    secret = 'sptrans_PRIVATE_TEST_VALUE_NOT_A_REAL_TOKEN'
    monkeypatch.setattr(main.settings, 'token', secret)
    monkeypatch.setattr(main.settings, 'metrics_token', 'metrics_PRIVATE_TEST_VALUE')
    for endpoint in ['/api/config', '/healthz', '/readyz', '/openapi.json']:
        response = client.get(endpoint)
        assert response.status_code == 200
        assert secret not in response.text
        assert 'metrics_PRIVATE_TEST_VALUE' not in response.text
    config = client.get('/api/config').json()
    assert config['mode'] in ('demo', 'live')
    assert isinstance(config['model'], str)
    assert isinstance(config['version'], str)


def test_metrics_requires_configured_bearer_token(client, monkeypatch):
    monkeypatch.setattr(main.settings, 'metrics_token', 'test_metrics_access')
    assert client.get('/metrics').status_code in (401, 403)
    assert client.get('/metrics', headers={'Authorization': 'Bearer wrong'}).status_code in (401, 403)
    response = client.get('/metrics', headers={'Authorization': 'Bearer test_metrics_access'})
    assert response.status_code == 200
    assert 'ponto_certo_http_requests_total' in response.text
    assert 'test_metrics_access' not in response.text


def test_metrics_disabled_without_token(client, monkeypatch):
    monkeypatch.setattr(main.settings, 'metrics_token', '')
    assert client.get('/metrics').status_code in (401, 403, 404, 503)


def test_metrics_never_labels_arbitrary_url_or_query(client, monkeypatch):
    monkeypatch.setattr(main.settings, 'metrics_token', 'test_metrics_access')
    client.get('/private-marker-in-path?question=private-marker-in-query')
    response = client.get('/metrics', headers={'Authorization': 'Bearer test_metrics_access'})
    assert response.status_code == 200
    assert 'private-marker-in-path' not in response.text
    assert 'private-marker-in-query' not in response.text


def test_model_outage_has_safe_structured_answer(client, model):
    model.failure = True
    response = client.post('/api/ask', json={'question': 'Previsão de chegada é garantia de horário?'})
    assert response.status_code in (200, 503)
    body = response.json()
    assert body['status'] == 'unavailable'
    assert isinstance(body['answer'], str)
    assert body['sources'] == []
    assert 'PRIVATE_DETAIL_MUST_NOT_ESCAPE' not in response.text
    assert model.calls == 1


def test_browser_entrypoint_and_assets(client):
    page = client.get('/')
    assert page.status_code == 200
    assert '<html lang="pt-BR">' in page.text
    assert 'DEMONSTRAÇÃO' in page.text
    for asset in ['/static/app.css', '/static/app.js']:
        assert client.get(asset).status_code == 200


def test_validation_error_does_not_echo_user_text(client, model):
    private_input = 'PRIVATE_INPUT_MUST_NOT_ESCAPE'
    response = client.post('/api/ask', json={'question': private_input, 'stop_code': -1})
    assert response.status_code == 422
    assert private_input not in response.text
    assert model.calls == 0
