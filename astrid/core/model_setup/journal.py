"""Sidecar setup journal (Batch B8, doc 27 §6.1, E5).

The setup journal is a crash-resumable **replay log, never truth**. It
lives at ``<root>/.astrid/setup/journal.jsonl`` — a plain fsync'd JSONL
append file, deliberately *not* product SQLite: setup runs pre-DB, so a
migration-backed journal would force creating the product database during
legitimate absence.

Per-artifact state machine (doc 27 §6.1):

    absent -> downloading(offset) -> verifying -> staged -> installed(verified)
                    \\-> corrupt(reason) -> repairing ------------------^

One authority: installed-ness is proven by artifact bytes + manifest
stamps + SQLite advertisement. The journal only records operational
progress; :func:`resolve_boot_state` reconciles every dangling
transaction against filesystem reality at boot (before
``derive_database_path``), and ``doctor setup`` rebuilds the whole log
from filesystem truth when the file itself is corrupted.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

JOURNAL_SCHEMA = "astrid.setup_journal.v1"
"""Durable schema marker on every journal record."""

MANAGED_DIR_NAME = ".astrid"
SETUP_DIR_NAME = "setup"
JOURNAL_NAME = "journal.jsonl"
ARTIFACTS_DIR_NAME = "artifacts"
MANIFESTS_DIR_NAME = "manifests"
TMP_DIR_NAME = "tmp"
PART_SUFFIX = ".part"
STAGED_SUFFIX = ".staged"

KILL_BOUNDARY_ENV = "ASTRID_SETUP_KILL_BOUNDARY"
"""When set to a boundary name, the process hard-dies at that boundary."""

RUNTIME_LOG_ENV = "ASTRID_SETUP_RUNTIME_LOG"
"""Optional child-process runtime log recording fired boundaries."""

# Observable hard-death boundaries used by the kill-mid-* fixtures.
KILL_BOUNDARIES = (
    "after_download_append",
    "after_verify_entry",
    "after_stage",
    "after_install_rename",
)
"""Named boundaries where an interrupted setup may be observed."""


class SetupJournalError(RuntimeError):
    """Typed failure for unrecoverable journal misuse."""


@dataclass(frozen=True, slots=True)
class ArtifactState:
    """Replayed end-state of one setup artifact."""

    artifact: str
    #: absent | downloading | verifying | staged | installed | corrupt |
    #: repairing
    phase: str = "absent"
    #: Resume offset for ``downloading`` (bytes already on disk).
    offset: int = 0
    #: Verified content digest recorded by the ``installed`` event.
    sha256: str | None = None
    #: Verified byte size recorded by the ``installed`` event.
    size: int | None = None
    #: Reason string carried by ``corrupt``.
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"artifact": self.artifact, "phase": self.phase}
        if self.offset:
            payload["offset"] = self.offset
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        if self.size is not None:
            payload["size"] = self.size
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class JournalSnapshot:
    """Replay result: per-artifact states plus the log's own health."""

    states: dict[str, ArtifactState]
    #: True when unparsable bytes were found — the log needs doctor
    #: reconciliation; boot still proceeds on the valid prefix.
    corrupt: bool
    #: Number of valid records consumed.
    records: int


def setup_dir(projects_root: str | Path) -> Path:
    """The sidecar setup directory under the managed-data root."""
    return Path(projects_root) / MANAGED_DIR_NAME / SETUP_DIR_NAME


def journal_path(projects_root: str | Path) -> Path:
    """The fsync'd replay-log path."""
    return setup_dir(projects_root) / JOURNAL_NAME


def artifacts_dir(projects_root: str | Path) -> Path:
    """Final install root: ``<root>/.astrid/setup/artifacts/<id>``."""
    return setup_dir(projects_root) / ARTIFACTS_DIR_NAME


def manifests_dir(projects_root: str | Path) -> Path:
    """Verified distribution-manifest store."""
    return setup_dir(projects_root) / MANIFESTS_DIR_NAME


