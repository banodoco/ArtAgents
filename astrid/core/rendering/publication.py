"""Locked publication for one rendered video and its provenance sidecar.

The provenance sidecar is the commit marker.  A video without a valid
sidecar is deliberately visible (and therefore recoverable), but it is never
considered a committed render result.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .errors import raise_invalid_artifact_error

try:
    from filelock import FileLock, Timeout
except ImportError:  # pragma: no cover - exercised only without optional dep.
    FileLock = None  # type: ignore[assignment]

    class Timeout(Exception):
        pass


_BACKEND = "astrid.core"
_RECOVERY = "rerender the video and retry publication"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class _FcntlLock:
    """Small ``filelock``-compatible fallback used by the asset cache too."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: Any | None = None

    def acquire(self, timeout: float | None = None) -> _FcntlLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        deadline = None if timeout is None or timeout < 0 else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError as exc:
                if timeout == 0 or (deadline is not None and time.monotonic() >= deadline):
                    self._handle.close()
                    self._handle = None
                    raise Timeout(str(self.path)) from exc
                time.sleep(0.05)

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> _FcntlLock:
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.release()


def _lock_for(path: Path) -> Any:
    """Return the per-output lock at ``<output>.lock``."""

    lock_path = Path(f"{path}.lock")
    if FileLock is not None:
        return FileLock(str(lock_path))
    return _FcntlLock(lock_path)


def _default_sidecar_path(video_path: Path) -> Path:
    return Path(f"{video_path}.provenance.json")


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _contains_symlink_component(path: str | Path) -> bool:
    """True if a non-system path component is a symbolic link.

    Only the macOS system redirects (``/tmp`` -> ``/private/tmp``,
    ``/var`` -> ``/private/var``, ``/etc`` -> ``/private/etc``) are exempt.
    Any other symlink component (e.g. a symlinked run directory) is treated
    as an escape and rejected.
    """
    current = Path(path).expanduser()
    parts = list(current.parts)
    for index in range(len(parts), 0, -1):
        candidate = Path(*parts[:index])
        try:
            if not candidate.is_symlink():
                continue
        except OSError:
            return True
        try:
            resolved = candidate.resolve(strict=False)
        except (OSError, RuntimeError):
            return True
        # macOS system redirect: /<name> -> /private/<name> at the ROOT only.
        if (
            len(parts[:index]) == 2
            and parts[0] == "/"
            and candidate.name in ("tmp", "var", "etc")
            and str(resolved) == f"/private/{candidate.name}"
        ):
            continue
        return True
    return False


def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
    raise_invalid_artifact_error(
        backend=_BACKEND,
        message=message,
        recovery_command=_RECOVERY,
        details={"reason": reason, "path": str(video_path)},
    )


def _validate_source_video(video_path: Path) -> None:
    try:
        exists = video_path.is_file()
    except OSError:
        exists = False
    if not exists:
        _invalid_video(
            video_path,
            reason="missing_artifact",
            message=f"rendered video does not exist: {video_path}",
        )
    try:
        size = video_path.stat().st_size
    except OSError:
        _invalid_video(
            video_path,
            reason="missing_artifact",
            message=f"rendered video cannot be read: {video_path}",
        )
    if size <= 0:
        _invalid_video(
            video_path,
            reason="empty_artifact",
            message=f"rendered video is empty: {video_path}",
        )


