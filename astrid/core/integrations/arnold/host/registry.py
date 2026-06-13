"""Read-only shape registry and Arnold operation snapshot projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from astrid.core.project.current_run import read_current_run
from astrid.core.session.lease import read_lease
from astrid.core.task.events import EVENTS_FILENAME, read_events


@dataclass(frozen=True)
class ShapeEntry:
    """A single registered shape in the host allowlist."""

    workflow_id: str
    description: str
    cli_alias: Optional[str] = None
    accepts_human_input: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    entry_stage_id: str | None = None
    stage_labels: dict[str, str] = field(default_factory=dict)
    pipeline_builder: Callable[..., Any] | None = None


@dataclass(frozen=True)
class ArnoldOperationSnapshot:
    """Read-only projection used by Arnold host next/status rendering."""

    project_slug: str
    workflow_id: str
    run_id: str
    run_root: Path
    lease: dict[str, Any]
    cursor: dict[str, Any] | None
    events_tail: tuple[dict[str, Any], ...]
    next_stage_id: str | None
    next_stage_label: str | None
    envelope: Any


@dataclass
class ShapeRegistry:
    """Host-side registry of allowlisted Arnold workflow shapes."""

    _entries: dict[str, ShapeEntry] = field(default_factory=dict)
    _aliases: dict[str, str] = field(default_factory=dict)

    def register(self, entry: ShapeEntry) -> None:
        if entry.workflow_id in self._entries:
            raise ValueError(f"Shape {entry.workflow_id!r} is already registered")
        self._entries[entry.workflow_id] = entry
        if entry.cli_alias:
            if entry.cli_alias in self._aliases:
                raise ValueError(
                    f"CLI alias {entry.cli_alias!r} is already mapped to "
                    f"{self._aliases[entry.cli_alias]!r}"
                )
            self._aliases[entry.cli_alias] = entry.workflow_id

    def get(self, workflow_id: str) -> Optional[ShapeEntry]:
        return self._entries.get(workflow_id)

    def resolve_alias(self, alias: str) -> Optional[str]:
        return self._aliases.get(alias)

    def is_allowlisted(self, workflow_id: str) -> bool:
        return workflow_id in self._entries

    @property
    def allowlisted_ids(self) -> frozenset[str]:
        return frozenset(self._entries)

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def get_cursor(
        self,
        *,
        project_slug: str,
        workflow_id: str,
        run_id: str | None = None,
        root: str | Path | None = None,
    ) -> dict[str, Any] | None:
        project_runtime_envelope, _ = _envelope_helpers()
        envelope = project_runtime_envelope(
            project_slug,
            workflow_id=workflow_id,
            run_id=run_id,
            root=root,
        )
        resume_cursor = getattr(envelope, "resume_cursor", None)
        cursor = getattr(resume_cursor, "cursor", None)
        return dict(cursor) if isinstance(cursor, dict) else None

    def get_lease(
        self,
        *,
        project_slug: str,
        run_id: str | None = None,
        root: str | Path | None = None,
    ) -> dict[str, Any]:
        _, resolve_run_root = _envelope_helpers()
        run_root = resolve_run_root(project_slug, run_id=run_id, root=root)
        return dict(read_lease(run_root))

    def get_events_tail(
        self,
        *,
        project_slug: str,
        run_id: str | None = None,
        root: str | Path | None = None,
        limit: int = 5,
    ) -> tuple[dict[str, Any], ...]:
        _, resolve_run_root = _envelope_helpers()
        run_root = resolve_run_root(project_slug, run_id=run_id, root=root)
        events = read_events(run_root / EVENTS_FILENAME)
        tail = events[-limit:] if limit > 0 else []
        return tuple(dict(event) for event in tail)

    def get_next_step(
        self,
        *,
        project_slug: str,
        workflow_id: str,
        run_id: str | None = None,
        root: str | Path | None = None,
    ) -> tuple[str | None, str | None]:
        entry = self.require(workflow_id)
        cursor = self.get_cursor(
            project_slug=project_slug,
            workflow_id=workflow_id,
            run_id=run_id,
            root=root,
        )
        stage_id = entry.entry_stage_id
        if isinstance(cursor, dict):
            raw_stage = cursor.get("stage")
            if isinstance(raw_stage, str) and raw_stage:
                stage_id = raw_stage
        if stage_id is None:
            return None, None
        return stage_id, entry.stage_labels.get(stage_id, stage_id)

    def snapshot_operation(
        self,
        *,
        project_slug: str,
        workflow_id: str,
        run_id: str | None = None,
        root: str | Path | None = None,
        events_tail_limit: int = 5,
    ) -> ArnoldOperationSnapshot:
        resolved_run_id = run_id or read_current_run(project_slug, root=root)
        if resolved_run_id is None:
            raise RuntimeError(f"project {project_slug!r} has no active Arnold run")
        project_runtime_envelope, resolve_run_root = _envelope_helpers()
        run_root = resolve_run_root(project_slug, run_id=resolved_run_id, root=root)
        envelope = project_runtime_envelope(
            project_slug,
            workflow_id=workflow_id,
            run_id=resolved_run_id,
            root=root,
        )
        next_stage_id, next_stage_label = self.get_next_step(
            project_slug=project_slug,
            workflow_id=workflow_id,
            run_id=resolved_run_id,
            root=root,
        )
        cursor = self.get_cursor(
            project_slug=project_slug,
            workflow_id=workflow_id,
            run_id=resolved_run_id,
            root=root,
        )
        return ArnoldOperationSnapshot(
            project_slug=project_slug,
            workflow_id=workflow_id,
            run_id=resolved_run_id,
            run_root=run_root,
            lease=self.get_lease(
                project_slug=project_slug,
                run_id=resolved_run_id,
                root=root,
            ),
            cursor=cursor,
            events_tail=self.get_events_tail(
                project_slug=project_slug,
                run_id=resolved_run_id,
                root=root,
                limit=events_tail_limit,
            ),
            next_stage_id=next_stage_id,
            next_stage_label=next_stage_label,
            envelope=envelope,
        )

    def require(self, workflow_id: str) -> ShapeEntry:
        entry = self.get(workflow_id)
        if entry is None:
            raise KeyError(f"unknown host shape {workflow_id!r}")
        return entry


_registry: Optional[ShapeRegistry] = None


def _envelope_helpers() -> tuple[Callable[..., Any], Callable[..., Path]]:
    from astrid.core.integrations.arnold.host.envelope import (
        project_runtime_envelope,
        resolve_run_root,
    )

    return project_runtime_envelope, resolve_run_root


def get_host_shape_registry() -> ShapeRegistry:
    global _registry  # noqa: PLW0603

    if _registry is not None:
        return _registry

    from astrid.core.integrations.arnold.host.shapes import SHAPE_DEFINITIONS

    _registry = ShapeRegistry()
    for entry in SHAPE_DEFINITIONS:
        _registry.register(entry)
    return _registry


__all__ = [
    "ArnoldOperationSnapshot",
    "ShapeEntry",
    "ShapeRegistry",
    "get_host_shape_registry",
]
