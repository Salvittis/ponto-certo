#!/usr/bin/env python3
"""Deploy approved digests to the Academy instance without secrets in Run Command."""
import base64
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE_KEYS = ('IMAGE_REF', 'LLM_IMAGE_REF', 'PROXY_IMAGE_REF')
SECRET_KEYS = ('METRICS_TOKEN', 'SPTRANS_TOKEN', 'REGISTRY_TOKEN')
spec = importlib.util.spec_from_file_location('azure_release_validation', ROOT/'scripts/deploy-azure.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
public_origin = common.public_origin
verify_public = common.verify_public
required = common.required


class AwsError(RuntimeError):
    def __init__(self, code='AWSCommandFailed'):
        self.code = code
        super().__init__('AWS request failed (' + code + ')')


class CommandFailure(RuntimeError):
    def __init__(self, command_id, status, recovery=None):
        self.command_id, self.status, self.recovery = command_id, status, recovery
        super().__init__('SSM release did not complete successfully')


def aws(service, operation, request, region):
    """Only a 0600 JSON filename reaches argv; stderr/request bodies are never echoed."""
    with tempfile.TemporaryDirectory(prefix='ponto-certo-aws-') as directory:
        path = Path(directory)/'request.json'
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
            json.dump(request, handle)
        result = subprocess.run(
            ['aws', service, operation, '--cli-input-json', 'file://' + str(path),
             '--region', region, '--output', 'json', '--no-cli-pager'],
            capture_output=True, text=True, timeout=60)
    if result.returncode:
        allowed = ('InvocationDoesNotExist', 'ParameterNotFound', 'ExpiredTokenException',
                   'ExpiredToken', 'InvalidClientTokenId', 'AccessDeniedException', 'InvalidInstanceId')
        code = next((code for code in allowed if '(' + code + ')' in result.stderr), 'AWSCommandFailed')
        raise AwsError(code)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def configuration():
    if os.environ.get('AWS_ENABLED') != 'true':
        raise RuntimeError('AWS deployment is disabled; activate only during a Lab session')
    region, account, instance = (required(key) for key in ('AWS_REGION', 'AWS_EXPECTED_ACCOUNT_ID', 'AWS_INSTANCE_ID'))
    if not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]+', region):
        raise RuntimeError('Invalid AWS_REGION')
    if not re.fullmatch(r'[0-9]{12}', account):
        raise RuntimeError('Invalid AWS_EXPECTED_ACCOUNT_ID')
    if not re.fullmatch(r'i-(?:[a-f0-9]{8}|[a-f0-9]{17})', instance):
        raise RuntimeError('Invalid AWS_INSTANCE_ID')
    # Static Lab credentials have no refresh provider. A supplied deadline is a
    # scheduling guard, never proof that STS credentials can be extended.
    until = os.environ.get('AWS_SESSION_VALID_UNTIL', '')
    if until:
        try:
            expires = datetime.fromisoformat(until.replace('Z', '+00:00'))
            if expires.tzinfo is None or (expires-datetime.now(timezone.utc)).total_seconds() < 2700:
                raise ValueError
        except ValueError:
            raise RuntimeError('Lab session deadline must leave at least 45 minutes for deploy and recovery') from None
    for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'):
        required(key)
    revision = required('APP_REVISION')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise RuntimeError('APP_REVISION must be a full Git SHA')
    origin = public_origin(required('AWS_PUBLIC_URL'))
    repository = os.environ.get('GITHUB_REPOSITORY', 'Salvittis/ponto-certo').lower()
    if not re.fullmatch(r'[a-z0-9_.-]+/[a-z0-9_.-]+', repository):
        raise RuntimeError('Invalid GITHUB_REPOSITORY')
    release = {key: required(key) for key in IMAGE_KEYS}
    for key, suffix in zip(IMAGE_KEYS, ('', '-llm', '-proxy')):
        if not re.fullmatch(re.escape('ghcr.io/' + repository + suffix + '@sha256:') + r'[a-f0-9]{64}', release[key]):
            raise RuntimeError('Only approved component digests from this repository can be deployed')
    mode = os.environ.get('DATA_MODE', 'demo')
    if mode not in ('demo', 'live'):
        raise RuntimeError('Invalid DATA_MODE')
    username = required('REGISTRY_USERNAME')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*(?:\[bot\])?', username):
        raise RuntimeError('Invalid REGISTRY_USERNAME')
    secrets = {key: os.environ.get(key, '') for key in SECRET_KEYS}
    if not secrets['METRICS_TOKEN'] or not secrets['REGISTRY_TOKEN'] or (mode == 'live' and not secrets['SPTRANS_TOKEN']):
        raise RuntimeError('Required runtime or private registry credentials are missing')
    if any(any(char in value for char in '\r\n\x00') for value in secrets.values()):
        raise RuntimeError('Runtime credentials must not contain CR, LF or NUL')
    secret_value = json.dumps(dict(secrets, APP_REVISION=revision), ensure_ascii=False)
    if len(secret_value.encode()) > 4096:
        raise RuntimeError('Runtime credentials exceed the Standard SecureString 4 KiB limit')
    release.update(APP_REVISION=revision, PUBLIC_HOST=origin.removeprefix('https://'), DATA_MODE=mode,
                   files={'compose.production.yaml': (ROOT/'compose.production.yaml').read_text(),
                          'Caddyfile': (ROOT/'deploy/Caddyfile').read_text()})
    return dict(region=region, account=account, instance=instance, revision=revision, origin=origin,
                mode=mode, username=username, release=release, secret_value=secret_value,
                session_valid_until=until or None)