def read_committed_provenance(
    video_path: str | Path,
    *,
    sidecar_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return provenance only when *video_path* and its marker form a valid pair.

    This check intentionally fails closed for missing, malformed, empty, or
    hash-mismatched pairs.  Callers can then re-render or leave the orphan for
    conservative recovery without mistaking it for a successful publication.
    """

    try:
        video_unresolved = Path(video_path).expanduser()
        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
        if (
            _contains_symlink_component(video_unresolved)
            or _contains_symlink_component(sidecar_unresolved)
        ):
            return None
        # Resolve only AFTER the symlink guard so a symlink loop cannot
        # raise RuntimeError here — it must fail closed to None.
        video = _resolved(video_path)
        sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
        if video.is_symlink() or sidecar.is_symlink():
            return None
        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
            return None
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    recorded_output = payload.get("output")
    if not isinstance(recorded_output, str):
        return None
    try:
        recorded_output_path = _resolved(recorded_output)
    except (OSError, RuntimeError, ValueError):
        return None
    if recorded_output_path != video:
        return None
    recorded_sha256 = payload.get("sha256")
    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
        return None
    try:
        if sha256_file(video) != recorded_sha256:
            return None
    except OSError:
        return None
    return payload


def is_render_result_committed(
    video_path: str | Path,
    *,
    sidecar_path: str | Path | None = None,
) -> bool:
    """Return whether the video-plus-sidecar pair is committed."""

    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None


def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
    if isinstance(candidate, Mapping):
        raw_video = candidate.get("out_path", candidate.get("output"))
        raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
        if raw_video is None:
            return None
        video = _resolved(raw_video)
        return video, _resolved(raw_sidecar or _default_sidecar_path(video))
    if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
        video = _resolved(candidate[0])
        return video, _resolved(candidate[1])
    if isinstance(candidate, (str, os.PathLike)):
        video = _resolved(candidate)
        return video, _resolved(_default_sidecar_path(video))
    return None


def _delete_previous_outputs(
    previous_outputs: Iterable[object],
    *,
    live_output: Path,
    timeline: object,
) -> None:
    if not isinstance(timeline, str):
        return
    seen: set[Path] = set()
    for candidate in previous_outputs:
        try:
            pair = _previous_pair(candidate)
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        if pair is None:
            continue
        video, sidecar = pair
        # Never delete through a symlink: neither the raw video nor the raw
        # sidecar path may be a link (the resolved pair may point elsewhere).
        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
        try:
            raw_path = Path(raw_candidate).expanduser()
            if _contains_symlink_component(raw_path):
                continue
        except (OSError, TypeError):
            continue
        try:
            # For bare paths the default sidecar is derived from the raw
            # video path; it must be checked unresolved like an explicit one.
            raw_sidecar = (
                Path(raw_sidecar_candidate).expanduser()
                if raw_sidecar_candidate is not None
                else _default_sidecar_path(raw_path)
            )
            if _contains_symlink_component(raw_sidecar):
                continue
        except (OSError, TypeError):
            continue
        if video == live_output or video in seen:
            continue
        seen.add(video)

        # Never wait while holding the live output lock.  Two concurrent
        # publications for sibling outputs can otherwise deadlock while each
        # tries to clean the other, and a locked candidate is by definition a
        # live render that cleanup must preserve.
        candidate_lock = _lock_for(video)
        try:
            candidate_lock.acquire(timeout=0)
        except (Timeout, OSError):
            continue
        try:
            provenance = read_committed_provenance(video, sidecar_path=sidecar)
            if provenance is None or provenance.get("timeline") != timeline:
                continue
            try:
                # The marker disappears first.  A crash or failure between
                # these unlinks leaves an orphan, never a false committed pair.
                sidecar.unlink()
            except (FileNotFoundError, OSError):
                continue
            try:
                video.unlink()
            except (FileNotFoundError, OSError):
                pass
        finally:
            candidate_lock.release()


def publish_render_result(
    video_path: str | Path,
    provenance_payload: Mapping[str, Any],
    *,
    out_path: str | Path,
    sidecar_path: str | Path,
    previous_outputs: Iterable[object] = (),
) -> Path:
    """Publish one video and atomically commit its hashed provenance marker.

    The source video is validated before any destination mutation.  Under the
    per-output lock an old marker is invalidated, the video is moved into
    place with :func:`os.replace`, and the complete sidecar is written
    atomically last.  A sidecar-write failure therefore leaves a detectable,
    recoverable orphan video and is propagated to the caller.
    """

    if not isinstance(provenance_payload, Mapping):
        raise TypeError("provenance_payload must be a mapping")

    source = _resolved(video_path)
    output = _resolved(out_path)
    sidecar = _resolved(sidecar_path)
    source_unresolved = Path(video_path).expanduser()
    output_unresolved = Path(out_path).expanduser()
    sidecar_unresolved = Path(sidecar_path).expanduser()
    if (
        _contains_symlink_component(source_unresolved)
        or _contains_symlink_component(output_unresolved)
        or _contains_symlink_component(sidecar_unresolved)
    ):
        raise_invalid_artifact_error(
            backend=_BACKEND,
            message="publication paths must not be symbolic links (or contain symlinked directories)",
            recovery_command=_RECOVERY,
        )
    _validate_source_video(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    with _lock_for(output):
        # Validate again after waiting for the lock so a moved or truncated
        # staging artifact can never be reported as successfully published.
        _validate_source_video(source)

        # Invalidate the previous marker BEFORE the first destination
        # mutation: a crash can then leave an orphan video (recoverable) but
        # can never leave a stale marker claiming the new bytes are committed.
        sidecar.unlink(missing_ok=True)
        os.replace(source, output)
        digest = sha256_file(output)
        committed_payload = dict(provenance_payload)
        committed_payload["output"] = str(output)
        committed_payload["sha256"] = digest
        write_json_atomic(sidecar, committed_payload)

        # Cleanup happens only after the new pair is committed and while its
        # lock remains held.  Candidate locks are non-blocking (see above).
        _delete_previous_outputs(
            previous_outputs,
            live_output=output,
            timeline=committed_payload.get("timeline"),
        )

        # Do not report success unless the bytes and marker we just wrote are
        # still a complete pair under the same lock.
        if read_committed_provenance(output, sidecar_path=sidecar) is None:
            _invalid_video(
                output,
                reason="uncommitted_artifact",
                message=f"published video has no valid provenance commit marker: {output}",
            )
    return output


__all__ = [
    "is_render_result_committed",
    "publish_render_result",
    "read_committed_provenance",
]
