#!/usr/bin/env python3
"""Run the real Engine/Transit/local LLM without changing the public service.

Run from /app in the existing container, with DATA_MODE=live and SPTRANS_TOKEN
already supplied through the protected environment. This file may be mounted or
passed on stdin; it is not currently copied into the application image.

python scripts/preflight_live.py --line-code 35274 --stop-code 614432 --direction 2

Only allowlisted evidence is printed. Exit 0 means the checks passed, including
the honest no-usable-forecast branch when applicable; inspect forecast_available.
This does not test public HTTP, browser rendering, or future source availability.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sys
import time

# Settings parses environment values at import time. Even bootstrap errors must
# not print a traceback containing a malformed credential/configuration value.
BOOTSTRAP_OK = False
previous_logging_level = logging.root.manager.disable
logging.disable(logging.CRITICAL)
try:
    # Support repository execution and a file mounted in /tmp with cwd=/app.
    for candidate in (Path(__file__).resolve().parents[1], Path.cwd()):
        if (candidate / 'app' / 'engine.py').is_file():
            sys.path.insert(0, str(candidate))
            break
    from app.engine import Engine
    from app.settings import Settings
    from app.transit import observed_time, current_time
    BOOTSTRAP_OK = True
except Exception:
    pass
finally:
    logging.disable(previous_logging_level)

DOCUMENTAL = 'Previsão de chegada é garantia de horário?'
ARRIVAL = 'Qual a previsão de chegada neste ponto?'
LINE_FALLBACK = 'Consultar a linha 8000'
STATUSES = {'ok', 'not_found', 'clarification', 'unavailable'}
MODES = {'demo', 'live', 'documental'}


def iso(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def summarize(result):
    """Never copy answers, raw model output, tool bodies, settings or URLs."""
    meta = result.get('metadata') or {}
    tool = meta.get('tool_result') or {}
    sources = result.get('sources') or []
    ids = sorted({s['id'] for s in sources if isinstance(s, dict)
                  and isinstance(s.get('id'), str)
                  and re.fullmatch(r'(?:[DP]\d{2}|SPTRANS_QUERY)', s['id'])})
    return {
        'status': result.get('status') if result.get('status') in STATUSES else 'invalid',
        'mode': result.get('data_mode') if result.get('data_mode') in MODES else 'invalid',
        'source_ids': ids, 'updated_at': iso(result.get('updated_at')),
        'model_called': meta.get('model_called') is True,
        'model_json_valid': meta.get('model_json_valid') is True,
        'tool': meta.get('tool') if meta.get('tool') in {'lines', 'stops', 'arrivals'} else None,
        'tool_mode': tool.get('mode') if tool.get('mode') in MODES else None,
        'synthetic': tool.get('synthetic') if type(tool.get('synthetic')) is bool else None,
        'extractive_fallback': meta.get('guardrail') == 'extractive_fallback',
    }


def arrival_counts(result, line_code, stop_code, direction, max_age, checked_at):
    tool = result['metadata']['tool_result']
    data = tool['data']
    if not isinstance(data, dict) or 'p' not in data:
        raise ValueError('invalid_point_schema')
    point = data['p']
    if point is None:
        lines = []
    else:
        if not isinstance(point, dict) or type(point.get('cp')) is not int or point['cp'] != stop_code:
            raise ValueError('point_mismatch')
        lines = point.get('l')
        if not isinstance(lines, list):
            raise ValueError('invalid_lines_schema')
    queried = datetime.fromisoformat(iso(tool['queried_at']))
    observed = datetime.fromisoformat(iso(tool['observed_at']))
    if checked_at.utcoffset() is None:
        raise ValueError('invalid_current_clock')
    age = round((checked_at - observed).total_seconds(), 3)
    matched = [row for row in lines if row.get('cl') == line_code and row.get('sl') == direction]
    vehicles = [v for row in matched for v in row.get('vs', [])]
    usable = []
    for vehicle in vehicles:
        if not re.fullmatch(r'\d{2}:\d{2}', str(vehicle.get('t', ''))):
            continue
        predicted = observed_time(vehicle['t'], queried)
        # Match the production Engine's filtering, without persisting times or IDs.
        if round((predicted - queried).total_seconds() / 60) >= 0:
            usable.append(vehicle)
    telemetry_ages = []
    for vehicle in usable[:6]:
        stamp = iso(vehicle.get('ta'))
        if stamp:
            telemetry_ages.append(round((checked_at - datetime.fromisoformat(stamp)).total_seconds(), 3))
    return {
        'returned_lines': len(lines), 'matching_lines': len(matched),
        'matching_vehicles': len(vehicles), 'usable_forecasts': len(usable),
        'queried_at': iso(tool.get('queried_at')), 'received_at': iso(tool.get('received_at')),
        'freshness_checked_at': checked_at.isoformat(),
        'source_clock_age_seconds': age,
        'source_clock_fresh': -60 <= age <= max_age,
        'displayed_vehicle_timestamps_present': len(telemetry_ages) == min(len(usable), 6),
        'displayed_vehicle_timestamps_fresh': bool(usable)
        and len(telemetry_ages) == min(len(usable), 6)
        and all(-60 <= value <= max_age for value in telemetry_ages),
        'oldest_displayed_vehicle_age_seconds': max(telemetry_ages) if telemetry_ages else None,
    }


def inference_proven(item):
    return item['model_called'] and item['model_json_valid']


def live_proven(item):
    return item['mode'] == item['tool_mode'] == 'live' and item['synthetic'] is False


async def preflight(settings, line_code=35274, stop_code=614432, direction=2, engine=None, clock=None):
    # A separate process only: suppress HTTP library logs containing auth URLs.
    logging.disable(logging.CRITICAL)
    report = {
        'schema_version': 2, 'scope': 'direct_engine_preflight_not_public_http',
        'freshness_reference': 'current_clock_after_inference',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'line_code': line_code, 'stop_code': stop_code, 'direction': direction,
        'checks': [], 'passed': False, 'forecast_available': False,
        'live_tool_with_model_proven': False, 'status': 'failed',
    }
    revision = settings.revision
    report['app_revision'] = revision if re.fullmatch(r'[0-9a-f]{7,40}', revision) else 'unreported'
    if settings.mode != 'live' or not settings.token:
        report['failure'] = 'live_mode_and_credentials_required'
        return finish(report)
    clock = clock or getattr(engine, 'clock', current_time)
    engine = engine or Engine(settings, clock=clock)

    async def run_case(name, **kwargs):
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(engine.answer(configuration='agent', evaluation=True, **kwargs), 180)
            item = {'name': name, **summarize(result), 'seconds': round(time.perf_counter() - started, 3), 'passed': False}
            report['checks'].append(item)
            return result, item
        except Exception:
            item = {'name': name, 'seconds': round(time.perf_counter() - started, 3), 'passed': False, 'failure': 'execution_error'}
            report['checks'].append(item)
            return None, item

    documentary, doc = await run_case('documental', question=DOCUMENTAL)
    if documentary:
        answer = documentary.get('answer', '').casefold()
        doc['passed'] = doc['status'] == 'ok' and doc['mode'] == 'documental' and bool(doc['source_ids']) \
            and inference_proven(doc) and 'garant' in answer and any(word in answer for word in ('não', 'nao', 'sem garantia'))
    arrival, arrival_check = await run_case('arrival_live', question=ARRIVAL,
                                            line_code=line_code, stop_code=stop_code, direction=direction)
    if arrival:
        try:
            counts = arrival_counts(arrival, line_code, stop_code, direction, settings.max_age, clock())
            arrival_check.update(counts)
            base_ok = live_proven(arrival_check) and arrival_check['tool'] == 'arrivals' \
                and arrival_check['updated_at'] is not None and 'SPTRANS_QUERY' in arrival_check['source_ids'] \
                and counts['source_clock_fresh']
            if counts['usable_forecasts'] > 0:
                arrival_check['passed'] = base_ok and arrival_check['status'] == 'ok' \
                    and inference_proven(arrival_check) and counts['displayed_vehicle_timestamps_fresh']
                report['forecast_available'] = arrival_check['passed']
                report['live_tool_with_model_proven'] = arrival_check['passed']
            else:
                arrival_check['passed'] = base_ok and arrival_check['status'] == 'not_found' and not arrival_check['model_called']
                arrival_check['classification'] = 'no_usable_forecast_after_line_direction_time_filters'
        except Exception:
            arrival_check['failure'] = 'no_valid_fresh_transit_evidence'
    if arrival_check['passed'] and not report['forecast_available']:
        # Empty arrivals short-circuit before the LLM. Prove the integrated path
        # with a nonempty live line lookup, never pretending it is an arrival.
        lines, line_check = await run_case('line_live_fallback', question=LINE_FALLBACK)
        if lines:
            tool_data = (lines.get('metadata', {}).get('tool_result') or {}).get('data')
            line_check['returned_lines'] = len(tool_data) if isinstance(tool_data, list) else 0
            line_check['passed'] = live_proven(line_check) and line_check['tool'] == 'lines' \
                and line_check['status'] in {'ok', 'clarification'} and inference_proven(line_check) \
                and line_check['returned_lines'] > 0 and 'SPTRANS_QUERY' in line_check['source_ids']
            report['live_tool_with_model_proven'] = line_check['passed']
    report['passed'] = all(item['passed'] for item in report['checks']) and report['live_tool_with_model_proven']
    if report['passed']:
        report['status'] = 'passed_with_forecast' if report['forecast_available'] else 'passed_without_usable_forecast'
    return finish(report)


def finish(report):
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    return report


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid_arguments')


def main(argv=None):
    try:
        if not BOOTSTRAP_OK:
            raise ValueError('bootstrap_failed')
        parser = SafeParser(description=__doc__)
        parser.add_argument('--line-code', type=int, default=35274)
        parser.add_argument('--stop-code', type=int, default=614432)
        parser.add_argument('--direction', type=int, choices=[1, 2], default=2)
        parser.add_argument('--output', type=Path)
        args = parser.parse_args(argv)
        if not (0 < args.line_code <= 2147483647 and 0 < args.stop_code <= 2147483647):
            raise ValueError('invalid_codes')
        settings = Settings()
        report = asyncio.run(preflight(settings, args.line_code, args.stop_code, args.direction))
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if settings.token:
            serialized = serialized.replace(settings.token, '[REDACTED]')
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding='utf-8')
        print(serialized, end='')
        return 0 if report['passed'] else 1
    except Exception:
        print('{"passed":false,"status":"failed","failure":"configuration_or_execution_error"}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
