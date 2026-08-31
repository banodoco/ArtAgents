"""Discover the single durable transcript attachment for a timeline.

The preferred, runtime-owned contract is the optional top-level ``transcript``
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

Only runtime-owned or already-materialized metadata is accepted.  The helper
never scans project files for a transcript: in particular, ``sources.json``
and ``runs/<id>/run.json`` are not transcript authorities.  A relative
``file`` in accepted metadata is resolved only below the owning materialized
root, and is hash-verified before it is exposed to normalization.

No transcript filename, extension, directory proximity, or transcript content
is inspected during discovery.  Multiple declarations at one metadata level
fail closed rather than creating an implicit competing authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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

    Resolution is strictly ordered: supplied timeline metadata, then
    runtime-supplied pipeline metadata.  A declaration at a higher-priority
    level blocks the lower-priority level even when malformed; stale metadata
    must never be silently replaced by a different authority.  No project
    file is inspected to discover a declaration.
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

    # There is deliberately no project-file fallback here.  The runtime must
    # materialize the declaration into one of the metadata mappings above.
    return None


def _attachment_from_declaration(
    declaration: Mapping,
    *,
    base: Path,
    root: Path,
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

    transcript_file = _resolve_contained_path(file_value, base=base, root=root)
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


def _pipeline_declarations(metadata: Mapping | None) -> list[object] | None:
    """Return explicitly declared pipeline transcript authorities.

    New producers use the top-level ``transcript`` contract.  Existing cut
    metadata may place the path at ``sources.<asset>.transcript_ref``; that
    path is accepted only as part of a complete hash-bound declaration in the
    same source entry (or its nested ``transcript`` mapping).  A bare ref is
    therefore reachable but malformed, and blocks a trusted attachment rather
    than being guessed into one.
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
