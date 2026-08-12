"""Discover the single durable transcript attachment for a timeline.

The preferred, project-owned contract is the optional top-level ``transcript``
field in Astrid pipeline metadata (normally persisted as
``hype.metadata.json``)::

    {
      "transcript": {
        "schema_version": 1,
        "source_id": "transcript:main",
        "source_version": "1",
        "file": "transcript.json",
        "sha256": "<64 lowercase hex characters>",
        "media": {"asset_key": "source-main", "sha256": "<optional hash>"},
        "producer": "editorial.transcribe",
        "producer_version": "<optional version>",
        "model": "<optional model id>"
      }
    }

``schema_version`` may be omitted by version-1 producers because the enclosing
pipeline metadata is itself versioned; discovery materializes it as ``1``.
The existing metadata validator preserves additive top-level fields, so this
contract does not require changing the frozen timeline container/projection
schema.  In particular, ``assembly.json`` is *not* a second home for it.

Two compatibility fallbacks accept the same hash-bound declaration:

* ``sources.json#sources.<id>`` with ``kind: "transcript"``.  A relative
  ``file`` is rooted at the project's ``sources/`` directory, matching the
  existing flat source registry contract.  Existing camel-case source identity
  and ``content_sha256`` spellings are accepted.
* ``runs/<id>/run.json#artifacts.transcript``.  A relative ``file`` is rooted
  at the run record's declared ``out`` path.  It is never rooted at process
  CWD or inferred from the run-record filename.

No transcript filename, extension, directory proximity, or transcript content
is inspected during discovery.  Multiple declarations at one fallback level
fail closed rather than creating an implicit competing authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final


_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class TranscriptAttachment:
    """A resolved, immutable transcript reference and its current integrity."""

    source_id: str
    source_version: str
    transcript_sha256: str
    media_identity: str
    media_sha256: str | None
    producer: str
    producer_version: str | None
    model: str | None
    schema_version: int = 1
    integrity: str = "ok"
    note: str | None = None
    file: Path | None = None
    observed_transcript_sha256: str | None = None

    @property
    def path(self) -> Path | None:
        """Compatibility-friendly alias for the resolved transcript file."""

        return self.file


def discover_attachment(
    project_root: Path,
    *,
    timeline_dir: Path | None = None,
    timeline_metadata: Mapping | None = None,
) -> TranscriptAttachment | None:
    """Find the one explicitly declared transcript attachment for a timeline.

    Resolution is strictly ordered: supplied timeline metadata, project
    ``sources.json``, then a run record's explicit transcript artifact.  A
    declaration at a higher-priority level blocks lower-priority fallbacks even
    when malformed or ambiguous; stale metadata must never be silently replaced
    by a different authority.
    """

    project_base = Path(project_root).expanduser().resolve()
    timeline_base = (
        Path(timeline_dir).expanduser().resolve()
        if timeline_dir is not None
        else project_base
    )

    if timeline_metadata is not None and "transcript" in timeline_metadata:
        declaration = timeline_metadata.get("transcript")
        if not isinstance(declaration, Mapping):
            return None
        return _attachment_from_declaration(declaration, base=timeline_base)

    source_declarations = _source_declarations(project_base / "sources.json")
    if source_declarations:
        if len(source_declarations) != 1:
            return None
        return _attachment_from_declaration(
            source_declarations[0],
            base=project_base / "sources",
        )

    run_declarations = _run_declarations(project_base, timeline_base if timeline_dir else None)
    if not run_declarations:
        return None
    if len(run_declarations) != 1:
        return None
    declaration, run_base = run_declarations[0]
    if run_base is None and not _has_absolute_file(declaration):
        return None
    return _attachment_from_declaration(
        declaration,
        base=run_base or project_base,
    )


def _attachment_from_declaration(
    declaration: Mapping,
    *,
    base: Path,
) -> TranscriptAttachment | None:
    schema_version = declaration.get("schema_version", 1)
    if schema_version != 1:
        return None

    source_id = _non_empty_string(
        declaration.get("source_id", declaration.get("sourceId"))
    )
    source_version = _non_empty_string(
        declaration.get("source_version", declaration.get("sourceVersion"))
    )
    producer = _non_empty_string(declaration.get("producer"))
    file_value = _non_empty_string(
        declaration.get("file", declaration.get("path"))
    )
    transcript_sha256 = _sha256_value(
        declaration.get(
            "sha256",
            declaration.get("content_sha256", declaration.get("content_hash")),
        )
    )
    media = declaration.get("media")
    if not isinstance(media, Mapping):
        return None
    media_identity = _declared_media_identity(media)

    if None in (source_id, source_version, producer, file_value, transcript_sha256, media_identity):
        return None

    producer_version = _optional_string(declaration.get("producer_version"))
    model = _optional_string(declaration.get("model"))
    media_sha256 = _sha256_value(media.get("sha256"), optional=True)
    if media.get("sha256") is not None and media_sha256 is None:
        return None

    transcript_file = _resolve_declared_path(file_value, base=base)
    observed: str | None = None
    integrity = "missing"
    notes: list[str] = []
    try:
        if transcript_file.is_file():
            observed = _sha256_file(transcript_file)
            if observed == transcript_sha256:
                integrity = "ok"
            else:
                integrity = "hash_mismatch"
                notes.append(
                    "transcript hash mismatch: the declared file was not substituted"
                )
        else:
            notes.append("declared transcript file is missing")
    except OSError:
        integrity = "unreadable"
        notes.append("declared transcript file is unreadable")

    if media_sha256 is None:
        notes.append(
            "source-media hash was not recorded; media identity was not inferred"
        )

    return TranscriptAttachment(
        source_id=source_id,
        source_version=source_version,
        transcript_sha256=transcript_sha256,
        media_identity=media_identity,
        media_sha256=media_sha256,
        producer=producer,
        producer_version=producer_version,
        model=model,
        schema_version=1,
        integrity=integrity,
        note="; ".join(notes) or None,
        file=transcript_file,
        observed_transcript_sha256=observed,
    )


def _source_declarations(sources_path: Path) -> list[Mapping]:
    payload = _read_mapping(sources_path)
    if payload is None:
        return []
    sources = payload.get("sources")
    if not isinstance(sources, Mapping):
        return []

    declarations: list[Mapping] = []
    for entry_id in sorted(sources, key=str):
        entry = sources[entry_id]
        if not isinstance(entry, Mapping) or entry.get("kind") != "transcript":
            continue
        normalized = dict(entry)
        normalized.setdefault("source_id", str(entry_id))
        declarations.append(normalized)
    return declarations


def _run_declarations(
    project_root: Path,
    timeline_dir: Path | None,
) -> list[tuple[Mapping, Path | None]]:
    run_paths = _declared_timeline_run_paths(project_root, timeline_dir)
    if run_paths is None:
        runs_dir = project_root / "runs"
        try:
            run_paths = sorted(
                path / "run.json"
                for path in runs_dir.iterdir()
                if path.is_dir() and (path / "run.json").is_file()
            )
        except OSError:
            run_paths = []

    declarations: list[tuple[Mapping, Path | None]] = []
    for run_path in run_paths:
        record = _read_mapping(run_path)
        if record is None:
            continue
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, Mapping) or "transcript" not in artifacts:
            continue
        declaration = artifacts.get("transcript")
        if not isinstance(declaration, Mapping):
            continue
        declarations.append((declaration, _declared_run_base(record, project_root)))
    return declarations


def _declared_timeline_run_paths(
    project_root: Path,
    timeline_dir: Path | None,
) -> list[Path] | None:
    if timeline_dir is None:
        return None
    manifest = _read_mapping(timeline_dir / "manifest.json")
    if manifest is None or "contributing_runs" not in manifest:
        return None
    run_ids = manifest.get("contributing_runs")
    if not isinstance(run_ids, list) or not all(isinstance(item, str) for item in run_ids):
        return []
    return [project_root / "runs" / run_id / "run.json" for run_id in run_ids]


def _declared_run_base(record: Mapping, project_root: Path) -> Path | None:
    out = _non_empty_string(record.get("out"))
    if out is None:
        return None
    path = Path(out).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _declared_media_identity(media: Mapping) -> str | None:
    asset_key = _non_empty_string(media.get("asset_key"))
    source_id = _non_empty_string(media.get("source_id"))
    if (asset_key is None) == (source_id is None):
        return None
    return asset_key if asset_key is not None else source_id


def _resolve_declared_path(value: str, *, base: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def _has_absolute_file(declaration: Mapping) -> bool:
    value = _non_empty_string(declaration.get("file", declaration.get("path")))
    return value is not None and Path(value).expanduser().is_absolute()


def _read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_value(value: object, *, optional: bool = False) -> str | None:
    if value is None:
        return None if optional else None
    if not isinstance(value, str):
        return None
    normalized = value.removeprefix("sha256:")
    return normalized if _SHA256_RE.fullmatch(normalized) else None


def _non_empty_string(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value)


__all__ = ["TranscriptAttachment", "discover_attachment"]