def tmp_dir(projects_root: str | Path) -> Path:
    """Scratch directory for partial downloads (same filesystem)."""
    return setup_dir(projects_root) / TMP_DIR_NAME


def artifact_path(projects_root: str | Path, artifact_id: str) -> Path:
    """Final installed path of one artifact id."""
    _validate_artifact_id(artifact_id)
    return artifacts_dir(projects_root) / artifact_id


def part_path(projects_root: str | Path, artifact_id: str) -> Path:
    """Partial-download path (Range resume target)."""
    _validate_artifact_id(artifact_id)
    return tmp_dir(projects_root) / f"{artifact_id}{PART_SUFFIX}"


def staged_path(projects_root: str | Path, artifact_id: str) -> Path:
    """Same-filesystem staged path awaiting the atomic rename."""
    _validate_artifact_id(artifact_id)
    return tmp_dir(projects_root) / f"{artifact_id}{STAGED_SUFFIX}"


def _validate_artifact_id(artifact_id: str) -> None:
    """Reject ids that could escape the setup artifact directories.

    Manifest ids are signed, but a valid signature does not make a path safe:
    the release key may sign an accidentally malformed id and direct callers
    can construct a manifest without parsing it. Keep ids as single filename
    components on every platform; colons remain allowed because built-in
    parameterized weight ids use them.
    """
    from pathlib import PureWindowsPath

    if (
        not isinstance(artifact_id, str)
        or not artifact_id
        or artifact_id in {".", ".."}
        or "/" in artifact_id
        or "\\" in artifact_id
        or Path(artifact_id).is_absolute()
        or PureWindowsPath(artifact_id).is_absolute()
        or PureWindowsPath(artifact_id).drive
    ):
        raise SetupJournalError(
            f"unsafe setup artifact id {artifact_id!r}; expected one filename"
        )