def validate_target(config):
    region = config['region']
    identity = aws('sts', 'get-caller-identity', {}, region)
    if identity.get('Account') != config['account']:
        raise RuntimeError('Refusing to deploy outside the expected Academy account')
    response = aws('ec2', 'describe-instances', {'InstanceIds': [config['instance']]}, region)
    instances = [item for reservation in response.get('Reservations', []) for item in reservation.get('Instances', [])]
    if len(instances) != 1 or instances[0].get('InstanceId') != config['instance']:
        raise RuntimeError('Exactly the configured Academy instance must be returned')
    instance = instances[0]
    tags = {tag.get('Key'): tag.get('Value') for tag in instance.get('Tags', [])}
    if (tags.get('project') != 'ponto-certo' or instance.get('State', {}).get('Name') != 'running'
            or instance.get('Architecture') != 'x86_64' or not instance.get('IamInstanceProfile', {}).get('Arn')):
        raise RuntimeError('Instance must be tagged ponto-certo, running, amd64 and have its existing Lab profile')
    managed = aws('ssm', 'describe-instance-information',
                  {'Filters': [{'Key': 'InstanceIds', 'Values': [config['instance']]}]}, region)
    nodes = managed.get('InstanceInformationList', [])
    if len(nodes) != 1 or nodes[0].get('InstanceId') != config['instance'] or nodes[0].get('PingStatus') != 'Online':
        raise RuntimeError('Configured instance is not Online in SSM')


def command_payload(config, action, parameter=None, version=None):
    if action not in ('deploy', 'rollback'):
        raise RuntimeError('Unsupported release action')
    public = {'action': action, 'revision': config['revision'], 'region': config['region'],
              'release_script': base64.b64encode((ROOT/'deploy/release.sh').read_bytes()).decode()}
    if action == 'deploy':
        public.update(parameter=parameter, version=version, registry_username=config['username'],
                      release=base64.b64encode(json.dumps(config['release']).encode()).decode())
    encoded = base64.b64encode(json.dumps(public).encode()).decode()
    wrapper = (ROOT/'deploy/release-aws.sh').read_text()
    # AWS-RunShellScript may launch /bin/sh on Ubuntu. Enter Bash explicitly;
    # its public heredoc contains no credential values or shell interpolation.
    script = "bash <<'PONTO_CERT0_AWS_WRAPPER'\nexport PC_AWS_PUBLIC_B64='" + encoded + "'\n" + wrapper + "\nPONTO_CERT0_AWS_WRAPPER\n"
    return {'DocumentName': 'AWS-RunShellScript', 'InstanceIds': [config['instance']],
            'Comment': 'ponto-certo ' + action + ' ' + config['revision'][:12],
            'TimeoutSeconds': 120,
            'Parameters': {'commands': [script], 'executionTimeout': ['900']},
            'CloudWatchOutputConfig': {'CloudWatchOutputEnabled': False}}


