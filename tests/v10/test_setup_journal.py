"""Batch B8 named fixtures: crash-resumable setup acquisition.

Every kill-mid-* fixture hard-dies a real child process at a durable
journal boundary (``os._exit`` via ``ASTRID_SETUP_KILL_BOUNDARY``) and
proves the parent resumes from recorded state against a real
Range-capable HTTP origin. The journal is a replay log, never truth:
filesystem reality wins at every resume.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.core.model_setup.acquire import (
    AcquisitionError,
    acquire_artifact,
)
from astrid.core.model_setup.journal import (
    SetupJournal,
    artifact_path,
    journal_path,
    part_path,
    read_stamp,
    resolve_boot_state,
    staged_path,
)
from astrid.core.model_setup.preflight import DiskPreflightError
from tests.v10._setup_harness import (
    PAYLOAD,
    RangeOrigin,
    manifest_for,
    sha256_hex,
    store_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = "test_bundle"


# ---------------------------------------------------------------------------
# Child entry point: die hard at a named journal boundary.
# ---------------------------------------------------------------------------


def _run_child(boundary: str, manifest_file: Path, root: Path, url: str):
    env = dict(os.environ)
    env["ASTRID_SETUP_KILL_BOUNDARY"] = boundary
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child-acquire",
            str(manifest_file),
            str(root),
            url,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO_ROOT),
        env=env,
    )


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--child-acquire":
    from astrid.core.model_setup.manifest import load_manifest

    _manifest = load_manifest(sys.argv[2])
    acquire_artifact(_manifest, sys.argv[3], sys.argv[4])
    sys.exit(0)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def origin():
    with RangeOrigin() as origin:
        yield origin


@pytest.fixture()
def signed(root: Path):
    """A signed stored manifest over the canonical payload."""
    manifest = manifest_for(PAYLOAD, artifact_id=ARTIFACT)
    return manifest, store_manifest(root, manifest)


# ---------------------------------------------------------------------------
# Journal primitives: fsync'd appends fold into per-artifact end-states.
# ---------------------------------------------------------------------------


def test_journal_replay_folds_state_machine_and_tolerates_torn_tail(
    root: Path,
) -> None:
    journal = SetupJournal(root)
    journal.append(ARTIFACT, "downloading", offset=0)
    journal.append(ARTIFACT, "downloading", offset=1024)
    journal.append(ARTIFACT, "verifying")
    journal.append(ARTIFACT, "staged")
    journal.append(ARTIFACT, "installed", sha256="abc", size=3)
    snapshot = journal.replay()
    assert snapshot.corrupt is False
    state = snapshot.states[ARTIFACT]
    assert (state.phase, state.sha256, state.size, state.offset) == (
        "installed",
        "abc",
        3,
        0,
    )
    # Torn final line (crash mid-append): ignored, prefix still folds.
    with open(journal_path(root), "ab") as handle:
        handle.write(b'{"schema":"astrid.setup_journal.v1","art')
    snapshot = journal.replay()
    assert snapshot.corrupt is False
    assert snapshot.states[ARTIFACT].phase == "installed"
    # Unparsable content INSIDE the durable prefix marks the log corrupt
    # (a garbage FINAL line would be a torn tail; mid-log is corruption).
    raw = journal_path(root).read_bytes()
    lines = raw.splitlines(keepends=True)
    lines.insert(2, b"\x00garbage-not-json\x00\n")
    lines.append(lines[0])
    journal_path(root).write_bytes(b"".join(lines))
    assert SetupJournal(root).replay().corrupt is True


def test_boot_replay_completes_interrupted_stage_rename(root: Path) -> None:
    """Kill-mid-rename leg (in-process): staged bytes present at boot are
    hash-verified and atomically promoted — the transaction completes."""
    journal = SetupJournal(root)
    staged = staged_path(root, ARTIFACT)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(PAYLOAD)
    journal.append(ARTIFACT, "downloading", offset=0)
    journal.append(ARTIFACT, "verifying")
    journal.append(ARTIFACT, "staged", sha256=sha256_hex(PAYLOAD), size=len(PAYLOAD))
    snapshot = resolve_boot_state(root)
    state = snapshot.states[ARTIFACT]
    assert state.phase == "installed"
    assert state.sha256 == sha256_hex(PAYLOAD)
    assert not staged.exists()
    final = artifact_path(root, ARTIFACT)
    assert final.read_bytes() == PAYLOAD
    # The completed transaction is durably journaled.
    assert SetupJournal(root).replay().states[ARTIFACT].phase == "installed"


def test_read_only_replay_does_not_advertise_staged_bytes(root: Path) -> None:
    journal = SetupJournal(root)
    staged = staged_path(root, ARTIFACT)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(PAYLOAD)
    journal.append(
        ARTIFACT,
        "staged",
        sha256=sha256_hex(PAYLOAD),
        size=len(PAYLOAD),
    )
    snapshot = resolve_boot_state(root, write=False)
    assert snapshot.states[ARTIFACT].phase == "staged"
    assert read_stamp(root, (ARTIFACT,))[0] is False


def test_boot_replay_promotion_refuses_drifted_staged_bytes(root: Path) -> None:
    journal = SetupJournal(root)
    staged = staged_path(root, ARTIFACT)
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(PAYLOAD + b"x")
    journal.append(ARTIFACT, "downloading", offset=0)
    journal.append(
        ARTIFACT,
        "staged",
        # The journal claims honest bytes; the staged file has drifted.
        sha256=sha256_hex(PAYLOAD),
        size=len(PAYLOAD),
    )
    snapshot = resolve_boot_state(root)
    state = snapshot.states[ARTIFACT]
    assert state.phase == "corrupt"
    assert state.reason == "staged_hash_mismatch"
    assert not artifact_path(root, ARTIFACT).exists()


def test_boot_replay_refreshes_download_offset_from_filesystem(
    root: Path,
) -> None:
    part = part_path(root, ARTIFACT)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(PAYLOAD[:777])
    journal = SetupJournal(root)
    journal.append(ARTIFACT, "downloading", offset=10)
    snapshot = resolve_boot_state(root)
    state = snapshot.states[ARTIFACT]
    assert state.phase == "downloading"
    assert state.offset == 777  # filesystem wins over the recorded offset


def test_installed_fast_path_is_stat_only_and_drift_flips_corrupt(
    root: Path,
) -> None:
    journal = SetupJournal(root)
    final = artifact_path(root, ARTIFACT)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(PAYLOAD)
    journal.append(ARTIFACT, "installed", sha256=sha256_hex(PAYLOAD), size=len(PAYLOAD))
    resolved = resolve_boot_state(root).states[ARTIFACT]
    assert resolved.phase == "installed"
    # Byte drift below the same size still passes boot's stat fast path;
    # deep re-hash is doctor's job, never boot's.
    final.write_bytes(bytes(range(255, -1, -1)) * 8192)
    resolved = resolve_boot_state(root).states[ARTIFACT]
    assert resolved.phase == "installed"
    # Size drift IS visible at boot and flips the stamp corrupt.
    smaller = manifest_for(b"tiny", artifact_id="tiny_bundle")
    store_manifest(root, smaller)
    tiny = artifact_path(root, "tiny_bundle")
    tiny.write_bytes(b"tiny!")
    tj = SetupJournal(root)
    tj.append("tiny_bundle", "installed", sha256=sha256_hex(b"tiny"), size=4)
    resolved = resolve_boot_state(root).states["tiny_bundle"]
    assert (resolved.phase, resolved.reason) == ("corrupt", "size_drift")


# ---------------------------------------------------------------------------
# Kill-mid-download / verify / rename against a REAL Range origin.
# ---------------------------------------------------------------------------


def test_kill_mid_download_resumes_from_recorded_offset_with_range(
    root: Path, origin: RangeOrigin, signed
) -> None:
    manifest, manifest_file = signed
    child = _run_child("after_download_append", manifest_file, root, origin.url)
    assert child.returncode == 79, child.stderr
    # One chunk landed; the journal holds the durable offset.
    part = part_path(root, ARTIFACT)
    assert part.stat().st_size == 1 << 20
    state = SetupJournal(root).replay().states[ARTIFACT]
    assert (state.phase, state.offset) == ("downloading", 1 << 20)
    assert not artifact_path(root, ARTIFACT).exists()

    result = acquire_artifact(manifest, root, origin.url)
    assert result.sha256 == sha256_hex(PAYLOAD)
    assert artifact_path(root, ARTIFACT).read_bytes() == PAYLOAD
    # Resume was a genuine HTTP Range request answered with 206; the
    # child's only request was the initial full download.
    assert origin.requests.count(("full", None)) == 1
    assert ("range", 1 << 20) in origin.requests
    assert SetupJournal(root).replay().states[ARTIFACT].phase == "installed"


def test_kill_mid_verify_resumes_at_eof_without_redownload(
    root: Path, origin: RangeOrigin, signed
) -> None:
    manifest, manifest_file = signed
    _run_child("after_verify_entry", manifest_file, root, origin.url)
    assert SetupJournal(root).replay().states[ARTIFACT].phase == "verifying"
    assert part_path(root, ARTIFACT).stat().st_size == len(PAYLOAD)
    assert origin.requests.count(("full", None)) == 1
    result = acquire_artifact(manifest, root, origin.url)
    assert result.sha256 == sha256_hex(PAYLOAD)
    # Boot demoted verifying→downloading at the real part length; the
    # origin saw exactly one Range request starting AT EOF (zero body).
    assert ("range", len(PAYLOAD)) in origin.requests
    assert artifact_path(root, ARTIFACT).read_bytes() == PAYLOAD


def test_kill_mid_rename_completes_without_network(
    root: Path, origin: RangeOrigin, signed
) -> None:
    manifest, manifest_file = signed
    child = _run_child("after_stage", manifest_file, root, origin.url)
    assert child.returncode == 79, child.stderr
    assert SetupJournal(root).replay().states[ARTIFACT].phase == "staged"
    assert staged_path(root, ARTIFACT).is_file()

    requests_before = len(origin.requests)
    result = acquire_artifact(manifest, root, origin.url)
    assert result.sha256 == sha256_hex(PAYLOAD)
    # The interrupted rename completed from staged bytes — no byte moved.
    assert len(origin.requests) == requests_before
    assert not staged_path(root, ARTIFACT).exists()
    assert artifact_path(root, ARTIFACT).read_bytes() == PAYLOAD


def test_hash_mismatch_refuses_fail_closed_then_targeted_repairs(
    root: Path, signed
) -> None:
    manifest, manifest_file = signed
    with RangeOrigin(payload=b"corrupted-bytes" * 4096) as bad_origin:
        with pytest.raises(AcquisitionError, match="fail the signed manifest"):
            acquire_artifact(manifest, root, bad_origin.url)
    state = SetupJournal(root).replay().states[ARTIFACT]
    assert (state.phase, state.reason) == ("corrupt", "hash_mismatch")
    assert not artifact_path(root, ARTIFACT).exists()

    # Targeted repair: re-run against honest bytes; the corrupt partial
    # is discarded and the download restarts cleanly.
    with RangeOrigin() as good_origin:
        result = acquire_artifact(manifest, root, good_origin.url)
    assert result.sha256 == sha256_hex(PAYLOAD)
    state = SetupJournal(root).replay().states[ARTIFACT]
    assert state.phase == "installed"


def test_disk_preflight_refuses_before_any_byte_moves(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import astrid.core.model_setup.preflight as preflight

    manifest = manifest_for(PAYLOAD, artifact_id=ARTIFACT)

    class _Full:
        total = 1 << 30
        used = 0
        free = 1024  # far below download + working + output headroom

    monkeypatch.setattr(preflight.shutil, "disk_usage", lambda _p: _Full())
    with RangeOrigin() as origin:
        with pytest.raises(DiskPreflightError, match="headroom"):
            acquire_artifact(manifest, root, origin.url)
    # No journal record, no partial file: refusal preceded every write.
    assert not journal_path(root).exists()
    assert not part_path(root, ARTIFACT).exists()
