#!/usr/bin/env bash
# Run Command contains only this public wrapper, a parameter name/version and digests.
set -Eeuo pipefail
umask 077
python3 - <<'PY'
import base64,json,os,re,subprocess,sys,tempfile
from pathlib import Path

def main():
    config=json.loads(base64.b64decode(os.environ.pop('PC_AWS_PUBLIC_B64')))
    revision=config['revision']
    if not re.fullmatch(r'[a-f0-9]{40}',revision):raise RuntimeError
    action=config['action']
    if action not in ('deploy','rollback'):raise RuntimeError
    env=dict(os.environ,PC_ACTION=action,PC_EXPECTED_REVISION=revision)
    if action=='deploy':
        name,version=config['parameter'],config['version']
        if not re.fullmatch(r'/ponto-certo/ci/[a-f0-9]{32}',name) or not isinstance(version,int) or version<1:raise RuntimeError
        result=subprocess.run(['aws','ssm','get-parameter','--name',name+':'+str(version),
            '--with-decryption','--region',config['region'],'--output','json','--no-cli-pager'],
            capture_output=True,text=True,timeout=60)
        if result.returncode:raise RuntimeError
        parameter=json.loads(result.stdout)['Parameter']
        if parameter['Type']!='SecureString' or parameter['Name']!=name or parameter['Version']!=version:raise RuntimeError
        credentials=json.loads(parameter['Value'])
        if credentials.pop('APP_REVISION')!=revision:raise RuntimeError
        if set(credentials)!={'METRICS_TOKEN','SPTRANS_TOKEN','REGISTRY_TOKEN'}:raise RuntimeError
        if any(not isinstance(v,str) or any(c in v for c in '\r\n\x00') for v in credentials.values()):raise RuntimeError
        if not credentials['METRICS_TOKEN'] or not credentials['REGISTRY_TOKEN']:raise RuntimeError
        env.update(credentials,REGISTRY_USERNAME=config['registry_username'],PC_RELEASE_B64=config['release'])
    with tempfile.TemporaryDirectory(prefix='ponto-certo-aws-release-') as folder:
        script=Path(folder)/'release.sh'
        script.write_bytes(base64.b64decode(config['release_script']));script.chmod(0o600)
        # Public release.sh owns lock, pull credentials cleanup, activation and rollback.
        process=subprocess.Popen(['bash',str(script)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        for key in ('METRICS_TOKEN','SPTRANS_TOKEN','REGISTRY_TOKEN'):env.pop(key,None)
        if action=='deploy':
            credentials.clear();parameter.clear();result=None
        try:
            stdout,_=process.communicate(timeout=880)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:process.communicate(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.communicate()
            raise RuntimeError from None
        # Never relay arbitrary guest/CLI output into the SSM execution history.
        for marker in ('previous_restored','first_release_stopped'):
            if 'PC_RECOVERY_RESULT='+marker in stdout:print('PC_RECOVERY_RESULT='+marker)
        if process.returncode:raise RuntimeError
    print('PC_RELEASE_RESULT=success')

try:main()
except Exception:
    print('AWS guest release failed; inspect the selected service status without printing runtime credentials.',file=sys.stderr)
    sys.exit(1)
PY
