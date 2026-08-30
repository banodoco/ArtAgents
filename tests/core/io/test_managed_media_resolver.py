from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from astrid.core.io.managed_media_resolver import (
    rebase_timeline_registry_managed_assets,
    resolve_owned_managed_media,
)
from astrid.core.io.media_import import managed_media_path


class _RuntimeMedia:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.projects: list[str] = []

    def list(self, project: str) -> SimpleNamespace:
        self.projects.append(project)
        return SimpleNamespace(ok=True, data=self.rows)


class _RuntimeClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.media = _RuntimeMedia(rows)


def _managed_fixture(tmp_path: Path) -> tuple[Path, str, _RuntimeClient]:
    root = tmp_path / "projects"
    payload = b"runtime-admitted managed bytes"
    digest = hashlib.sha256(payload).hexdigest()
    locator = managed_media_path(root, digest)
    locator.parent.mkdir(parents=True)
    locator.write_bytes(payload)
    client = _RuntimeClient(
        [
            {
                "object_id": f"sha256:{digest}",
                "digest": f"sha256:{digest}",
                "media_type": "image/png",
                "size": len(payload),
            }
        ]
    )
    return root, digest, client


def test_resolution_uses_project_scoped_runtime_media_and_verifies_cas_bytes(
    tmp_path: Path,
) -> None:
    root, digest, client = _managed_fixture(tmp_path)

    resolved = resolve_owned_managed_media(
        projects_root=root,
        project_ref="demo",
        content_hash=digest,
        runtime_client=client,
    )

    assert resolved == managed_media_path(root, digest).resolve()
    assert client.media.projects == ["demo"]


def test_resolution_rejects_runtime_managed_locator_that_is_not_current_cas(
    tmp_path: Path,
) -> None:
    root, digest, _client = _managed_fixture(tmp_path)
    client = _RuntimeClient(
        [
            {
                "digest": digest,
                "media_type": "image/png",
                "locations": [
                    {"realm": "managed_local", "locator": str(tmp_path / "other")}
                ],
            }
        ]
    )
    assert (
        resolve_owned_managed_media(
            projects_root=root,
            project_ref="demo",
            content_hash=digest,
            runtime_client=client,
        )
        is None
    )


def test_resolution_fails_closed_without_runtime_admission_or_after_tamper(
    tmp_path: Path,
) -> None:
    root, digest, _client = _managed_fixture(tmp_path)
    locator = managed_media_path(root, digest)

    # A local CAS file, even with a valid digest-shaped path, is not authority
    # by itself.  This is the important no-SQLite/no-offline-fallback boundary.
    assert (
        resolve_owned_managed_media(
            projects_root=root,
            project_ref="demo",
            content_hash=digest,
        )
        is None
    )

    locator.write_bytes(b"tampered")
    client = _RuntimeClient([{"digest": digest, "media_type": "image/png"}])
    assert (
        resolve_owned_managed_media(
            projects_root=root,
            project_ref="demo",
            content_hash=digest,
            runtime_client=client,
        )
        is None
    )


def test_rebase_uses_admitted_runtime_snapshot_and_preserves_input(
    tmp_path: Path,
) -> None:
    root, digest, _client = _managed_fixture(tmp_path)
    stale = tmp_path / "old-root" / ".astrid" / "media" / "sha256" / digest[:2] / digest[2:4] / digest
    registry = {"assets": {"frame": {"file": str(stale), "content_sha256": digest}}}
    snapshot = [{"object_id": f"sha256:{digest}", "media_type": "image/png"}]

    rebased = rebase_timeline_registry_managed_assets(
        registry,
        projects_root=root,
        project_ref="demo",
        media_snapshot=snapshot,
    )

    assert registry["assets"]["frame"]["file"] == str(stale)
    assert rebased["assets"]["frame"]["file"] == str(managed_media_path(root, digest))


def test_media_id_snapshot_resolves_type_without_local_authority(tmp_path: Path) -> None:
    root, digest, _client = _managed_fixture(tmp_path)
    registry = {"assets": {"frame": {"media_id": "legacy-media", "content_sha256": digest}}}

    rebased = rebase_timeline_registry_managed_assets(
        registry,
        projects_root=root,
        project_ref="demo",
        media_snapshot={
            "legacy-media": {"digest": digest, "media_type": "image/png"}
        },
    )

    assert rebased["assets"]["frame"]["file"] == str(managed_media_path(root, digest))
    assert rebased["assets"]["frame"]["type"] == "image/png"


def test_subprocess_import_does_not_load_sqlite_or_local_authority() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import astrid.core.io.managed_media_resolver; "
            "print('sqlite3' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "False"
