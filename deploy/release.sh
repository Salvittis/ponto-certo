#!/usr/bin/env bash
# Run as VM administrator through Azure Managed RunCommand. Workloads are non-root.
set -Eeuo pipefail
umask 077
bootstrap_status=0
timeout 300 cloud-init status --wait >/dev/null || bootstrap_status=$?
if [[ "$bootstrap_status" != 0 && "$bootstrap_status" != 2 ]]; then
    printf 'Cloud-init did not finish successfully.\n' >&2
    exit 1
fi
# Exit 2 can mean recoverable cloud-init warnings. Require our completed bootstrap
# and a functioning daemon/plugin; never silently continue after a failed install.
test -s /opt/ponto-certo/bootstrap-ready.txt
docker info >/dev/null
docker compose version >/dev/null
install -d -m 700 /opt/ponto-certo
cd /opt/ponto-certo
exec 9>/opt/ponto-certo/deploy.lock
flock -w 60 9
registry_auth_dir=''
cleanup_registry() {
    if [[ -n "$registry_auth_dir" ]]; then
        rm -rf "$registry_auth_dir"
        registry_auth_dir=''
    fi
    unset REGISTRY_TOKEN REGISTRY_USERNAME DOCKER_CONFIG
}
trap cleanup_registry EXIT

recover_previous() {
    if [ -f previous/release.env ]; then
        for file in release.env runtime.env compose.production.yaml Caddyfile; do
            cp "previous/$file" "$file"
        done
        # Caddy runs as UID 10001 and must read this non-secret bind mount.
        chmod 0644 Caddyfile
        docker compose --env-file release.env -f compose.production.yaml up -d --force-recreate --wait --wait-timeout 300
        docker compose --env-file release.env -f compose.production.yaml exec -T app \
            python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=10)"
        printf 'PC_RECOVERY_RESULT=previous_restored\n'
    else
        # The first release has no healthy predecessor. Stop only this failed stack.
        if [ -f release.env ] && [ -f compose.production.yaml ]; then
            docker compose --env-file release.env -f compose.production.yaml down
            mv release.env failed-release.env
        fi
        printf 'PC_RECOVERY_RESULT=first_release_stopped\n'
    fi
}

if [[ "${PC_ACTION:-deploy}" == rollback ]]; then
    # A later operator/deploy must not be rolled back by an older validation task.
    python3 - <<'PY'
import os
from pathlib import Path
expected = os.environ.get('PC_EXPECTED_REVISION', '')
current = dict(line.split('=', 1) for line in Path('release.env').read_text().splitlines() if '=' in line)
if not expected or current.get('APP_REVISION') != expected:
    raise SystemExit('Refusing to roll back a different release')
PY
    recover_previous
    exit 0
fi
if [[ "${PC_ACTION:-deploy}" != deploy ]]; then
    printf 'Unsupported deployment action.\n' >&2
    exit 1
fi
if [ -f release.env ]; then
    backup_dir=$(mktemp -d /opt/ponto-certo/previous.XXXXXX)
    for file in release.env runtime.env compose.production.yaml Caddyfile; do
        cp "$file" "$backup_dir/$file"
    done
    # Only replace a previous snapshot after every file of this one was copied.
    rm -rf previous
    mv "$backup_dir" previous
fi
rollback_on_error() {
    trap - ERR
    printf 'Release failed; attempting recovery of the previous complete configuration.\n' >&2
    recover_previous
    exit 1
}
trap rollback_on_error ERR
python3 - <<'PY'
import base64,json,os,re
from pathlib import Path
payload=json.loads(base64.b64decode(os.environ['PC_RELEASE_B64']))
for key in ('IMAGE_REF','LLM_IMAGE_REF','PROXY_IMAGE_REF'):
 if not re.fullmatch(r'ghcr\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}',payload[key]):
  raise SystemExit('Unapproved image reference')
if not re.fullmatch(r'[0-9a-f]{40}',payload['APP_REVISION']):
 raise SystemExit('Invalid release revision')
if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',payload['PUBLIC_HOST']):
 raise SystemExit('Invalid public hostname')
mode=payload['DATA_MODE']
if mode not in ('demo','live'):raise SystemExit('Invalid data mode')
secrets={k:os.environ.get(k,'') for k in ('METRICS_TOKEN','SPTRANS_TOKEN')}
if not secrets['METRICS_TOKEN']:raise SystemExit('Metrics token is required')
if mode=='live' and not secrets['SPTRANS_TOKEN']:raise SystemExit('Live mode requires SPTrans token')
for v in secrets.values():
 if any(c in v for c in '\r\n\x00'):raise SystemExit('Invalid multiline credential')
# Compose env_file format: raw preserves $, quotes and backslashes exactly.
Path('runtime.env.new').write_text('DATA_MODE='+mode+'\n'+''.join(k+'='+v+'\n' for k,v in secrets.items()))
Path('runtime.env.new').chmod(0o600)
public={k:payload[k] for k in ('IMAGE_REF','LLM_IMAGE_REF','PROXY_IMAGE_REF','APP_REVISION','PUBLIC_HOST')}
Path('release.env.new').write_text(''.join(k+'='+v+'\n' for k,v in public.items()))
for name in ('compose.production.yaml','Caddyfile'):
 Path(name).write_text(payload['files'][name])
# The shell umask remains 077 for credentials; Caddy's public config is readable
# by the unprivileged proxy, including when replacing an older 0600 file.
Path('Caddyfile').chmod(0o644)
Path('runtime.env.new').replace('runtime.env')
PY
unset METRICS_TOKEN SPTRANS_TOKEN PC_RELEASE_B64
install -d -o 10001 -g 10001 -m 700 caddy/data caddy/config
docker compose --env-file release.env.new -f compose.production.yaml config --quiet
test -n "${REGISTRY_TOKEN:-}"
test -n "${REGISTRY_USERNAME:-}"
registry_auth_dir=$(mktemp -d /opt/ponto-certo/docker-auth.XXXXXX)
chmod 700 "$registry_auth_dir"
export DOCKER_CONFIG="$registry_auth_dir"
# Short-lived GitHub token is passed only on stdin and never put in release files.
printf '%s' "$REGISTRY_TOKEN" | docker login ghcr.io --username "$REGISTRY_USERNAME" --password-stdin >/dev/null
unset REGISTRY_TOKEN
timeout 300 docker compose --env-file release.env.new -f compose.production.yaml pull --quiet
cleanup_registry
mv release.env.new release.env
docker compose --env-file release.env -f compose.production.yaml up -d --wait --wait-timeout 300
# Caddy admin API is disabled. A changed bind-mounted Caddyfile alone does not
# recreate a Compose service; recreate the proxy so the approved file is loaded.
docker compose --env-file release.env -f compose.production.yaml up -d --no-deps --force-recreate --wait --wait-timeout 60 proxy
docker compose --env-file release.env -f compose.production.yaml exec -T app \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=10)"
docker compose --env-file release.env -f compose.production.yaml ps
trap - ERR
printf 'Approved release started and internal readiness verified; external validation is still required.\n'
