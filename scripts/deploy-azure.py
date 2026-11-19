#!/usr/bin/env python3
"""Publish approved digests via OIDC and Managed RunCommand protected parameters."""
import base64
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
API_VERSION = '2025-04-01'
IMAGE_KEYS = ('IMAGE_REF', 'LLM_IMAGE_REF', 'PROXY_IMAGE_REF')


def required(name):
    value = os.environ.get(name, '')
    if not value:
        raise RuntimeError(f'Missing required configuration: {name}')
    return value


def public_origin(value):
    """Accept an HTTPS DNS origin, never evaluator localhost or URL credentials."""
    try:
        origin = urlsplit(value)
        host = origin.hostname or ''
        invalid = (value != value.strip() or origin.scheme != 'https'
                   or origin.username is not None or origin.password is not None
                   or '?' in value or '#' in value or origin.path not in ('', '/')
                   or origin.port not in (None, 443) or len(host) > 253)
        if invalid:
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        labels = host.split('.')
        if (len(labels) < 2 or host.endswith(('.localhost', '.local', '.internal', '.invalid', '.test'))
                or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)):
            raise ValueError
    except ValueError:
        raise RuntimeError('PUBLIC_URL must be a public DNS HTTPS origin without credentials, path, query or fragment') from None
    return 'https://' + host


