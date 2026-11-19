"""Public runtime rejects mismatched/stale live forecasts; no network or secrets."""
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
import httpx
from fastapi.testclient import TestClient

from app import main
from app.engine import Engine
from app.settings import Settings
from app.transit import DOC, Transit

QUERY = {'question': 'Qual a previsão de chegada neste ponto?',
         'line_code': 35274, 'stop_code': 614432, 'direction': 2}
NOW = datetime.fromisoformat('2026-11-19T10:20:30-03:00')
CANARY = 'synthetic_private_timestamp_not_for_output'


class Clock:
    def __init__(self, now=NOW): self.now = now
    def __call__(self): return self.now
    def advance(self, seconds): self.now += timedelta(seconds=seconds)


class CopyModel:
    def __init__(self): self.calls = 0

    async def generate(self, question, evidence, instruction=''):
        self.calls += 1
        return {'status': 'ok', 'answer': evidence[0]['text'], 'source_ids': [evidence[0]['id']]}, {
            'model_called': True, 'model_json_valid': True,
        }


class DelayedModel(CopyModel):
    def __init__(self, clock, seconds):
        super().__init__()
        self.clock, self.seconds = clock, seconds

    async def generate(self, *args, **kwargs):
        result = await super().generate(*args, **kwargs)
        self.clock.advance(self.seconds)
        return result


class LiveSource:
    def __init__(self, data, now): self.data, self.now = data, now

    async def call(self, action, **kwargs):
        assert action == 'arrivals'
        return {'data': deepcopy(self.data), 'queried_at': self.now.isoformat(),
                'received_at': self.now.isoformat(),
                'observed_at': self.now.isoformat(), 'mode': 'live', 'synthetic': False,
                'source': DOC, 'action': action}


def payload(now=NOW, age=5):
    return {'hr': now.strftime('%H:%M'), 'p': {'cp': QUERY['stop_code'], 'l': [{
        'cl': QUERY['line_code'], 'sl': 2, 'c': '8000-01',
        'vs': [{'t': (now + timedelta(minutes=5)).strftime('%H:%M'),
                'ta': (now - timedelta(seconds=age)).isoformat()}],
    }]}}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs): raise AssertionError('Runtime regression tests must be offline')
    monkeypatch.setattr('httpx.AsyncClient', refuse)


@pytest.fixture
def public_ask(monkeypatch):
    def ask(data, now=NOW, mode='live', clock=None, model=None, transit=None):
        model = model or CopyModel()
        engine = Engine(Settings(mode=mode, token='synthetic_runtime_token', max_age=180),
                        model=model, transit=transit or LiveSource(data, now), clock=clock or Clock(now))
        monkeypatch.setattr(main, 'engine', engine)
        with TestClient(main.app) as client:
            response = client.post('/api/ask', json=QUERY)
        assert CANARY not in response.text
        return response, model
    return ask


@pytest.mark.parametrize('age', [5, 180, -60])
def test_fresh_live_vehicle_and_inclusive_boundaries_reach_model(public_ask, age):
    response, model = public_ask(payload(age=age))
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok' and body['data_mode'] == 'live'
    assert body['sources'][0]['id'] == 'SPTRANS_QUERY' and model.calls == 1


@pytest.mark.parametrize('kind', ['old', 'future', 'absent', 'null', 'malformed', 'naive'])
def test_bad_telemetry_never_becomes_a_public_arrival(public_ask, kind):
    data = payload(age=181 if kind == 'old' else -61 if kind == 'future' else 5)
    vehicle = data['p']['l'][0]['vs'][0]
    if kind == 'absent': vehicle.pop('ta')
    if kind == 'null': vehicle['ta'] = None
    if kind == 'malformed': vehicle['ta'] = CANARY
    if kind == 'naive': vehicle['ta'] = NOW.replace(tzinfo=None).isoformat()
    response, model = public_ask(data)
    assert response.status_code == 503 and response.json()['status'] == 'unavailable'
    assert response.json()['data_mode'] == 'live' and model.calls == 0
    assert 'Não consta previsão' not in response.json()['answer']


@pytest.mark.parametrize('point_code', [999999, None, True, '614432'])
def test_different_or_invalid_point_is_unavailable_even_without_forecasts(public_ask, point_code):
    data = payload(); data['p']['cp'] = point_code; data['p']['l'] = []
    response, model = public_ask(data)
    assert response.status_code == 503 and response.json()['status'] == 'unavailable'
    assert 'ponto diferente' in response.json()['answer'] and model.calls == 0


def test_real_empty_return_remains_honest_not_found(public_ask):
    response, model = public_ask({'hr': NOW.strftime('%H:%M'), 'p': None})
    assert response.status_code == 200 and response.json()['status'] == 'not_found'
    assert 'não significa ausência' in response.json()['answer'] and model.calls == 0


def test_vehicle_timestamp_and_forecast_cross_midnight(public_ask):
    now = datetime.fromisoformat('2026-11-20T00:00:30-03:00')
    response, model = public_ask(payload(now, age=60), now=now)
    assert response.status_code == 200 and response.json()['status'] == 'ok'
    assert '00:05' in response.json()['answer'] and model.calls == 1


