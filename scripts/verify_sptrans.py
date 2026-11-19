#!/usr/bin/env python3
"""Verify a real SPTrans session without exposing credentials or scanning broadly.

After the operator puts SPTRANS_TOKEN in the ignored .env file:
    .venv/bin/python -m scripts.verify_sptrans --query 8000

At most 6 HTTP requests: authenticate once, find lines, then at most two directions
of one line, with one stop search and one arrival query per direction. API source
values are reduced to an explicit allowlist before saving. No raw body is saved.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

import httpx

# Allow both `python scripts/verify_sptrans.py` and `python -m scripts.verify_sptrans`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.settings import Settings

API = 'https://api.olhovivo.sptrans.com.br/v2.1'
DOC = 'https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api'
TZ = ZoneInfo('America/Sao_Paulo')
MAX_BODY_BYTES = 1_000_000
MAX_REQUESTS = 6
CLOCK = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d\Z')


class VerificationError(Exception):
    """Only fixed public codes; never wrap a raw HTTP exception or URL."""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 2_147_483_647


def public_name(value):
    if not isinstance(value, str) or len(value) > 300:
        raise VerificationError('invalid_schema')
    return ' '.join(value.split())


def redact(value, secret):
    """Defense against an upstream body unexpectedly echoing the credential."""
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]') if secret else value
    if isinstance(value, dict):
        return {key: redact(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    return value


class Verifier:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport  # Injected only by offline tests; CLI cannot change API URL.
        self.request_count = 0

    async def fetch(self, client, path, params=None, method='GET'):
        if path not in {'/Login/Autenticar', '/Linha/Buscar', '/Parada/BuscarParadasPorLinha', '/Previsao'}:
            raise VerificationError('endpoint_not_allowed')
        if self.request_count >= MAX_REQUESTS:
            raise VerificationError('request_limit_reached')
        self.request_count += 1
        try:
            async with client.stream(method, API + path, params=params) as response:
                if response.status_code != 200:
                    # Do not inspect redirect URLs, response headers or error bodies.
                    raise VerificationError(f'http_{response.status_code}')
                raw = bytearray()
                async for part in response.aiter_bytes():
                    raw.extend(part)
                    if len(raw) > MAX_BODY_BYTES:
                        raise VerificationError('response_too_large')
            return json.loads(raw)
        except httpx.TimeoutException:
            raise VerificationError('timeout') from None
        except httpx.HTTPError:
            raise VerificationError('network_error') from None
        except (ValueError, UnicodeDecodeError):
            raise VerificationError('invalid_json') from None

    @staticmethod
    def parse_lines(data):
        if not isinstance(data, list) or len(data) > 5000:
            raise VerificationError('invalid_lines_schema')
        lines = []
        for item in data:
            if not isinstance(item, dict) or not positive_int(item.get('cl')) or item.get('sl') not in (1, 2) or isinstance(item.get('sl'), bool):
                raise VerificationError('invalid_lines_schema')
            number = item.get('lt')
            service = item.get('tl')
            if not isinstance(number, str) or not re.fullmatch(r'[A-Za-z0-9]{1,8}', number) or not positive_int(service):
                raise VerificationError('invalid_lines_schema')
            lines.append({'code': item['cl'], 'number': number.upper(), 'service': service, 'direction': item['sl'],
                          'primary_label': public_name(item.get('tp')), 'secondary_label': public_name(item.get('ts'))})
        return sorted(lines, key=lambda row: (row['number'], row['service'], row['direction'], row['code']))

    @staticmethod
    def parse_stops(data):
        if not isinstance(data, list) or len(data) > 5000:
            raise VerificationError('invalid_stops_schema')
        stops = []
        for item in data:
            if not isinstance(item, dict) or not positive_int(item.get('cp')):
                raise VerificationError('invalid_stops_schema')
            stops.append({'code': item['cp'], 'name': public_name(item.get('np'))})
        return sorted(stops, key=lambda row: row['code'])

    def parse_arrivals(self, data, line, stop):
        if not isinstance(data, dict) or not isinstance(data.get('hr'), str) or not CLOCK.fullmatch(data['hr']):
            raise VerificationError('invalid_arrivals_schema')
        observed_at = datetime.now(TZ)
        hour, minute = map(int, data['hr'].split(':'))
        candidate = observed_at.replace(hour=hour, minute=minute, second=0, microsecond=0)
        source_clock = min((candidate - timedelta(days=1), candidate, candidate + timedelta(days=1)),
                           key=lambda value: abs((observed_at - value).total_seconds()))
        age = round((observed_at - source_clock).total_seconds())
        summary = {
            'queried_at': observed_at.isoformat(), 'source_time_of_day': data['hr'],
            'inferred_source_age_seconds': age,
            'source_clock_within_limit': -60 <= age <= self.settings.max_age,
            'clock_note': 'hr só informa hora/minuto; data inferida pelo dia mais próximo da consulta, não fornecida pela API.',
            'returned_line_count': 0, 'matching_line_count': 0, 'forecast_count': 0, 'forecasts': [],
        }
        if data.get('p') is None:
            return summary
        point = data['p']
        if not isinstance(point, dict) or point.get('cp') != stop['code'] or isinstance(point.get('cp'), bool):
            raise VerificationError('stop_mismatch_or_invalid_schema')
        lines = point.get('l')
        if not isinstance(lines, list) or len(lines) > 5000:
            raise VerificationError('invalid_arrivals_schema')
        summary['returned_line_count'] = len(lines)
        forecasts = []
        for item in lines:
            if not isinstance(item, dict) or not positive_int(item.get('cl')) or item.get('sl') not in (1, 2) or isinstance(item.get('sl'), bool):
                raise VerificationError('invalid_arrivals_schema')
            vehicles = item.get('vs')
            if not isinstance(vehicles, list) or len(vehicles) > 5000:
                raise VerificationError('invalid_arrivals_schema')
            if item['cl'] != line['code'] or item['sl'] != line['direction']:
                continue
            summary['matching_line_count'] += 1
            for vehicle in vehicles:
                if not isinstance(vehicle, dict) or not isinstance(vehicle.get('t'), str) or not CLOCK.fullmatch(vehicle['t']):
                    raise VerificationError('invalid_forecast_schema')
                record = {'arrival_time_of_day': vehicle['t']}
                ta = vehicle.get('ta')
                if ta is not None:
                    if not isinstance(ta, str) or len(ta) > 64:
                        raise VerificationError('invalid_vehicle_timestamp')
                    try:
                        telemetry_time = datetime.fromisoformat(ta.replace('Z', '+00:00'))
                        if telemetry_time.tzinfo is None:
                            raise ValueError()
                    except ValueError:
                        raise VerificationError('invalid_vehicle_timestamp') from None
                    record['vehicle_observed_at'] = telemetry_time.isoformat()
                    record['vehicle_observation_age_seconds'] = round((observed_at - telemetry_time).total_seconds())
                # Do not copy prefix/plate, position, accessibility or other fields.
                forecasts.append(record)
        summary['forecast_count'] = len(forecasts)
        summary['forecasts'] = sorted(forecasts, key=lambda item: (item['arrival_time_of_day'], item.get('vehicle_observed_at', '')))
        return summary

    async def run(self, query):
        report = {
            'schema_version': 1, 'started_at': timestamp(), 'mode': 'live',
            'notice': 'Verificação real pontual. Evidência histórica, não previsão atual nem garantia de chegada.',
            'source': {'name': 'SPTrans Olho Vivo', 'api_version': 'v2.1', 'documentation_url': DOC},
            'selection_policy': 'Primeira linha por número/serviço ordenados; até dois sentidos distintos e menor código de parada de cada retorno. Sem varredura ampla.',
            'authentication': {'verified': False, 'status': 'not_attempted'},
            'line_discovery': {'query_succeeded': False}, 'checks': [],
            'summary': {'authenticated': False, 'real_query_succeeded': False, 'arrival_queries_succeeded': 0,
                        'nonempty_predictions': False, 'fresh_source_clock_with_predictions': False},
        }
        if not self.settings.token:
            report['status'] = 'missing_credentials'
            report['authentication']['status'] = 'missing_token'
            return self.finish(report)
        # httpx receives the credential in the API-mandated query parameter. Silence
        # URL-bearing library diagnostics; exception messages are never persisted.
        for name in ('httpx', 'httpcore'):
            logging.getLogger(name).setLevel(logging.CRITICAL)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(12), follow_redirects=False, transport=self.transport) as client:
                try:
                    auth = await self.fetch(client, '/Login/Autenticar', {'token': self.settings.token}, 'POST')
                    if auth is not True:
                        raise VerificationError('authentication_rejected' if auth is False else 'invalid_authentication_response')
                    report['authentication'] = {'verified': True, 'status': 'authenticated', 'verified_at': timestamp()}
                    report['summary']['authenticated'] = True
                except VerificationError as exc:
                    report['authentication']['status'] = str(exc)
                    report['status'] = 'authentication_failed'
                    return self.finish(report)
                try:
                    data = await self.fetch(client, '/Linha/Buscar', {'termosBusca': query})
                    lines = self.parse_lines(data)
                    report['line_discovery'] = {'query_succeeded': True, 'queried_at': timestamp(), 'returned_line_count': len(lines)}
                    report['summary']['real_query_succeeded'] = True
                except VerificationError as exc:
                    report['line_discovery']['error'] = str(exc)
                    report['status'] = 'line_query_failed'
                    return self.finish(report)
                selected = []
                if lines:
                    route_key = (lines[0]['number'], lines[0]['service'])
                    seen = set()
                    for line in lines:
                        if (line['number'], line['service']) == route_key and line['direction'] not in seen:
                            selected.append(line)
                            seen.add(line['direction'])
                        if len(selected) == 2:
                            break
                    report['line_discovery']['selected_route'] = f'{route_key[0]}-{route_key[1]}'
                report['line_discovery']['selected_directions'] = len(selected)
                had_failure = False
                for line in selected:
                    check = {'line': line, 'stop_search': {'query_succeeded': False}, 'arrival': {'query_succeeded': False}}
                    report['checks'].append(check)
                    try:
                        data = await self.fetch(client, '/Parada/BuscarParadasPorLinha', {'codigoLinha': line['code']})
                        stops = self.parse_stops(data)
                        check['stop_search'] = {'query_succeeded': True, 'queried_at': timestamp(), 'returned_stop_count': len(stops)}
                        if not stops:
                            check['arrival']['status'] = 'not_attempted_no_stops'
                            continue
                        stop = stops[0]
                        check['selected_stop'] = stop
                    except VerificationError as exc:
                        check['stop_search']['error'] = str(exc)
                        check['arrival']['status'] = 'not_attempted_stop_query_failed'
                        had_failure = True
                        continue
                    try:
                        data = await self.fetch(client, '/Previsao', {'codigoLinha': line['code'], 'codigoParada': stop['code']})
                        arrival = self.parse_arrivals(data, line, stop)
                        check['arrival'] = {'query_succeeded': True, 'status': 'forecasts_returned' if arrival['forecast_count'] else 'empty_return', **arrival}
                        report['summary']['arrival_queries_succeeded'] += 1
                        report['summary']['nonempty_predictions'] |= arrival['forecast_count'] > 0
                        report['summary']['fresh_source_clock_with_predictions'] |= arrival['forecast_count'] > 0 and arrival['source_clock_within_limit']
                    except VerificationError as exc:
                        check['arrival'] = {'query_succeeded': False, 'status': 'query_failed', 'error': str(exc)}
                        had_failure = True
                if had_failure:
                    report['status'] = 'live_partially_verified'
                elif report['summary']['nonempty_predictions']:
                    report['status'] = 'live_verified_with_forecasts'
                elif report['summary']['arrival_queries_succeeded']:
                    report['status'] = 'live_verified_without_forecasts'
                else:
                    report['status'] = 'live_verified_limited_coverage'
        except Exception:
            # Last boundary: no unexpected exception traceback or credential-bearing URL.
            report['status'] = 'verification_failed'
            report['error'] = 'unexpected_error'
        return self.finish(report)

    def finish(self, report):
        report['http_request_count'] = self.request_count
        report['finished_at'] = timestamp()
        report['limits'] = [
            'Autenticação e consulta bem-sucedidas não implicam previsão não vazia.',
            'Ausência de paradas/previsão não comprova ausência de ônibus ou serviço.',
            'A categoria de paradas tem cobertura limitada; uma parada por sentido não representa toda a linha.',
            'Horários retornados e idade da telemetria são evidências da fonte, não garantia de chegada.',
        ]
        return redact(report, self.settings.token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='8000', help='Termo enviado à busca oficial; os códigos são sempre descobertos no retorno.')
    parser.add_argument('--output', type=Path, help='JSON de evidência; padrão: evidencias/sptrans-verificacao-DATA.json')
    args = parser.parse_args()
    query = args.query.strip()
    if not query or len(query) > 80 or any(ord(char) < 32 for char in query):
        parser.error('--query deve ter 1–80 caracteres, sem controles')
    try:
        report = asyncio.run(Verifier(Settings(mode='live')).run(query))
        output = args.output or ROOT / 'evidencias' / ('sptrans-verificacao-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # Report only a fixed status and counters on stdout. Never print raw bodies/paths.
        print(json.dumps({'status': report['status'], **report['summary'], 'http_request_count': report['http_request_count']}, ensure_ascii=False))
        return 0 if report['status'].startswith('live_verified_') else 1
    except KeyboardInterrupt:
        print('{"status":"interrupted"}')
        return 130
    except Exception:
        print('{"status":"verification_failed","error":"configuration_or_output_error"}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