def _fsync_directory(path: Path) -> None:
    """Durably record a directory entry where the platform supports it."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _runtime_log(boundary: str) -> None:
    """Record one boundary in the optional child-process runtime log."""
    log = os.environ.get(RUNTIME_LOG_ENV)
    if not log:
        return
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(f"{boundary}\n")
        handle.flush()
        os.fsync(handle.fileno())


def kill_boundary(boundary: str) -> None:
    """Expose a durable boundary and optionally hard-kill the process.

    Cloned from the proven ``core/backup/operations.py`` seam: fixtures
    set ``ASTRID_SETUP_KILL_BOUNDARY`` to the boundary name and the
    process dies with ``os._exit`` after the journaled append is fsync'd,
    producing a real crash mid-transaction.
    """
    _runtime_log(boundary)
    if os.environ.get(KILL_BOUNDARY_ENV) == boundary:
        os._exit(79)  # noqa: PLR1722 - intentional hard-death test seam


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SetupJournal:
    """Fsync'd JSONL appender over one setup journal."""

    def __init__(self, projects_root: str | Path) -> None:
        self._path = journal_path(projects_root)
        self._seq = 0
        # Replay first so appended sequences continue the durable order.
        self._seq = self.replay().records

    @property
    def path(self) -> Path:
        return self._path

    def append(self, artifact: str, event: str, **fields: Any) -> None:
        """Append one fsync'd transition record for *artifact*."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "schema": JOURNAL_SCHEMA,
            "seq": self._seq + 1,
            "ts": _utc_now(),
            "artifact": artifact,
            "event": event,
        }
        record.update(fields)
        line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        created = not self._path.exists()
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        if created:
            _fsync_directory(self._path.parent)
        self._seq += 1

    def replay(self) -> JournalSnapshot:
        """Fold the log into per-artifact end-states.

        Tolerant by construction: a torn final line (crash mid-append) is
        ignored; unparsable content inside the durable prefix marks the
        log ``corrupt`` — never truth, so boot proceeds on the valid
        prefix and ``doctor setup`` rebuilds from filesystem reality.
        """
        states: dict[str, ArtifactState] = {}
        corrupt = False
        records = 0
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return JournalSnapshot(states={}, corrupt=False, records=0)
        lines = raw.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        for index, line in enumerate(lines):
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record must be an object")
                if record.get("schema") != JOURNAL_SCHEMA:
                    raise ValueError("record schema mismatch")
                artifact = record["artifact"]
                event = record["event"]
                _validate_artifact_id(artifact)
                if not isinstance(event, str):
                    raise ValueError("event must be a string")
            except (json.JSONDecodeError, UnicodeDecodeError):
                if index == len(lines) - 1:
                    break  # torn tail from a crash mid-append
                corrupt = True
                continue
            except (ValueError, KeyError, TypeError, SetupJournalError):
                # A complete JSON object with bad fields/schema is corruption,
                # including at the tail. Only an unparseable final line can be
                # the expected crash-torn append.
                corrupt = True
                continue
            records += 1
            prior = states.get(artifact, ArtifactState(artifact=artifact))
            try:
                if event == "absent":
                    states[artifact] = ArtifactState(artifact=artifact)
                elif event == "downloading":
                    offset = record.get("offset", 0)
                    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                        raise ValueError("offset must be a non-negative integer")
                    states[artifact] = replace(
                        prior, phase="downloading", offset=offset
                    )
                elif event == "verifying":
                    states[artifact] = replace(prior, phase="verifying")
                elif event == "staged":
                    size = record.get("size", prior.size)
                    if size is not None and (
                        isinstance(size, bool) or not isinstance(size, int) or size < 0
                    ):
                        raise ValueError("size must be a non-negative integer")
                    sha256 = record.get("sha256", prior.sha256)
                    if sha256 is not None and not isinstance(sha256, str):
                        raise ValueError("sha256 must be a string")
                    states[artifact] = replace(
                        prior, phase="staged", sha256=sha256, size=size
                    )
                elif event == "installed":
                    sha256 = record["sha256"]
                    size = record["size"]
                    if not isinstance(sha256, str) or not sha256:
                        raise ValueError("installed sha256 must be a string")
                    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                        raise ValueError("installed size must be a non-negative integer")
                    states[artifact] = replace(
                        prior, phase="installed", sha256=sha256, size=size, offset=0
                    )
                elif event == "corrupt":
                    reason = record.get("reason")
                    if not isinstance(reason, str) or not reason:
                        raise ValueError("corrupt reason must be a non-empty string")
                    states[artifact] = replace(prior, phase="corrupt", reason=reason)
                elif event == "repairing":
                    states[artifact] = replace(prior, phase="repairing", reason=None)
                else:
                    raise ValueError(f"unknown event {event!r}")
            except (KeyError, TypeError, ValueError):
                corrupt = True
        return JournalSnapshot(states=states, corrupt=corrupt, records=records)


def resolve_boot_state(
    projects_root: str | Path, *, write: bool = True
) -> JournalSnapshot:
    """Boot-time replay BEFORE ``derive_database_path`` (doc 27 §6.1).

    Folds the journal, then resolves every dangling transaction against
    filesystem reality:

    - ``staged`` with a staged file present → hash-verify, atomic rename,
      fsync, ``installed`` (completes the interrupted transaction).
    - ``staged``/``verifying`` without staged bytes → back to
      ``downloading`` resumed from the actual ``.part`` length.
    - ``downloading`` → offset refreshed from the real ``.part`` length
      (filesystem wins over the recorded offset).
    - ``installed`` fast path: stored stamp + size only (stat); deep
      re-hash is ``doctor``'s job, never boot's.
    """
    root = Path(projects_root)
    journal = SetupJournal(root)
    snapshot = journal.replay()
    resolved: dict[str, ArtifactState] = {}
    for artifact, state in snapshot.states.items():
        final = artifact_path(root, artifact)
        staged = staged_path(root, artifact)
        part = part_path(root, artifact)
        if state.phase == "staged" or state.phase == "verifying":
            if staged.is_file() and not staged.is_symlink():
                if state.sha256 is None or state.size is None:
                    if write:
                        journal.append(
                            artifact, "corrupt", reason="staged_metadata_missing"
                        )
                    resolved[artifact] = replace(
                        state, phase="corrupt", reason="staged_metadata_missing"
                    )
                    continue
                if write:
                    promoted_sha, promoted_size = _promote_staged(
                        root, journal, artifact, state, staged, final
                    )
                    if promoted_sha is None:
                        resolved[artifact] = replace(
                            state, phase="corrupt", reason="staged_hash_mismatch"
                        )
                        continue
                    resolved[artifact] = replace(
                        state,
                        phase="installed",
                        offset=0,
                        sha256=promoted_sha,
                        size=promoted_size or state.size,
                    )
                else:
                    # Read-only replay: staged bytes are presumed promotable.
                    resolved[artifact] = replace(state, phase="installed", offset=0)
            elif part.is_file() and not part.is_symlink():
                offset = part.stat().st_size
                if write:
                    journal.append(artifact, "downloading", offset=offset)
                resolved[artifact] = replace(
                    state, phase="downloading", offset=offset
                )
            else:
                if write:
                    journal.append(artifact, "downloading", offset=0)
                resolved[artifact] = replace(state, phase="downloading", offset=0)
        elif state.phase == "downloading":
            offset = part.stat().st_size if part.is_file() else 0
            resolved[artifact] = replace(state, phase="downloading", offset=offset)
        elif state.phase == "installed":
            # Fast path: stamp + size only. Deep re-hash belongs to doctor.
            try:
                ok = (
                    final.is_file()
                    and not final.is_symlink()
                    and final.stat().st_size == state.size
                )
            except OSError:
                ok = False
            if ok:
                resolved[artifact] = state
            else:
                resolved[artifact] = replace(
                    state, phase="corrupt", reason="size_drift"
                )
                if write:
                    journal.append(artifact, "corrupt", reason="size_drift")
        else:
            resolved[artifact] = state
    return JournalSnapshot(
        states=resolved, corrupt=snapshot.corrupt, records=snapshot.records
    )

def _promote_staged(
    root: Path,
    journal: SetupJournal,
    artifact: str,
    state: ArtifactState,
    staged: Path,
    final: Path,
) -> tuple[str | None, int | None]:
    """Complete an interrupted stage→install rename durably.

    Returns ``(sha256, size)`` of the promoted bytes, or ``(None,
    None)`` when the staged bytes drifted and promotion was refused.
    """
    final.parent.mkdir(parents=True, exist_ok=True)
    digest, size = _hash_file(staged)
    expected = state.sha256
    if expected is not None and digest != expected:
        # Staged bytes drifted: refuse the promotion, keep it corrupt.
        journal.append(artifact, "corrupt", reason="staged_hash_mismatch")
        return None, None
    if state.size is not None and size != state.size:
        journal.append(artifact, "corrupt", reason="staged_size_mismatch")
        return None, None
    os.replace(staged, final)
    _fsync_directory(final.parent)
    journal.append(artifact, "installed", sha256=digest, size=size)
    return digest, size


def _hash_file(path: Path, *, chunk: int = 1 << 20) -> tuple[str, int]:
    """Stream one SHA-256 over *path*; returns ``(hexdigest, size)``."""
    import hashlib

    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def read_stamp(
    projects_root: str | Path, artifact_ids: tuple[str, ...]
) -> tuple[bool, list[str]]:
    """Single-place probe read of ``installed(verified)`` stamps.

    This is the one function availability probes consult for weight /
    template stamps (E7: probes read one place). Boot's resolved state is
    recomputed here from the journal + cheap stat checks; deep hashing is
    never done on the probe path.
    """
    root = Path(projects_root)
    missing: list[str] = []
    states = resolve_boot_state(root, write=False).states
    for artifact_id in artifact_ids:
        state = states.get(artifact_id)
        if state is None or state.phase != "installed":
            missing.append(
                f"{artifact_id} not installed (setup stamp "
                f"{state.phase if state else 'absent'}); run 'astrid doctor setup'"
            )
    return (not missing), missing
