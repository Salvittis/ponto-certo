"""Bind-mount regression checks using only temporary files and synthetic data."""
import importlib.util
from pathlib import Path
import stat

import pytest


spec = importlib.util.spec_from_file_location(
    'monitoring_config', Path(__file__).resolve().parents[1]/'scripts/configure-monitoring-aws.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def test_unchanged_mount_file_preserves_inode_and_normalizes_permissions(tmp_path):
    path = tmp_path/'mount-file'
    config.write_mount_file(path, 'synthetic-content\n')
    before = path.stat()
    path.chmod(0o600)

    config.write_mount_file(path, 'synthetic-content\n')

    after = path.stat()
    assert after.st_ino == before.st_ino
    assert after.st_mtime_ns == before.st_mtime_ns
    assert path.read_text() == 'synthetic-content\n'
    assert stat.S_IMODE(after.st_mode) == 0o444


def test_changed_mount_file_is_replaced_atomically(tmp_path):
    path = tmp_path/'mount-file'
    config.write_mount_file(path, 'previous-content\n')
    before = path.stat()
    with path.open() as mounted_file:
        config.write_mount_file(path, 'updated-content\n')
        assert mounted_file.read() == 'previous-content\n'
    assert path.stat().st_ino != before.st_ino
    assert path.read_text() == 'updated-content\n'
    assert stat.S_IMODE(path.stat().st_mode) == 0o444
    assert not list(tmp_path.glob('.prepare-*'))


def test_symlink_is_rejected_even_when_content_matches(tmp_path):
    target = tmp_path/'target'
    target.write_text('synthetic-content\n')
    target.chmod(0o600)
    link = tmp_path/'mount-link'
    link.symlink_to(target)

    with pytest.raises(ValueError, match='symlink'):
        config.write_mount_file(link, 'synthetic-content\n')

    assert link.is_symlink()
    assert target.read_text() == 'synthetic-content\n'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
