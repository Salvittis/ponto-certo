"""AWS release boundaries with synthetic credentials; no AWS/GH/network calls."""
import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
INSTANCE = 'i-' + '1' * 17
ACCOUNT = '123456789012'
COMMAND = '12345678-1234-1234-1234-123456789012'


def load_module():
    spec = importlib.util.spec_from_file_location('aws_release_test', ROOT/'scripts/deploy-aws.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cloud(monkeypatch, tmp_path):
    module = load_module()
    env = {'AWS_ENABLED': 'true', 'AWS_REGION': 'us-east-1', 'AWS_EXPECTED_ACCOUNT_ID': ACCOUNT,
           'AWS_INSTANCE_ID': INSTANCE, 'AWS_PUBLIC_URL': 'https://ponto-certo-fixture.example.com',
           'AWS_ACCESS_KEY_ID': 'synthetic_access', 'AWS_SECRET_ACCESS_KEY': 'synthetic_aws_secret',
           'AWS_SESSION_TOKEN': 'synthetic_session', 'AWS_SESSION_VALID_UNTIL': '',
           'APP_REVISION': REVISION, 'GITHUB_REPOSITORY': 'Salvittis/ponto-certo', 'DATA_MODE': 'demo',
           'REGISTRY_USERNAME': 'Salvittis', 'REGISTRY_TOKEN': 'synthetic_registry',
           'METRICS_TOKEN': 'synthetic_metrics', 'SPTRANS_TOKEN': ''}
    env.update({key: 'ghcr.io/salvittis/ponto-certo'+suffix+'@sha256:'+'1'*64
                for key, suffix in zip(module.IMAGE_KEYS, ('', '-llm', '-proxy'))})
    for key, value in env.items(): monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    state = SimpleNamespace(module=module, calls=[], env=env, account=ACCOUNT, tag='ponto-certo',
                            online=True, instance=INSTANCE, code=0, status='Success',
                            public_failure=False, delete_failure=False, put_failure=False,
                            invocation_missing=False, marker='previous_restored')

    def fake_aws(service, operation, request, region):
        state.calls.append((service, operation, request))
        assert region == 'us-east-1'
        if operation == 'get-caller-identity': return {'Account': state.account}
        if operation == 'describe-instances':
            return {'Reservations': [{'Instances': [{'InstanceId': state.instance, 'State': {'Name': 'running'},
                    'Architecture': 'x86_64', 'IamInstanceProfile': {'Arn': 'synthetic-profile'},
                    'Tags': [{'Key': 'project', 'Value': state.tag}]}]}]}
        if operation == 'describe-instance-information':
            return {'InstanceInformationList': [{'InstanceId': INSTANCE, 'PingStatus': 'Online' if state.online else 'Offline'}]}
        if operation == 'put-parameter':
            if state.put_failure: raise module.AwsError('AWSCommandFailed')
            return {'Version': 1}
        if operation == 'delete-parameter':
            if state.delete_failure: raise module.AwsError('ExpiredToken')
            return {}
        if operation == 'send-command': return {'Command': {'CommandId': COMMAND}}
        if operation == 'get-command-invocation':
            if state.invocation_missing:
                state.invocation_missing = False
                raise module.AwsError('InvocationDoesNotExist')
            return {'Status': state.status, 'ResponseCode': state.code,
                    'StandardOutputContent': 'synthetic_registry\nPC_RECOVERY_RESULT='+state.marker,
                    'StandardErrorContent': 'synthetic_metrics'}
        raise AssertionError(operation)

    def fake_verify(*args):
        if state.public_failure: raise RuntimeError('synthetic public failure')
        return {'status': 'ok', 'version': 'test', 'revision': REVISION}

    monkeypatch.setattr(module, 'aws', fake_aws)
    monkeypatch.setattr(module, 'verify_public', fake_verify)
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a, 0))
    return state


def public_command(request):
    encoded = request['Parameters']['commands'][0].split("PC_AWS_PUBLIC_B64='", 1)[1].split("'", 1)[0]
    return json.loads(base64.b64decode(encoded))


