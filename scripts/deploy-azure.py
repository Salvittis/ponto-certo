#!/usr/bin/env python3
"""Publish approved digests via OIDC and Managed RunCommand protected parameters."""
import base64
from datetime import datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
API_VERSION = '2025-04-01'


def required(name):
    value = os.environ.get(name, '')
    if not value:
        raise RuntimeError(f'Missing required configuration: {name}')
    return value


def az(*args):
    result = subprocess.run(['az', *args, '--only-show-errors', '--output', 'json'],
                            capture_output=True, text=True, timeout=300)
    if result.returncode:
        # CLI errors may echo a request body. No credential-bearing diagnostics in CI.
        raise RuntimeError('Azure command failed; inspect the selected VM operation in Azure')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    group, vm = required('AZURE_RESOURCE_GROUP'), required('AZURE_VM_NAME')
    revision = required('APP_REVISION')
    public_url = required('PUBLIC_URL').rstrip('/')
    origin = urlsplit(public_url)
    if origin.scheme != 'https' or not origin.hostname or origin.username or origin.query or origin.path:
        raise RuntimeError('PUBLIC_URL must be a clean HTTPS origin')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('APP_REVISION must be a full Git SHA')
    release = {key: required(key) for key in ('IMAGE_REF', 'LLM_IMAGE_REF')}
    for image in release.values():
        if not re.fullmatch(r'ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}', image):
            raise RuntimeError('Only previously scanned image digests can be deployed')
    mode = os.environ.get('DATA_MODE', 'demo')
    if mode not in ('demo', 'live'):
        raise RuntimeError('Invalid DATA_MODE')
    metrics = required('METRICS_TOKEN')
    sptrans = os.environ.get('SPTRANS_TOKEN', '')
    if mode == 'live' and not sptrans:
        raise RuntimeError('Live mode requires SPTRANS_TOKEN')
    release.update(APP_REVISION=revision, PUBLIC_HOST=origin.hostname, DATA_MODE=mode,
                   files={'compose.production.yaml': (ROOT/'compose.production.yaml').read_text(),
                          'Caddyfile': (ROOT/'deploy/Caddyfile').read_text()})
    target = az('vm', 'show', '--resource-group', group, '--name', vm)
    if target.get('tags', {}).get('project') != 'ponto-certo':
        raise RuntimeError('Refusing to deploy outside the tagged academic VM')
    command_name = 'deploy-' + revision[:12] + '-' + str(int(time.time()))
    endpoint = 'https://management.azure.com' + target['id'] + '/runCommands/' + command_name
    payload = {'location': target['location'], 'properties': {
        'source': {'script': (ROOT/'deploy/release.sh').read_text()},
        'asyncExecution': True, 'timeoutInSeconds': 900,
        'treatFailureAsDeploymentFailure': True,
        'parameters': [{'name': 'PC_RELEASE_B64', 'value': base64.b64encode(json.dumps(release).encode()).decode()}],
        'protectedParameters': [{'name': 'METRICS_TOKEN', 'value': metrics},
                                {'name': 'SPTRANS_TOKEN', 'value': sptrans}],
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
            print('Managed RunCommand:', state, flush=True); last = state
        if view.get('executionState') == 'Succeeded':
            if view.get('exitCode') != 0:
                raise RuntimeError('Release script did not report exit code zero')
            break
        if state in ('Failed', 'Canceled', 'TimedOut'):
            raise RuntimeError('Release failed; previous release recovery attempted on VM')
        time.sleep(10)
    else:
        raise RuntimeError('Timed out waiting for deployment')
    # Read through public DNS/TLS, without exposing a private evaluator localhost.
    deadline = time.monotonic() + 180
    health = None
    while time.monotonic() < deadline:
        try:
            with urlopen(public_url+'/healthz', timeout=10) as response:
                health = json.load(response)
            with urlopen(public_url+'/readyz', timeout=10) as response:
                ready = json.load(response)
            if health.get('revision') == revision and ready.get('model_ready') is True:
                break
        except (OSError, ValueError):
            pass
        time.sleep(5)
    else:
        raise RuntimeError('Public HTTPS readiness/revision verification failed')
    subprocess.run([sys.executable, str(ROOT/'scripts/smoke.py'), '--base-url', public_url,
                    '--expect-mode', mode, '--output', 'reports/smoke-public.json'], check=True)
    evidence = {'checked_at': datetime.now(timezone.utc).isoformat(), 'commit': revision,
                'url': public_url, 'images': {k:release[k] for k in ('IMAGE_REF','LLM_IMAGE_REF')},
                'run_command': command_name, 'health': health, 'data_mode': mode,
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
