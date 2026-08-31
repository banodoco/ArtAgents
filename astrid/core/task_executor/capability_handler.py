"""Generic capability TaskHandler — executor/orchestrator via subprocess runner.

One handler replaces every per-executor bespoke adapter. It builds the
appropriate RunRequest for the declared kind, invokes the runner in a
subprocess under ASTRID_INTERNAL_INVOCATION=1, discovers concrete
outputs (preferring the capability's manifest.json else walking staging),
and returns a universal result manifest for ExecutionService re-validation.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager, nullcontext
from importlib import import_module
from pathlib import Path
from typing import Any, Iterator, Mapping

from astrid.core._shared.result_manifest import validate_result_manifest
from astrid.core.audit.util import SECRET_VALUE_RE
from astrid.core.env_vars import ASTRID_PACKS_PATH, ASTRID_PROJECTS_ROOT
from astrid.core.execution.generic_host import GenericPackHost, HostError
from astrid.core.io.media_import import prepare_media_file
from astrid.core.runtime.manifest import (
    discover_manifest_path,
    load_manifest_output_artifacts,
)

_TIMELINE_VISUALIZE_AUTHORITY_ENV = "ASTRID_TIMELINE_VISUALIZE_AUTHORITY_CONTEXT"


def __getattr__(name: str):
    """Preserve the test/extension hook without an eager runner import."""

    if name == "executor_runner":
        module = import_module("astrid.core.execution.executor.runner")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _failure_log_detail(out_dir: Path) -> str:
    """Return a bounded, secret-scrubbed tail from child runtime logs."""
    log_roots = [out_dir / "logs", out_dir.parent / "logs"]
    chunks: list[str] = []
    paths = sorted({path for root in log_roots if root.is_dir() for path in root.rglob("*.log")})
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        tail = "\n".join(lines[-12:])
        tail = SECRET_VALUE_RE.sub("<redacted>", tail)
        for key, value in os.environ.items():
            if value and any(
                token in key.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD")
            ):
                tail = tail.replace(value, "<redacted>")
        chunks.append(f"{path.name}: {tail}")
    return "\n".join(chunks)[:3500]


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


@contextmanager
def _scoped_pack_roots(extra_pack_roots: Any) -> Iterator[None]:
    """Expose invocation-selected pack roots to nested pack runtimes.

    Discovery is intentionally allowed to inspect ``ASTRID_PACKS_PATH`` while
    a task is being admitted, but the child-process policy must also carry the
    same scope into the renderer.  Keep the overlay process-local and restore
    the caller's environment even when a renderer fails.
    """
    roots = tuple(
        str(Path(root).expanduser().resolve())
        for root in (extra_pack_roots if isinstance(extra_pack_roots, (list, tuple)) else ())
        if isinstance(root, (str, os.PathLike)) and str(root)
    )
    if not roots:
        yield
        return
    previous = os.environ.get(ASTRID_PACKS_PATH)
    existing = tuple(item for item in (previous or "").split(os.pathsep) if item)
    merged: list[str] = []
    for root in (*roots, *existing):
        if root not in merged:
            merged.append(root)
    os.environ[ASTRID_PACKS_PATH] = os.pathsep.join(merged)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(ASTRID_PACKS_PATH, None)
        else:
            os.environ[ASTRID_PACKS_PATH] = previous


class CapabilityTaskHandler:
    """Generic pack-free TaskHandler for executor/orchestrator capabilities."""

    def __init__(
        self,
        *,
        capability_kind: str,
        capability_id: str,
        projects_root: str | Path | None = None,
        invocation: str = "sdk",
        require_executor_version: bool = False,
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
        self._require_executor_version = require_executor_version

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
                    "extra_pack_roots",
                    "authority_context",
                }
                if not any(k in spec for k in reserved):
                    request_inputs = dict(spec)
                req_env = spec.get("request")
                if isinstance(req_env, Mapping):
                    request_inputs = dict(req_env.get("inputs") or request_inputs)
                    request_outputs = dict(req_env.get("outputs") or request_outputs)
        # The immutable invocation spec retains the caller's requested output
        # path.  A retry must not hand that path back to a pack runner: the
        # runner would bypass the staging/completion fence and write a
        # post-admission artifact directly into the project.  Preserve each
        # declared output's filename while relocating it under this attempt's
        # private staging directory.
        staged_outputs: dict[str, Any] = {}
        for name, value in request_outputs.items():
            if isinstance(value, (str, os.PathLike)) and str(value):
                staged_outputs[str(name)] = str(out_dir / Path(value).name)
            else:
                staged_outputs[str(name)] = value
        request_outputs = staged_outputs
        project = None
        if isinstance(spec, Mapping):
            if spec.get("project") is not None:
                project = spec.get("project")
            elif isinstance(spec.get("request"), Mapping):
                project = spec.get("request", {}).get("project")
        if project is None:
            project = getattr(task, "project", None)

        extra_pack_roots = spec.get("extra_pack_roots", ()) if isinstance(spec, Mapping) else ()
        authority_context = (
            spec.get("authority_context") if isinstance(spec, Mapping) else None
        )
        admitted_executor_version = (
            authority_context.get("executor_version")
            if isinstance(authority_context, Mapping)
            and isinstance(authority_context.get("executor_version"), str)
            and authority_context.get("executor_version")
            else None
        )
        if (
            self._kind == "executor"
            and self._require_executor_version
            and admitted_executor_version is None
        ):
            from astrid.core.execution.executor.runner import ExecutorRunnerError

            raise ExecutorRunnerError(
                "cannot retry an executor task admitted before executor-version fencing; "
                "submit a new invocation"
            )

        # Generic single-task admission: no ghost fan-out. All capabilities
        # (executor or orchestrator) execute via their subprocess runner under
        # ASTRID_INTERNAL_INVOCATION=1 (staging-only, kernel-owned ledger).
        root_scope = (
            _scoped_env(ASTRID_PROJECTS_ROOT, str(self._projects_root))
            if self._projects_root is not None
            else nullcontext()
        )
        authority_scope = (
            _scoped_env(
                _TIMELINE_VISUALIZE_AUTHORITY_ENV,
                json.dumps(dict(authority_context), sort_keys=True, separators=(",", ":")),
            )
            if self._capability_id == "rendering.timeline_visualize"
            and isinstance(authority_context, Mapping)
            else nullcontext()
        )
        with (
            _scoped_pack_roots(extra_pack_roots),
            root_scope,
            authority_scope,
        ):
            host_roots = [Path(__file__).resolve().parents[3] / "astrid" / "packs"]
            host_roots.extend(
                Path(root).expanduser().resolve()
                for root in extra_pack_roots
                if isinstance(root, (str, os.PathLike)) and str(root)
            )
            host = GenericPackHost(pack_roots=host_roots)
            admitted_definition, admission = host.admit(self._kind, self._capability_id)
            request_payload = {
                "out": str(out_dir),
                "project": project,
                "inputs": dict(request_inputs),
                "outputs": dict(request_outputs),
                "brief": None,
                "dry_run": False,
                "check_binaries": False,
                "python_exec": None,
                "verbose": False,
                "project_was_auto_resolved": True,
                "invocation": self._invocation,
                "projects_root": str(self._projects_root) if self._projects_root else None,
                "run_root": str(staging_dir),
                "run_id": getattr(task, "id", None),
            }
            if self._kind == "executor":
                request_payload["expected_executor_version"] = admitted_executor_version
            try:
                result = host.invoke_capability(
                    capability_kind=self._kind,
                    capability_id=self._capability_id,
                    request=request_payload,
                    attempt=staging_dir,
                    definition=admitted_definition,
                    admission=admission,
                )
            except HostError as exc:
                detail = _failure_log_detail(out_dir)
                if detail:
                    raise RuntimeError(f"{exc}\n{detail}") from exc
                raise RuntimeError(str(exc)) from exc
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
                        # art path is relative to manifest dir; resolve to staging rel
                        cand = (Path(manifest_path).parent / raw).resolve()
                        if cand.name.endswith(".lock"):
                            continue
                        staging_root = staging_dir.resolve()
                        if not cand.is_relative_to(staging_root):
                            raise RuntimeError(f"manifest output escapes kernel staging: {raw!r}")
                        if cand.is_dir():
                            # Project-level visualization manifests declare
                            # TLxx directories. Kernel publication still owns
                            # concrete files, so expand those directories
                            # deterministically instead of passing a directory
                            # to the media importer.
                            for child in sorted(cand.rglob("*")):
                                resolved_child = child.resolve()
                                if not child.is_file():
                                    continue
                                if not resolved_child.is_relative_to(staging_root):
                                    raise RuntimeError(
                                        "manifest directory output contains a file "
                                        f"outside kernel staging: {raw!r}"
                                    )
                                rels.append(resolved_child.relative_to(staging_root).as_posix())
                            continue
                        if cand.is_file():
                            rels.append(cand.relative_to(staging_root).as_posix())
                # A visualization pack's hash ledger cannot list itself in
                # manifest.outputs without creating a hash cycle, but frozen
                # navigation needs that ledger beside the durable manifest.
                # Publish it as a secondary kernel output explicitly.
                if self._capability_id == "rendering.timeline_visualize":
                    pack_hashes = Path(manifest_path).parent / "pack-hashes.json"
                    if pack_hashes.is_file():
                        rels.append(
                            pack_hashes.resolve().relative_to(staging_dir.resolve()).as_posix()
                        )
            if not rels:
                for p in sorted(out_dir.rglob("*")):
                    if p.is_file() and not p.name.endswith(".lock"):
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
                if p.is_file() and not p.name.endswith(".lock"):
                    try:
                        rels.append(p.resolve().relative_to(staging_dir.resolve()).as_posix())
                    except ValueError:
                        continue
            ordered = sorted(set(rels))
            primary_rel = ordered[0] if ordered else None

        if not ordered:
            # Evidence-only: batch-1 relaxed contract — allow empty outputs as evidence manifest.
            created = getattr(task, "created_at", "") or ""
            empty_manifest: dict[str, Any] = {
                "schema_version": 1,
                "kind": self._capability_id,
                "inputs": dict(request_inputs),
                "outputs": [],
                "created": created,
                "warnings": [],
            }
            capability_version = getattr(result, "executor_version", None)
            if isinstance(capability_version, str) and capability_version:
                empty_manifest["executor_version"] = capability_version
            return empty_manifest

        outputs: list[dict[str, Any]] = []
        for ordinal, rel in enumerate(ordered):
            path = staging_dir / rel
            prepared = prepare_media_file(path, root=staging_dir)
            label = Path(rel).name
            if self._capability_id == "rendering.timeline_visualize" and manifest_path is not None:
                pack_root = Path(manifest_path).parent.resolve()
                resolved_path = path.resolve()
                if resolved_path.is_relative_to(pack_root):
                    # Preserve the logical path inside the evidence pack. CAS
                    # stores each member independently, so a basename alone
                    # cannot reconstruct nested filmstrip assets safely.
                    label = resolved_path.relative_to(pack_root).as_posix()
            outputs.append(
                {
                    "path": rel,
                    "content_hash": f"sha256:{prepared.digest}",
                    "bytes": prepared.byte_size,
                    "ordinal": ordinal,
                    "is_primary": ordinal == 0,
                    "role": "result" if ordinal == 0 else "output",
                    "label": label,
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
        capability_version = getattr(result, "executor_version", None)
        if isinstance(capability_version, str) and capability_version:
            raw_manifest["executor_version"] = capability_version
        # Reuse service validation — don't reimplement, just ensure it passes here.
        validate_result_manifest(raw_manifest, staging_root=staging_dir)
        return raw_manifest
