"""Pack-owned TaskHandler adapter around ``timeline_visualize.run_sdk`` (T23).

Plan step 14's boundary: the adapter is **pack code** — kernel code never
imports it, and the adapter never imports kernel executor internals. It
implements the injected kernel handler protocol
(:class:`astrid.core.task_executor.service.TaskHandler`) by duck typing, and
it runs the real read-only timeline renderer in-process:

1. **Read-only seed input.** The task's immutable ``spec`` names the managed
   project slug and the timeline ULID (plus optional ``layout``,
   ``formats``, and ``filmstrip``). The timeline itself lives read-only
   under the assigned projects root; the adapter never writes into it.
2. **Sanctioned in-process invocation.** ``run_sdk`` is imported lazily
   inside :func:`astrid.core.pack.entrypoint.canonical_runtime_entrypoint`
   (the canonical runtime capability context), and ``ASTRID_PROJECTS_ROOT``
   is scoped to the assigned managed root for the duration of the call — so
   the renderer resolves the seeded project without touching the caller's
   environment. No provider key, network, remote execution, GPU, or child
   process is involved.
3. **Concrete files under the assigned staging root.** ``run_sdk`` writes
   the deterministic evidence pack (``agent-view/`` with ``manifest.json``,
   ``reading-guide.md``, ``structure.md``, and page ``.png``/``.svg`` files)
   directly under the assigned staging directory.
4. **Universal result manifest.** The adapter returns a valid manifest
   whose outputs are exactly the concrete SVG/PNG/Markdown files plus the
   pack's own ``manifest.json`` as the single primary ``result`` — byte
   SHA-256 identity, unique ordinals, no directory identities. The kernel
   service validates it strictly and prepares media descriptors from it.

Import direction is exact: the adapter imports only kernel *public* helpers
(``astrid.core.pack.entrypoint``) and its own pack's ``run`` module; it
never imports ``astrid.core.task_executor`` and nothing in the kernel
imports this module.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

PACK_ID = "rendering.timeline_visualize"
"""The canonical capability id the adapter wraps and reports in manifests."""

_RESULT_MANIFEST_REL = "agent-view/manifest.json"
"""The pack's own result manifest, the single primary output of the adapter."""

_DEFAULT_FORMATS: tuple[str, ...] = ("png", "svg", "md")
_DEFAULT_LAYOUT = "time-scaled"
_DEFAULT_FILMSTRIP = "off"


class TimelineVisualizeAdapterError(RuntimeError):
    """Raised when the real renderer cannot produce a valid result manifest.

    The kernel execution service routes any handler exception through the
    fenced repository failure command, so raising here surfaces a typed
    ``failed`` execution outcome instead of corrupting state.
    """


@dataclass(frozen=True, slots=True)
class RendererInputs:
    """Validated renderer inputs decoded from the task's immutable spec."""

    project_slug: str
    timeline_ulid: str
    layout: str
    formats: tuple[str, ...]
    filmstrip: str

    def timeline_dir(self, projects_root: Path) -> Path:
        """The read-only managed timeline directory for this input."""
        return (
            Path(projects_root).resolve()
            / self.project_slug
            / "timelines"
            / self.timeline_ulid
        )


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TimelineVisualizeAdapterError(
            f"task spec field {field!r} must be a non-empty string, got {value!r}"
        )
    return value.strip()


def _decode_inputs(spec: Mapping[str, Any]) -> RendererInputs:
    """Decode and validate the adapter's inputs from one immutable spec."""
    if not isinstance(spec, Mapping):
        raise TimelineVisualizeAdapterError(
            f"task spec must be an object, got {type(spec).__name__}"
        )
    project_slug = _require_non_empty_string(spec.get("project_slug"), "project_slug")
    timeline_ulid = _require_non_empty_string(spec.get("timeline_ulid"), "timeline_ulid")
    layout = _require_non_empty_string(
        spec.get("layout", _DEFAULT_LAYOUT), "layout"
    )
    filmstrip = _require_non_empty_string(
        spec.get("filmstrip", _DEFAULT_FILMSTRIP), "filmstrip"
    )
    raw_formats = spec.get("formats", _DEFAULT_FORMATS)
    if not isinstance(raw_formats, Sequence) or isinstance(raw_formats, (str, bytes)):
        raise TimelineVisualizeAdapterError(
            f"task spec field 'formats' must be a list of strings, got {raw_formats!r}"
        )
    formats = tuple(
        sorted(
            {
                _require_non_empty_string(fmt, "formats[]")
                for fmt in raw_formats
            }
        )
    )
    if not formats:
        raise TimelineVisualizeAdapterError("task spec field 'formats' must not be empty")
    return RendererInputs(
        project_slug=project_slug,
        timeline_ulid=timeline_ulid,
        layout=layout,
        formats=formats,
        filmstrip=filmstrip,
    )


@contextmanager
def _scoped_env(key: str, value: str) -> Iterator[None]:
    """Temporarily set one environment variable, restoring the prior value."""
    previous = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


