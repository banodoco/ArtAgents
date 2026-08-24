"""Batch B8 fixtures: ``doctor setup`` deep re-hash, targeted repair,
and journal reconciliation from filesystem reality (T8.3).

One authority: the journal is a replay log, never truth — a
hand-corrupted log cannot make an artifact look installed; doctor
rebuilds from artifact bytes + manifest stamps.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


from astrid.core import doctor
from astrid.core.model_setup.journal import (
    SetupJournal,
    artifact_path,
    journal_path,
    read_stamp,
)
from astrid.core.model_setup.repair import (
    doctor_setup,
    reconcile_journal,
    stored_manifests,
)

from tests.v10._setup_harness import (
    PAYLOAD,
    RangeOrigin,
    manifest_for,
    sha256_hex,
    store_manifest,
)

ARTIFACT = "doctor_bundle"


def _install(root: Path, content: bytes = PAYLOAD) -> None:
    """Simulate a completed install: manifest + bytes + stamp."""
    store_manifest(root, manifest_for(content, artifact_id=ARTIFACT))
    final = artifact_path(root, ARTIFACT)
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(content)
    SetupJournal(root).append(
        ARTIFACT, "installed", sha256=sha256_hex(content), size=len(content)
    )


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# Journal reconciliation from filesystem truth
# ---------------------------------------------------------------------------


def test_hand_corrupted_journal_is_reconciled_to_filesystem_truth(
    root: Path,
) -> None:
    _install(root)
    # Hand-corrupt the middle of the durable prefix.
    path = journal_path(root)
    lines = path.read_bytes().splitlines(keepends=True)
    lines.insert(0, b"\xff\xfe not json at all\n")
    lines.append(b"{}\n")
    path.write_bytes(b"".join(lines))
    assert SetupJournal(root).replay().corrupt is True

    reports = reconcile_journal(root)
    assert [r.verdict for r in reports] == ["installed"]
    assert reports[0].artifact_id == ARTIFACT
    # The rebuilt log folds clean and the stamp reads installed again.
    snapshot = SetupJournal(root).replay()
    assert snapshot.corrupt is False
    assert snapshot.states[ARTIFACT].phase == "installed"
    ok, missing = read_stamp(root, (ARTIFACT,))
    assert ok is True and missing == []


def test_reconciliation_reports_missing_and_orphaned_bytes(root: Path) -> None:
    _install(root)
    artifact_path(root, ARTIFACT).unlink()  # stamp claims install; no bytes
    orphan = artifact_path(root, "orphan_thing")
    orphan.write_bytes(b"I have no manifest")

    # Force corruption so reconciliation actually rebuilds.
    raw = journal_path(root).read_bytes()
    journal_path(root).write_bytes(b"garbage\n" + raw + b"\x00\x00\n")

    verdicts = {r.artifact_id: r.verdict for r in reconcile_journal(root)}
    assert verdicts[ARTIFACT] == "absent"
    assert verdicts["orphan_thing"] == "orphaned"


def test_reconciliation_skipped_when_journal_is_clean(root: Path) -> None:
    _install(root)
    assert reconcile_journal(root) == []
    # The clean log was left untouched (no rewrite churn).
    assert b'"seq":1,' in journal_path(root).read_bytes()


def test_untrusted_manifests_are_invisible_to_repair(root: Path) -> None:
    store_manifest(root, manifest_for(PAYLOAD, artifact_id=ARTIFACT))
    tampered = stored_manifests(root)
    # Signature verification filters: only trusted manifests load.
    assert ARTIFACT in tampered
    from astrid.core.model_setup.manifest import ManifestError, load_manifest

    path = root / ".astrid" / "setup" / "manifests" / f"{ARTIFACT}.json"
    payload = load_manifest(path).to_dict()
    payload["size"] = 1  # forge without re-signing
    import json

    path.write_text(json.dumps(payload))
    with pytest.raises(ManifestError):
        load_manifest(path)


# ---------------------------------------------------------------------------
# Deep re-hash + targeted repair
# ---------------------------------------------------------------------------


def test_deep_rehash_verifies_clean_install(root: Path) -> None:
    _install(root)
    reports = doctor_setup(root)
    assert [(r.artifact_id, r.verdict) for r in reports] == [
        (ARTIFACT, "verified")
    ]


def test_corrupted_bytes_reported_without_network(root: Path) -> None:
    _install(root)
    final = artifact_path(root, ARTIFACT)
    data = bytearray(final.read_bytes())
    data[0] ^= 0xFF  # same size, different bytes — invisible to boot stat
    final.write_bytes(bytes(data))

    reports = doctor_setup(root)
    assert reports[0].verdict == "corrupt"
    assert "deep hash mismatch" in reports[0].detail
    state = SetupJournal(root).replay().states[ARTIFACT]
    assert (state.phase, state.reason) == ("corrupt", "deep_hash_mismatch")


def test_targeted_repair_reacquires_via_setup_mode(root: Path) -> None:
    good = manifest_for(PAYLOAD, artifact_id=ARTIFACT)
    store_manifest(root, good)
    with RangeOrigin(payload=b"tainted" * 1024) as bad_origin:
        from astrid.core.model_setup.acquire import acquire_artifact

        with pytest.raises(Exception, match="fail the signed manifest"):
            acquire_artifact(good, root, bad_origin.url)

    def acquire(manifest) -> None:
        from astrid.core.model_setup.acquire import acquire_artifact

        with RangeOrigin() as origin:
            acquire_artifact(manifest, root, origin.url)

    reports = doctor_setup(root, acquire=acquire)
    assert [r.verdict for r in reports] == ["repaired"]
    assert artifact_path(root, ARTIFACT).read_bytes() == PAYLOAD
    state = SetupJournal(root).replay().states[ARTIFACT]
    assert state.phase == "installed"


# ---------------------------------------------------------------------------
# CLI surface: ``astrid doctor setup``
# ---------------------------------------------------------------------------


def test_doctor_cli_setup_exit_codes_and_json(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(root)
    assert doctor.main(["--json", "setup", "--projects-root", str(root)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["reports"][0]["verdict"] == "verified"

    # Corrupt bytes -> exit 1 with a typed report.
    final = artifact_path(root, ARTIFACT)
    final.write_bytes(b"drifted")
    assert doctor.main(["--json", "setup", "--projects-root", str(root)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["reports"][0]["verdict"] == "corrupt"