def test_secret_values_only_reach_securestring_and_are_deleted(cloud, capsys):
    cloud.module.main()
    put = next(request for _, op, request in cloud.calls if op == 'put-parameter')
    assert (put['Type'], put['Tier'], put['DataType'], put['KeyId']) == ('SecureString', 'Standard', 'text', 'alias/aws/ssm')
    assert json.loads(put['Value'])['REGISTRY_TOKEN'] == 'synthetic_registry'
    sent = next(request for _, op, request in cloud.calls if op == 'send-command')
    public = public_command(sent)
    assert (public['parameter'], public['version']) == (put['Name'], 1)
    visible = json.dumps(sent) + json.dumps(public) + base64.b64decode(public['release']).decode() + base64.b64decode(public['release_script']).decode()
    evidence = Path('reports/aws-deployment.json').read_text()
    output = capsys.readouterr()
    for key in ('REGISTRY_TOKEN', 'METRICS_TOKEN', 'AWS_SESSION_TOKEN', 'AWS_SECRET_ACCESS_KEY'):
        assert cloud.env[key] not in visible + evidence + output.out + output.err
    assert cloud.calls[-1][1:] == ('delete-parameter', {'Name': put['Name']})
    assert json.loads(evidence)['pipeline_success'] is True


@pytest.mark.parametrize('field,value', [('account', '000000000000'), ('tag', 'another-project'),
                                        ('online', False), ('instance', 'i-'+'2'*17)])
def test_target_guards_precede_all_mutations(cloud, field, value):
    setattr(cloud, field, value)
    with pytest.raises(RuntimeError): cloud.module.main()
    assert not any(op in ('put-parameter', 'send-command', 'delete-parameter') for _, op, _ in cloud.calls)


@pytest.mark.parametrize('key,value', [('AWS_ENABLED', 'false'), ('AWS_SESSION_TOKEN', ''),
    ('AWS_PUBLIC_URL', 'http://localhost'), ('APP_REVISION', 'main'),
    ('PROXY_IMAGE_REF', 'ghcr.io/salvittis/ponto-certo-proxy:latest'),
    ('METRICS_TOKEN', 'bad\nvalue'), ('REGISTRY_TOKEN', 'x'*4096),
    ('AWS_SESSION_VALID_UNTIL', '2020-01-01T00:00:00Z')])
def test_invalid_or_expired_configuration_fails_before_aws(cloud, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError): cloud.module.main()
    assert cloud.calls == []


