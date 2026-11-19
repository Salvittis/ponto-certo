#!/usr/bin/env python3
"""Collect sanitized public/Prometheus evidence; never inject faults or read tokens."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT/'observability/grafana/dashboards/ponto-certo.json'
WINDOW_SECONDS = 300
STEP_SECONDS = 15
API_VERSION = '2025-04-01'
METRIC_FIELDS = {
    'latency_p95_seconds': (5, 'A'),
    'traffic_requests_per_second': (6, 'A'),
    'error_rate_percent': (7, 'A'),
    'saturation_percent': (8, 'A'),
}
ALERT_NAMES = {'PontoCertoPublicReadyUnavailable', 'PontoCertoModelNotReady', 'PontoCertoMetricsUnavailable'}
# No env, logs, healthcheck output, mounts, command line or IP addresses are printed.
GUEST_SCRIPT = r'''#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from datetime import datetime,timezone
import json,re,subprocess
from pathlib import Path

def now():return datetime.now(timezone.utc).isoformat()

def run(args,timeout=30):
 p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
 if p.returncode:raise RuntimeError('container_read_failed')
 return p.stdout

def memory_bytes(value):
 match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(B|kB|KB|KiB|MB|MiB|GB|GiB|TB|TiB)',value.strip())
 if not match:raise ValueError('invalid_memory_unit')
 unit=match[2];units={'B':1,'kB':1000,'KB':1000,'KiB':1024,'MB':1000**2,'MiB':1024**2,'GB':1000**3,'GiB':1024**3,'TB':1000**4,'TiB':1024**4}
 return int(float(match[1])*units[unit])

result={'checked_at':now(),'scope':'public','services':[]}
result['host_memory']={'collection_status':'failed'}
try:
 mem=Path('/proc/meminfo').read_text()
 result['host_memory']={'checked_at':now(),'total_bytes':int(re.search(r'^MemTotal:\s+(\d+) kB$',mem,re.M)[1])*1024,
  'available_bytes':int(re.search(r'^MemAvailable:\s+(\d+) kB$',mem,re.M)[1])*1024,'collection_status':'collected'}
except Exception:pass
running={};selected={}
result['model_artifact']={'path':'/models/qwen.gguf','collection_status':'not_running'}
inspect_format=('{"Image":{{json .Image}},"Config":{"Image":{{json .Config.Image}},"User":{{json .Config.User}},'
 '"Labels":{"com.docker.compose.service":{{json (index .Config.Labels "com.docker.compose.service")}}}},'
 '"HostConfig":{"ReadonlyRootfs":{{json .HostConfig.ReadonlyRootfs}},"CapDrop":{{json .HostConfig.CapDrop}},'
 '"SecurityOpt":{{json .HostConfig.SecurityOpt}},"Memory":{{json .HostConfig.Memory}},"NanoCpus":{{json .HostConfig.NanoCpus}},'
 '"RestartPolicy":{"Name":{{json .HostConfig.RestartPolicy.Name}}}},'
 '"State":{"Running":{{json .State.Running}},"Paused":{{json .State.Paused}},"Status":{{json .State.Status}},'
 '"Health":{"Status":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}}}},'
 '"NetworkSettings":{"Ports":{{json .NetworkSettings.Ports}}}}')
try:
 ids=run(['docker','ps','-a','--filter','label=com.docker.compose.project=ponto-certo','--format','{{.ID}}']).split()
 for cid in ids[:10]:
  if not re.fullmatch('[0-9a-f]{12,64}',cid):continue
  obj=json.loads(run(['docker','inspect','--format',inspect_format,cid]))
  config=obj.get('Config',{});host=obj.get('HostConfig',{});state=obj.get('State',{})
  service=config.get('Labels',{}).get('com.docker.compose.service')
  if service not in ('app','llm','proxy'):continue
  if service in selected:raise RuntimeError('duplicate_service')
  selected[service]=cid
  uid=None
  if state.get('Running') and not state.get('Paused'):
   try:
    candidate=run(['docker','exec',cid,'id','-u']).strip()
    if candidate.isdigit():uid=int(candidate)
   except Exception:pass
  ports=[]
  for port,bindings in (obj.get('NetworkSettings',{}).get('Ports') or {}).items():
   for binding in bindings or []:
    # Only published port numbers and exposure class, never host IPs.
    host_ip=binding.get('HostIp','')
    exposure='loopback' if host_ip in ('127.0.0.1','::1') else 'all_interfaces' if host_ip in ('','0.0.0.0','::') else 'specific_interface'
    ports.append({'container_port':port,'host_port':binding.get('HostPort'),'exposure':exposure})
  item={'service':service,'image_id':obj.get('Image'),'image_ref':config.get('Image'),'configured_user':config.get('User'),
   'effective_uid':uid,'status':state.get('Status'),'health':state.get('Health',{}).get('Status'),'read_only':host.get('ReadonlyRootfs'),
   'cap_drop':host.get('CapDrop',[]),'security_opt':host.get('SecurityOpt',[]),'memory_limit_bytes':host.get('Memory'),'cpu_nanos':host.get('NanoCpus'),
   'restart_policy':host.get('RestartPolicy',{}).get('Name'),'published_ports':ports,'resources':{'collection_status':'not_running'}}
  result['services'].append(item)
  if state.get('Running') and not state.get('Paused'):
   running[cid]=item
   item['resources']={'collection_status':'failed'}
 # Sample resource use before hashing the model to avoid measuring the hash workload.
 if running:
  try:
   snapshot=run(['docker','stats','--no-stream','--format','{{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}',*running])
   for line in snapshot.splitlines():
    cid,cpu,memory=line.split('\t')
    if cid not in running or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?%',cpu):continue
    used,limit=memory.split('/')
    running[cid]['resources']={'checked_at':now(),'cpu_percent':float(cpu[:-1]),'memory_usage_bytes':memory_bytes(used),
     'memory_limit_bytes':memory_bytes(limit),'collection_status':'collected'}
  except Exception:pass
 llm=selected.get('llm')
 if llm in running:
  result['model_artifact']['collection_status']='failed'
  try:
   digest=run(['docker','exec',llm,'sha256sum','/models/qwen.gguf'],timeout=90).split()[0]
   size=run(['docker','exec',llm,'stat','--printf=%s','/models/qwen.gguf']).strip()
   if not re.fullmatch('[0-9a-f]{64}',digest) or not size.isdigit():raise ValueError('invalid_artifact')
   result['model_artifact'].update(sha256=digest,size_bytes=int(size),checked_at=now(),collection_status='collected')
  except Exception:pass
 result['collection_status']='collected'
except Exception:
 result['collection_status']='failed'
 result['error']='container_read_failed'
result['finished_at']=now()
encoded=json.dumps(result,separators=(',',':'),allow_nan=False)
# Managed Run Command retains only the last 4 KiB: fail explicitly instead of truncating JSON.
if len(encoded.encode())>3800:
 encoded=json.dumps({'collection_status':'failed','error':'guest_output_exceeds_budget','services':[]},separators=(',',':'))
print(encoded)
PY
'''


def utc(timestamp=None):
    return datetime.fromtimestamp(timestamp if timestamp is not None else time.time(), timezone.utc).isoformat()


def origin_url(value, local=False):
    try:
        url = urlsplit(value)
        host = url.hostname or ''
        if (url.username is not None or url.password is not None or '?' in value or '#' in value
                or url.path not in ('', '/') or any(character.isspace() for character in value)):
            raise ValueError
        if local:
            if url.scheme not in ('http', 'https') or host not in ('127.0.0.1', 'localhost', '::1'):
                raise ValueError
            port = url.port
            return url.scheme + '://' + ('['+host+']' if ':' in host else host) + (':'+str(port) if port else '')
        if url.scheme != 'https' or url.port not in (None, 443):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        if ('.' not in host or host.endswith(('.localhost', '.internal', '.local', '.invalid', '.test'))
                or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', item) for item in host.split('.'))):
            raise ValueError
        return 'https://' + host
    except ValueError:
        raise ValueError('Use a clean public HTTPS DNS origin and a loopback-only Prometheus URL') from None


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def http_json(url, params=None):
    if params:
        url += '?' + urlencode(params)
    request = Request(url, headers={'Accept': 'application/json'})
    started = time.monotonic()
    try:
        with build_opener(NoRedirects()).open(request, timeout=12) as response:
            code, raw = response.status, response.read(2_000_001)
    except HTTPError as failure:
        code, raw = failure.code, failure.read(2_000_001)
    except (URLError, OSError, TimeoutError):
        return {'http_status': None, 'error': 'connection_failed', 'seconds': round(time.monotonic()-started, 3)}, None
    metadata = {'http_status': code, 'seconds': round(time.monotonic()-started, 3)}
    if len(raw) > 2_000_000:
        return dict(metadata, error='response_too_large'), None
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return dict(metadata, error='response_not_json_object'), None
    return metadata, body


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def byte_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 2**63 else None


def technical_text(value, pattern, limit=160):
    return value if isinstance(value, str) and len(value) <= limit and re.fullmatch(pattern, value) else None


def clean_labels(labels, public_url):
    allowed = {
        'job': {'ponto-certo-api', 'ponto-certo-ready'}, 'application': {'ponto-certo'},
        'environment': {'public', 'local-check'}, 'severity': {'critical', 'warning'},
        'component': {'public-readiness', 'local-llm', 'monitoring'},
        'alertstate': {'pending', 'firing'}, 'method': {'GET', 'POST', 'HEAD', 'OPTIONS'},
        'outcome': {'ok', 'invalid_json', 'unavailable'},
        'status': {'ok', 'not_found', 'clarification', 'unavailable'},
        'route': {'/api/ask', '/healthz', '/readyz', '/metrics'},
    }
    result = {}
    for key, value in (labels if isinstance(labels, dict) else {}).items():
        if key in allowed and value in allowed[key]:
            result[key] = value
        elif key == 'status' and technical_text(value, r'[1-5][0-9]{2}'):
            result[key] = value
        elif key == 'instance' and value in {urlsplit(public_url).hostname, urlsplit(public_url).hostname+':443', public_url+'/readyz'}:
            result[key] = value
        elif key == 'alertname' and value in ALERT_NAMES:
            result[key] = value
    return result


def sample(pair):
    if not isinstance(pair, list) or len(pair) != 2:
        return None
    timestamp = finite(pair[0])
    if timestamp is None or not 0 < timestamp < 32_503_680_000:
        return None
    value = finite(pair[1])
    return {'timestamp': timestamp, 'timestamp_utc': utc(timestamp), 'value': value,
            'value_state': 'finite' if value is not None else 'non_finite_or_missing'}


def query(prometheus, expression, public_url, end, history=False):
    params = {'query': expression, 'timeout': '8s', 'limit': 100}
    if history:
        endpoint = '/api/v1/query_range'
        params.update(start=end-WINDOW_SECONDS, end=end, step=STEP_SECONDS)
    else:
        endpoint = '/api/v1/query'
        params['time'] = end
    metadata, body = http_json(prometheus+endpoint, params)
    result = dict(metadata, collection_status='failed', series=[])
    if metadata.get('http_status') != 200 or not body or body.get('status') != 'success':
        return result
    data = body.get('data', {})
    result_type = data.get('resultType')
    if result_type not in ('vector', 'matrix'):
        return dict(result, error='unexpected_result_type')
    result.update(collection_status='collected', result_type=result_type)
    for row in data.get('result', [])[:100]:
        pairs = row.get('values', []) if history else [row.get('value')]
        samples = [item for item in (sample(pair) for pair in pairs[:100]) if item is not None]
        result['series'].append({'labels': clean_labels(row.get('metric', {}), public_url), 'samples': samples})
    result['series_count'] = len(result['series'])
    result['finite_sample_count'] = sum(item['value'] is not None for row in result['series'] for item in row['samples'])
    return result


def scalar(result):
    series = result.get('series', [])
    return series[0]['samples'][0]['value'] if len(series) == 1 and len(series[0]['samples']) == 1 else None


def labels_match_public(labels, public_url):
    host = urlsplit(public_url).hostname
    expected = {'ponto-certo-api': {host, host+':443'}, 'ponto-certo-ready': {public_url+'/readyz'}}
    return labels.get('instance') in expected.get(labels.get('job'), set())


def historical_target_guard(prometheus, public_url, end):
    # Earliest historical rate sample is five minutes ago and itself looks back five minutes.
    expression = 'count by (job, instance) (count_over_time(up{job=~"ponto-certo-api|ponto-certo-ready"}[10m]))'
    result = query(prometheus, expression, public_url, end)
    rows = result['series']
    verified = (result['collection_status'] == 'collected' and len(rows) == 2
                and {row['labels'].get('job') for row in rows} == {'ponto-certo-api', 'ponto-certo-ready'}
                and all(labels_match_public(row['labels'], public_url) for row in rows))
    return {'expression': expression, 'lookback_seconds': 600, 'result': result,
            'only_requested_public_targets_observed': verified}


def public_checks(public_url):
    result = {}
    for path in ('/healthz', '/readyz', '/api/config', '/metrics'):
        metadata, body = http_json(public_url+path)
        row = dict(metadata, checked_at=utc())
        if body:
            for key in ('model_ready', 'data_ready', 'sptrans_live_verified'):
                if isinstance(body.get(key), bool):
                    row[key] = body[key]
            for key, pattern in [('revision', r'[0-9a-f]{40}'), ('version', r'[A-Za-z0-9_.-]+'),
                                 ('model', r'[A-Za-z0-9_./-]+'), ('status', r'(?:ok|ready|not_ready)'),
                                 ('mode', r'(?:demo|live)'), ('data_mode', r'(?:demo|live|documental)')]:
                value = technical_text(body.get(key), pattern)
                if value is not None:
                    row[key] = value
        result[path] = row
    result['metrics_without_token_denied'] = result['/metrics'].get('http_status') in (401, 403)
    return result


def targets(prometheus, public_url):
    metadata, body = http_json(prometheus+'/api/v1/targets', {'state': 'active'})
    rows, matches = [], []
    if body and body.get('status') == 'success':
        for target in body.get('data', {}).get('activeTargets', []):
            job = target.get('labels', {}).get('job')
            if job not in ('ponto-certo-api', 'ponto-certo-ready'):
                continue
            scrape = urlsplit(target.get('scrapeUrl', ''))
            candidate = parse_qs(scrape.query).get('target', [''])[0] if job == 'ponto-certo-ready' else target.get('scrapeUrl', '')
            expected = public_url + ('/metrics' if job == 'ponto-certo-api' else '/readyz')
            # This strict comparison avoids mixing extra targets into sum() dashboard queries.
            aligned = candidate == expected
            matches.append((job, aligned))
            rows.append({'job': job, 'target': expected if aligned else '[target differs from requested public URL]',
                         'matches_public_url': aligned, 'health': target.get('health') if target.get('health') in ('up', 'down', 'unknown') else None,
                         'last_scrape': technical_text(target.get('lastScrape'), r'[0-9TZ:+.\-]+'),
                         'last_scrape_duration_seconds': finite(target.get('lastScrapeDuration')),
                         'has_scrape_error': bool(target.get('lastError'))})
    aligned = sorted(matches) == [('ponto-certo-api', True), ('ponto-certo-ready', True)]
    return dict(metadata, targets=rows, single_public_target_per_job=aligned,
                collection_status='collected' if body and body.get('status') == 'success' else 'failed')


def alerts(prometheus, public_url):
    metadata, body = http_json(prometheus+'/api/v1/alerts')
    rows = []
    if body and body.get('status') == 'success':
        for alert in body.get('data', {}).get('alerts', []):
            raw_labels = alert.get('labels', {})
            if not labels_match_public(raw_labels, public_url):
                continue
            labels = clean_labels(raw_labels, public_url)
            if 'alertname' not in labels:
                continue
            rows.append({'labels': labels, 'state': alert.get('state') if alert.get('state') in ('pending', 'firing', 'inactive') else None,
                         'active_at': technical_text(alert.get('activeAt'), r'[0-9TZ:+.\-]+'), 'value': finite(alert.get('value'))})
    return dict(metadata, collection_status='collected' if body and body.get('status') == 'success' else 'failed', alerts=rows,
                firing_names=sorted({row['labels']['alertname'] for row in rows if row['state'] == 'firing'}))


def clean_containers(body, scope):
    rows = []
    for row in body.get('services', [])[:10]:
        service = row.get('service')
        if service not in ('app', 'llm', 'proxy'):
            continue
        uid = row.get('effective_uid')
        item = {'service': service, 'effective_uid': uid if isinstance(uid, int) and not isinstance(uid, bool) and uid >= 0 else None,
                'read_only': row.get('read_only') if isinstance(row.get('read_only'), bool) else None,
                'cap_drop': [value for value in row.get('cap_drop', []) if value == 'ALL'],
                'security_opt': [value for value in row.get('security_opt', []) if value in ('no-new-privileges:true', 'no-new-privileges')],
                'memory_limit_bytes': finite(row.get('memory_limit_bytes')), 'cpu_nanos': finite(row.get('cpu_nanos')),
                'published_ports': []}
        for key, pattern in [('image_id', r'sha256:[0-9a-f]{64}'), ('image_ref', r'(?:ghcr\.io/)?[a-z0-9_./:-]+(?:@sha256:[0-9a-f]{64})?'),
                             ('configured_user', r'[0-9]+(?::[0-9]+)?'), ('status', r'(?:running|created|exited|restarting|paused|dead|removing)'),
                             ('health', r'(?:healthy|unhealthy|starting)'), ('restart_policy', r'(?:no|always|unless-stopped|on-failure)')]:
            item[key] = technical_text(row.get(key), pattern)
        for port in row.get('published_ports', [])[:10]:
            if (technical_text(port.get('container_port'), r'[0-9]{1,5}/(?:tcp|udp)')
                    and technical_text(port.get('host_port'), r'[0-9]{1,5}')
                    and port.get('exposure') in ('loopback', 'all_interfaces', 'specific_interface')):
                item['published_ports'].append({key: port[key] for key in ('container_port', 'host_port', 'exposure')})
        stats = row.get('resources', {})
        stats = stats if isinstance(stats, dict) else {}
        cpu = finite(stats.get('cpu_percent'))
        item['resources'] = {
            'checked_at': technical_text(stats.get('checked_at'), r'[0-9TZ:+.\-]+'),
            'cpu_percent': cpu if cpu is not None and cpu >= 0 else None,
            'memory_usage_bytes': byte_count(stats.get('memory_usage_bytes')),
            'memory_limit_bytes': byte_count(stats.get('memory_limit_bytes')),
            'collection_status': stats.get('collection_status') if stats.get('collection_status') in ('collected', 'not_running') else 'failed',
        }
        if item['resources']['collection_status'] == 'collected' and any(item['resources'][key] is None for key in ('cpu_percent', 'memory_usage_bytes', 'memory_limit_bytes')):
            item['resources']['collection_status'] = 'failed'
        rows.append(item)
    complete = sorted(row['service'] for row in rows) == ['app', 'llm', 'proxy']
    non_root = complete and all(row['effective_uid'] is not None and row['effective_uid'] > 0 for row in rows)
    host = body.get('host_memory', {})
    host = host if isinstance(host, dict) else {}
    host_memory = {'checked_at': technical_text(host.get('checked_at'), r'[0-9TZ:+.\-]+'),
                   'total_bytes': byte_count(host.get('total_bytes')), 'available_bytes': byte_count(host.get('available_bytes'))}
    host_complete = (host.get('collection_status') == 'collected' and host_memory['total_bytes'] is not None
                     and host_memory['available_bytes'] is not None and 0 <= host_memory['available_bytes'] <= host_memory['total_bytes'] and host_memory['total_bytes'] > 0)
    host_memory['collection_status'] = 'collected' if host_complete else 'failed'
    weights = body.get('model_artifact', {})
    weights = weights if isinstance(weights, dict) else {}
    model_artifact = {'path': '/models/qwen.gguf', 'sha256': technical_text(weights.get('sha256'), r'[0-9a-f]{64}'),
                      'size_bytes': byte_count(weights.get('size_bytes')), 'checked_at': technical_text(weights.get('checked_at'), r'[0-9TZ:+.\-]+')}
    model_complete = (weights.get('path') == model_artifact['path'] and weights.get('collection_status') == 'collected'
                      and model_artifact['sha256'] is not None and model_artifact['size_bytes'] is not None and model_artifact['size_bytes'] > 0)
    model_artifact['collection_status'] = 'collected' if model_complete else 'not_running' if weights.get('collection_status') == 'not_running' else 'failed'
    resource_complete = complete and host_complete and all(row['resources']['collection_status'] == 'collected' for row in rows)
    status = ('collected' if resource_complete and model_complete else 'partial') if body.get('collection_status') == 'collected' else 'failed'
    return {'scope': scope, 'checked_at': technical_text(body.get('checked_at'), r'[0-9TZ:+.\-]+'),
            'finished_at': technical_text(body.get('finished_at'), r'[0-9TZ:+.\-]+'), 'collection_status': status,
            'services': rows, 'all_three_services_observed': complete, 'all_effective_uids_non_root': non_root,
            'all_running': complete and all(row['status'] == 'running' for row in rows),
            'host_memory': host_memory, 'model_artifact': model_artifact, 'resource_snapshot_complete': resource_complete,
            'resource_notes': ['Point-in-time snapshot; services and host are sampled sequentially, not a load benchmark.',
                               'Host memory comes from /proc/meminfo. MemAvailable is the kernel estimate, not merely MemFree.',
                               'docker stats --no-stream CPU percent can exceed 100% across cores. Memory is CLI usage minus inactive cache on Linux; displayed units are rounded before conversion to bytes.',
                               'Resource sampling precedes SHA-256 hashing. Compare a post-restart hash/size with the pinned build artifact; this collector never performs the restart.']}


def azure(*args):
    result = subprocess.run(['az', *args, '--only-show-errors', '--output', 'json'], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError('azure_read_operation_failed')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def azure_containers(group, vm):
    target = azure('vm', 'show', '--resource-group', group, '--name', vm)
    if target.get('tags', {}).get('project') != 'ponto-certo':
        raise RuntimeError('vm_project_tag_mismatch')
    name = 'evidence-' + uuid.uuid4().hex[:12]
    endpoint = 'https://management.azure.com'+target['id']+'/runCommands/'+name+'?api-version='+API_VERSION
    payload = {'location': target['location'], 'properties': {'source': {'script': GUEST_SCRIPT},
               'asyncExecution': True, 'timeoutInSeconds': 180, 'treatFailureAsDeploymentFailure': True}}
    with tempfile.TemporaryDirectory(prefix='ponto-certo-evidence-') as directory:
        request = Path(directory)/'request.json'
        request.write_text(json.dumps(payload)); request.chmod(0o600)
        azure('rest', '--method', 'put', '--url', endpoint, '--body', '@'+str(request))
    deadline = time.monotonic()+240
    while time.monotonic() < deadline:
        result = azure('rest', '--method', 'get', '--url', endpoint+'&$expand=instanceView')
        view = result.get('properties', {}).get('instanceView', {})
        if view.get('executionState') == 'Succeeded' and view.get('exitCode') == 0:
            body = json.loads(view.get('output') or '{}')
            return dict(clean_containers(body, 'public'), run_command=name)
        if view.get('executionState') in ('Failed', 'Canceled', 'TimedOut'):
            raise RuntimeError('guest_container_read_failed')
        time.sleep(5)
    raise RuntimeError('guest_container_read_timeout')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--prometheus-url', default='http://127.0.0.1:9090')
    parser.add_argument('--expect-revision', help='Optional full deployed Git SHA, never a branch name')
    parser.add_argument('--output', type=Path, help='Defaults to a timestamped JSON in evidencias/cloud/')
    parser.add_argument('--azure-resource-group', help='Opt in to read-only guest container inspection through Managed Run Command')
    parser.add_argument('--azure-vm', help='Must be supplied together with --azure-resource-group')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        public_url = origin_url(args.public_url)
        prometheus = origin_url(args.prometheus_url, local=True)
    except ValueError as error:
        parser.error(str(error))
    if args.expect_revision and not re.fullmatch(r'[0-9a-f]{40}', args.expect_revision):
        parser.error('--expect-revision must be a complete lowercase Git SHA')
    if bool(args.azure_resource_group) != bool(args.azure_vm):
        parser.error('Supply both Azure resource group and VM, or neither')
    end = time.time()
    output = args.output or ROOT/'evidencias/cloud'/('observability-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    if output.exists() and not args.overwrite:
        parser.error('Output already exists; choose another path or use --overwrite explicitly')
    dashboard = json.loads(DASHBOARD.read_text())
    report = {'schema_version': 1, 'checked_at': utc(end), 'scope': 'public', 'public_url': public_url,
              'prometheus_url': prometheus, 'window': {'start': utc(end-WINDOW_SECONDS), 'end': utc(end), 'seconds': WINDOW_SECONDS, 'step_seconds': STEP_SECONDS,
              'meaning': 'Instant evaluation at end; history samples over last 5 min. Each rate/p95 sample uses its trailing 5 min. Saturation is instantaneous.'},
              'dashboard_sha256': hashlib.sha256(DASHBOARD.read_bytes()).hexdigest(),
              'privacy': 'No token is read or sent. No questions, answers, arbitrary labels, Env, logs or raw Azure output are stored.',
              'public_checks': public_checks(public_url), 'targets': targets(prometheus, public_url),
              'alerts': alerts(prometheus, public_url), 'queries': [],
              'limitations': ['This collector does not generate traffic, inject faults, restart services or prove real inference.',
                              'Current healthy state does not alone prove recovery; compare the firing capture and run the public smoke.',
                              'Saturation samples every 15 s may miss short peaks; it measures LLM slots, not CPU.']}
    instant_by_ref = {}
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            expression = target['expr']
            instant = query(prometheus, expression, public_url, end)
            history = query(prometheus, expression, public_url, end, history=True)
            instant_by_ref[(panel['id'], target['refId'])] = instant
            report['queries'].append({'panel_id': panel['id'], 'panel_title': panel['title'], 'ref_id': target['refId'],
                                      'expression': expression, 'unit': panel.get('fieldConfig', {}).get('defaults', {}).get('unit'),
                                      'instant': instant, 'history': history})
    api_instance = json.dumps(re.escape(urlsplit(public_url).hostname)+'(:443)?')
    ready_instance = json.dumps(public_url+'/readyz')
    alert_expression = ('ALERTS{alertname=~"PontoCerto.*",job="ponto-certo-api",instance=~'+api_instance+'} or '
                        'ALERTS{alertname=~"PontoCerto.*",job="ponto-certo-ready",instance='+ready_instance+'}')
    report['alert_history'] = dict(query(prometheus, alert_expression, public_url, end, history=True), expression=alert_expression)
    report['historical_target_guard'] = historical_target_guard(prometheus, public_url, end)
    aligned = (report['targets']['single_public_target_per_job']
               and report['historical_target_guard']['only_requested_public_targets_observed'])
    report['scope'] = 'public' if aligned else 'configuration'
    report['metrics'] = {'scope': 'public' if aligned else 'configuration', 'target': public_url,
                         'window': '5m ending '+utc(end)+'; saturation sampled at window end',
                         **{name: scalar(instant_by_ref.get(reference, {})) if aligned else None for name, reference in METRIC_FIELDS.items()}}
    report['metrics_complete'] = aligned and all(report['metrics'][name] is not None for name in METRIC_FIELDS)
    report['revision'] = report['public_checks']['/healthz'].get('revision')
    report['revision_matches_expected'] = report['revision'] == args.expect_revision if args.expect_revision else None
    report['container_checks'] = {'scope': 'public', 'collection_status': 'not_requested', 'services': []}
    if args.azure_vm:
        try:
            report['container_checks'] = azure_containers(args.azure_resource_group, args.azure_vm)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            report['container_checks'] = {'scope': 'public', 'collection_status': 'failed', 'error': 'azure_container_read_failed', 'services': []}
    report['finished_at'] = utc()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output': str(output), 'metrics_complete': report['metrics_complete'], 'targets_match_public_url': aligned,
                      'firing_alerts': report['alerts']['firing_names'], 'container_collection': report['container_checks']['collection_status'],
                      'revision_matches_expected': report['revision_matches_expected']}))
    # An unhealthy service during a planned alert is valid evidence, not a collector error.
    collected = aligned and report['alerts']['collection_status'] == 'collected'
    collected = collected and all(row[kind]['collection_status'] == 'collected'
                                  for row in report['queries'] for kind in ('instant', 'history'))
    collected = collected and report['alert_history']['collection_status'] == 'collected'
    if args.expect_revision:
        collected = collected and report['revision_matches_expected']
    if args.azure_vm:
        collected = collected and report['container_checks']['collection_status'] == 'collected'
    return 0 if collected else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('Evidence collection failed; no raw response or credential was printed.', file=sys.stderr)
        sys.exit(2)
