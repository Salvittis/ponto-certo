"""Offline release-boundary checks: no Azure network or real credential is used."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
ORIGIN = 'https://ponto-certo-fixture.eastus2.cloudapp.azure.com'
IMAGES = {
    'IMAGE_REF': 'ghcr.io/salvittis/ponto-certo@sha256:' + '1' * 64,
    'LLM_IMAGE_REF': 'ghcr.io/salvittis/ponto-certo-llm@sha256:' + '2' * 64,
    'PROXY_IMAGE_REF': 'ghcr.io/salvittis/ponto-certo-proxy@sha256:' + '3' * 64,
}


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('deploy_azure_tested', ROOT/'scripts/deploy-azure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = {'AZURE_RESOURCE_GROUP': 'ponto-certo-fixture-rg', 'AZURE_VM_NAME': 'ponto-certo-fixture-vm',
           'APP_REVISION': REVISION, 'PUBLIC_URL': ORIGIN, 'GITHUB_REPOSITORY': 'Salvittis/ponto-certo',
           'DATA_MODE': 'live', 'METRICS_TOKEN': 'test_metrics', 'SPTRANS_TOKEN': 'test_sptrans',
           'REGISTRY_TOKEN': 'test_registry', 'REGISTRY_USERNAME': 'Salvittis', **IMAGES}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    state = SimpleNamespace(module=module, env=env, puts=[], calls=[], paths=[], smoke=[],
                            project_tag='ponto-certo', public_failure=False, smoke_failure=False,
                            run_state='Succeeded', recovery='previous_restored', clock=0)

    def fake_az(*args):
        state.calls.append(args)
        if args[:2] == ('vm', 'show'):
            return {'id': '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/ponto-certo-fixture-rg/providers/Microsoft.Compute/virtualMachines/ponto-certo-fixture-vm',
                    'location': 'eastus2', 'tags': {'project': state.project_tag}}
        if args[:3] == ('rest', '--method', 'put'):
            path = Path(args[args.index('--body')+1][1:])
            assert path.stat().st_mode & 0o777 == 0o600
            state.paths.append(path)
            state.puts.append(json.loads(path.read_text()))
            return {'properties': {'provisioningState': 'Creating'}}
        if args[:3] == ('rest', '--method', 'get'):
            action = dict((p['name'], p['value']) for p in state.puts[-1]['properties']['parameters'])['PC_ACTION']
            output = 'PC_RECOVERY_RESULT=' + state.recovery if action == 'rollback' else ''
            return {'properties': {'instanceView': {'executionState': state.run_state, 'exitCode': 0, 'output': output}}}
        raise AssertionError('Unexpected Azure call: ' + str(args))

    def fake_open(url, **kwargs):
        if state.public_failure:
            raise OSError('synthetic public failure')
        if url.endswith('/healthz'):
            data = {'status': 'ok', 'revision': REVISION}
        elif url.endswith('/readyz'):
            data = {'model_ready': True}
        else:
            raise AssertionError('Unexpected public endpoint')
        return io.BytesIO(json.dumps(data).encode())

    def fake_smoke(args, **kwargs):
        state.smoke.append(args)
        if state.smoke_failure:
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0)

    def clock():
        state.clock += 10
        return state.clock

    monkeypatch.setattr(module, 'az', fake_az)
    monkeypatch.setattr(module, 'urlopen', fake_open)
    monkeypatch.setattr(module.subprocess, 'run', fake_smoke)
    monkeypatch.setattr(module.time, 'monotonic', clock)
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    return state


def test_release_secrets_only_use_protected_parameters(cloud, capsys):
    cloud.module.main()
    payload = cloud.puts[0]['properties']
    protected = {p['name']: p['value'] for p in payload['protectedParameters']}
    assert protected == {'METRICS_TOKEN': 'test_metrics', 'SPTRANS_TOKEN': 'test_sptrans', 'REGISTRY_TOKEN': 'test_registry'}
    public = {p['name']: p['value'] for p in payload['parameters']}
    assert public['REGISTRY_USERNAME'] == 'Salvittis'
    release = json.loads(base64.b64decode(public['PC_RELEASE_B64']))
    visible = json.dumps({'script': payload['source']['script'], 'parameters': public, 'decoded_release': release})
    output = capsys.readouterr()
    evidence = Path('reports/deployment.json').read_text()
    for secret in protected.values():
        assert secret not in visible
        assert secret not in output.out + output.err + evidence
    assert {key: release[key] for key in IMAGES} == IMAGES
    assert all(not path.exists() for path in cloud.paths)
    assert json.loads(evidence)['images'] == IMAGES
    assert len(cloud.smoke) == 1


@pytest.mark.parametrize('url', [
    'http://ponto-certo-fixture.eastus2.cloudapp.azure.com',
    ORIGIN + '/api', ORIGIN + '?token=synthetic', ORIGIN + '#fragment',
    'https://user:synthetic@ponto-certo-fixture.eastus2.cloudapp.azure.com',
    'https://:synthetic@ponto-certo-fixture.eastus2.cloudapp.azure.com',
    'https://localhost', 'https://127.0.0.1', 'https://[::1]', ORIGIN + ':8443',
    'https://service.internal',
])
def test_rejects_nonpublic_or_nonorigin_urls_before_azure(cloud, monkeypatch, url):
    monkeypatch.setenv('PUBLIC_URL', url)
    with pytest.raises(RuntimeError, match='PUBLIC_URL'):
        cloud.module.main()
    assert cloud.calls == []


@pytest.mark.parametrize('revision', ['main', 'a' * 39, 'a' * 40 + '\n', 'G' * 40])
def test_rejects_noncommit_revision_before_azure(cloud, monkeypatch, revision):
    monkeypatch.setenv('APP_REVISION', revision)
    with pytest.raises(RuntimeError, match='APP_REVISION'):
        cloud.module.main()
    assert cloud.calls == []


@pytest.mark.parametrize('key,value', [
    ('IMAGE_REF', 'ghcr.io/salvittis/ponto-certo:latest'),
    ('LLM_IMAGE_REF', 'ghcr.io/salvittis/ponto-certo-llm@sha256:' + 'a' * 63),
    ('PROXY_IMAGE_REF', 'docker.io/library/caddy@sha256:' + 'a' * 64),
    ('IMAGE_REF', 'ghcr.io/another-owner/another-app@sha256:' + 'a' * 64),
    ('LLM_IMAGE_REF', IMAGES['IMAGE_REF']),
])
def test_only_repository_component_digests_reach_azure(cloud, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match='image digests'):
        cloud.module.main()
    assert cloud.calls == []


def test_proxy_digest_is_required(cloud, monkeypatch):
    monkeypatch.delenv('PROXY_IMAGE_REF')
    with pytest.raises(RuntimeError, match='PROXY_IMAGE_REF'):
        cloud.module.main()
    assert cloud.calls == []


def test_private_registry_requires_short_lived_token(cloud, monkeypatch):
    monkeypatch.delenv('REGISTRY_TOKEN')
    with pytest.raises(RuntimeError, match='REGISTRY_TOKEN'):
        cloud.module.main()
    assert cloud.calls == []


def test_refuses_vm_outside_project_without_mutation(cloud):
    cloud.project_tag = 'another-project'
    with pytest.raises(RuntimeError, match='tagged academic VM'):
        cloud.module.main()
    assert cloud.puts == []


@pytest.mark.parametrize('key,value', [('METRICS_TOKEN', 'synthetic\nextra'), ('SPTRANS_TOKEN', 'synthetic\rextra')])
def test_multiline_credentials_are_rejected_before_azure(cloud, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match='CR, LF or NUL'):
        cloud.module.main()
    assert cloud.calls == []


def test_live_requires_source_credential_before_azure(cloud, monkeypatch):
    monkeypatch.delenv('SPTRANS_TOKEN')
    with pytest.raises(RuntimeError, match='Live mode requires'):
        cloud.module.main()
    assert cloud.calls == []


@pytest.mark.parametrize('failure', ['public_failure', 'smoke_failure'])
@pytest.mark.parametrize('recovery', ['previous_restored', 'first_release_stopped'])
def test_public_validation_failure_requests_revision_guarded_recovery(cloud, failure, recovery):
    setattr(cloud, failure, True)
    cloud.recovery = recovery
    with pytest.raises(RuntimeError, match='Public validation failed; automatic recovery: ' + recovery):
        cloud.module.main()
    assert len(cloud.puts) == 2
    payload = cloud.puts[-1]['properties']
    public = {p['name']: p['value'] for p in payload['parameters']}
    assert public == {'PC_ACTION': 'rollback', 'PC_EXPECTED_REVISION': REVISION}
    assert payload['protectedParameters'] == []
    assert not Path('reports/deployment.json').exists()
    assert json.loads(Path('reports/deployment-failure.json').read_text())['recovery_result'] == recovery


def test_azure_errors_do_not_echo_credential_bearing_stderr(monkeypatch):
    spec = importlib.util.spec_from_file_location('deploy_azure_error_test', ROOT/'scripts/deploy-azure.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, 'run', lambda *args, **kwargs:
                        subprocess.CompletedProcess(args, 1, '', 'synthetic credential test_metrics test_sptrans'))
    with pytest.raises(RuntimeError) as failure:
        module.az('rest', '--method', 'put', '--body', '@/private/request.json')
    assert 'test_metrics' not in str(failure.value)
    assert 'test_sptrans' not in str(failure.value)


def test_guest_runtime_credentials_round_trip_raw_compose_env(tmp_path):
    """Exercises the real guest renderer and Compose parser without starting containers."""
    if not shutil.which('docker'):
        pytest.skip('Docker Compose is needed for this offline serialization check')
    source = (ROOT/'deploy/release.sh').read_text()
    blocks = source.split("python3 - <<'PY'\n")
    renderer = next(block.split('\nPY\n', 1)[0] for block in blocks[1:] if "payload=json.loads" in block)
    renderer_file = tmp_path/'render-release.py'
    renderer_file.write_text(renderer)
    payload = {**IMAGES, 'APP_REVISION': REVISION, 'PUBLIC_HOST': 'ponto-certo-fixture.eastus2.cloudapp.azure.com', 'DATA_MODE': 'live',
               'files': {'compose.production.yaml': (ROOT/'compose.production.yaml').read_text(),
                         'Caddyfile': (ROOT/'deploy/Caddyfile').read_text()}}
    metric = "synthetic\\path'quote\"hash#equals=tail"
    sptrans = "synthetic-sptrans\\second'quote"
    env = dict(os.environ, PC_RELEASE_B64=base64.b64encode(json.dumps(payload).encode()).decode(),
               METRICS_TOKEN=metric, SPTRANS_TOKEN=sptrans, REGISTRY_TOKEN='test_registry')
    subprocess.run([sys.executable, str(renderer_file)], cwd=tmp_path, env=env, check=True, capture_output=True, text=True, umask=0o077)
    result = subprocess.run(['docker', 'compose', '--env-file', str(tmp_path/'release.env.new'), '-f',
                             str(tmp_path/'compose.production.yaml'), 'config', '--format', 'json'],
                            cwd=tmp_path, check=True, capture_output=True, text=True)
    actual = json.loads(result.stdout)['services']['app']['environment']
    assert actual['METRICS_TOKEN'] == metric
    assert actual['SPTRANS_TOKEN'] == sptrans
    assert (tmp_path/'runtime.env').stat().st_mode & 0o777 == 0o600
    assert (tmp_path/'Caddyfile').stat().st_mode & 0o777 == 0o644
    assert metric not in (tmp_path/'release.env.new').read_text()
    assert 'test_registry' not in (tmp_path/'runtime.env').read_text()
    assert 'test_registry' not in (tmp_path/'release.env.new').read_text()


@pytest.mark.parametrize('pull_fails', [False, True])
def test_guest_registry_login_is_ephemeral_on_success_and_failure(tmp_path, pull_fails):
    """Run the guest Bash flow with local command stubs, never Docker/Azure/network."""
    guest = tmp_path/'guest'
    guest.mkdir()
    (guest/'bootstrap-ready.txt').write_text('synthetic bootstrap complete')
    commands = tmp_path/'commands'
    commands.mkdir()
    events = tmp_path/'events.jsonl'
    stub = commands/'command-stub'
    stub.write_text('''#!/usr/bin/env python3
import base64,json,os,pathlib,subprocess,sys
command=pathlib.Path(sys.argv[0]).name
args=sys.argv[1:]
if command=='timeout':
 os.execvp(args[1],args[1:])
if command=='install':
 paths=[];index=0
 while index<len(args):
  if args[index] in ('-o','-g','-m'):index+=2
  elif args[index].startswith('-'):index+=1
  else:paths.append(args[index]);index+=1
 for name in paths:pathlib.Path(name).mkdir(parents=True,exist_ok=True)
if command=='docker':
 event={'args':args,'registry_token_in_environment':'REGISTRY_TOKEN' in os.environ}
 if args and args[0]=='login':
  value=sys.stdin.read()
  assert value=='test_registry'
  folder=pathlib.Path(os.environ['DOCKER_CONFIG'])
  assert folder.stat().st_mode & 0o777 == 0o700
  (folder/'config.json').write_text(json.dumps({'auths':{'ghcr.io':{'auth':base64.b64encode(value.encode()).decode()}}}))
  event['auth_dir']=str(folder)
 with open(os.environ['TEST_GUEST_EVENTS'],'a') as handle:handle.write(json.dumps(event)+'\\n')
 if 'pull' in args and os.environ.get('TEST_GUEST_PULL_FAIL')=='1':sys.exit(17)
''')
    stub.chmod(0o755)
    for name in ('docker', 'cloud-init', 'timeout', 'install', 'flock'):
        (commands/name).symlink_to(stub)
    script = tmp_path/'release-under-test.sh'
    script.write_text((ROOT/'deploy/release.sh').read_text().replace('/opt/ponto-certo', str(guest)))
    payload = {**IMAGES, 'APP_REVISION': REVISION, 'PUBLIC_HOST': 'ponto-certo-fixture.eastus2.cloudapp.azure.com', 'DATA_MODE': 'demo',
               'files': {'compose.production.yaml': (ROOT/'compose.production.yaml').read_text(), 'Caddyfile': (ROOT/'deploy/Caddyfile').read_text()}}
    env = dict(os.environ, PATH=str(commands)+os.pathsep+os.environ['PATH'],
               TEST_GUEST_EVENTS=str(events), TEST_GUEST_PULL_FAIL='1' if pull_fails else '0',
               PC_ACTION='deploy', PC_EXPECTED_REVISION=REVISION,
               PC_RELEASE_B64=base64.b64encode(json.dumps(payload).encode()).decode(),
               METRICS_TOKEN='test_metrics', SPTRANS_TOKEN='', REGISTRY_TOKEN='test_registry', REGISTRY_USERNAME='Salvittis')
    run = subprocess.run(['bash', str(script)], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert (run.returncode != 0) == pull_fails, run.stderr
    recorded = [json.loads(line) for line in events.read_text().splitlines()]
    login = next(event for event in recorded if event['args'][0] == 'login')
    pull = next(event for event in recorded if 'pull' in event['args'])
    assert not Path(login['auth_dir']).exists()
    assert not pull['registry_token_in_environment']
    assert 'test_registry' not in run.stdout + run.stderr
    for name in ('runtime.env', 'release.env', 'release.env.new'):
        if (guest/name).exists():
            assert 'test_registry' not in (guest/name).read_text()
    assert not list(guest.glob('docker-auth.*'))