def test_stale_vehicle_from_a_different_line_does_not_contaminate_requested_line(public_ask):
    data = payload(); other = deepcopy(data['p']['l'][0]); other['cl'] = 2506
    other['vs'][0]['ta'] = (NOW - timedelta(hours=1)).isoformat()
    data['p']['l'].insert(0, other)
    response, model = public_ask(data)
    assert response.status_code == 200 and response.json()['status'] == 'ok' and model.calls == 1


def test_expired_prediction_is_filtered_before_telemetry_validation(public_ask):
    data = payload(); expired = {'t': (NOW - timedelta(minutes=5)).strftime('%H:%M')}
    data['p']['l'][0]['vs'].insert(0, expired)
    response, model = public_ask(data)
    assert response.status_code == 200 and response.json()['status'] == 'ok' and model.calls == 1


def test_only_six_displayed_forecasts_require_vehicle_telemetry(public_ask):
    data = payload(); vehicle = data['p']['l'][0]['vs'][0]
    data['p']['l'][0]['vs'] = [deepcopy(vehicle) for _ in range(6)] + [{'t': vehicle['t']}]
    response, model = public_ask(data)
    assert response.status_code == 200 and response.json()['status'] == 'ok' and model.calls == 1
    assert response.json()['answer'].count('previsão') == 6


def test_frozen_demo_contract_does_not_require_live_vehicle_timestamp(public_ask):
    data = payload(); data['p']['l'][0]['vs'][0].pop('ta')
    response, model = public_ask(data, mode='demo')
    assert response.status_code == 200 and response.json()['status'] == 'ok' and model.calls == 1
    assert response.json()['data_mode'] == 'demo'


def mock_delayed_http(monkeypatch, data, clock, seconds):
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            clock.advance(seconds / 2)
            return httpx.Response(200, json=True, request=httpx.Request('POST', url))
        async def get(self, url, **kwargs):
            clock.advance(seconds / 2)
            return httpx.Response(200, json=deepcopy(data), request=httpx.Request('GET', url))
    monkeypatch.setattr('httpx.AsyncClient', Client)


def test_auth_and_get_latency_counts_toward_vehicle_age(monkeypatch, public_ask):
    clock = Clock()
    data = payload(age=170)
    mock_delayed_http(monkeypatch, data, clock, seconds=20)
    transit = Transit(Settings(mode='live', token='synthetic_runtime_token'), clock=clock)
    response, model = public_ask(data, clock=clock, transit=transit)
    assert clock.now == NOW + timedelta(seconds=20)
    assert response.status_code == 503 and response.json()['status'] == 'unavailable'
    assert model.calls == 0 and response.json()['sources'] == []
    assert '10:25' not in response.json()['answer']


def test_api_clock_is_validated_at_http_receipt(monkeypatch, public_ask):
    clock = Clock()
    data = payload(); data['hr'] = '10:18'
    mock_delayed_http(monkeypatch, data, clock, seconds=40)
    transit = Transit(Settings(mode='live', token='synthetic_runtime_token'), clock=clock)
    response, model = public_ask(data, clock=clock, transit=transit)
    assert response.status_code == 503 and model.calls == 0
    assert 'desatualizada' in response.json()['answer']


@pytest.mark.asyncio
async def test_transit_preserves_query_start_and_records_receipt(monkeypatch):
    clock = Clock()
    data = payload()
    mock_delayed_http(monkeypatch, data, clock, seconds=20)
    transit = Transit(Settings(mode='live', token='synthetic_runtime_token'), clock=clock)
    result = await transit.call('arrivals', line_code=35274, stop_code=614432)
    assert result['queried_at'] == NOW.isoformat()
    assert result['received_at'] == (NOW + timedelta(seconds=20)).isoformat()
    assert result['observed_at'] == NOW.replace(second=0).isoformat()


@pytest.mark.parametrize('seconds,status', [(10, 200), (11, 503)])
@pytest.mark.parametrize('now', [NOW, datetime.fromisoformat('2026-11-19T23:59:55-03:00')])
def test_llm_latency_rechecks_selected_vehicle_before_public_response(public_ask, seconds, status, now):
    clock = Clock(now)
    model = DelayedModel(clock, seconds)
    response, model = public_ask(payload(now, age=170), now=now, clock=clock, model=model)
    assert response.status_code == status and model.calls == 1
    if status == 503:
        assert response.json()['status'] == 'unavailable' and response.json()['sources'] == []
        assert 'minutos' not in response.json()['answer']
        assert (now + timedelta(minutes=5)).strftime('%H:%M') not in response.json()['answer']
        assert 'Não consta previsão' not in response.json()['answer']


def test_llm_latency_rechecks_source_clock_even_with_fresh_vehicle(public_ask):
    clock = Clock()
    model = DelayedModel(clock, 181)
    response, model = public_ask(payload(age=-10), clock=clock, model=model)
    assert response.status_code == 503 and model.calls == 1
    assert 'desatualizada' in response.json()['answer']
    assert 'minutos' not in response.json()['answer']


def test_naive_current_clock_is_unavailable(public_ask):
    response, model = public_ask(payload(), clock=Clock(NOW.replace(tzinfo=None)))
    assert response.status_code == 503 and model.calls == 0
