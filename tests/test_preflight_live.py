"""Exercise the actual Engine with offline transports; no network or secrets."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.engine import Engine
from app.settings import Settings
from app.transit import DOC, TransitUnavailable
from scripts import preflight_live

CANARY = 'not_a_real_token_private_canary'


class Clock:
    def __init__(self): self.now = datetime.fromisoformat('2026-11-19T10:20:30-03:00')
    def __call__(self): return self.now
    def advance(self, seconds): self.now += timedelta(seconds=seconds)


class CopyModel:
    def __init__(self, clock, scenario):
        self.calls = 0
        self.clock, self.scenario = clock, scenario

    async def generate(self, question, evidence, instruction=''):
        self.calls += 1
        if self.scenario == 'slow_llm' and evidence[0]['id'] == 'SPTRANS_QUERY':
            self.clock.advance(11)
        return {'status': 'ok', 'answer': evidence[0]['text'], 'source_ids': [evidence[0]['id']]}, {
            'model_called': True, 'model_json_valid': True, 'model_raw': CANARY,
        }


class Source:
    def __init__(self, clock, scenario='normal'):
        self.scenario = scenario
        self.clock = clock
        self.calls = []

    async def call(self, action, **kwargs):
        self.calls.append(action)
        if self.scenario == 'unavailable':
            raise TransitUnavailable('https://example.invalid/auth?token=' + CANARY)
        now = self.clock()
        observed = now - timedelta(seconds=400 if self.scenario == 'stale_clock' else 0)
        telemetry_age = 400 if self.scenario == 'stale_vehicle' else 170 if self.scenario in {'slow_http', 'slow_llm'} else 5
        telemetry = now - timedelta(seconds=telemetry_age)
        if action == 'lines':
            data = [{'cl': 35274, 'lt': '8000', 'tl': 1, 'sl': 2, 'tp': 'TERMINAL', 'ts': 'PRACA'}]
        else:
            line_code = 2506 if self.scenario == 'filtered' else 35274
            data = {'hr': now.strftime('%H:%M'), 'p': {'cp': 614432, 'np': CANARY, 'l': [{
                'cl': line_code, 'sl': 2, 'c': '8000-01',
                'vs': [{'p': CANARY, 'px': -46.5, 'py': -23.5,
                        't': (now + timedelta(minutes=5)).strftime('%H:%M'), 'ta': telemetry.isoformat()}],
            }]}}
            if self.scenario == 'empty':
                data['p'] = None
            if self.scenario == 'wrong_stop':
                data['p']['cp'] = 999999
        if self.scenario == 'slow_http':
            self.clock.advance(20)
        return {'data': data, 'queried_at': now.isoformat(), 'observed_at': observed.isoformat(),
                'received_at': self.clock().isoformat(),
                'mode': 'demo' if self.scenario == 'synthetic' else 'live',
                'synthetic': self.scenario == 'synthetic', 'source': DOC, 'action': action}


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    old_level = logging.root.manager.disable
    def no_network(*args, **kwargs):
        raise AssertionError('Tests must remain offline')
    monkeypatch.setattr('httpx.AsyncClient', no_network)
    yield
    logging.disable(old_level)


def run_case(scenario='normal'):
    settings = Settings(mode='live', token=CANARY)
    clock = Clock()
    model, source = CopyModel(clock, scenario), Source(clock, scenario)
    engine = Engine(settings, model=model, transit=source, clock=clock)
    report = asyncio.run(preflight_live.preflight(settings, engine=engine))
    serialized = json.dumps(report)
    assert CANARY not in serialized
    assert 'model_raw' not in serialized and 'tool_result' not in serialized
    assert '-46.5' not in serialized and '-23.5' not in serialized
    return report, model, source


def test_real_engine_forecast_path_and_allowlisted_evidence():
    report, model, source = run_case()
    assert report['passed'] and report['forecast_available']
    assert report['status'] == 'passed_with_forecast'
    assert report['live_tool_with_model_proven']
    assert model.calls == 2 and source.calls == ['arrivals']
    assert report['checks'][1]['synthetic'] is False
    assert report['checks'][1]['displayed_vehicle_timestamps_fresh']
    assert report['schema_version'] == 2
    assert report['freshness_reference'] == 'current_clock_after_inference'


@pytest.mark.parametrize('scenario,returned_lines', [('empty', 0), ('filtered', 1)])
def test_no_usable_forecast_requires_separate_live_model_proof(scenario, returned_lines):
    report, model, source = run_case(scenario)
    assert report['passed'] and not report['forecast_available']
    assert report['status'] == 'passed_without_usable_forecast'
    assert report['checks'][1]['returned_lines'] == returned_lines
    assert not report['checks'][1]['model_called']
    assert report['checks'][2]['name'] == 'line_live_fallback'
    assert model.calls == 2 and source.calls == ['arrivals', 'lines']


@pytest.mark.parametrize('scenario', ['synthetic', 'stale_clock', 'stale_vehicle', 'unavailable', 'wrong_stop'])
def test_unsafe_or_missing_source_is_never_a_passing_live_proof(scenario):
    report, _, _ = run_case(scenario)
    assert not report['passed'] and not report['forecast_available']
    assert not report['live_tool_with_model_proven']


@pytest.mark.parametrize('scenario,age,model_calls', [('slow_http', 190, 1), ('slow_llm', 181, 2)])
def test_preflight_measures_age_after_transport_and_inference(scenario, age, model_calls):
    report, model, _ = run_case(scenario)
    assert not report['passed'] and not report['forecast_available']
    check = report['checks'][1]
    assert check['status'] == 'unavailable'
    assert not check['displayed_vehicle_timestamps_fresh']
    assert check['oldest_displayed_vehicle_age_seconds'] == age
    assert check['freshness_checked_at'] > check['queried_at']
    assert model.calls == model_calls


@pytest.mark.parametrize('scenario', ['normal', 'empty'])
def test_sanitized_report_fits_managed_run_command_stdout(scenario):
    report, _, _ = run_case(scenario)
    assert len((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()) < 3800


def test_refuses_demo_without_network():
    report = asyncio.run(preflight_live.preflight(Settings(mode='demo', token=CANARY)))
    assert not report['passed'] and report['checks'] == []
    assert report['failure'] == 'live_mode_and_credentials_required'


def test_bad_arguments_never_echo_a_credential(capsys):
    assert preflight_live.main(['--token', CANARY]) == 1
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err
    assert json.loads(captured.out)['failure'] == 'configuration_or_execution_error'


def test_invalid_environment_never_escapes_bootstrap_as_traceback():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, 'scripts/preflight_live.py'], cwd=root,
                            env={**os.environ, 'DATA_MODE': 'demo', 'SPTRANS_TOKEN': CANARY,
                                 'LLM_TIMEOUT_SECONDS': CANARY},
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1
    assert CANARY not in result.stdout + result.stderr
    assert 'Traceback' not in result.stdout + result.stderr
    assert json.loads(result.stdout)['failure'] == 'configuration_or_execution_error'