class TimelineVisualizeAdapter:
    """The injected pack-owned handler for ``rendering.timeline_visualize``.

    Construct with the assigned managed projects root (the same root the
    kernel media staging and managed publication use); the caller injects
    the instance into :meth:`ExecutionService.execute` exactly like any
    other :class:`~astrid.core.task_executor.service.TaskHandler`.
    """

    def __init__(self, *, projects_root: str | Path) -> None:
        self._projects_root = Path(projects_root).resolve()
        if not self._projects_root.is_dir():
            raise TimelineVisualizeAdapterError(
                f"projects root is not a directory: {self._projects_root}"
            )

    def execute(
        self, *, task: Any, staging_dir: Path
    ) -> Mapping[str, Any]:
        """Run the real renderer and return a universal result manifest.

        ``task`` is the kernel :class:`TaskReadModel` (duck-typed: only
        ``task.spec``, ``task.id``, and ``task.created_at`` are read);
        ``staging_dir`` is the assigned staging root the kernel service
        created. All writes land under ``staging_dir``; the seeded timeline
        is never modified.
        """
        staging_dir = Path(staging_dir)
        inputs = _decode_inputs(task.spec)
        timeline_dir = inputs.timeline_dir(self._projects_root)
        if not timeline_dir.is_dir():
            raise TimelineVisualizeAdapterError(
                f"seeded timeline directory is missing: {timeline_dir}"
            )

        argv: list[str] = [
            "--out", str(staging_dir),
            "--project-slug", inputs.project_slug,
            "--timeline-source", str(timeline_dir),
            "--layout", inputs.layout,
            "--filmstrip", inputs.filmstrip,
        ]
        for fmt in inputs.formats:
            argv.extend(["--format", fmt])

        # Lazy import inside the sanctioned canonical runtime context: the
        # pack's run module guards direct invocation, and the context is the
        # in-process equivalent of ASTRID_INTERNAL_INVOCATION=1. Importing
        # here (not at module import) keeps the adapter importable without
        # the renderer's heavy dependency chain.
        with _scoped_env("ASTRID_PROJECTS_ROOT", str(self._projects_root)):
            from astrid.core.pack.entrypoint import canonical_runtime_entrypoint

            with canonical_runtime_entrypoint(PACK_ID):
                from astrid.packs.rendering.executors.timeline_visualize.run import (
                    run_sdk,
                )

                result = run_sdk(argv)

        returncode = result.get("returncode")
        if returncode != 0:
            error = result.get("error")
            message = (
                error.get("message")
                if isinstance(error, Mapping)
                else f"renderer returned {returncode!r}"
            )
            raise TimelineVisualizeAdapterError(
                f"{PACK_ID} renderer failed: {message}"
            )
        outputs_info = result.get("outputs")
        if not isinstance(outputs_info, Mapping):
            raise TimelineVisualizeAdapterError(
                "renderer returned no outputs mapping"
            )
        return self._build_manifest(task, inputs, staging_dir, outputs_info)

    # -- manifest construction --------------------------------------------

    def _build_manifest(
        self,
        task: Any,
        inputs: RendererInputs,
        staging_dir: Path,
        outputs_info: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Build the universal result manifest from the renderer's outputs.

        Only concrete files participate: the pack's ``manifest.json`` is the
        single primary ``result``, and every concrete SVG/PNG/Markdown file
        under the pack root is a secondary ordered output — no directory
        identities, no derived index JSON, exact byte SHA-256 digests.
        """
        pack_root = Path(outputs_info["pack_root"]).resolve()
        try:
            rel_pack = pack_root.relative_to(staging_dir.resolve())
        except ValueError as exc:
            raise TimelineVisualizeAdapterError(
                f"renderer wrote outside the assigned staging root: {pack_root}"
            ) from exc
        file_hashes = outputs_info.get("file_hashes")
        if not isinstance(file_hashes, Mapping):
            raise TimelineVisualizeAdapterError(
                "renderer returned no file_hashes mapping"
            )

        rel_pack_posix = rel_pack.as_posix()
        primary_rel = f"{rel_pack_posix}/manifest.json"
        selected: list[str] = []
        for key in file_hashes:
            rel = f"{rel_pack_posix}/{key}"
            if rel == primary_rel:
                continue
            suffix = Path(rel).suffix.lower()
            if suffix in (".png", ".svg", ".md"):
                selected.append(rel)
        ordered = [primary_rel, *sorted(selected)]

        outputs: list[dict[str, Any]] = []
        for ordinal, rel in enumerate(ordered):
            path = staging_dir / rel
            if not path.is_file():
                raise TimelineVisualizeAdapterError(
                    f"declared renderer output is not a concrete file: {rel}"
                )
            digest = file_hashes.get(Path(rel).name)
            if not isinstance(digest, str) or not digest:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            outputs.append(
                {
                    "path": rel,
                    "content_hash": f"sha256:{digest}",
                    "bytes": path.stat().st_size,
                    "ordinal": ordinal,
                    "is_primary": ordinal == 0,
                    "role": "result" if ordinal == 0 else "output",
                    "label": Path(rel).name,
                }
            )

        created = getattr(task, "created_at", None)
        return {
            "schema_version": 1,
            "kind": PACK_ID,
            "inputs": {
                "task_id": task.id,
                "project_slug": inputs.project_slug,
                "timeline_ulid": inputs.timeline_ulid,
                "layout": inputs.layout,
                "formats": list(inputs.formats),
                "filmstrip": inputs.filmstrip,
            },
            "outputs": outputs,
            "created": created if isinstance(created, str) and created else PACK_ID,
            "warnings": [],
        }
