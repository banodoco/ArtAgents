"""Generic capability TaskHandler — executor/orchestrator via in-process runner.

One handler replaces every per-executor bespoke adapter. It builds the
appropriate RunRequest for the declared kind, invokes the runner
in-process under ASTRID_INTERNAL_INVOCATION=1, discovers concrete
outputs (preferring the capability's manifest.json else walking staging),
and returns a universal result manifest for ExecutionService re-validation.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from astrid.core._shared.result_manifest import validate_result_manifest
from astrid.core.env_vars import ASTRID_INTERNAL_INVOCATION
from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor
from astrid.core.io.media_import import prepare_media_file
from astrid.core.project.run import discover_manifest_path, load_manifest_output_artifacts


@contextmanager
def _scoped_env(key: str, value: str) -> Iterator[None]:
    prev = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prev


class CapabilityTaskHandler:
    """Generic pack-free TaskHandler for executor/orchestrator capabilities."""

    def __init__(
        self,
        *,
        capability_kind: str,
        capability_id: str,
        projects_root: str | Path | None = None,
        invocation: str = "sdk",
    ) -> None:
        if capability_kind not in ("executor", "orchestrator"):
            raise ValueError(
                f"capability_kind must be executor/orchestrator, got {capability_kind!r}"
            )
        if not capability_id:
            raise ValueError("capability_id must be non-empty")
        self._kind = capability_kind
        self._capability_id = capability_id
        self._projects_root = (
            Path(projects_root).expanduser().resolve() if projects_root is not None else None
        )
        self._invocation = invocation
        self._last_result: Any | None = None

    @property
    def last_result(self) -> Any | None:
        """Return the runner result produced by the most recent execution.

        The kernel service owns validation and completion, while the SDK
        boundary still needs the capability's public payload, output map, and
        executor definition digest.  Keeping that non-authoritative result on
        this per-invocation handler avoids reconstructing public metadata from
        the universal task manifest.
        """

        return self._last_result

    def execute(self, *, task: Any, staging_dir: Path) -> Mapping[str, Any]:
        staging_dir = Path(staging_dir)
        out_dir = staging_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        request_inputs: Mapping[str, Any] = {}
        request_outputs: Mapping[str, Any] = {}
        spec = getattr(task, "spec", {}) or {}
        if isinstance(spec, Mapping):
            request_inputs = dict(spec.get("inputs") or spec.get("request_inputs") or {})
            request_outputs = dict(spec.get("outputs") or {})
            if not request_inputs and spec:
                reserved = {
                    "capability_id",
                    "capability_kind",
                    "inputs",
                    "outputs",
                    "project",
                    "kind",
                    "request",
                }
                if not any(k in spec for k in reserved):
                    request_inputs = dict(spec)
                req_env = spec.get("request")
                if isinstance(req_env, Mapping):
                    request_inputs = dict(req_env.get("inputs") or request_inputs)
                    request_outputs = dict(req_env.get("outputs") or request_outputs)
        project = None
        if isinstance(spec, Mapping):
            if spec.get("project") is not None:
                project = spec.get("project")
            elif isinstance(spec.get("request"), Mapping):
                project = spec.get("request", {}).get("project")

        # Generic single-task admission: no ghost fan-out. All capabilities
        # (executor or orchestrator) execute via their real runner under
        # ASTRID_INTERNAL_INVOCATION=1 (staging-only, kernel-owned ledger).
        with _scoped_env(ASTRID_INTERNAL_INVOCATION, "1"):
            if self._kind == "executor":
                req = ExecutorRunRequest(
                    executor_id=self._capability_id,
                    out=out_dir,
                    project=project,
                    inputs=dict(request_inputs),
                    outputs=dict(request_outputs),
                    brief=None,
                    dry_run=False,
                    check_binaries=False,
                    python_exec=None,
                    verbose=False,
                    execution_mode="in_process",
                    argv=(),
                    invocation=self._invocation,
                    projects_root=self._projects_root,
                    project_was_auto_resolved=True,
                )
                result = run_executor(req, None)
                self._last_result = result
                ok = bool(getattr(result, "ok", False))
                if not ok:
                    msg = getattr(result, "payload", {}) or {}
                    raise RuntimeError(f"executor {self._capability_id!r} failed: {msg}")
            else:
                from astrid.core.execution.orchestrator.runner import (
                    OrchestratorRunRequest,
                    run_orchestrator,
                )  # noqa: E402

                req = OrchestratorRunRequest(
                    orchestrator_id=self._capability_id,
                    out=out_dir,
                    project=project,
                    inputs=dict(request_inputs),
                    outputs=dict(request_outputs),
                    brief=None,
                    orchestrator_args=(),
                    dry_run=False,
                    python_exec=None,
                    verbose=False,
                    execution_mode="in_process",
                    invocation=self._invocation,
                    projects_root=self._projects_root,
                    project_was_auto_resolved=True,
                )
                result = run_orchestrator(req, None)
                self._last_result = result
                ok = bool(getattr(result, "ok", False))
                if not ok:
                    raise RuntimeError(f"orchestrator {self._capability_id!r} failed: {result}")
        manifest_path = discover_manifest_path(out_dir, fallback_root=staging_dir)
        if manifest_path is None:
            for cand in (
                staging_dir / "manifest.json",
                out_dir / "manifest.json",
                staging_dir / "agent-view" / "manifest.json",
                out_dir / "agent-view" / "manifest.json",
            ):
                if cand.is_file():
                    manifest_path = cand
                    break

        rels: list[str] = []
        primary_rel: str | None = None
        if manifest_path is not None and Path(manifest_path).is_file():
            artifacts = load_manifest_output_artifacts(manifest_path)
            # Collect concrete files: prefer artifacts list, else walk out_dir
            if artifacts:
                for art in artifacts:
                    raw = art.get("path") or art.get("relative_path") or art.get("file")
                    if isinstance(raw, str) and raw:
                        # Artifact manifests may declare a directory (for
                        # example one child pack per timeline). Expand such
                        # entries into concrete files before preparing media;
                        # the universal task manifest never names a directory.
                        cand = (Path(manifest_path).parent / raw).resolve()
                        candidates = (
                            sorted(path for path in cand.rglob("*") if path.is_file())
                            if cand.is_dir()
                            else [cand]
                        )
                        for concrete in candidates:
                            try:
                                rel = concrete.relative_to(staging_dir.resolve()).as_posix()
                            except ValueError:
                                rel = raw
                            rels.append(rel)
            if not rels:
                for p in sorted(out_dir.rglob("*")):
                    if p.is_file():
                        try:
                            rels.append(p.resolve().relative_to(staging_dir.resolve()).as_posix())
                        except ValueError:
                            continue
            primary_rel = (
                Path(manifest_path).resolve().relative_to(staging_dir.resolve()).as_posix()
                if Path(manifest_path).resolve().is_relative_to(staging_dir.resolve())
                else Path(manifest_path).name
            )
            if primary_rel not in rels:
                rels.append(primary_rel)
            uniq: list[str] = []
            seen: set[str] = set()
            for r in rels:
                if r not in seen:
                    seen.add(r)
                    uniq.append(r)
            if primary_rel in uniq:
                uniq.remove(primary_rel)
                ordered = [primary_rel, *sorted(uniq)]
            else:
                ordered = sorted(uniq)
        else:
            search_root = out_dir if any(out_dir.iterdir()) else staging_dir
            for p in sorted(search_root.rglob("*")):
                if p.is_file():
                    try:
                        rels.append(p.resolve().relative_to(staging_dir.resolve()).as_posix())
                    except ValueError:
                        continue
            ordered = sorted(set(rels))
            primary_rel = ordered[0] if ordered else None

        if not ordered:
            # Evidence-only: batch-1 relaxed contract — allow empty outputs as evidence manifest.
            created = getattr(task, "created_at", "") or ""
            return {
                "schema_version": 1,
                "kind": self._capability_id,
                "inputs": dict(request_inputs),
                "outputs": [],
                "created": created,
                "warnings": [],
            }

        outputs: list[dict[str, Any]] = []
        for ordinal, rel in enumerate(ordered):
            path = staging_dir / rel
            prepared = prepare_media_file(path, root=staging_dir)
            outputs.append(
                {
                    "path": rel,
                    "content_hash": f"sha256:{prepared.digest}",
                    "bytes": prepared.byte_size,
                    "ordinal": ordinal,
                    "is_primary": ordinal == 0,
                    "role": "result" if ordinal == 0 else "output",
                    "label": Path(rel).name,
                }
            )
        created = getattr(task, "created_at", "") or ""
        raw_manifest: dict[str, Any] = {
            "schema_version": 1,
            "kind": self._capability_id,
            "inputs": dict(request_inputs),
            "outputs": outputs,
            "created": created,
            "warnings": [],
        }
        # Reuse service validation — don't reimplement, just ensure it passes here.
        validate_result_manifest(raw_manifest, staging_root=staging_dir)
        return raw_manifest
