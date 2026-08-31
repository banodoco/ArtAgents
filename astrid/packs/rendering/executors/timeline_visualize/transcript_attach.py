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
    pipeline_metadata: Mapping | None = None,
    pipeline_metadata_base: Path | None = None,
    pipeline_root: Path | None = None,
) -> TranscriptAttachment | None:
    """Find the one explicitly declared transcript attachment for a timeline.

    Resolution is strictly ordered: supplied timeline metadata, preserved
    pipeline metadata, project ``sources.json``, then a run record's explicit
    transcript artifact.  A declaration at a higher-priority level blocks
    lower-priority fallbacks even when malformed or ambiguous; stale metadata
    must never be silently replaced by a different authority.
    """

    project_base = Path(project_root).expanduser().resolve()
    timeline_base = (
        Path(timeline_dir).expanduser().resolve() if timeline_dir is not None else project_base
    )

    if timeline_metadata is not None and "transcript" in timeline_metadata:
        declaration = timeline_metadata.get("transcript")
        if not isinstance(declaration, Mapping):
            return None
        return _attachment_from_declaration(
            declaration,
            base=timeline_base,
            root=project_base,
        )

    pipeline_declarations = _pipeline_declarations(pipeline_metadata)
    if pipeline_declarations is not None:
        if len(pipeline_declarations) != 1:
            return None
        declaration = pipeline_declarations[0]
        if not isinstance(declaration, Mapping):
            return None
        metadata_base = (
            Path(pipeline_metadata_base).expanduser().resolve()
            if pipeline_metadata_base is not None
            else project_base
        )
        metadata_root = (
            Path(pipeline_root).expanduser().resolve()
            if pipeline_root is not None
            else project_base
        )
        return _attachment_from_declaration(
            declaration,
            base=metadata_base,
            root=metadata_root,
        )

    source_declarations = _source_declarations(project_base / "sources.json")
    if source_declarations:
        if len(source_declarations) != 1:
            return None
        return _attachment_from_declaration(
            source_declarations[0],
            base=project_base / "sources",
            root=project_base / "sources",
        )

    run_declarations = _run_declarations(project_base, timeline_base if timeline_dir else None)
    if not run_declarations:
        return None
    if len(run_declarations) != 1:
        return None
    declaration, run_base, run_root, base_is_contained = run_declarations[0]
    return _attachment_from_declaration(
        declaration,
        base=run_base or run_root,
        root=run_root,
        force_uncontained=not base_is_contained,
    )


def _attachment_from_declaration(
    declaration: Mapping,
    *,
    base: Path,
    root: Path,
    force_uncontained: bool = False,
) -> TranscriptAttachment | None:
    schema_version = declaration.get("schema_version", 1)
    if schema_version != 1:
        return None

    source_id = _non_empty_string(declaration.get("source_id", declaration.get("sourceId")))
    source_version = _non_empty_string(
        declaration.get("source_version", declaration.get("sourceVersion"))
    )
    producer = _non_empty_string(declaration.get("producer"))
    file_value = _non_empty_string(declaration.get("file", declaration.get("path")))
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

    transcript_file = (
        None if force_uncontained else _resolve_contained_path(file_value, base=base, root=root)
    )
    observed: str | None = None
    integrity = "uncontained" if transcript_file is None else "missing"
    notes: list[str] = []
    if transcript_file is None:
        notes.append("declared transcript path is outside its owning root")
    try:
        if transcript_file is not None and transcript_file.is_file():
            observed = _sha256_file(transcript_file)
            if observed == transcript_sha256:
                integrity = "ok"
            else:
                integrity = "hash_mismatch"
                notes.append("transcript hash mismatch: the declared file was not substituted")
        elif transcript_file is not None:
            notes.append("declared transcript file is missing")
    except OSError:
        integrity = "unreadable"
        notes.append("declared transcript file is unreadable")

    if media_sha256 is None:
        notes.append("source-media hash was not recorded; media identity was not inferred")

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


