"""Doctor-side setup repair and journal reconciliation (Batch B8, T8.3).

Division of labor (doc 27 §6.1, one authority):

- **Boot** reads the stored stamp + size — the fast path.
- **``doctor setup``** performs the deep re-hash of every stamped
  artifact against its verified manifest, applies targeted repair
  (re-acquire corrupt artifacts), and reconciles a hand-corrupted
  journal from filesystem reality.

The journal is a replay log, never truth: reconciliation rebuilds it
from what is actually on disk (artifact bytes + manifest hashes), so a
garbled or lying journal cannot make an artifact look installed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from astrid.core.model_setup import journal as jrn
from astrid.core.model_setup.manifest import (
    DistributionManifest,
    ManifestError,
    load_manifest,
)


@dataclass(frozen=True)
class RepairReport:
    """What ``doctor setup`` observed and did, per artifact."""

    artifact_id: str
    verdict: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "verdict": self.verdict,
            "detail": self.detail,
        }


def stored_manifests(projects_root: str | Path) -> dict[str, DistributionManifest]:
    """Load every signature-verified manifest in the setup store."""
    manifests: dict[str, DistributionManifest] = {}
    directory = jrn.manifests_dir(projects_root)
    if not directory.is_dir():
        return manifests
    for path in sorted(directory.glob("*.json")):
        try:
            manifest = load_manifest(path)
        except ManifestError:
            continue  # untrusted manifests are invisible to repair
        manifests[manifest.artifact_id] = manifest
    return manifests


def reconcile_journal(projects_root: str | Path) -> list[RepairReport]:
    """Rebuild a corrupted journal from filesystem truth.

    Hand-corruption fixture leg: when the log contains unparsable bytes,
    the valid prefix cannot be trusted to name installed-ness either.
    Truth is the artifact bytes + manifest stamps: for every known
    manifest, re-hash the installed file and rewrite one clean
    ``installed`` / ``corrupt`` / ``absent`` record; unknown files under
    ``artifacts/`` are reported as orphaned, never silently blessed.
    """
    root = Path(projects_root)
    snapshot = jrn.resolve_boot_state(root, write=False)
    manifests = stored_manifests(root)
    if not snapshot.corrupt:
        return []
    reports: list[RepairReport] = []
    # Start a fresh log: the old bytes are evidence only.
    jrn.journal_path(root).unlink(missing_ok=True)
    journal = jrn.SetupJournal(root)
    for artifact_id, manifest in sorted(manifests.items()):
        final = jrn.artifact_path(root, artifact_id)
        if final.is_file():
            digest, size = jrn._hash_file(final)
            if digest == manifest.sha256 and size == manifest.size:
                journal.append(artifact_id, "installed", sha256=digest, size=size)
                reports.append(
                    RepairReport(
                        artifact_id=artifact_id,
                        verdict="installed",
                        detail="reconciled from filesystem truth",
                    )
                )
                continue
            journal.append(artifact_id, "corrupt", reason="deep_hash_mismatch")
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="corrupt",
                    detail=f"deep hash mismatch (found {digest})",
                )
            )
        else:
            journal.append(artifact_id, "absent")
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="absent",
                    detail="no installed bytes on disk",
                )
            )
    artifacts = jrn.artifacts_dir(root)
    if artifacts.is_dir():
        for orphan in sorted(artifacts.glob("*")):
            if orphan.is_file() and orphan.name not in manifests:
                reports.append(
                    RepairReport(
                        artifact_id=orphan.name,
                        verdict="orphaned",
                        detail=(
                            "bytes on disk with no trusted manifest; provision "
                            "the manifest, then re-run 'astrid doctor setup'"
                        ),
                    )
                )
    return reports


def doctor_setup(
    projects_root: str | Path,
    *,
    acquire: Callable[[DistributionManifest], None] | None = None,
) -> list[RepairReport]:
    """Deep re-hash + targeted repair + journal reconciliation.

    ``acquire`` (setup-mode networking) is injected by the CLI wrapper so
    this module stays importable without network side effects; when it is
    None, corrupt artifacts are reported for targeted repair instead of
    re-downloaded.
    """
    root = Path(projects_root)
    # Reconciliation first: a hand-corrupted log must not steer repair.
    reports = reconcile_journal(root)
    reconciled = {report.artifact_id for report in reports}
    snapshot = jrn.resolve_boot_state(root, write=False)
    manifests = stored_manifests(root)
    journal = jrn.SetupJournal(root)
    for artifact_id, manifest in sorted(manifests.items()):
        if artifact_id in reconciled:
            continue
        final = jrn.artifact_path(root, artifact_id)
        state = snapshot.states.get(artifact_id)
        if state is None:
            continue  # unknown artifact ids are acquisition's business
        if state.phase == "corrupt":
            # Targeted repair of a known-corrupt artifact: re-acquire its
            # exact bytes via setup mode when networking is sanctioned.
            if acquire is None:
                reports.append(
                    RepairReport(
                        artifact_id=artifact_id,
                        verdict="corrupt",
                        detail=(
                            f"{artifact_id} is marked corrupt "
                            f"({state.reason}); run 'astrid doctor setup' "
                            "with network access to repair"
                        ),
                    )
                )
                continue
            try:
                acquire(manifest)
            except Exception as exc:  # noqa: BLE001 - surfaced in the report
                reports.append(
                    RepairReport(
                        artifact_id=artifact_id,
                        verdict="repair_failed",
                        detail=str(exc),
                    )
                )
                continue
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="repaired",
                    detail="re-acquired via setup mode",
                )
            )
            continue
        if state.phase != "installed":
            continue  # absent/in-flight artifacts are acquisition's business
        digest, size = jrn._hash_file(final)
        if digest == manifest.sha256 and size == manifest.size:
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="verified",
                    detail="deep re-hash matches the signed manifest",
                )
            )
            continue
        journal.append(artifact_id, "corrupt", reason="deep_hash_mismatch")
        if acquire is not None:
            try:
                acquire(manifest)
            except Exception as exc:  # noqa: BLE001 - surfaced in the report
                reports.append(
                    RepairReport(
                        artifact_id=artifact_id,
                        verdict="repair_failed",
                        detail=str(exc),
                    )
                )
                continue
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="repaired",
                    detail="re-acquired via setup mode",
                )
            )
        else:
            reports.append(
                RepairReport(
                    artifact_id=artifact_id,
                    verdict="corrupt",
                    detail=(
                        f"deep hash mismatch (found {digest}); run 'astrid "
                        "doctor setup' with network access to repair"
                    ),
                )
            )
    return reports


__all__ = [
    "RepairReport",
    "doctor_setup",
    "reconcile_journal",
    "stored_manifests",
]

