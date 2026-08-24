"""Deterministic media discovery, byte identity, probing, and frozen paths (m2 plan step 2).

This module is the pure filesystem half of the media pipeline. It never
touches SQLite, never imports repositories, and never opens a transaction:
hashing, probing, walking, staging, verification, and atomic publication are
exactly the preparation work that must stay **outside** ``BEGIN IMMEDIATE``
(m2 watch item; v10 section 5.3). Plan step 3 adds the publication half —
per-transaction quarantine staging, staged-byte re-verification, atomic
rename plus directory fsync, verified reuse of existing digests, explicit
``external_local`` preparation, missing/mutated location detection, and
startup GC of unreferenced staging directories — while keeping the same
purity boundary.

Contracts kept here:

- **Byte identity (SD2).** A prepared record's identity is the lowercase
  SHA-256 hex of the file's *bytes* alone. Paths, URLs, and locators never
  participate in identity, so identical bytes at different paths resolve to
  the same digest and the same exact sharded managed path, while changed
  bytes at one path change the digest.
- **Deterministic walking.** :func:`walk_media_files` returns a total,
  stable order independent of filesystem creation order: depth-first,
  each directory's regular files sorted by name first, then its
  subdirectories sorted by name recursed in order. Symlinks are skipped
  (no cycles, no escapes), and the managed root directory (``.astrid``)
  is never walked into.
- **Independent derivation.** MIME type is derived from the file name,
  media kind is derived from the MIME type alone, and probe metadata is
  derived from the file itself — none of the three reads another's
  output, so a wrong extension can never silently reclassify bytes and
  probe facts stay observable facts.
- **Strict media-kind validation.** The media kind is the frozen v10 DDL
  CHECK vocabulary ``('image','video','audio','text','document','data',
  'other')`` (decision artifact section 7). :func:`validate_media_kind`
  rejects anything outside it before any downstream SQL could run.
- **Exact frozen paths.** :func:`managed_media_path` and
  :func:`staging_path` reproduce the m1 decision artifact section 5
  layout byte-for-byte: managed media at
  ``<projects_root>/.astrid/media/sha256/<first2>/<next2>/<digest>`` and
  per-transaction staging at ``<projects_root>/.astrid/media/.staging/
  <txn_id>``. A malformed digest or txn id is rejected rather than
  silently mapped onto a different path.
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from astrid.core.media import MediaProbeError, ffprobe_metadata_strict

# ---------------------------------------------------------------------------
# Frozen vocabulary and layout (decision artifact sections 5 and 7)
# ---------------------------------------------------------------------------

MEDIA_KINDS: tuple[str, ...] = (
    "image",
    "video",
    "audio",
    "text",
    "document",
    "data",
    "other",
)
"""The frozen ``media.media_kind`` DDL CHECK vocabulary (v10 decision
artifact section 7). Order is the DDL transcription order."""

MANAGED_ROOT_DIRNAME = ".astrid"
"""The managed data root directory name under ``ASTRID_PROJECTS_ROOT``."""

MEDIA_ROOT_RELATIVE = "media"
"""Relative path of the media tree under the managed data root."""

SHA256_TREE_RELATIVE = "media/sha256"
"""Relative path of the content-addressed tree under the managed root."""

STAGING_RELATIVE = "media/.staging"
"""Relative path of the per-transaction staging tree under the managed root."""

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
"""Lowercase SHA-256 hex grammar (exactly 64 hex digits)."""

_TXN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
"""Kernel transaction id grammar (``uuid.uuid4().hex``, 32 lowercase hex)."""

_MIME_FALLBACKS: Mapping[str, str] = {
    ".md": "text/markdown",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".toml": "application/toml",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".heic": "image/heic",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".m4a": "audio/mp4",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".log": "text/plain",
    ".txt": "text/plain",
    ".json": "application/json",
    ".sql": "application/sql",
    ".rtf": "application/rtf",
}
"""Small extension fallbacks for common types ``mimetypes`` may miss on a
bare Python install. Used only when ``mimetypes.guess_type`` returns
nothing useful; the stdlib result wins when present."""

_DOCUMENT_MIME_PREFIXES: tuple[str, ...] = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.",
    "application/vnd.oasis.opendocument.",
    "application/vnd.ms-",
    "application/rtf",
    "application/epub+zip",
)
"""MIME families classified as ``document`` by :func:`derive_media_kind`."""

_DATA_MIME_PREFIXES: tuple[str, ...] = (
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/toml",
    "application/sql",
    "application/zip",
    "application/gzip",
    "application/x-tar",
    "application/x-7z-compressed",
    "application/x-sqlite3",
    "application/x-bzip2",
    "application/x-xz",
    "application/vnd.sqlite3",
)
"""MIME families classified as ``data`` by :func:`derive_media_kind``."""

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MediaPreparationError(ValueError):
    """Base error for media preparation (hashing, walking, probing, paths)."""


class MediaKindError(MediaPreparationError):
    """Raised when a media kind is not one of the frozen seven values."""


class MediaDigestError(MediaPreparationError):
    """Raised when a digest is not a lowercase 64-hex SHA-256."""


class MediaPathError(MediaPreparationError):
    """Raised when a filesystem path is missing, non-regular, or out of root."""


class MediaDecodabilityError(MediaPreparationError):
    """Raised when an extension-classified media file cannot be probed."""

    def __init__(
        self,
        message: str,
        *,
        media_kind: str,
        mime_type: str,
        extension: str,
        probe_reason: str,
    ) -> None:
        super().__init__(message)
        self.media_kind = media_kind
        self.mime_type = mime_type
        self.extension = extension
        self.probe_reason = probe_reason


# ---------------------------------------------------------------------------
# Strict media-kind validation
# ---------------------------------------------------------------------------


def validate_media_kind(media_kind: object) -> str:
    """Return *media_kind* unchanged if it is one of the frozen seven values.

    Raises :class:`MediaKindError` for anything else — including uppercase
    spellings and near-misses — so no value outside the frozen DDL CHECK
    vocabulary can ever reach a ``media.media_kind`` write.
    """
    if not isinstance(media_kind, str) or media_kind not in MEDIA_KINDS:
        raise MediaKindError(
            f"media_kind must be one of {MEDIA_KINDS}, got {media_kind!r}"
        )
    return media_kind


def validate_digest(digest: object) -> str:
    """Return *digest* unchanged if it is a lowercase 64-hex SHA-256.

    Raises :class:`MediaDigestError` otherwise. The digest grammar is the
    sharding contract: the managed path splits ``digest[:2]`` and
    ``digest[2:4]``, so a non-canonical spelling must be rejected instead
    of silently producing a different shard.
    """
    if not isinstance(digest, str) or _DIGEST_RE.fullmatch(digest) is None:
        raise MediaDigestError(
            "digest must be the lowercase 64-hex SHA-256 of file bytes, "
            f"got {digest!r}"
        )
    return digest


def validate_txn_id(txn_id: object) -> str:
    """Return *txn_id* unchanged if it is a kernel transaction id.

    Kernel transaction ids are ``uuid.uuid4().hex`` (32 lowercase hex).
    The staging path is ``<projects_root>/.astrid/media/.staging/<txn_id>``,
    so a txn id that could smuggle path separators or escape the staging
    tree is rejected before any filesystem operation.
    """
    if not isinstance(txn_id, str) or _TXN_ID_RE.fullmatch(txn_id) is None:
        raise MediaPreparationError(
            "txn_id must be a 32-character lowercase hex transaction id, "
            f"got {txn_id!r}"
        )
    return txn_id


# ---------------------------------------------------------------------------
# Byte identity (SD2): lowercase file-byte SHA-256
# ---------------------------------------------------------------------------


def sha256_file_bytes(path: str | Path) -> str:
    """Return the lowercase SHA-256 hex digest of *path*'s bytes.

    The digest covers the file's bytes and only the file's bytes, in 1 MiB
    chunks; the path, name, and any locator never participate. An empty
    file digests to the standard empty-input SHA-256
    (``e3b0c442…b7852b855``) with ``byte_size`` 0.
    """
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Independent kind / MIME / probe derivation
# ---------------------------------------------------------------------------


def derive_mime_type(path: str | Path) -> str:
    """Derive a MIME type from *path*'s name (extension-based).

    Independent derivation: this function reads only the file name. The
    stdlib ``mimetypes`` result wins when present; otherwise a small
    fallback table covers common types. Unknown extensions produce
    ``application/octet-stream`` — never a fabricated specific type.
    """
    name = Path(path).name
    guessed, _encoding = mimetypes.guess_type(name)
    if guessed is not None:
        return guessed
    fallback = _MIME_FALLBACKS.get(Path(name).suffix.lower())
    return fallback if fallback is not None else "application/octet-stream"


def derive_media_kind(mime_type: object) -> str:
    """Derive the frozen media kind from *mime_type* alone.

    Independent derivation: this function reads only the MIME string, never
    the path or extension. The result is validated against the frozen seven
    values before it is returned, so a classification bug surfaces as a
    :class:`MediaKindError` instead of an invalid row.
    """
    if not isinstance(mime_type, str) or not mime_type:
        raise MediaKindError(f"mime_type must be a non-empty string, got {mime_type!r}")
    lowered = mime_type.lower()
    if lowered.startswith("image/"):
        kind = "image"
    elif lowered.startswith("video/"):
        kind = "video"
    elif lowered.startswith("audio/"):
        kind = "audio"
    elif lowered.startswith("text/"):
        kind = "text"
    elif any(lowered.startswith(prefix) for prefix in _DOCUMENT_MIME_PREFIXES):
        kind = "document"
    elif any(lowered.startswith(prefix) for prefix in _DATA_MIME_PREFIXES):
        kind = "data"
    else:
        kind = "other"
    return validate_media_kind(kind)


def probe_media_file(path: str | Path) -> Mapping[str, object]:
    """Return independent probe facts for one file.

    The probe is derived from the file itself — byte size, extension, and
    emptiness — and never from the MIME type or media kind. It is frozen
    into the prepared record as ``probe``; downstream code may store it as
    media metadata but must never treat it as identity.
    """
    file_path = Path(path)
    stat = file_path.stat()
    byte_size = int(stat.st_size)
    return {
        "byte_size": byte_size,
        "extension": file_path.suffix,
        "is_empty": byte_size == 0,
    }


# ---------------------------------------------------------------------------
# Immutable prepared-media record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    """One immutable prepared-media record (m2 plan step 2).

    ``digest`` is the lowercase SHA-256 hex of the file's bytes — the sole
    identity. ``media_kind`` and ``mime_type`` are independently derived,
    ``probe`` is the independent filesystem probe, and ``rel_path`` is the
    deterministic POSIX path relative to the walked root (the file name for
    single-file preparation). The record is frozen: downstream publication
    (plan step 3/4) consumes it, never mutates it.
    """

    source_path: Path
    digest: str
    byte_size: int
    media_kind: str
    mime_type: str
    rel_path: str
    probe: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_digest(self.digest)
        validate_media_kind(self.media_kind)
        if not isinstance(self.source_path, Path):
            raise MediaPreparationError(
                "source_path must be a pathlib.Path, got "
                f"{type(self.source_path).__name__}"
            )
        if not isinstance(self.rel_path, str) or not self.rel_path:
            raise MediaPreparationError(
                "rel_path must be a non-empty POSIX string, got "
                f"{self.rel_path!r}"
            )
        if isinstance(self.byte_size, bool) or not isinstance(
            self.byte_size, int
        ) or self.byte_size < 0:
            raise MediaPreparationError(
                f"byte_size must be a non-negative integer, got {self.byte_size!r}"
            )

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe mapping persisted as media metadata."""
        return {
            "source_path": str(self.source_path),
            "digest": self.digest,
            "byte_size": self.byte_size,
            "media_kind": self.media_kind,
            "mime_type": self.mime_type,
            "rel_path": self.rel_path,
            "probe": dict(self.probe),
        }


# ---------------------------------------------------------------------------
# Deterministic directory walking
# ---------------------------------------------------------------------------


def walk_media_files(
    root: str | Path,
    *,
    skip_dir_names: frozenset[str] = frozenset({MANAGED_ROOT_DIRNAME}),
) -> list[Path]:
    """Return every regular file under *root* in deterministic walk order.

    Ordering contract (stable across filesystems and creation orders):

    - depth-first; for each directory, its own regular files sorted by
      name come first, then its subdirectories sorted by name, recursed in
      that sorted order;
    - symlinks (file or directory) are skipped entirely — no cycles, no
      escapes;
    - directories whose name is in *skip_dir_names* (by default the
      managed root ``.astrid``) are never descended into;
    - the returned paths are absolute (resolved against *root*).

    Raises :class:`MediaPathError` when *root* is not an existing
    directory.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise MediaPathError(f"walk root must be an existing directory: {root!r}")
    results: list[Path] = []

    def visit(directory: Path) -> None:
        entries = sorted(directory.iterdir(), key=lambda entry: entry.name)
        subdirs: list[Path] = []
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in skip_dir_names:
                    subdirs.append(entry)
            elif entry.is_file():
                results.append(entry)
        for subdir in subdirs:
            visit(subdir)

    visit(root_path)
    return results


def _rel_posix(path: Path, root: Path) -> str:
    """Return *path*'s deterministic POSIX string relative to *root*."""
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise MediaPathError(
            f"prepared file {path!s} is outside walk root {root!s}"
        ) from exc
    return relative.as_posix()


# ---------------------------------------------------------------------------
# Preparation entry points
# ---------------------------------------------------------------------------


def prepare_media_file(
    path: str | Path, *, root: str | Path | None = None
) -> PreparedMedia:
    """Prepare one file into an immutable :class:`PreparedMedia` record.

    When *root* is supplied, ``rel_path`` is the POSIX path relative to it
    (and *path* must live under it); otherwise ``rel_path`` is the file
    name. Hashing and probing run here, outside any transaction, exactly as
    the m2 watch item requires.
    """
    file_path = Path(path)
    if file_path.is_symlink() or not file_path.is_file():
        raise MediaPathError(f"prepared file must be a regular file: {path!r}")
    if root is not None:
        root_path = Path(root)
        rel_path = _rel_posix(file_path, root_path)
    else:
        rel_path = file_path.name
    digest = sha256_file_bytes(file_path)
    mime_type = derive_mime_type(file_path)
    media_kind = derive_media_kind(mime_type)
    probe = probe_media_file(file_path)
    # Extension-only classification is unsafe for containers: a Git-LFS
    # pointer (or any other text blob named .mp4/.wav) must fail before the
    # media/event/receipt transaction rather than becoming a doomed asset.
    # Generic files and images retain the historical lightweight probe; the
    # strict container boundary covers video/audio where late render failure
    # is materially expensive and ffprobe has a reliable stream contract.
    if media_kind in {"video", "audio"}:
        try:
            strict_probe = ffprobe_metadata_strict(file_path)
        except MediaProbeError as exc:
            reason = "ffprobe_unavailable" if "not available on PATH" in str(exc) else "undecodable"
            recovery = (
                "install ffprobe (from the ffmpeg package) and retry"
                if reason == "ffprobe_unavailable"
                else "replace the file with a valid decodable media file and retry"
            )
            raise MediaDecodabilityError(
                f"{file_path.suffix.lower()} media is not importable: {exc}; {recovery}",
                media_kind=media_kind,
                mime_type=mime_type,
                extension=file_path.suffix.lower(),
                probe_reason=reason,
            ) from exc
        required_stream = (
            strict_probe.has_video_stream if media_kind == "video" else strict_probe.has_audio_stream
        )
        if not required_stream:
            raise MediaDecodabilityError(
                f"{file_path.suffix.lower()} media contains no {media_kind} stream; "
                "replace the file with a valid decodable media file and retry",
                media_kind=media_kind,
                mime_type=mime_type,
                extension=file_path.suffix.lower(),
                probe_reason="missing_stream",
            )
        # Preserve the cheap probe keys while making successful decodability
        # observable without changing the frozen media row schema.
        probe = {
            **dict(probe),
            "decodable": True,
            "container": strict_probe.container or strict_probe.format_name,
            "duration_seconds": strict_probe.duration_seconds,
            "has_video_stream": strict_probe.has_video_stream,
            "has_audio_stream": strict_probe.has_audio_stream,
        }
    byte_size = int(probe["byte_size"])
    return PreparedMedia(
        source_path=file_path,
        digest=digest,
        byte_size=byte_size,
        media_kind=media_kind,
        mime_type=mime_type,
        rel_path=rel_path,
        probe=probe,
    )


def prepare_media_directory(root: str | Path) -> list[PreparedMedia]:
    """Prepare every file under *root* in deterministic walk order.

    Returns one :class:`PreparedMedia` per regular file, in exactly the
    order :func:`walk_media_files` produces, so callers can rely on a
    stable, replayable import order. Raises :class:`MediaPathError` when a
    file disappears between walking and preparation (the caller retries or
    surfaces a typed error; no SQL has run).
    """
    root_path = Path(root)
    return [prepare_media_file(path, root=root_path) for path in walk_media_files(root_path)]


# ---------------------------------------------------------------------------
# Exact managed and staging paths (decision artifact section 5)
# ---------------------------------------------------------------------------


def managed_media_path(projects_root: str | Path, digest: object) -> Path:
    """Return the exact frozen managed path for one content digest.

    Layout (frozen): ``<projects_root>/.astrid/media/sha256/<first2>/
    <next2>/<digest>`` where ``<first2>``/``<next2>`` are the first four
    hex characters of the lowercase digest split into two pairs. The
    digest is validated first, so a malformed or uppercase digest can
    never resolve onto a different shard.
    """
    valid_digest = validate_digest(digest)
    root = Path(projects_root)
    return (
        root
        / MANAGED_ROOT_DIRNAME
        / SHA256_TREE_RELATIVE
        / valid_digest[:2]
        / valid_digest[2:4]
        / valid_digest
    )


def managed_shard_path(projects_root: str | Path, digest: object) -> Path:
    """Return the frozen shard directory (parent of the digest file)."""
    return managed_media_path(projects_root, digest).parent


def staging_path(projects_root: str | Path, txn_id: object) -> Path:
    """Return the exact frozen per-transaction staging path.

    Layout (frozen): ``<projects_root>/.astrid/media/.staging/<txn_id>``.
    The txn id is validated against the kernel transaction grammar before
    any path is built, so no caller-supplied string can escape the staging
    tree.
    """
    valid_txn = validate_txn_id(txn_id)
    return Path(projects_root) / MANAGED_ROOT_DIRNAME / STAGING_RELATIVE / valid_txn


def managed_root(projects_root: str | Path) -> Path:
    """Return the managed data root: ``<projects_root>/.astrid``."""
    return Path(projects_root) / MANAGED_ROOT_DIRNAME


# ---------------------------------------------------------------------------
# Per-transaction staging, verified publication, and location verification
# (m2 plan step 3)
# ---------------------------------------------------------------------------
#
# Plan step 3 keeps the same purity boundary as step 2: every function here
# is plain filesystem work — quarantine copy, fsync, re-hash verification,
# atomic rename, missing/mutated detection, and selective staging GC. None of
# it opens SQLite or a transaction; repositories call it from inside their
# unit of work only for the *short* atomic publication window (m2 watch item;
# v10 section 5.3).
#
# The crash contract (SD5): a managed digest file left by a pre-commit crash
# is safe, non-semantic, and reusable, and startup GC removes **only**
# unreferenced staging directories — never managed digest bytes and never
# rows. Every staged file is re-hashed before publication, and an existing
# managed digest is re-hashed before it is reused, so no unverified byte ever
# becomes semantic truth.

MEDIA_LOCATION_REALMS: tuple[str, ...] = ("managed_local", "external_local", "remote")
"""The frozen ``media_locations.realm`` DDL CHECK vocabulary (v10 decision
artifact section 7). ``managed_local`` is the default; ``external_local`` is
always an explicit opt-in (:func:`prepare_external_local`)."""


class MediaStagingError(MediaPreparationError):
    """Raised when per-transaction quarantine staging of prepared bytes fails."""


class MediaIntegrityError(MediaPreparationError):
    """Raised when bytes do not match the expected digest.

    Covers staged bytes that fail re-verification before publication and any
    digest-mismatch that must surface before bytes become semantic truth.
    """


class MediaLocationError(MediaPreparationError):
    """Raised when a managed or external location is missing or mutated.

    ``reason`` is ``"missing"`` (no regular file at the path) or
    ``"mutated"`` (the bytes no longer match the recorded digest).
    """

    def __init__(
        self,
        *,
        reason: str,
        path: str | Path,
        expected_digest: str | None = None,
        actual_digest: str | None = None,
    ) -> None:
        if reason not in ("missing", "mutated"):
            raise ValueError(f"reason must be 'missing' or 'mutated', got {reason!r}")
        self.reason: str = reason
        self.path: Path = Path(path)
        self.expected_digest: str | None = expected_digest
        self.actual_digest: str | None = actual_digest
        if reason == "missing":
            detail = f"location is missing or not a regular file: {self.path!s}"
        else:
            detail = (
                f"location bytes mutated: {self.path!s} expected "
                f"sha256:{expected_digest} but hashes to sha256:{actual_digest}"
            )
        super().__init__(detail)


class MediaPublicationError(MediaPreparationError):
    """Raised when atomic publication into the managed tree fails."""


# ---------------------------------------------------------------------------
# Deterministic crash hooks (m2 plan step 16, T26_impl)
# ---------------------------------------------------------------------------
# The subprocess crash matrix must be able to terminate a child *inside* the
# filesystem pipeline — not only at SQL statement boundaries — so the
# staging/publication sequence exposes deterministic hook points:
#
# - ``"staged"`` — after the quarantine copy and staged-file fsync;
# - ``"published"`` — after the atomic rename and directory fsyncs (the
#   managed digest now exists, no SQL row references it yet);
# - ``"reused"`` — after a verified existing digest was reused and its
#   staged copy drained.
#
# A crash at ``"published"`` (or at any repository SQL boundary after it,
# before COMMIT) leaves an orphan managed digest with rolled-back SQL —
# exactly the SD5 case: the digest is safe, non-semantic, and must be
# verified and reused by the next import, never duplicated or swept. The
# hook is test-only: production code never installs one, and an unset hook
# is a no-op, so the shipping paths are byte-identical with or without the
# hook facility compiled in.

_CRASH_HOOK: Callable[[str], None] | None = None
"""The installed deterministic crash hook (test-only, default unset)."""


def set_media_crash_hook(hook: Callable[[str], None] | None) -> None:
    """Install or clear the deterministic filesystem crash hook.

    *hook* is invoked with a stable point name at every deterministic
    filesystem boundary of the staging/publication pipeline. Tests install
    a counting hook so a subprocess can ``os._exit`` at exactly one point;
    kernel and pack code never install one.
    """
    global _CRASH_HOOK
    _CRASH_HOOK = hook


def media_crash_point(point: str) -> None:
    """Invoke the installed crash hook for one deterministic boundary.

    No-op when no hook is installed (the default), so the media pipeline's
    behavior is unchanged outside the crash matrix.
    """
    hook = _CRASH_HOOK
    if hook is not None:
        hook(point)


@dataclass(frozen=True, slots=True)
class StagedMedia:
    """One file quarantined in the per-transaction staging directory.

    ``rel_path`` mirrors the prepared record's deterministic POSIX path, so a
    staging directory is a faithful quarantine of the walk order. ``digest``
    is the byte identity the staged bytes must verify against.
    """

    txn_id: str
    staged_path: Path
    rel_path: str
    digest: str
    byte_size: int

    def __post_init__(self) -> None:
        validate_txn_id(self.txn_id)
        validate_digest(self.digest)
        if not isinstance(self.staged_path, Path):
            raise MediaPreparationError(
                "staged_path must be a pathlib.Path, got "
                f"{type(self.staged_path).__name__}"
            )
        if not isinstance(self.rel_path, str) or not self.rel_path:
            raise MediaPreparationError(
                "rel_path must be a non-empty POSIX string, got "
                f"{self.rel_path!r}"
            )
        if isinstance(self.byte_size, bool) or not isinstance(
            self.byte_size, int
        ) or self.byte_size < 0:
            raise MediaPreparationError(
                f"byte_size must be a non-negative integer, got {self.byte_size!r}"
            )

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe mapping persisted as staging metadata."""
        return {
            "txn_id": self.txn_id,
            "staged_path": str(self.staged_path),
            "rel_path": self.rel_path,
            "digest": self.digest,
            "byte_size": self.byte_size,
        }


@dataclass(frozen=True, slots=True)
class PublishedMedia:
    """One byte-verified managed publication (or verified reuse).

    ``reused`` is ``True`` when the digest already existed in the managed
    tree and its bytes were re-verified rather than re-copied — the
    project-scoped dedupe contract (SD2; success criterion 2).
    """

    digest: str
    managed_path: Path
    byte_size: int
    reused: bool

    def __post_init__(self) -> None:
        validate_digest(self.digest)
        if not isinstance(self.managed_path, Path):
            raise MediaPreparationError(
                "managed_path must be a pathlib.Path, got "
                f"{type(self.managed_path).__name__}"
            )
        if isinstance(self.byte_size, bool) or not isinstance(
            self.byte_size, int
        ) or self.byte_size < 0:
            raise MediaPreparationError(
                f"byte_size must be a non-negative integer, got {self.byte_size!r}"
            )
        if not isinstance(self.reused, bool):
            raise MediaPreparationError("reused must be a bool")

    def to_dict(self) -> dict[str, object]:
        """Return the JSON-safe mapping persisted as publication metadata."""
        return {
            "digest": self.digest,
            "managed_path": str(self.managed_path),
            "byte_size": self.byte_size,
            "reused": self.reused,
        }


@dataclass(frozen=True, slots=True)
class StagingGcResult:
    """Outcome of one selective staging-GC pass."""

    removed_directories: int
    removed_files: int
    remaining_directories: int

    def to_dict(self) -> dict[str, int]:
        """Return the JSON-safe mapping for logs and tests."""
        return {
            "removed_directories": self.removed_directories,
            "removed_files": self.removed_files,
            "remaining_directories": self.remaining_directories,
        }


def _fsync_file(path: Path) -> None:
    """Flush one regular file's bytes to stable storage."""
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    """Flush one directory's entry changes to stable storage.

    Directory fsync is the crash-safety half of an atomic rename: it makes
    the new directory entry (and the removed staging entry) durable before a
    crash could reopen the tree mid-publication.
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage_prepared_media(
    projects_root: str | Path,
    txn_id: object,
    prepared: PreparedMedia,
) -> StagedMedia:
    """Quarantine one prepared file into the per-transaction staging directory.

    Copies *prepared*'s source bytes to
    ``<projects_root>/.astrid/media/.staging/<txn_id>/<rel_path>`` (creating
    the staging tree), then fsyncs the staged file so a crash cannot leave a
    partially flushed quarantine. The staged bytes are *not* yet trusted:
    :func:`verify_staged_media` (or publication) re-hashes them before any
    managed publication. Raises :class:`MediaStagingError` on copy failure
    and rejects a ``rel_path`` that would escape the staging root.
    """
    valid_txn = validate_txn_id(txn_id)
    if not isinstance(prepared, PreparedMedia):
        raise MediaPreparationError(
            "prepared must be a PreparedMedia record, got "
            f"{type(prepared).__name__}"
        )
    staging_root = staging_path(projects_root, valid_txn)
    staged_path = staging_root / prepared.rel_path
    try:
        staged_path.resolve().relative_to(staging_root.resolve())
    except ValueError as exc:
        raise MediaStagingError(
            f"staged rel_path {prepared.rel_path!r} escapes the staging "
            f"directory {staging_root!s}"
        ) from exc
    try:
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(prepared.source_path, staged_path)
        _fsync_file(staged_path)
    except OSError as exc:
        raise MediaStagingError(
            f"cannot stage {prepared.source_path!s} into {staging_root!s}: {exc}"
        ) from exc
    media_crash_point("staged")
    return StagedMedia(
        txn_id=valid_txn,
        staged_path=staged_path,
        rel_path=prepared.rel_path,
        digest=prepared.digest,
        byte_size=prepared.byte_size,
    )


def verify_staged_media(staged: StagedMedia) -> StagedMedia:
    """Re-hash one staged file and require it to match its byte identity.

    Raises :class:`MediaIntegrityError` when the staged bytes no longer hash
    to ``staged.digest`` — a quarantine that fails verification must never be
    published. Returns the record unchanged on success.
    """
    try:
        actual = sha256_file_bytes(staged.staged_path)
    except OSError as exc:
        raise MediaIntegrityError(
            f"cannot re-verify staged bytes {staged.staged_path!s}: {exc}"
        ) from exc
    if actual != staged.digest:
        raise MediaIntegrityError(
            f"staged bytes {staged.staged_path!s} hash to sha256:{actual} "
            f"but the prepared identity is sha256:{staged.digest}"
        )
    return staged


def verify_media_bytes(path: str | Path, digest: object) -> int:
    """Verify one location's bytes against *digest* (missing/mutated check).

    Raises :class:`MediaLocationError` with ``reason="missing"`` when *path*
    is absent, a symlink, or not a regular file, and ``reason="mutated"``
    when the bytes hash to a different digest. Returns the verified byte
    size on success. This is the single location-verification primitive for
    both managed and external locations.
    """
    expected = validate_digest(digest)
    location = Path(path)
    if location.is_symlink() or not location.is_file():
        raise MediaLocationError(reason="missing", path=location)
    actual = sha256_file_bytes(location)
    if actual != expected:
        raise MediaLocationError(
            reason="mutated",
            path=location,
            expected_digest=expected,
            actual_digest=actual,
        )
    return int(location.stat().st_size)


def verify_managed_bytes(projects_root: str | Path, digest: object) -> int:
    """Verify the managed digest file for *digest* (missing/mutated check)."""
    return verify_media_bytes(managed_media_path(projects_root, digest), digest)


def _remove_staged_file(staged: StagedMedia) -> None:
    """Remove one staged file and fsync its staging directory.

    Called only after the bytes are safely published (renamed) or verified
    reused, so the quarantine holds nothing that no longer needs staging.
    A removal failure is surfaced so callers see staging did not fully
    drain, but the managed publication is already complete.
    """
    try:
        staged.staged_path.unlink()
        _fsync_directory(staged.staged_path.parent)
    except OSError as exc:
        raise MediaStagingError(
            f"cannot drain staged file {staged.staged_path!s}: {exc}"
        ) from exc


def _prune_staging_txn_dir(
    projects_root: str | Path, staged: StagedMedia
) -> None:
    """Remove the now-empty per-transaction staging tree after publication.

    Called only from :func:`publish_staged_media` **success** paths, after
    the staged bytes are safely published (renamed) or verified-reused, so
    a failed import keeps its quarantine for forensics. The walk removes
    empty directories from the staged file's parent up to (and including)
    the ``<txn_id>`` directory, never the shared ``.staging`` root and
    never a directory that still holds another transaction's bytes. A
    failure here is best-effort: the managed publication is already
    complete, and startup GC (:func:`gc_unreferenced_staging`) still
    removes anything a crash leaves behind.
    """
    staging_root = Path(projects_root) / MANAGED_ROOT_DIRNAME / STAGING_RELATIVE
    current = staged.staged_path.parent
    while current != staging_root and staging_root in current.parents:
        try:
            if any(current.iterdir()):
                break
            current.rmdir()
        except OSError:
            break
        current = current.parent


def publish_staged_media(
    projects_root: str | Path,
    staged: StagedMedia,
) -> PublishedMedia:
    """Atomically publish one verified staged file into the managed tree.

    Publication order (crash-safe, SD5):

    1. Re-verify the staged bytes against their digest — nothing unverified
       is ever published.
    2. When the exact managed digest path already exists, verify its bytes
       and **reuse** it (project-scoped dedupe); a mutated existing digest
       raises :class:`MediaLocationError` instead of being silently
       overwritten.
    3. Otherwise ``os.replace`` the staged file onto the exact frozen sharded
       path (atomic on the same filesystem), then fsync the file, its shard
       directory, and the staging directory — so a crash reopens the managed
       tree old-or-complete and never a partial digest file.

    Raises :class:`MediaIntegrityError` for unverified staged bytes and
    :class:`MediaPublicationError` when the rename or fsync fails.
    """
    verify_staged_media(staged)
    managed = managed_media_path(projects_root, staged.digest)
    if managed.exists():
        verify_media_bytes(managed, staged.digest)
        _remove_staged_file(staged)
        media_crash_point("reused")
        _prune_staging_txn_dir(projects_root, staged)
        return PublishedMedia(
            digest=staged.digest,
            managed_path=managed,
            byte_size=staged.byte_size,
            reused=True,
        )
    try:
        managed.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged.staged_path, managed)
        _fsync_file(managed)
        _fsync_directory(managed.parent)
        _fsync_directory(staged.staged_path.parent)
    except OSError as exc:
        raise MediaPublicationError(
            f"cannot atomically publish {staged.staged_path!s} to {managed!s}: "
            f"{exc}"
        ) from exc
    media_crash_point("published")
    _prune_staging_txn_dir(projects_root, staged)
    return PublishedMedia(
        digest=staged.digest,
        managed_path=managed,
        byte_size=staged.byte_size,
        reused=False,
    )


def publish_prepared_media(
    projects_root: str | Path,
    txn_id: object,
    prepared: PreparedMedia,
) -> PublishedMedia:
    """Stage, verify, and publish one prepared record in one helper call.

    This is the in-UoW media helper repositories call for the short atomic
    publication window: quarantine the prepared bytes, re-verify them, and
    atomically place (or verified-reuse) the exact managed digest path.
    """
    return publish_staged_media(projects_root, stage_prepared_media(projects_root, txn_id, prepared))


def prepare_external_local(
    path: str | Path, *, root: str | Path | None = None
) -> PreparedMedia:
    """Explicit ``external_local`` reference-in-place preparation (SD2).

    Managed copy is the default; reference-in-place is **never** a default.
    Callers must name this function (or otherwise record realm
    ``external_local`` in ``media_locations``) to opt in. Identity remains
    the byte SHA-256 — the returned record is byte-identical to
    :func:`prepare_media_file`, so the repository dedupes and verifies it
    exactly like a managed candidate — and :func:`verify_media_bytes` gives
    the same missing/mutated detection for the external path.
    """
    return prepare_media_file(path, root=root)


def gc_unreferenced_staging(
    projects_root: str | Path,
    live_txn_ids: object,
) -> StagingGcResult:
    """Remove staging directories unreferenced by live attempts (startup GC).

    Removes every ``<projects_root>/.astrid/media/.staging/<txn_id>``
    directory whose txn id is **not** in *live_txn_ids* (the set of
    transaction ids referenced by live attempts, supplied by the caller from
    the database). Contracts:

    - only directories whose name matches the kernel txn grammar are
      considered — any other entry is left untouched;
    - referenced staging directories (and everything under them) are kept;
    - the managed ``media/sha256`` digest tree is never touched, so a
      pre-commit published digest survives (SD5);
    - GC is best-effort cleanup: a crash mid-GC leaves leftovers the next
      pass removes.

    Returns a :class:`StagingGcResult` with removal/remaining counts.
    """
    live: set[str] = {validate_txn_id(txn) for txn in (live_txn_ids or ())}
    staging_root = Path(projects_root) / MANAGED_ROOT_DIRNAME / STAGING_RELATIVE
    if not staging_root.is_dir():
        return StagingGcResult(
            removed_directories=0, removed_files=0, remaining_directories=0
        )
    removed_directories = 0
    removed_files = 0
    remaining_directories = 0
    for entry in sorted(staging_root.iterdir(), key=lambda item: item.name):
        if _TXN_ID_RE.fullmatch(entry.name) is None:
            continue
        if entry.name in live:
            remaining_directories += 1
            continue
        if entry.is_dir() and not entry.is_symlink():
            file_count = sum(1 for p in entry.rglob("*") if p.is_file())
            shutil.rmtree(entry)
            removed_directories += 1
            removed_files += file_count
    return StagingGcResult(
        removed_directories=removed_directories,
        removed_files=removed_files,
        remaining_directories=remaining_directories,
    )


__all__ = [
    "MANAGED_ROOT_DIRNAME",
    "MEDIA_KINDS",
    "MEDIA_LOCATION_REALMS",
    "MEDIA_ROOT_RELATIVE",
    "PreparedMedia",
    "PublishedMedia",
    "StagedMedia",
    "StagingGcResult",
    "MediaDigestError",
    "MediaDecodabilityError",
    "MediaIntegrityError",
    "MediaKindError",
    "MediaLocationError",
    "MediaPathError",
    "MediaPreparationError",
    "MediaPublicationError",
    "MediaStagingError",
    "SHA256_TREE_RELATIVE",
    "STAGING_RELATIVE",
    "derive_media_kind",
    "derive_mime_type",
    "gc_unreferenced_staging",
    "managed_media_path",
    "managed_root",
    "managed_shard_path",
    "media_crash_point",
    "prepare_external_local",
    "prepare_media_directory",
    "prepare_media_file",
    "probe_media_file",
    "publish_prepared_media",
    "publish_staged_media",
    "set_media_crash_hook",
    "sha256_file_bytes",
    "stage_prepared_media",
    "staging_path",
    "validate_digest",
    "validate_media_kind",
    "validate_txn_id",
    "verify_managed_bytes",
    "verify_media_bytes",
    "verify_staged_media",
    "walk_media_files",
]