def _pipeline_declarations(metadata: Mapping | None) -> list[object] | None:
    """Return explicitly declared pipeline transcript authorities.

    New producers use the top-level ``transcript`` contract.  Existing cut
    metadata may place the path at ``sources.<asset>.transcript_ref``; that
    path is accepted only as part of a complete hash-bound declaration in the
    same source entry (or its nested ``transcript`` mapping).  A bare ref is
    therefore reachable but malformed, and blocks lower-priority fallbacks
    rather than being guessed into a trusted attachment.
    """

    if metadata is None:
        return None
    if "transcript" in metadata:
        return [metadata.get("transcript")]
    sources = metadata.get("sources")
    if not isinstance(sources, Mapping):
        return None
    declarations: list[object] = []
    for asset_key in sorted(sources, key=str):
        source = sources[asset_key]
        if not isinstance(source, Mapping):
            continue
        transcript_ref = _non_empty_string(source.get("transcript_ref"))
        nested = source.get("transcript")
        if nested is None and transcript_ref is None:
            continue
        if nested is not None and not isinstance(nested, Mapping):
            declarations.append(nested)
            continue
        normalized = dict(nested) if isinstance(nested, Mapping) else dict(source)
        if transcript_ref is not None:
            normalized.setdefault("file", transcript_ref)
        normalized.setdefault("media", {"asset_key": str(asset_key)})
        declarations.append(normalized)
    return declarations or None


def _run_declarations(
    project_root: Path,
    timeline_dir: Path | None,
) -> list[tuple[Mapping, Path | None, Path, bool]]:
    # Runtime runs are authoritative.  This transcript helper has no runtime
    # artifact lookup API yet, so it intentionally declines to infer producer
    # declarations from local run files (including the old directory scan).
    run_paths = _declared_timeline_run_paths(project_root, timeline_dir)
    if run_paths is None:
        return []

    runs_root = (project_root / "runs").resolve()
    declarations: list[tuple[Mapping, Path | None, Path, bool]] = []
    for run_path in run_paths:
        if run_path.parent.is_symlink():
            continue
        run_root = run_path.parent.resolve()
        if run_root.parent != runs_root:
            continue
        resolved_run_path = run_path.resolve()
        if resolved_run_path.parent != run_root:
            continue
        record = _read_mapping(resolved_run_path)
        if record is None:
            continue
        artifacts = record.get("artifacts")
        if not isinstance(artifacts, Mapping) or "transcript" not in artifacts:
            continue
        declaration = artifacts.get("transcript")
        if not isinstance(declaration, Mapping):
            continue
        run_base, base_is_contained = _declared_run_base(
            record,
            project_root,
            run_root,
        )
        declarations.append((declaration, run_base, run_root, base_is_contained))
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
    # A frozen timeline may retain producer ids for provenance, but this
    # module cannot turn those ids into authoritative artifact declarations
    # without the runtime's artifact read operation.  Fail closed until that
    # API exists rather than reading a local run.json projection.
    del project_root, run_ids
    return []


def _declared_run_base(
    record: Mapping,
    project_root: Path,
    run_root: Path,
) -> tuple[Path | None, bool]:
    out = _non_empty_string(record.get("out"))
    if out is None:
        return run_root, True
    path = Path(out).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (project_root / path).resolve()
    return (resolved, True) if resolved.is_relative_to(run_root) else (None, False)


def _declared_media_identity(media: Mapping) -> str | None:
    asset_key = _non_empty_string(media.get("asset_key"))
    source_id = _non_empty_string(media.get("source_id"))
    if (asset_key is None) == (source_id is None):
        return None
    return asset_key if asset_key is not None else source_id


def _resolve_contained_path(value: str, *, base: Path, root: Path) -> Path | None:
    path = Path(value).expanduser()
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (base / path).resolve()
    contained_root = Path(root).expanduser().resolve()
    return resolved if resolved.is_relative_to(contained_root) else None


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
