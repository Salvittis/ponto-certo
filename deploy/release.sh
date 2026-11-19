#!/usr/bin/env bash
# Run as VM administrator through Azure Managed RunCommand. Workloads are non-root.
set -euo pipefail
umask 077
cloud-init status --wait >/dev/null
install -d -m 700 /opt/ponto-certo
cd /opt/ponto-certo
exec 9>/opt/ponto-certo/deploy.lock
flock -w 600 9
if [ -f release.env ]; then
    install -d -m 700 previous
    for file in release.env runtime.env compose.production.yaml Caddyfile; do
        cp "$file" "previous/$file"
    done
fi
rollback() {
    trap - ERR
    if [ -f previous/release.env ]; then
        for file in release.env runtime.env compose.production.yaml Caddyfile; do
            cp "previous/$file" "$file"
        done
        docker compose --env-file release.env -f compose.production.yaml up -d --wait --wait-timeout 300 || true
    fi
    printf 'Release failed; previous complete configuration restored when available.\n' >&2
    exit 1
}
trap rollback ERR
python3 - <<'PY'
import base64,json,os,re
from pathlib import Path
payload=json.loads(base64.b64decode(os.environ['PC_RELEASE_B64']))
for key in ('IMAGE_REF','LLM_IMAGE_REF'):
 if not re.fullmatch(r'ghcr\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}',payload[key]):
  raise SystemExit('Unapproved image reference')
for name in ('compose.production.yaml','Caddyfile'):
 Path(name).write_text(payload['files'][name])
public={k:payload[k] for k in ('IMAGE_REF','LLM_IMAGE_REF','APP_REVISION','PUBLIC_HOST')}
Path('release.env.new').write_text(''.join(k+'='+v+'\n' for k,v in public.items()))
mode=payload['DATA_MODE']
if mode not in ('demo','live'):raise SystemExit('Invalid data mode')
secrets={k:os.environ.get(k,'') for k in ('METRICS_TOKEN','SPTRANS_TOKEN')}
if not secrets['METRICS_TOKEN']:raise SystemExit('Metrics token is required')
if mode=='live' and not secrets['SPTRANS_TOKEN']:raise SystemExit('Live mode requires SPTrans token')
for v in secrets.values():
 if any(c in v for c in '\r\n\x00'):raise SystemExit('Invalid multiline credential')
# Single-quoted Compose env values disable interpolation. Escape literal quotes.
def quote(v):return "'"+v.replace('\\','\\\\').replace("'","\\'")+"'"
Path('runtime.env').write_text('DATA_MODE='+mode+'\n'+''.join(k+'='+quote(v)+'\n' for k,v in secrets.items()))
Path('runtime.env').chmod(0o600)
PY
unset METRICS_TOKEN SPTRANS_TOKEN PC_RELEASE_B64
install -d -o 10001 -g 10001 -m 700 caddy/data caddy/config
docker compose --env-file release.env.new -f compose.production.yaml config --quiet
docker compose --env-file release.env.new -f compose.production.yaml pull --quiet
mv release.env.new release.env
docker compose --env-file release.env -f compose.production.yaml up -d --wait --wait-timeout 300
docker compose --env-file release.env -f compose.production.yaml exec -T app \
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=10)"
docker compose --env-file release.env -f compose.production.yaml ps
trap - ERR
printf 'Approved release started and internal readiness verified.\n'
