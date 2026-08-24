"""Crash-resumable artifact acquisition (Batch B8, doc 27 §6.1).

The ONLY sanctioned outbound networking in the product lives here:
explicit setup mode. Task execution never imports this module.

Pipeline per artifact, journaled at every transition:

    absent -> downloading(offset) -> verifying -> staged -> installed(verified)

- Download: HTTP ``Range: bytes=<offset>-`` resume into
  ``<setup>/tmp/<id>.part`` from the boot-replayed offset; the offset is
  fsync-journaled after every chunk so a kill mid-download resumes from
  recorded progress.
- Verifying: stream SHA-256 over the complete ``.part`` against the
  signed manifest hash. Mismatch → ``corrupt(hash_mismatch)``, typed
  refusal — never a silent retry loop.
- Staging: same-filesystem rename to ``<id>.staged``.
- Installing: atomic rename to ``artifacts/<id>`` + directory fsync +
  ``installed(sha256,size)`` stamp.

Kill-mid-download / kill-mid-verify / kill-mid-rename are observable at
the named :data:`journal.KILL_BOUNDARIES` via
``ASTRID_SETUP_KILL_BOUNDARY``; :func:`journal.resolve_boot_state`
replays and completes or resumes each one.
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from astrid.core.model_setup import journal as jrn
from astrid.core.model_setup.manifest import DistributionManifest
from astrid.core.model_setup.preflight import require_disk

CHUNK_SIZE = 1 << 20
"""Download chunk size; each chunk boundary journals the new offset."""


class AcquisitionError(RuntimeError):
    """Typed failure for setup acquisition (hash mismatch, network)."""


class _HashMismatch(AcquisitionError):
    """Internal marker carrying the found digest for corrupt journaling."""

    def __init__(self, found: str) -> None:
        super().__init__(f"hash mismatch: found {found}")
        self.found = found


@dataclass(frozen=True)
class AcquisitionResult:
    """Outcome of one completed acquisition."""

    artifact_id: str
    path: Path
    sha256: str
    size: int


def acquire_artifact(
    manifest: DistributionManifest,
    projects_root: str | Path,
    url: str,
    *,
    urlopen: Callable[..., object] | None = None,
) -> AcquisitionResult:
    """Acquire one manifest-described artifact, crash-resumably.

    ``urlopen`` is injectable so fixtures serve deterministic bytes
    without real networking; production uses
    :func:`urllib.request.urlopen`. The manifest's signature must already
    be verified by the caller (:func:`manifest.load_manifest` refuses
    untrusted manifests).
    """
    root = Path(projects_root)
    artifact_id = manifest.artifact_id
    final = jrn.artifact_path(root, artifact_id)

    # Disk preflight BEFORE any byte moves (download + working + output).
    require_disk(jrn.setup_dir(root), manifest.size)

    state = jrn.resolve_boot_state(root).states.get(
        artifact_id, jrn.ArtifactState(artifact=artifact_id)
    )
    journal = jrn.SetupJournal(root)

    if state.phase == "installed":
        return AcquisitionResult(
            artifact_id=artifact_id,
            path=final,
            sha256=state.sha256 or "",
            size=state.size or 0,
        )

    part = jrn.part_path(root, artifact_id)
    offset = _resume_offset(state, part)
    if state.phase == "corrupt" and state.reason == "hash_mismatch":
        # Targeted repair starts over: the partial bytes failed verify.
        offset = 0
        journal.append(artifact_id, "repairing")
        if part.exists():
            part.unlink()
    elif state.phase == "corrupt" or state.phase == "repairing":
        journal.append(artifact_id, "repairing")
        offset = 0
        if part.exists():
            part.unlink()
    journal.append(artifact_id, "downloading", offset=offset)

    offset = _download(manifest, url, part, offset, journal, urlopen=urlopen)

    journal.append(artifact_id, "verifying")
    jrn.kill_boundary("after_verify_entry")
    try:
        digest, size = _verify(part, manifest)
    except _HashMismatch as exc:
        journal.append(artifact_id, "corrupt", reason="hash_mismatch")
        raise AcquisitionError(
            f"{artifact_id}: downloaded bytes fail the signed manifest "
            f"hash (found {exc.found}, expected {manifest.sha256})"
        ) from None
    if size != manifest.size:
        journal.append(artifact_id, "corrupt", reason="size_mismatch")
        raise AcquisitionError(
            f"{artifact_id}: downloaded size {size} does not match "
            f"manifest size {manifest.size}"
        )

    staged = jrn.staged_path(root, artifact_id)
    journal.append(artifact_id, "staged", sha256=digest, size=size)
    os.replace(part, staged)
    jrn._fsync_directory(staged.parent)
    jrn.kill_boundary("after_stage")

    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged, final)
    jrn._fsync_directory(final.parent)
    journal.append(artifact_id, "installed", sha256=digest, size=size)
    jrn.kill_boundary("after_install_rename")

    return AcquisitionResult(
        artifact_id=artifact_id, path=final, sha256=digest, size=size
    )


def _resume_offset(state: jrn.ArtifactState, part: Path) -> int:
    """Filesystem wins over the journal: resume from real bytes on disk."""
    if state.phase == "downloading" and state.offset:
        return state.offset
    if part.is_file():
        return part.stat().st_size
    return 0


def _download(
    manifest: DistributionManifest,
    url: str,
    part: Path,
    offset: int,
    journal: jrn.SetupJournal,
    *,
    urlopen: Callable[..., object] | None,
) -> int:
    """Range-resume the download, journaling the offset after each chunk."""
    opener = urlopen or urllib.request.urlopen
    part.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url)
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with opener(request) as response:  # type: ignore[operator]
        status = getattr(response, "status", 200)
        if offset and status == 200:
            # Server ignored Range: restart cleanly rather than append.
            offset = 0
            part.write_bytes(b"")
        elif offset and status != 206:
            raise AcquisitionError(
                f"{manifest.artifact_id}: server refused Range resume "
                f"(status {status}, offset {offset})"
            )
        with open(part, "ab") as handle:
            while True:
                block = response.read(CHUNK_SIZE)  # type: ignore[attr-defined]
                if not block:
                    break
                handle.write(block)
                handle.flush()
                offset += len(block)
                journal.append(manifest.artifact_id, "downloading", offset=offset)
                jrn.kill_boundary("after_download_append")
    return offset


def _verify(part: Path, manifest: DistributionManifest) -> tuple[str, int]:
    """Deep-hash the downloaded bytes against the signed manifest."""
    digest, size = jrn._hash_file(part)
    if digest != manifest.sha256:
        raise _HashMismatch(digest)
    return digest, size