def az(*args):
    result = subprocess.run(['az', *args, '--only-show-errors', '--output', 'json'],
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        # CLI errors may echo a request body. No credential-bearing diagnostics in CI.
        raise RuntimeError('Azure command failed; inspect the selected VM operation in Azure')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def managed_command(target, action, revision, release=None, secrets=None, registry_username=None):
    command_name = action + '-' + revision[:12] + '-' + uuid.uuid4().hex[:8]
    endpoint = 'https://management.azure.com' + target['id'] + '/runCommands/' + command_name
    parameters = [{'name': 'PC_ACTION', 'value': action},
                  {'name': 'PC_EXPECTED_REVISION', 'value': revision}]
    if registry_username is not None:
        parameters.append({'name': 'REGISTRY_USERNAME', 'value': registry_username})
    if release is not None:
        parameters.append({'name': 'PC_RELEASE_B64', 'value': base64.b64encode(json.dumps(release).encode()).decode()})
    payload = {'location': target['location'], 'properties': {
        'source': {'script': (ROOT/'deploy/release.sh').read_text()},
        'asyncExecution': True, 'timeoutInSeconds': 900,
        'treatFailureAsDeploymentFailure': True,
        'parameters': parameters,
        'protectedParameters': [{'name': key, 'value': value} for key, value in (secrets or {}).items()],
    }}
    with tempfile.TemporaryDirectory(prefix='ponto-certo-deploy-') as directory:
        request = Path(directory)/'request.json'
        request.write_text(json.dumps(payload)); request.chmod(0o600)
        az('rest', '--method', 'put', '--url', endpoint+'?api-version='+API_VERSION,
           '--body', '@'+str(request))
    deadline = time.monotonic() + 1000
    last = None
    while time.monotonic() < deadline:
        result = az('rest', '--method', 'get', '--url', endpoint+'?api-version='+API_VERSION+'&$expand=instanceView')
        properties = result.get('properties', {})
        view = properties.get('instanceView', {})
        state = view.get('executionState', properties.get('provisioningState'))
        if state != last:
            print('Managed RunCommand', action + ':', state, flush=True); last = state
        if view.get('executionState') == 'Succeeded':
            if view.get('exitCode') != 0:
                raise RuntimeError('Release operation did not report exit code zero')
            recovery = None
            # Only allow fixed markers from guest output into evidence; never echo logs.
            for marker in ('previous_restored', 'first_release_stopped'):
                if 'PC_RECOVERY_RESULT=' + marker in (view.get('output') or ''):
                    recovery = marker
            return {'name': command_name, 'recovery': recovery}
        if state in ('Failed', 'Canceled', 'TimedOut'):
            raise RuntimeError('Managed release operation failed; inspect its bounded status in Azure')
        time.sleep(10)
    raise RuntimeError('Timed out waiting for deployment')


def verify_public(public_url, revision):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            with urlopen(public_url+'/healthz', timeout=10) as response:
                health = json.load(response)
            with urlopen(public_url+'/readyz', timeout=10) as response:
                ready = json.load(response)
            if (isinstance(health, dict) and isinstance(ready, dict)
                    and health.get('revision') == revision and ready.get('model_ready') is True):
                return health
        except (OSError, ValueError):
            pass
        time.sleep(5)
    raise RuntimeError('Public HTTPS readiness/revision verification failed')


def main():
    group, vm = required('AZURE_RESOURCE_GROUP'), required('AZURE_VM_NAME')
    revision = required('APP_REVISION')
    public_url = public_origin(required('PUBLIC_URL'))
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('APP_REVISION must be a full Git SHA')
    repository = os.environ.get('GITHUB_REPOSITORY', 'Salvittis/ponto-certo').lower()
    if not re.fullmatch(r'[a-z0-9_.-]+/[a-z0-9_.-]+', repository):
        raise RuntimeError('Invalid GITHUB_REPOSITORY')
    release = {key: required(key) for key in IMAGE_KEYS}
    for key, suffix in zip(IMAGE_KEYS, ('', '-llm', '-proxy')):
        expected = 'ghcr.io/' + repository + suffix + '@sha256:'
        if not re.fullmatch(re.escape(expected) + r'[a-f0-9]{64}', release[key]):
            raise RuntimeError('Only approved image digests from this repository can be deployed')
    mode = os.environ.get('DATA_MODE', 'demo')
    if mode not in ('demo', 'live'):
        raise RuntimeError('Invalid DATA_MODE')
    registry_username = required('REGISTRY_USERNAME')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*(?:\[bot\])?', registry_username):
        raise RuntimeError('Invalid REGISTRY_USERNAME')
    secrets = {'METRICS_TOKEN': required('METRICS_TOKEN'), 'SPTRANS_TOKEN': os.environ.get('SPTRANS_TOKEN', ''),
               'REGISTRY_TOKEN': required('REGISTRY_TOKEN')}
    if mode == 'live' and not secrets['SPTRANS_TOKEN']:
        raise RuntimeError('Live mode requires SPTRANS_TOKEN')
    if any(any(character in value for character in '\r\n\x00') for value in secrets.values()):
        raise RuntimeError('Runtime credentials must not contain CR, LF or NUL')
    release.update(APP_REVISION=revision, PUBLIC_HOST=urlsplit(public_url).hostname, DATA_MODE=mode,
                   files={'compose.production.yaml': (ROOT/'compose.production.yaml').read_text(),
                          'Caddyfile': (ROOT/'deploy/Caddyfile').read_text()})
    target = az('vm', 'show', '--resource-group', group, '--name', vm)
    if target.get('tags', {}).get('project') != 'ponto-certo':
        raise RuntimeError('Refusing to deploy outside the tagged academic VM')
    command = managed_command(target, 'deploy', revision, release, secrets, registry_username)
    try:
        health = verify_public(public_url, revision)
        subprocess.run([sys.executable, str(ROOT/'scripts/smoke.py'), '--base-url', public_url,
                        '--expect-mode', mode, '--timeout', '120', '--ready-timeout', '30',
                        '--output', 'reports/smoke-public.json'], check=True, timeout=420)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
        failure = {'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': revision,
                   'url': public_url, 'result': 'public_validation_failed', 'run_command': command['name']}
        try:
            recovery = managed_command(target, 'rollback', revision)
            failure['recovery_command'] = recovery['name']
            failure['recovery_result'] = recovery['recovery'] or 'unconfirmed'
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            failure['recovery_result'] = 'failed_or_unconfirmed'
        Path('reports').mkdir(exist_ok=True)
        Path('reports/deployment-failure.json').write_text(json.dumps(failure, indent=2)+'\n')
        print(json.dumps(failure, indent=2))
        raise RuntimeError('Public validation failed; automatic recovery: ' + failure['recovery_result']) from None
    evidence = {'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': revision,
                'url': public_url, 'images': {key: release[key] for key in IMAGE_KEYS},
                'run_command': command['name'], 'health': health, 'data_mode': mode,
                'result': 'public_model_verified'}
    Path('reports').mkdir(exist_ok=True)
    Path('reports/deployment.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError) as error:
        print('Deploy failed:', str(error), file=sys.stderr)
        sys.exit(1)
