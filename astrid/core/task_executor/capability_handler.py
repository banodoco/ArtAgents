"""Generic capability TaskHandler — executor/orchestrator via in-process runner.

One handler replaces every per-executor bespoke adapter. It builds the
appropriate RunRequest for the declared kind, invokes the runner
in-process under ASTRID_INTERNAL_INVOCATION=1, discovers concrete
outputs (preferring the capability's manifest.json else walking staging),
and returns a universal result manifest for ExecutionService re-validation.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from astrid.core.env_vars import ASTRID_INTERNAL_INVOCATION
from astrid.core.project.run import discover_manifest_path


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
            raise ValueError(f"capability_kind must be executor/orchestrator, got {capability_kind!r}")
        if not capability_id:
            raise ValueError("capability_id must be non-empty")
        self._kind = capability_kind
        self._capability_id = capability_id
        self._projects_root = Path(projects_root).expanduser().resolve() if projects_root is not None else None
        self._invocation = invocation

    def execute(self, *, task: Any, staging_dir: Path) -> Mapping[str, Any]:
        staging_dir = Path(staging_dir)
        # Build out dir inside staging — the runner writes here, not to a
        # second ledger location. Mirrors bespoke adapters' staging/out split.
        out_dir = staging_dir / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        request_inputs: Mapping[str, Any] = {}
        request_outputs: Mapping[str, Any] = {}
        # Decode inputs from immutable task spec: spec is the runner request
        # payload (inputs/outputs/project/brief etc). Be permissive.
        spec = getattr(task, "spec", {}) or {}
        if isinstance(spec, Mapping):
            request_inputs = dict(spec.get("inputs") or spec.get("request_inputs") or {})
            request_outputs = dict(spec.get("outputs") or {})
            # fallback: spec itself may be flat inputs
            if not request_inputs and spec:
                # if spec looks like input bag (no reserved keys), use it
                reserved = {"capability_id", "capability_kind", "inputs", "outputs", "project", "kind", "request"}
                if not any(k in spec for k in reserved):
                    request_inputs = dict(spec)
                # also support spec.request envelope
                req_env = spec.get("request")
                if isinstance(req_env, Mapping):
                    request_inputs = dict(req_env.get("inputs") or request_inputs)
                    request_outputs = dict(req_env.get("outputs") or request_outputs)
        # project from spec if present
        project = None
        if isinstance(spec, Mapping):
            project = spec.get("project") or (spec.get("request") or {}).get("project") if isinstance(spec.get("request"), Mapping) else spec.get("project")

        with _scoped_env(ASTRID_INTERNAL_INVOCATION, "1"):
            if self._kind == "executor":
                from astrid.core.execution.executor.runner import ExecutorRunRequest, run_executor

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
                )
                result = run_executor(req, None)
                ok = bool(getattr(result, "ok", False))
                if not ok:
                    msg = getattr(result, "payload", {}) or {}
                    raise RuntimeError(f"executor {self._capability_id!r} failed: {msg}")
            else:
                from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest, run_orchestrator

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
                )
                result = run_orchestrator(req, None)
                ok = bool(getattr(result, "ok", False))
                if not ok:
                    raise RuntimeError(f"orchestrator {self._capability_id!r} failed: {result}")

        # Harvest: prefer manifest.json else walk staging/out
        manifest_path = discover_manifest_path(out_dir, fallback_root=staging_dir)
        # also check staging root directly
        if manifest_path is None:
            for cand in (staging_dir / "manifest.json", out_dir / "manifest.json", staging_dir / "agent-view" / "manifest.json", out_dir / "agent-view" / "manifest.json"):
                if cand.is_file():
                    manifest_path = cand
                    break

        rels: list[str] = []
        primary_rel: str | None = None
        if manifest_path is not None and Path(manifest_path).is_file():
            # Re-derive outputs from files referenced by manifest? Prefer walking
            # manifest's declared outputs would require parsing; instead walk out
            # and also include manifest itself as primary.
            primary_rel = Path(manifest_path).resolve().relative_to(staging_dir.resolve()).as_posix() if Path(manifest_path).resolve().is_relative_to(staging_dir.resolve()) else Path(manifest_path).name
            # collect files under out_dir + manifest
            for p in sorted(out_dir.rglob("*")):
                if p.is_file():
                    try:
                        rels.append(p.resolve().relative_to(staging_dir.resolve()).as_posix())
                    except ValueError:
                        continue
            if primary_rel not in rels:
                rels.append(primary_rel)
            # dedup & order with primary first
            uniq = []
            seen = set()
            for r in rels:
                if r not in seen:
                    seen.add(r)
                    uniq.append(r)
            # primary first, rest sorted
            if primary_rel in uniq:
                uniq.remove(primary_rel)
                ordered = [primary_rel, *sorted(uniq)]
            else:
                ordered = sorted(uniq)
        else:
            # walk staging/out
            search_root = out_dir if any(out_dir.iterdir()) else staging_dir
            for p in sorted(search_root.rglob("*")):
                if p.is_file():
                    try:
                        rels.append(p.resolve().relative_to(staging_dir.resolve()).as_posix())
                    except ValueError:
                        continue
            ordered = sorted(set(rels))
            # exclude manifest-less case: first file is primary if any
            primary_rel = ordered[0] if ordered else None

        if not ordered:
            # No concrete files — return evidence-only manifest; ExecutionService
            # expects at least a result summary or output, but handler returns
            # minimal manifest; complete step will need result summary.
            # Provide empty outputs with a result fact so complete can succeed via result path.
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
        created = getattr(task, "created_at", "") or ""
        return {
            "schema_version": 1,
            "kind": self._capability_id,
            "inputs": dict(request_inputs),
            "outputs": outputs,
            "created": created,
            "warnings": [],
        }
