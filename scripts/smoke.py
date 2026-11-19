#!/usr/bin/env python3
"""Verify a running Ponto Certo deployment without persisting free-text responses.

Example: python scripts/smoke.py --base-url http://127.0.0.1:8000 \
    --expect-mode demo --output evidencias/smoke-local.json
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class CheckFailed(Exception):
    """A bounded, non-sensitive failure description."""


def request(base, path, timeout, payload=None):
    headers = {'Accept': 'application/json'}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    started = time.perf_counter()
    req = Request(base + path, data=body, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            code = response.status
            raw = response.read(1_000_001)
    except HTTPError as exc:
        code, raw = exc.code, exc.read(1_000_001)
    except (URLError, TimeoutError, OSError):
        raise CheckFailed('connection_failed') from None
    if len(raw) > 1_000_000:
        raise CheckFailed('response_too_large')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise CheckFailed('response_not_json') from None
    if not isinstance(data, dict):
        raise CheckFailed('response_not_object')
    return code, data, round(time.perf_counter() - started, 3)


def require(condition, label):
    if not condition:
        raise CheckFailed(label)


def metadata(data):
    """Only allow bounded structural metadata into the saved public evidence."""
    result = {}
    for field, allowed in (
        ('status', {'ok', 'not_found', 'clarification', 'unavailable'}),
        ('data_mode', {'demo', 'live', 'documental'}),
    ):
        value = data.get(field)
        if isinstance(value, str) and value in allowed:
            result[field] = value
    sources = data.get('sources', [])
    result['source_count'] = len(sources) if isinstance(sources, list) else 0
    result['has_update'] = isinstance(data.get('updated_at'), str)
    return result


def validate_answer(data, mode):
    require(data.get('status') == 'ok', 'answer_not_ok')
    require(isinstance(data.get('answer'), str) and bool(data['answer'].strip()), 'answer_missing')
    require(data.get('data_mode') == mode, 'data_mode_mismatch')
    require(isinstance(data.get('sources'), list) and len(data['sources']) > 0, 'sources_missing')
    require(isinstance(data.get('warnings'), list), 'warnings_missing')
    require(isinstance(data.get('request_id'), str), 'request_id_missing')
    for source in data['sources']:
        require(isinstance(source, dict) and isinstance(source.get('id'), str), 'source_id_missing')
        require(isinstance(source.get('title'), str), 'source_title_missing')
        url = source.get('url', '')
        require(isinstance(url, str) and (urlsplit(url).scheme == 'https' or url == '/base/POLITICA-DO-PRODUTO.md'), 'source_url_not_allowed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--expect-mode', choices=['demo', 'live'], default='demo')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--ready-timeout', type=float, default=90)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    url = urlsplit(base)
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment:
        parser.error('--base-url deve ser uma URL HTTP(S) sem credenciais, query ou fragmento')
    if args.timeout <= 0 or args.ready_timeout < 0:
        parser.error('timeouts devem ser positivos')
    report = {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'base_url': base,
        'expected_mode': args.expect_mode,
        'checks': [],
        'passed': False,
        'privacy': 'Somente checks e metadados; perguntas e respostas livres não são salvas.',
    }
    stage = 'healthz'
    try:
        code, data, elapsed = request(base, '/healthz', args.timeout)
        require(code == 200, 'healthz_not_200')
        report['checks'].append({'name': stage, 'passed': True, 'http_status': code, 'seconds': elapsed})
        stage = 'readiness'
        deadline = time.monotonic() + args.ready_timeout
        while True:
            try:
                code, data, elapsed = request(base, '/readyz', min(args.timeout, 8))
                if code == 200:
                    break
            except CheckFailed:
                code = None
            if time.monotonic() >= deadline:
                raise CheckFailed('dependencies_not_ready')
            time.sleep(min(2, max(0, deadline - time.monotonic())))
        report['checks'].append({'name': stage, 'passed': True, 'http_status': code, 'seconds': elapsed})
        stage = 'config'
        code, config, elapsed = request(base, '/api/config', args.timeout)
        require(code == 200, 'config_not_200')
        require(config.get('mode') == args.expect_mode, 'configured_mode_mismatch')
        report['checks'].append({'name': stage, 'passed': True, 'http_status': code, 'mode': config['mode']})
        stage = 'documental'
        code, data, elapsed = request(base, '/api/ask', args.timeout, {'question': 'Previsão de chegada é garantia de horário?'})
        require(code == 200, 'documental_not_200')
        validate_answer(data, 'documental')
        answer = data['answer'].casefold()
        require('garant' in answer and any(term in answer for term in ['não', 'nao', 'sem garantia']), 'forecast_caution_missing')
        report['checks'].append({'name': stage, 'passed': True, 'http_status': code, 'seconds': elapsed, **metadata(data)})
        if args.expect_mode == 'demo':
            stage = 'arrival_demo'
            code, data, elapsed = request(base, '/api/ask', args.timeout, {
                'question': 'Qual a previsão de chegada da linha 8000 neste ponto?',
                'line_code': 1273, 'stop_code': 4200153, 'direction': 1,
            })
            require(code == 200, 'arrival_not_200')
            validate_answer(data, 'demo')
            visible = ' '.join([data['answer'], *[x for x in data['warnings'] if isinstance(x, str)]]).casefold()
            require(any(word in visible for word in ['simulad', 'teste', 'demonstra']), 'demo_label_missing')
            require(isinstance(data.get('updated_at'), str), 'arrival_update_missing')
            try:
                datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
            except ValueError:
                raise CheckFailed('arrival_update_invalid') from None
            report['checks'].append({'name': stage, 'passed': True, 'http_status': code, 'seconds': elapsed, **metadata(data)})
        else:
            report['checks'].append({'name': 'arrival_live', 'passed': None, 'reason': 'requires_verified_live_line_and_stop; demo IDs are not used as proof of live coverage'})
        report['passed'] = True
    except CheckFailed as exc:
        report['checks'].append({'name': stage, 'passed': False, 'failure': str(exc)})
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