def run_command(config, action, parameter=None, version=None):
    validate_target(config)
    sent = aws('ssm', 'send-command', command_payload(config, action, parameter, version), config['region'])
    command_id = sent.get('Command', {}).get('CommandId', '')
    if not re.fullmatch(r'[a-f0-9-]{36}', command_id):
        raise RuntimeError('SSM did not return a valid command ID')
    deadline, last = time.monotonic()+1000, None
    while time.monotonic() < deadline:
        try:
            result = aws('ssm', 'get-command-invocation',
                         {'CommandId': command_id, 'InstanceId': config['instance']}, config['region'])
        except AwsError as error:
            if error.code != 'InvocationDoesNotExist':
                raise
            time.sleep(5)
            continue
        status = result.get('Status')
        if status != last:
            # Never copy arbitrary stdout/stderr, API errors or request bodies to CI.
            print('SSM', action + ':', status if status in ('Pending', 'InProgress', 'Delayed', 'Success', 'Failed', 'TimedOut', 'Cancelled', 'Cancelling') else 'Unknown', flush=True)
            last = status
        recovery = next((marker for marker in ('previous_restored', 'first_release_stopped')
                         if 'PC_RECOVERY_RESULT=' + marker in result.get('StandardOutputContent', '')), None)
        # AWS calls this terminal state Success, not Azure's Succeeded.
        if status == 'Success' and result.get('ResponseCode') == 0:
            return {'id': command_id, 'recovery': recovery}
        if status not in ('Pending', 'InProgress', 'Delayed', 'Cancelling'):
            raise CommandFailure(command_id, status if status in ('Success', 'Failed', 'TimedOut', 'Cancelled') else 'Unknown', recovery)
        time.sleep(5)
    raise CommandFailure(command_id, 'PollingTimeout')


def main():
    config = configuration()
    validate_target(config)  # Account and target guards precede even PutParameter.
    parameter = '/ponto-certo/ci/' + uuid.uuid4().hex
    attempted, failure, stage = False, None, 'parameter_create'
    evidence = {'checked_at': datetime.now(timezone.utc).isoformat(), 'provider': 'aws-academy',
                'commit': config['revision'], 'url': config['origin'], 'data_mode': config['mode'],
                'images': {key: config['release'][key] for key in IMAGE_KEYS},
                'session_valid_until': config['session_valid_until'], 'result': 'not_verified'}
    try:
        attempted = True
        created = aws('ssm', 'put-parameter', {'Name': parameter, 'Value': config['secret_value'],
                      'Type': 'SecureString', 'Tier': 'Standard', 'DataType': 'text',
                      'KeyId': 'alias/aws/ssm', 'Overwrite': False}, config['region'])
        version = created.get('Version')
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise RuntimeError('SSM did not return a valid parameter version')
        stage = 'ssm_deploy'
        command = run_command(config, 'deploy', parameter, version)
        evidence['run_command'] = command['id']
        stage = 'public_validation'
        try:
            health = verify_public(config['origin'], config['revision'])
            subprocess.run([sys.executable, str(ROOT/'scripts/smoke.py'), '--base-url', config['origin'],
                            '--expect-mode', config['mode'], '--timeout', '120', '--ready-timeout', '30',
                            '--output', 'reports/aws-smoke-public.json'], check=True, timeout=420)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
            evidence['result'] = 'public_validation_failed'
            try:
                recovery = run_command(config, 'rollback')
                evidence.update(recovery_command=recovery['id'], recovery_result=recovery['recovery'] or 'unconfirmed')
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
                evidence['recovery_result'] = 'failed_or_unconfirmed'
            raise RuntimeError('Public validation failed') from None
        evidence.update(result='public_model_verified', health={key: health[key] for key in ('status', 'version', 'revision') if key in health})
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        failure = 'AWS deployment failed during ' + stage
        evidence['failure_stage'] = stage
        if isinstance(error, CommandFailure):
            evidence.update(run_command=error.command_id, command_status=error.status,
                            recovery_result=error.recovery or 'unconfirmed')
    finally:
        if attempted:
            try:
                aws('ssm', 'delete-parameter', {'Name': parameter}, config['region'])
                evidence['parameter_cleanup'] = 'deleted'
            except AwsError as error:
                if error.code == 'ParameterNotFound':
                    evidence['parameter_cleanup'] = 'absent'
                else:
                    evidence['parameter_cleanup'] = 'failed_or_unconfirmed'
                    failure = failure or 'Temporary SecureString cleanup could not be confirmed'
            except (OSError, ValueError, subprocess.SubprocessError):
                evidence['parameter_cleanup'] = 'failed_or_unconfirmed'
                failure = failure or 'Temporary SecureString cleanup could not be confirmed'
        evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
        evidence['pipeline_success'] = failure is None
        Path('reports').mkdir(exist_ok=True)
        path = Path('reports/aws-deployment-failure.json' if failure else 'reports/aws-deployment.json')
        path.write_text(json.dumps(evidence, indent=2)+'\n')
        print(json.dumps(evidence, indent=2))
    if failure:
        raise RuntimeError(failure)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
        print('AWS deployment failed; inspect the sanitized deployment evidence and selected Lab operation.', file=sys.stderr)
        sys.exit(1)