def test_future_session_window_is_recorded(cloud, monkeypatch):
    expires = (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    monkeypatch.setenv('AWS_SESSION_VALID_UNTIL', expires)
    cloud.module.main()
    assert json.loads(Path('reports/aws-deployment.json').read_text())['session_valid_until'] == expires


@pytest.mark.parametrize('status,code', [('Success', 1), ('Failed', 0), ('TimedOut', -1)])
def test_ssm_requires_both_success_and_zero_exit_and_cleans(cloud, status, code):
    cloud.status, cloud.code = status, code
    with pytest.raises(RuntimeError): cloud.module.main()
    assert cloud.calls[-1][1] == 'delete-parameter'
    evidence = json.loads(Path('reports/aws-deployment-failure.json').read_text())
    assert evidence['failure_stage'] == 'ssm_deploy'
    assert evidence['pipeline_success'] is False


def test_eventual_consistency_does_not_turn_initial_missing_invocation_into_failure(cloud):
    cloud.invocation_missing = True
    cloud.module.main()
    assert sum(op == 'get-command-invocation' for _, op, _ in cloud.calls) == 2


def test_ambiguous_parameter_creation_still_attempts_cleanup(cloud):
    cloud.put_failure = True
    with pytest.raises(RuntimeError): cloud.module.main()
    assert cloud.calls[-1][1] == 'delete-parameter'
    assert not any(op == 'send-command' for _, op, _ in cloud.calls)


def test_cleanup_failure_is_not_a_green_pipeline(cloud):
    cloud.delete_failure = True
    with pytest.raises(RuntimeError): cloud.module.main()
    evidence = json.loads(Path('reports/aws-deployment-failure.json').read_text())
    assert evidence['parameter_cleanup'] == 'failed_or_unconfirmed'
    assert evidence['pipeline_success'] is False


def test_public_failure_requests_secretless_revision_guarded_rollback(cloud):
    cloud.public_failure = True
    with pytest.raises(RuntimeError): cloud.module.main()
    commands = [public_command(request) for _, op, request in cloud.calls if op == 'send-command']
    assert len(commands) == 2 and commands[1]['action'] == 'rollback'
    assert commands[1]['revision'] == REVISION
    assert 'parameter' not in commands[1] and 'release' not in commands[1]
    evidence = json.loads(Path('reports/aws-deployment-failure.json').read_text())
    assert evidence['recovery_result'] == 'previous_restored'
    assert evidence['parameter_cleanup'] == 'deleted'


def test_cli_request_file_is_private_and_removed_on_failure(monkeypatch):
    module = load_module(); paths = []
    def fake_run(argv, **kwargs):
        assert 'synthetic_secret' not in repr(argv)
        path = Path(argv[argv.index('--cli-input-json')+1].removeprefix('file://'))
        paths.append(path)
        assert path.stat().st_mode & 0o777 == 0o600
        assert json.loads(path.read_text())['Value'] == 'synthetic_secret'
        return subprocess.CompletedProcess(argv, 1, '', 'secret synthetic_secret (ExpiredToken)')
    monkeypatch.setattr(module.subprocess, 'run', fake_run)
    with pytest.raises(module.AwsError) as failure:
        module.aws('ssm', 'put-parameter', {'Value': 'synthetic_secret'}, 'us-east-1')
    assert 'synthetic_secret' not in str(failure.value)
    assert all(not path.exists() for path in paths)


@pytest.mark.parametrize('release_exit', [0, 1])
def test_real_guest_wrapper_does_not_relay_secret_stdout_stderr(tmp_path, monkeypatch, release_exit):
    commands = tmp_path/'commands'; commands.mkdir()
    name = '/ponto-certo/ci/'+'b'*32
    credentials = {'APP_REVISION': REVISION, 'METRICS_TOKEN': 'synthetic_metrics',
                   'SPTRANS_TOKEN': '', 'REGISTRY_TOKEN': 'synthetic_registry'}
    response = {'Parameter': {'Type': 'SecureString', 'Name': name, 'Version': 1, 'Value': json.dumps(credentials)}}
    stub = commands/'aws'
    stub.write_text('#!/usr/bin/env python3\nimport json,sys\nassert "--with-decryption" in sys.argv\nprint('+repr(json.dumps(response))+')\n')
    stub.chmod(0o755)
    script = ('#!/usr/bin/env bash\nset -eu\n'
              'test "$PC_EXPECTED_REVISION" = "'+REVISION+'"\n'
              'test "$METRICS_TOKEN" = synthetic_metrics\n'
              'test "$REGISTRY_TOKEN" = synthetic_registry\n'
              'printf "%s\\n" "$REGISTRY_TOKEN"\n'
              'printf "%s\\n" "$METRICS_TOKEN" >&2\n'
              'echo PC_RECOVERY_RESULT=previous_restored\nexit '+str(release_exit)+'\n')
    fixture_root = tmp_path/'source'; (fixture_root/'deploy').mkdir(parents=True)
    (fixture_root/'deploy/release.sh').write_text(script)
    (fixture_root/'deploy/release-aws.sh').write_text((ROOT/'deploy/release-aws.sh').read_text())
    module = load_module(); monkeypatch.setattr(module, 'ROOT', fixture_root)
    config = {'instance': INSTANCE, 'revision': REVISION, 'region': 'us-east-1',
              'username': 'Salvittis', 'release': {}}
    payload = module.command_payload(config, 'deploy', name, 1)
    env = dict(os.environ, PATH=str(commands)+os.pathsep+os.environ['PATH'])
    # AWS-RunShellScript starts with sh; the payload must explicitly enter Bash.
    result = subprocess.run(['sh', '-c', payload['Parameters']['commands'][0]], env=env,
                            capture_output=True, text=True, timeout=10)
    assert (result.returncode != 0) == (release_exit != 0)
    assert 'PC_RECOVERY_RESULT=previous_restored' in result.stdout
    assert 'synthetic_registry' not in result.stdout+result.stderr
    assert 'synthetic_metrics' not in result.stdout+result.stderr
