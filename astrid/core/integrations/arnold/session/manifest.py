"""Projection schema for ``session-manifest.json``."""

from __future__ import annotations

from collections.abc import Mapping
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core._shared.jsonio import write_json_atomic

from .state import ArtifactRef, StateRef, prefixed_hash

SESSION_MANIFEST_SCHEMA_VERSION = 1
SESSION_MANIFEST_FILENAME = "session-manifest.json"
PIPELINE_REF = "pipeline.json"


@dataclass(frozen=True)
class EventLineageHashes:
    """Stable ledger anchors for one session segment."""

    segment_start_hash: str | None = None
    segment_boundary_hash: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "EventLineageHashes":
        if not payload:
            return cls()
        return cls(
            segment_start_hash=str(payload["segment_start_hash"])
            if payload.get("segment_start_hash") is not None
            else None,
            segment_boundary_hash=str(payload["segment_boundary_hash"])
            if payload.get("segment_boundary_hash") is not None
            else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.segment_start_hash is not None:
            payload["segment_start_hash"] = self.segment_start_hash
        if self.segment_boundary_hash is not None:
            payload["segment_boundary_hash"] = self.segment_boundary_hash
        return payload


@dataclass(frozen=True)
class SegmentRecord:
    """One frozen or active segment in the session projection."""

    segment_id: str
    plan_hash: str
    state: StateRef
    parent_segment_id: str | None = None
    status: str = "prepared"
    pipeline_ref: str = PIPELINE_REF
    pipeline_hash: str | None = None
    cursor_ref: str | None = None
    artifacts: tuple[ArtifactRef, ...] = field(default_factory=tuple)
    event_lineage: EventLineageHashes = field(default_factory=EventLineageHashes)
    frozen_at: str | None = None
    launched_at: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SegmentRecord":
        raw_artifacts = payload.get("artifacts", ())
        artifacts = tuple(
            ArtifactRef.from_dict(item)
            for item in raw_artifacts
            if isinstance(item, Mapping)
        )
        return cls(
            segment_id=str(payload.get("segment_id") or ""),
            plan_hash=str(payload.get("plan_hash") or ""),
            state=StateRef.from_dict(payload.get("state", {})),
            parent_segment_id=str(payload["parent_segment_id"])
            if payload.get("parent_segment_id") is not None
            else None,
            status=str(payload.get("status") or "prepared"),
            pipeline_ref=str(payload.get("pipeline_ref") or PIPELINE_REF),
            pipeline_hash=str(payload["pipeline_hash"])
            if payload.get("pipeline_hash") is not None
            else None,
            cursor_ref=str(payload["cursor_ref"]) if payload.get("cursor_ref") is not None else None,
            artifacts=artifacts,
            event_lineage=EventLineageHashes.from_dict(payload.get("event_lineage")),
            frozen_at=str(payload["frozen_at"]) if payload.get("frozen_at") is not None else None,
            launched_at=str(payload["launched_at"]) if payload.get("launched_at") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "segment_id": self.segment_id,
            "plan_hash": self.plan_hash,
            "state": self.state.to_dict(),
            "status": self.status,
            "pipeline_ref": self.pipeline_ref,
        }
        if self.parent_segment_id is not None:
            payload["parent_segment_id"] = self.parent_segment_id
        if self.pipeline_hash is not None:
            payload["pipeline_hash"] = self.pipeline_hash
        if self.cursor_ref is not None:
            payload["cursor_ref"] = self.cursor_ref
        if self.artifacts:
            payload["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        lineage = self.event_lineage.to_dict()
        if lineage:
            payload["event_lineage"] = lineage
        if self.frozen_at is not None:
            payload["frozen_at"] = self.frozen_at
        if self.launched_at is not None:
            payload["launched_at"] = self.launched_at
        return payload


@dataclass(frozen=True)
class SessionManifest:
    """Stable rebuildable projection for a session-succession run."""

    run_id: str = ""
    artifact_root: str = "."
    current_segment_id: str | None = None
    segments: tuple[SegmentRecord, ...] = field(default_factory=tuple)
    projection_hash: str | None = None
    schema_version: int = SESSION_MANIFEST_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SessionManifest":
        segments = tuple(
            SegmentRecord.from_dict(item)
            for item in payload.get("segments", ())
            if isinstance(item, Mapping)
        )
        manifest = cls(
            run_id=str(payload.get("run_id") or ""),
            artifact_root=str(payload.get("artifact_root") or "."),
            current_segment_id=str(payload["current_segment_id"])
            if payload.get("current_segment_id") is not None
            else None,
            segments=segments,
            projection_hash=str(payload["projection_hash"])
            if payload.get("projection_hash") is not None
            else None,
            schema_version=int(payload.get("schema_version") or SESSION_MANIFEST_SCHEMA_VERSION),
        )
        computed_hash = manifest.compute_projection_hash()
        if manifest.projection_hash is not None and manifest.projection_hash != computed_hash:
            raise RuntimeError(
                f"{SESSION_MANIFEST_FILENAME} projection_hash mismatch: "
                f"expected {computed_hash}, got {manifest.projection_hash}"
            )
        return manifest

    def payload_without_hash(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "artifact_root": self.artifact_root,
            "segments": [segment.to_dict() for segment in self.segments],
        }
        if self.current_segment_id is not None:
            payload["current_segment_id"] = self.current_segment_id
        return payload

    def compute_projection_hash(self) -> str:
        return prefixed_hash(self.payload_without_hash())

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload_without_hash()
        payload["projection_hash"] = self.projection_hash or self.compute_projection_hash()
        return payload


def load_manifest_file(run_root: Path) -> SessionManifest:
    manifest_path = run_root / SESSION_MANIFEST_FILENAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return SessionManifest()
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"invalid JSON in {SESSION_MANIFEST_FILENAME} for run {run_root.name!r}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"{SESSION_MANIFEST_FILENAME} for run {run_root.name!r} is not a JSON object"
        )
    return SessionManifest.from_dict(payload)


def write_manifest_file(run_root: Path, manifest: SessionManifest) -> None:
    write_json_atomic(run_root / SESSION_MANIFEST_FILENAME, manifest.to_dict())


__all__ = [
    "EventLineageHashes",
    "PIPELINE_REF",
    "SESSION_MANIFEST_FILENAME",
    "SESSION_MANIFEST_SCHEMA_VERSION",
    "SegmentRecord",
    "SessionManifest",
    "load_manifest_file",
    "write_manifest_file",
]
