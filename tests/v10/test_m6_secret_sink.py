"""Secret-sink tests for the m6 operational surface (serve/backup/doctor).

Proves the m6 sprint-plan Phase 5 "secret sink" contract:

* ``create_backup`` drops ``.env`` and secret-bearing paths from the managed
  media copy, and a sentinel secret value (``ASTRID_TEST_SECRET=canary``)
  never appears anywhere inside the backup directory (not in the media copy,
  not in the SQLite snapshot, not in ``backup.json``);
* ``build_child_subprocess_env`` never carries provider/credential or
  account/cloud environment variables into a child process environment —
  neither from an explicit base mapping nor from the live host environment
  (reuses the canonical ``PROVIDER_ENV_VARS`` and ``ACCOUNT_CLOUD_ENV_VARS``
  tables from ``tests/sdk/test_zero_secret_smoke.py``);
* the eight-family help text (product help plus the entrypoint banner)
  references no provider/cloud/account variable names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.application import compose_standard_application
from astrid.core.backup import create_backup
from astrid.core.gateway.help import _print_entrypoint_help, _product_help_text
from astrid.core.subprocess_env import build_child_subprocess_env
from tests.sdk.test_zero_secret_smoke import (
    ACCOUNT_CLOUD_ENV_VARS,
    PROVIDER_ENV_VARS,
)

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

# The sentinel secret value that must never reach a backup directory.
SENTINEL = "ASTRID_TEST_SECRET=canary"


def _seed_project(root: Path) -> None:
    """Create one demo project plus one managed media file under *root*."""
    with compose_standard_application(projects_root=root) as app:
        project = app.projects_service.create(
            slug="demo", name="Demo", idempotency_key="p1"
        )
        assert project.ok, project.error
        media_path = root / "shot.png"
        media_path.write_bytes(_PNG_BYTES)
        media = app.media_service.import_file(
            project="demo", path=media_path, idempotency_key="m1"
        )
        assert media.ok, media.error


def _all_backup_bytes(backup: Path) -> bytes:
    """Concatenate every file inside *backup* (including the SQLite snapshot)."""
    return b"".join(p.read_bytes() for p in backup.rglob("*") if p.is_file())


# ---------------------------------------------------------------------------
# Backup media copy: .env and secret-bearing paths never cross the sink
# ---------------------------------------------------------------------------


def test_backup_media_copy_excludes_env_and_secret_bearing_paths(
    tmp_path: Path,
) -> None:
    _seed_project(tmp_path)
    media_root = tmp_path / ".astrid" / "media"

    (media_root / ".env").write_text(f"{SENTINEL}\n", encoding="utf-8")
    (media_root / ".env.local").write_text(f"OPENAI_API_KEY={SENTINEL}\n", encoding="utf-8")
    (media_root / "credentials.json").write_text(
        f'{{"token": "{SENTINEL}"}}\n', encoding="utf-8"
    )
    (media_root / "client_secret.txt").write_text(f"{SENTINEL}\n", encoding="utf-8")
    (media_root / "id_rsa.pem").write_text(f"{SENTINEL}\n", encoding="utf-8")
    secrets_dir = media_root / "secrets"
    secrets_dir.mkdir(exist_ok=True)
    (secrets_dir / "auth_token.bin").write_text(f"{SENTINEL}\n", encoding="utf-8")

    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)
    dest_media = dest / "media"

    copied_names = {p.name for p in dest_media.rglob("*") if p.is_file()}
    assert ".env" not in copied_names
    assert ".env.local" not in copied_names
    assert "credentials.json" not in copied_names
    assert "client_secret.txt" not in copied_names
    assert "id_rsa.pem" not in copied_names
    assert "auth_token.bin" not in copied_names


def test_backup_directory_never_contains_sentinel_secret_value(
    tmp_path: Path,
) -> None:
    _seed_project(tmp_path)
    media_root = tmp_path / ".astrid" / "media"
    (media_root / ".env").write_text(f"{SENTINEL}\n", encoding="utf-8")
    (media_root / "my_secret.txt").write_text(f"{SENTINEL}\n", encoding="utf-8")

    dest = tmp_path / "backup"
    create_backup(projects_root=tmp_path, dest_path=dest)

    blob = _all_backup_bytes(dest)
    assert SENTINEL.encode("utf-8") not in blob
    assert b"canary" not in blob


# ---------------------------------------------------------------------------
# Child subprocess environment: provider/credential/account vars never leak
# ---------------------------------------------------------------------------


def test_build_child_subprocess_env_excludes_provider_and_account_cloud_vars() -> None:
    base = {
        "PATH": "/bin",
        "HOME": "/tmp/home",
        **{name: f"canary-{name.lower()}" for name in PROVIDER_ENV_VARS},
        **{name: f"canary-{name.lower()}" for name in ACCOUNT_CLOUD_ENV_VARS},
    }

    env = build_child_subprocess_env(base=base, parent={})

    # The allowlist keeps only known-safe process variables; every provider
    # and account/cloud variable must be absent from the child environment.
    assert set(PROVIDER_ENV_VARS).isdisjoint(env)
    assert set(ACCOUNT_CLOUD_ENV_VARS).isdisjoint(env)
    # Positive control: the safe base variables still survive the filter.
    assert env["PATH"] == "/bin"
    assert env["HOME"] == "/tmp/home"


def test_build_child_subprocess_env_default_base_never_leaks_host_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in PROVIDER_ENV_VARS + ACCOUNT_CLOUD_ENV_VARS:
        monkeypatch.setenv(name, f"canary-{name.lower()}")

    env = build_child_subprocess_env(base={}, parent={})

    assert set(PROVIDER_ENV_VARS).isdisjoint(env)
    assert set(ACCOUNT_CLOUD_ENV_VARS).isdisjoint(env)


# ---------------------------------------------------------------------------
# Eight-family help text: provider/cloud/account names never advertised
# ---------------------------------------------------------------------------


def test_product_help_text_references_no_provider_cloud_account_vars() -> None:
    text = _product_help_text()
    for name in PROVIDER_ENV_VARS + ACCOUNT_CLOUD_ENV_VARS:
        assert name not in text, f"help text advertises {name}"


def test_entrypoint_help_references_no_provider_cloud_account_vars(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _print_entrypoint_help()
    text = capsys.readouterr().out
    for name in PROVIDER_ENV_VARS + ACCOUNT_CLOUD_ENV_VARS:
        assert name not in text, f"entrypoint help advertises {name}"
