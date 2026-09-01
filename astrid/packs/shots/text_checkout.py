"""Filesystem projection for shot-owned text bindings.

The checkout is an operation snapshot only. Binding rows, their event streams,
and immutable media remain the authority.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from astrid.packs.shots.text_bindings import (
    MAX_SHOT_TEXT_BYTES,
    FrozenTextBytes,
    ShotTextBindingIntegrityError,
    ShotTextBindingRepository,
    freeze_text_bytes,
    validate_text_binding_kind,
    validate_text_binding_slot,
)

MANIFEST_NAME = ".astrid-text-checkout.json"
MANIFEST_SCHEMA = "astrid.shot-text-checkout/v1"
_MANIFEST_KEYS = {"schema", "project_id", "entries"}
_ENTRY_KEYS = {
    "binding_id",
    "shot_id",
    "kind",
    "slot",
    "file",
    "expected_head",
    "media_id",
    "content_hash",
}
_HEX = frozenset("0123456789abcdef")


def _root(path: str | Path) -> Path:
    root = Path(path)
    try:
        if root.is_symlink():
            raise ValueError("checkout root must not be a symlink")
        if root.exists() and not root.is_dir():
            raise ValueError("checkout destination must be a directory")
    except OSError as exc:
        raise ValueError("checkout root cannot be inspected") from exc
    return root


def _safe_relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("manifest file must be relative")
    rel = Path(name)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise ValueError("manifest file must be relative")
    target = root.joinpath(*rel.parts)
    current = root
    try:
        if current.is_symlink():
            raise ValueError("manifest path traverses a symlink")
        for part in rel.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ValueError("manifest path traverses a symlink")
        if target.is_symlink():
            raise ValueError("manifest file is a symlink")
        target.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        raise
    except OSError as exc:
        raise ValueError("manifest path cannot be inspected") from exc
    return target


def _entry_file(binding: Any) -> str:
    suffix = f".{binding.slot}" if binding.slot is not None else ""
    return f"text/{binding.shot_id}/{binding.kind}{suffix}.txt"


def _manifest(entries: Sequence[Any], project_id: str) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "project_id": project_id,
        "entries": [
            {
                "binding_id": b.binding_id,
                "shot_id": b.shot_id,
                "kind": b.kind,
                "slot": b.slot,
                "file": _entry_file(b),
                "expected_head": b.head,
                "media_id": b.media_id,
                "content_hash": b.content_hash,
            }
            for b in sorted(entries, key=lambda item: item.binding_id)
        ],
    }


def _string(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(message)
    return value


def _load(checkout: str | Path) -> tuple[Path, dict[str, Any]]:
    root = _root(checkout)
    try:
        value = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid or missing checkout manifest") from exc
    if (
        not isinstance(value, dict)
        or set(value) != _MANIFEST_KEYS
        or value.get("schema") != MANIFEST_SCHEMA
    ):
        raise ValueError("invalid checkout manifest")
    _string(value.get("project_id"), "invalid checkout project")
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise ValueError("invalid checkout entries")
    ids: set[str] = set()
    files: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
            raise ValueError("invalid checkout entry")
        binding_id = _string(entry.get("binding_id"), "invalid binding id")
        shot_id = _string(entry.get("shot_id"), "invalid shot id")
        kind = validate_text_binding_kind(entry.get("kind"))
        slot = validate_text_binding_slot(entry.get("slot"), kind=kind)
        file_name = _string(entry.get("file"), "invalid manifest file")
        expected_file = f"text/{shot_id}/{kind}{f'.{slot}' if slot is not None else ''}.txt"
        if file_name != expected_file:
            raise ValueError("manifest file does not match binding identity")
        _safe_relative(root, file_name)
        if binding_id in ids:
            raise ValueError("duplicate binding")
        if file_name in files:
            raise ValueError("duplicate manifest file")
        ids.add(binding_id)
        files.add(file_name)
        head = entry.get("expected_head")
        if isinstance(head, bool) or not isinstance(head, int) or head < 0:
            raise ValueError("invalid expected head")
        _string(entry.get("media_id"), "invalid media id")
        digest = entry.get("content_hash")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or digest != digest.lower()
            or any(c not in _HEX for c in digest)
        ):
            raise ValueError("invalid content hash")
    if [entry["binding_id"] for entry in entries] != sorted(ids):
        raise ValueError("manifest entries are not canonical")
    return root, value


def _validate_ids(binding_ids: Sequence[str] | None) -> tuple[str, ...] | None:
    if binding_ids is None:
        return None
    if isinstance(binding_ids, (str, bytes)) or not isinstance(binding_ids, Sequence):
        raise ValueError("binding_ids must be a non-empty sequence")
    ids = tuple(binding_ids)
    if not ids or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("binding_ids must be a non-empty sequence of strings")
    if len(set(ids)) != len(ids):
        raise ValueError("binding_ids must be duplicate-free")
    return ids


def _selected(manifest: dict[str, Any], binding_ids: Sequence[str] | None) -> list[dict[str, Any]]:
    ids = _validate_ids(binding_ids)
    if ids is None:
        return list(manifest["entries"])
    by_id = {entry["binding_id"]: entry for entry in manifest["entries"]}
    if any(value not in by_id for value in ids):
        raise ValueError("binding selection is not a manifest subset")
    return [by_id[value] for value in sorted(ids)]


def _read_bounded(root: Path, relative: str) -> bytes:
    path = _safe_relative(root, relative)
    try:
        stat = path.stat()
        if not path.is_file() or stat.st_size > MAX_SHOT_TEXT_BYTES:
            raise ValueError("checkout file is missing, non-regular, or oversized")
        with path.open("rb") as handle:
            data = handle.read(MAX_SHOT_TEXT_BYTES + 1)
    except OSError as exc:
        raise ValueError("checkout file is unreadable or missing") from exc
    if len(data) > MAX_SHOT_TEXT_BYTES:
        raise ValueError("checkout file is oversized")
    return data


def _read_file(root: Path, relative: str) -> bytes:
    return freeze_text_bytes(_read_bounded(root, relative)).value


def _frozen_file(root: Path, relative: str) -> FrozenTextBytes:
    return freeze_text_bytes(_read_bounded(root, relative))


def _mkdir_tracked(path: Path, created: list[Path]) -> None:
    if path.exists():
        return
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    path.mkdir(parents=True, exist_ok=False)
    created.extend(missing)


def prepare_selection(
    repo: ShotTextBindingRepository,
    writer: Any,
    *,
    project_id: str,
    binding_ids: Sequence[str] | None = None,
    shot_ref: str | None = None,
    kind: str | None = None,
    slot: str | None = None,
    all_project: bool = False,
) -> list[Any]:
    ids = _validate_ids(binding_ids)
    if not isinstance(all_project, bool):
        raise ValueError("all_project must be a boolean")
    if ids is not None:
        if shot_ref is not None or kind is not None or slot is not None or all_project:
            raise ValueError("exact binding selection cannot be combined with filters")
        return sorted(
            [repo.show(writer, project_id=project_id, binding_id=value) for value in ids],
            key=lambda item: item.binding_id,
        )
    if shot_ref is None and not all_project:
        raise ValueError("a selection is required")
    if shot_ref is not None and all_project:
        raise ValueError("shot and project-wide selection are mutually exclusive")
    if shot_ref is not None and (not isinstance(shot_ref, str) or not shot_ref):
        raise ValueError("shot_ref must be a non-empty string")
    if slot is not None:
        if kind is None:
            raise ValueError("slot requires kind=prompt")
        validate_text_binding_slot(slot, kind=kind)
    if kind is not None:
        validate_text_binding_kind(kind)
    return repo.list(writer, project_id=project_id, shot_ref=shot_ref, kind=kind, slot=slot)


def _source_bytes(
    repo: ShotTextBindingRepository, reader: Any, project_id: str, binding: Any
) -> bytes:
    if repo._media is None:
        raise ValueError("a Core MediaRepository is required")
    media = repo._media.read_project_media(reader, project_id=project_id, media_id=binding.media_id)
    if media is None:
        raise ShotTextBindingIntegrityError(detail="bound_media_missing", media_id=binding.media_id)
    verified = repo._verify_managed_text(media, current=True)
    repo._verify_fingerprint(verified)
    data = verified.path.read_bytes()
    if hashlib.sha256(data).hexdigest() != binding.content_hash:
        raise ValueError("bound media changed during checkout")
    return data


def checkout(
    repo: ShotTextBindingRepository,
    writer: Any,
    *,
    project_id: str,
    checkout_dir: str | Path,
    **selection: Any,
) -> dict[str, Any]:
    root = _root(checkout_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError("checkout destination must be nonexistent or empty")
    bindings = prepare_selection(repo, writer, project_id=project_id, **selection)
    if not bindings:
        raise ValueError("checkout selection is empty")
    manifest = _manifest(bindings, project_id)
    # Complete source validation precedes creation of the root or any temp.
    with writer.read_only_connection() as reader:
        import sqlite3

        reader.row_factory = sqlite3.Row
        material = [
            (_entry, _source_bytes(repo, reader, project_id, binding))
            for _entry, binding in zip(manifest["entries"], bindings, strict=True)
        ]
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    try:
        if not root.exists():
            _mkdir_tracked(root, created_dirs)
        for entry, data in material:
            target = _safe_relative(root, entry["file"])
            if not target.parent.exists():
                _mkdir_tracked(target.parent, created_dirs)
            fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
            temp_path = Path(temp_name)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, target)
                created_files.append(target)
            finally:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        manifest_path = root / MANIFEST_NAME
        temp_manifest = root / f".{MANIFEST_NAME}.tmp"
        try:
            fd = os.open(temp_manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    manifest, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_manifest, manifest_path)
            created_files.append(manifest_path)
        finally:
            try:
                temp_manifest.unlink()
            except FileNotFoundError:
                pass
    except BaseException:
        for path in reversed(created_files):
            try:
                path.unlink()
            except OSError:
                pass
        for directory in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return manifest


def _status_row(
    repo: ShotTextBindingRepository,
    reader: Any,
    root: Path,
    manifest: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    if repo._media is None:
        raise ValueError("a Core MediaRepository is required")
    row = repo._resolve_binding(
        reader, project_id=manifest["project_id"], binding_id=entry["binding_id"]
    )
    binding = repo._binding_row(reader, row)
    base = repo._media.read_project_media(
        reader, project_id=manifest["project_id"], media_id=entry["media_id"]
    )
    if base is None:
        raise ShotTextBindingIntegrityError(
            detail="manifest_base_missing", media_id=entry["media_id"]
        )
    verified = repo._verify_managed_text(base, current=True)
    repo._verify_fingerprint(verified)
    if base.content_hash != entry["content_hash"]:
        raise ShotTextBindingIntegrityError(
            detail="manifest_base_mismatch", media_id=entry["media_id"]
        )
    local_hash: str | None = None
    local_state: str
    try:
        raw = _read_bounded(root, entry["file"])
        local_hash = hashlib.sha256(raw).hexdigest()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            local_state = "invalid_utf8"
            local_hash = None
        else:
            local_state = "clean" if local_hash == entry["content_hash"] else "modified"
    except ValueError:
        local_state = "missing"
    return {
        "binding_id": entry["binding_id"],
        "file": entry["file"],
        "local_state": local_state,
        "head_state": "current" if binding.head == entry["expected_head"] else "stale",
        "expected_head": entry["expected_head"],
        "current_head": binding.head,
        "base_content_hash": entry["content_hash"],
        "local_content_hash": local_hash,
        "_base_bytes": verified.path.read_bytes(),
    }


def status(
    repo: ShotTextBindingRepository,
    writer: Any,
    checkout_dir: str | Path,
    binding_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    root, manifest = _load(checkout_dir)
    entries = _selected(manifest, binding_ids)
    with writer.read_only_connection() as reader:
        import sqlite3

        reader.row_factory = sqlite3.Row
        rows = [_status_row(repo, reader, root, manifest, entry) for entry in entries]
    for row in rows:
        row.pop("_base_bytes", None)
    return rows


def diff(
    repo: ShotTextBindingRepository,
    writer: Any,
    checkout_dir: str | Path,
    binding_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    root, manifest = _load(checkout_dir)
    entries = _selected(manifest, binding_ids)
    result = []
    with writer.read_only_connection() as reader:
        import sqlite3

        reader.row_factory = sqlite3.Row
        for entry in entries:
            row = _status_row(repo, reader, root, manifest, entry)
            try:
                local = _read_bounded(root, entry["file"]).decode("utf-8")
                base = row.pop("_base_bytes").decode("utf-8")
                row["diff"] = "".join(
                    difflib.unified_diff(
                        base.splitlines(keepends=True),
                        local.splitlines(keepends=True),
                        fromfile=entry["file"],
                        tofile=entry["file"],
                    )
                )
            except (ValueError, UnicodeDecodeError):
                row.pop("_base_bytes", None)
                row["diff"] = None
            result.append(row)
    return result


def prepare_apply(
    checkout_dir: str | Path, *, binding_ids: Sequence[str] | None = None
) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    root, manifest = _load(checkout_dir)
    selected = _selected(manifest, binding_ids)
    return (
        root,
        manifest,
        [{**entry, "frozen": _frozen_file(root, entry["file"])} for entry in selected],
    )


__all__ = [
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA",
    "prepare_selection",
    "checkout",
    "status",
    "diff",
    "prepare_apply",
    "_load",
    "_selected",
    "_read_file",
]
