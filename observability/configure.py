#!/usr/bin/env python3
"""Prepare local monitor targets and file secrets without printing their values."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime' / 'monitoring'


def write_local(path, value):
    # Only the owner can traverse RUNTIME (0700). Read-only file secrets can be
    # mounted individually into non-root containers without exposing the folder.
    if path.exists():
        path.chmod(0o600)
    path.write_text(value, encoding='utf-8')
    path.chmod(0o444)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Public HTTPS origin of the deployed MVP')
    parser.add_argument('--metrics-token-file', type=Path,
                        help='Read the existing server METRICS_TOKEN from this local file')
    parser.add_argument('--allow-local-http', action='store_true',
                        help='Only for localhost/127.0.0.1/host.docker.internal integration checks')
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    local_http = (args.allow_local_http and parsed.scheme == 'http'
                  and parsed.hostname in ('localhost', '127.0.0.1', 'host.docker.internal'))
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/') or not (parsed.scheme == 'https' or local_http)):
        parser.error('Use a clean HTTPS origin, without credentials, query string or path.')
    origin = args.url.rstrip('/')
    if args.metrics_token_file:
        token = args.metrics_token_file.read_text(encoding='utf-8').strip()
    else:
        token = os.environ.get('METRICS_TOKEN') or getpass.getpass('Existing server METRICS_TOKEN (hidden): ')
    if not token or any(ch.isspace() for ch in token):
        parser.error('METRICS_TOKEN must be nonempty and must not contain whitespace.')
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    RUNTIME.chmod(0o700)
    write_local(RUNTIME / 'metrics-token', token + '\n')
    if not (RUNTIME / 'grafana-admin-password').exists():
        write_local(RUNTIME / 'grafana-admin-password', secrets.token_urlsafe(32) + '\n')
    labels = {'application': 'ponto-certo', 'environment': 'local-check' if local_http else 'public'}
    metrics = [{'targets': [parsed.netloc], 'labels': dict(labels, __scheme__=parsed.scheme)}]
    ready = [{'targets': [origin + '/readyz'], 'labels': labels}]
    for filename, content in [('metrics-targets.json', metrics), ('ready-targets.json', ready)]:
        write_local(RUNTIME / filename, json.dumps(content, indent=2) + '\n')
    print('Prepared monitoring targets and private local file secrets in .runtime/monitoring/.')
    print('Grafana user: admin. Password remains in .runtime/monitoring/grafana-admin-password.')
    print('Next: docker compose -f compose.monitoring.yaml up -d')


if __name__ == '__main__':
    main()
