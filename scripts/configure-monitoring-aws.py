#!/usr/bin/env python3
"""Prepare only the isolated AWS monitor; never start containers or contact a target."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shlex
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME = Path.home()/'.local/share/ponto-certo/monitoring-aws'


def evidence_module():
    spec = importlib.util.spec_from_file_location('cloud_evidence', ROOT/'scripts/collect-cloud-evidence.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def outside_checkout(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Use an absolute path outside the checkout.')
    path = path.resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('AWS runtime and source credentials must stay outside the checkout.')
    return path


def read_private_token(path):
    path = outside_checkout(path)
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077
            or info.st_uid != os.getuid() or not 1 <= info.st_size <= 4096):
        raise ValueError('The token source must be a small, owner-only regular file (0600 or 0400).')
    token = path.read_text(encoding='utf-8').strip()
    if not token or any(character.isspace() for character in token):
        raise ValueError('The AWS metrics token must be nonempty and contain no whitespace.')
    return token


def write_mount_file(path, value):
    if path.is_symlink():
        raise ValueError('Refusing to replace a symlink in the private AWS runtime.')
    # Docker bind mounts can retain the old inode after an atomic replacement.
    # Preserve unchanged files so a dashboard-only update cannot detach the
    # Prometheus token/target mounts on Docker Desktop.
    if path.is_file() and path.read_bytes() == value.encode('utf-8'):
        path.chmod(0o444)
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.prepare-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(value)
        # Only the owner can traverse the 0700 parent. Individual read-only files
        # must be readable by the non-root Prometheus/Grafana containers.
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_aws_dashboard(runtime):
    source = ROOT/'observability/grafana/dashboards/ponto-certo.json'
    source_bytes = source.read_bytes()
    dashboard = json.loads(source_bytes)
    dashboard['title'] = dashboard['title']+' · AWS Academy'
    for link in dashboard.get('links', []):
        if link.get('url') == 'http://127.0.0.1:9090/alerts':
            link['url'] = 'http://127.0.0.1:9091/alerts'
    folder = runtime/'dashboards'
    if folder.is_symlink():
        raise ValueError('Refusing a symlink for the generated AWS dashboards.')
    folder.mkdir(exist_ok=True, mode=0o755)
    folder.chmod(0o755)
    generated = json.dumps(dashboard, ensure_ascii=False, indent=2)+'\n'
    write_mount_file(folder/'ponto-certo.json', generated)
    write_mount_file(runtime/'dashboard-provenance.json', json.dumps({
        'source': str(source.relative_to(ROOT)),
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'generated': 'dashboards/ponto-certo.json',
        'generated_sha256': hashlib.sha256(generated.encode()).hexdigest(),
        'changes': ['title identifies AWS Academy', 'Prometheus alert link uses port9091'],
        'panels_queries_and_uid_unchanged': True,
        'note': 'Public display metadata only; no credentials or target answers.'
    }, indent=2)+'\n')


def configure(public_url, token_file, runtime_dir=DEFAULT_RUNTIME, replace_target=False):
    collector = evidence_module()
    origin = collector.origin_url(public_url)
    runtime = outside_checkout(runtime_dir)
    token = read_private_token(token_file)
    metadata = runtime/'target.json'
    if metadata.exists():
        previous = json.loads(metadata.read_text(encoding='utf-8'))
        if previous.get('public_url') != origin and not replace_target:
            raise ValueError('AWS target changed. Preserve evidence first and use --replace-target explicitly; mixed history is rejected for 10 minutes.')
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    runtime.chmod(0o700)
    write_aws_dashboard(runtime)
    labels = {'application': 'ponto-certo', 'environment': 'public'}
    host = origin.removeprefix('https://')
    write_mount_file(runtime/'metrics-token', token+'\n')
    password = runtime/'grafana-admin-password'
    if not password.exists():
        write_mount_file(password, secrets.token_urlsafe(32)+'\n')
    elif password.is_symlink():
        raise ValueError('Refusing a symlink for the AWS Grafana password.')
    write_mount_file(runtime/'metrics-targets.json', json.dumps([
        {'targets': [host], 'labels': dict(labels, __scheme__='https')}
    ], indent=2)+'\n')
    write_mount_file(runtime/'ready-targets.json', json.dumps([
        {'targets': [origin+'/readyz'], 'labels': labels}
    ], indent=2)+'\n')
    write_mount_file(metadata, json.dumps({
        'scope': 'configuration', 'provider': 'aws', 'public_url': origin,
        'compose_project': 'ponto-certo-monitoring-aws',
        'note': 'Prepared targets only. This script makes no network request and does not prove deployment or metrics.'
    }, indent=2)+'\n')
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Real AWS HTTPS origin, normally Terraform public_url')
    parser.add_argument('--metrics-token-file', required=True, type=Path,
                        help='Existing AWS token in an external owner-only file; never the Azure token')
    parser.add_argument('--runtime-dir', type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument('--replace-target', action='store_true', help='Explicitly retarget only AWS; mixed Prometheus history remains rejected')
    args = parser.parse_args()
    try:
        runtime = configure(args.url, args.metrics_token_file, args.runtime_dir, args.replace_target)
    except (OSError, ValueError, KeyError, TypeError):
        print('AWS monitor configuration failed. Check HTTPS origin, absolute external paths, private token permissions and explicit target replacement. No credential was printed.', file=sys.stderr)
        return 2
    print('Prepared AWS monitor configuration only; Azure monitor and source credential were unchanged.')
    print('AWS Grafana user: admin; password remains in the private AWS runtime.')
    print('After verifying the deployed AWS URL, start only this stack:')
    print('PC_AWS_MONITORING_DIR='+shlex.quote(str(runtime))+' docker compose -f compose.monitoring.aws.yaml up -d --force-recreate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
