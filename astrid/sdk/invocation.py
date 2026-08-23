"""Public SDK discovery and invocation helpers.

This module keeps invocation orchestration behind the SDK package boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from collections.abc import Mapping
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from ._module import _sdk_module
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
    CapabilityValidationError,
    UnsupportedCapabilityError,
    _error_payload_from_internal_error,
    _internal_error_from_result,
    _sdk_error_from_exception,
)
from .results import DiscoveryResult, InvocationResult, _json_safe, _json_safe_mapping


def run_executor(request: Any, registry: Any) -> Any:
    from astrid.core.execution.executor.runner import run_executor as _run_executor

    return _run_executor(request, registry)


def run_orchestrator(request: Any, registry: Any) -> Any:
    from astrid.core.execution.orchestrator.runner import run_orchestrator as _run_orchestrator

    return _run_orchestrator(request, registry)


def discover(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    kind: str | None = None,
) -> DiscoveryResult:
    sdk_module = _sdk_module()
    discovered_packs = sdk_module._discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    pack_permission_ids_by_pack_id = sdk_module._pack_permission_ids_by_pack_id(discovered_packs)
    executor_registry, orchestrator_registry, element_registry = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=True,
    )
    if element_registry is None:
        raise CapabilityInvocationError("element registry was not loaded")
    (
        packs,
        generation_backends,
        element_kinds,
        generation_features,
        generation_modes,
    ) = sdk_module._build_discovery_metadata(
        discovered_packs,
        element_registry=element_registry,
    )

    if pack_permission_ids_by_pack_id:
        executors = tuple(
            sdk_module._capability_from_executor(
                definition,
                executor_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in executor_registry.list()
        )
        orchestrators = tuple(
            sdk_module._capability_from_orchestrator(
                definition,
                orchestrator_registry,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in orchestrator_registry.list()
        )
        elements = tuple(
            sdk_module._capability_from_element(
                definition,
                pack_permission_ids_by_pack_id=pack_permission_ids_by_pack_id,
            )
            for definition in element_registry.list()
        )
    else:
        executors = tuple(
            sdk_module._capability_from_executor(definition, executor_registry)
            for definition in executor_registry.list()
        )
        orchestrators = tuple(
            sdk_module._capability_from_orchestrator(definition, orchestrator_registry)
            for definition in orchestrator_registry.list()
        )
        elements = tuple(
            sdk_module._capability_from_element(definition)
            for definition in element_registry.list()
        )
    if kind is not None and kind not in ("executor", "orchestrator", "element"):
        raise CapabilityValidationError(
            f"discover(kind=...) must be one of 'executor', 'orchestrator', "
            f"'element' — got {kind!r}"
        )
    executors = executors if kind in (None, "executor") else ()
    orchestrators = orchestrators if kind in (None, "orchestrator") else ()
    elements = elements if kind in (None, "element") else ()
    return DiscoveryResult(
        executors=executors,
        orchestrators=orchestrators,
        elements=elements,
        capabilities=executors + orchestrators + elements,
        packs=packs,
        generation_backends=generation_backends,
        element_kinds=element_kinds,
        generation_features=generation_features,
        generation_modes=generation_modes,
    )


def get_capability(
    capability_id: str,
    *,
    kind: Any | None = None,
    element_kind: str | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    include_elements: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    _registries: tuple[Any, Any, Any | None] | None = None,
):
    sdk_module = _sdk_module()
    if _registries is None:
        executor_registry, orchestrator_registry, element_registry = sdk_module._load_registries(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            banodoco_config=banodoco_config,
            active_theme=active_theme,
            include_missing_roots=include_missing_roots,
            include_elements=include_elements or kind == "element" or kind is None,
        )
    else:
        executor_registry, orchestrator_registry, element_registry = _registries

    return sdk_module._resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )


def _normalize_executor_result(result: Any) -> dict[str, Any]:
    payload = {
        "executor_id": result.executor_id,
        "kind": result.kind,
        "command": result.command,
        "cwd": result.cwd,
        "env": result.env,
        "payload": result.payload,
        "returncode": result.returncode,
        "dry_run": result.dry_run,
        "skipped": result.skipped,
        "skipped_reason": result.skipped_reason,
        "missing_binaries": result.missing_binaries,
        "error": result.error,
        "ok": result.ok,
        "run_id": getattr(result, "run_id", None),
        "run_root": getattr(result, "run_root", None),
        "outputs": getattr(result, "outputs", {}),
        "executor_version": getattr(result, "executor_version", None),
    }
    return _json_safe_mapping(payload)


def _normalize_orchestrator_result(result: Any) -> dict[str, Any]:
    return _json_safe_mapping(result.to_dict())


def _payload_manifest_path(raw_result: Mapping[str, Any]) -> str | None:
    payload = raw_result.get("payload")
    if not isinstance(payload, Mapping):
        return None
    for key in ("manifest_path", "manifest"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        path = Path(value).expanduser().resolve()
        if path.name == "manifest.json":
            return str(path)
    return None


def _discover_invocation_manifest_path(
    raw_result: Mapping[str, Any],
    *,
    out: Path | str | None,
) -> str | None:
    manifest_path = _payload_manifest_path(raw_result)
    if manifest_path is not None:
        return manifest_path
    outputs = raw_result.get("outputs")
    if isinstance(outputs, Mapping):
        output_manifest = outputs.get("manifest_path")
        if isinstance(output_manifest, str):
            candidate = Path(output_manifest).expanduser().resolve()
            if candidate.name == "manifest.json" and candidate.is_file():
                return str(candidate)
    roots: list[Path] = []
    for raw in (raw_result.get("run_root"), out):
        if raw in (None, ""):
            continue
        root = Path(str(raw)).expanduser().resolve()
        if root not in roots:
            roots.append(root)
    for root in roots:
        for candidate in (root / "manifest.json", root / "agent-view" / "manifest.json"):
            if candidate.is_file():
                return str(candidate)
    return None


def _invocation_outputs(
    raw_result: Mapping[str, Any],
    *,
    manifest_path: str | None,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    declared = raw_result.get("outputs")
    if isinstance(declared, Mapping):
        outputs.update(declared)
    payload = raw_result.get("payload")
    if isinstance(payload, Mapping) and isinstance(payload.get("outputs"), Mapping):
        outputs.update(payload["outputs"])
    if manifest_path is not None:
        manifest = Path(manifest_path)
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = None
        if isinstance(document, dict) and document.get("kind") in {
            "timeline_visualize",
            "timeline_visualize_project",
        }:
            pack_root = manifest.parent
            outputs.setdefault("pack_root", str(pack_root))
            outputs.setdefault("manifest_path", str(manifest))
            outputs.setdefault(
                "pages",
                [str(path) for path in sorted(pack_root.rglob("PG*.png"))],
            )
            outputs.setdefault(
                "file_hashes",
                {
                    path.relative_to(pack_root).as_posix(): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(pack_root.rglob("*"))
                    if path.is_file()
                },
            )
    return _json_safe_mapping(outputs)


def _resolve_projects_root(project_root: str | Path | None, project: str | None) -> Path:
    from astrid.core.foundation.project_paths import resolve_projects_root

    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    return resolve_projects_root(None)


def _promote_staged_run_outputs(
    *,
    projects_root: Path,
    project_slug: str,
    run_id: str,
    staging_dir: Path,
) -> Path:
    """Atomically publish one successful task's output tree as its run root.

    Handlers write only into the kernel-owned quarantine.  Once the task has
    completed, the public artifact pack must live below the owning project's
    kernel run, never below global ``.astrid/media/.staging``.  Copying into a
    sibling temporary directory and renaming that complete tree makes readers
    observe either no run artifact directory or the complete immutable pack.
    """

    from astrid.core.foundation.project_paths import run_dir

    source = (staging_dir / "out").resolve()
    if not source.is_dir():
        raise RuntimeError(f"kernel staging output directory is missing: {source}")
    for entry in source.rglob("*"):
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise RuntimeError(f"kernel staging output contains an unsupported entry: {entry}")

    destination = run_dir(project_slug, run_id, root=projects_root).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_dir() and not any(destination.iterdir()):
            destination.rmdir()
        else:
            raise RuntimeError(f"kernel run artifact directory already exists: {destination}")

    temporary = destination.parent / f".{run_id}.{uuid.uuid4().hex}.promoting"
    try:
        shutil.copytree(source, temporary)
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return destination


def _rewrite_promoted_paths(
    value: Any,
    *,
    staging_output: Path,
    run_root: Path,
) -> Any:
    """Rewrite absolute public result paths from quarantine to the run root."""

    if isinstance(value, str):
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            try:
                relative = candidate.resolve().relative_to(staging_output.resolve())
            except ValueError:
                return value
            return str(run_root / relative)
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _rewrite_promoted_paths(
                item,
                staging_output=staging_output,
                run_root=run_root,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _rewrite_promoted_paths(
                item,
                staging_output=staging_output,
                run_root=run_root,
            )
            for item in value
        ]
    return value


def _kernel_invoke(
    capability: Any,
    *,
    kind: Any,
    project: str | None,
    projects_root: Path,
    inputs: Mapping[str, Any] | None,
    outputs: Mapping[str, Any] | None,
) -> tuple[str, str, str, Path | None, dict[str, Any], bool, Any]:
    """Real kernel admission: RunRepository.create with compute_spec_hash idempotency, claim/start, handler, execute/complete."""
    from astrid.core.events.service import EventAppendService
    from astrid.core.integrations.reigh.bridge_service import derive_database_path
    from astrid.core.receipts.service import ReceiptService
    from astrid.core.repositories.media import MediaRepository
    from astrid.core.repositories.projects import (
        ProjectNotFoundError,
        ProjectRepository,
        ProjectSlugConflictError,
    )
    from astrid.core.repositories.runs import RunRepository
    from astrid.core.repositories.tasks import TaskRepository, compute_spec_hash
    from astrid.core.store.uow import UnitOfWork
    from astrid.core.task_executor import CapabilityTaskHandler, ExecutionService
    from astrid.packs import build_standard_registry, open_standard_writer

    registry = build_standard_registry()
    db_path = derive_database_path(projects_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer = open_standard_writer(db_path, registry=registry)
    try:
        events = EventAppendService(registry)
        receipts = ReceiptService()
        runs = RunRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        projects = ProjectRepository(events=events, receipts=receipts)
        media_repo = MediaRepository(events=events, receipts=receipts, projects_root=projects_root)
        project_ref = project if project else "default"
        try:
            project_id = projects.resolve(writer, project_ref)
        except ProjectNotFoundError:
            generated_project_id = hashlib.sha256(f"project:{project_ref}".encode()).hexdigest()[
                :26
            ]
            try:
                created = UnitOfWork(writer).run(
                    lambda u: projects.create(
                        u,
                        slug=project_ref,
                        name=project_ref,
                        settings={},
                        idempotency_key=f"proj:{project_ref}",
                        project_id=generated_project_id,
                    )
                )
                project_id = created.id
            except ProjectSlugConflictError:
                project_id = projects.resolve(writer, project_ref)
        project_row = UnitOfWork(writer).run(
            lambda u: u.query_one("SELECT slug FROM projects WHERE id = ?", (project_id,))
        )
        if project_row is None:
            raise RuntimeError(f"kernel project disappeared after resolution: {project_id!r}")
        project_slug = str(project_row["slug"])
        spec_payload = {
            "capability_id": capability.id,
            "inputs": dict(inputs or {}),
            "outputs": dict(outputs or {}),
            "project": project,
            "kind": str(kind),
        }
        # ``invoke`` has no caller idempotency key, so each public call is a
        # distinct run even when its semantic inputs are identical.  The
        # per-call nonce still gives every repository command in this one
        # drive a stable shared key and deterministic child identities.
        idempotency_key = compute_spec_hash(
            {"invocation_nonce": uuid.uuid4().hex, "request": spec_payload}, []
        )
        deterministic_run_id = hashlib.sha256(f"run:{idempotency_key}".encode()).hexdigest()[:26]
        deterministic_task_id = hashlib.sha256(f"task:{idempotency_key}:0".encode()).hexdigest()[
            :26
        ]
        child_spec = {
            "capability_id": capability.id,
            "inputs": dict(inputs or {}),
            "outputs": dict(outputs or {}),
            "project": project,
            "kind": str(kind),
        }

        def _create(u):
            return runs.create(
                u,
                project_id=project_id,
                children=[
                    {
                        "capability": capability.id,
                        "spec": child_spec,
                        "input_manifest": [],
                        "task_id": deterministic_task_id,
                    }
                ],
                idempotency_key=idempotency_key,
                kind=capability.capability_type,
                title=capability.id,
                input=child_spec,
                run_id=deterministic_run_id,
            )

        fanout = UnitOfWork(writer).run(_create)
        run_id = fanout.run_id
        task_id = fanout.task_ids[0] if fanout.task_ids else None
        if task_id is None:
            raise RuntimeError("kernel admission produced no task")
        # If run already terminal (idempotent replay after success), skip re-drive.
        # Query run status without receipt side-effects.
        row = UnitOfWork(writer).run(
            lambda u: u.query_one("SELECT status FROM runs WHERE id = ?", (run_id,))
        )
        if row is not None and row["status"] in ("succeeded", "failed", "cancelled"):
            # Derive the winning attempt for a stable idempotent return.
            trow = UnitOfWork(writer).run(
                lambda u: u.query_one(
                    "SELECT winning_attempt_id FROM tasks WHERE id = ?", (task_id,)
                )
            )
            winning = (
                trow["winning_attempt_id"]
                if trow is not None and trow["winning_attempt_id"]
                else f"{idempotency_key}:complete"
            )
            from astrid.core.foundation.project_paths import run_dir

            durable_run_root = run_dir(project_slug, run_id, root=projects_root).resolve()
            raw_result = {
                "ok": row["status"] == "succeeded",
                "run_id": run_id,
                "run_root": (str(durable_run_root) if durable_run_root.is_dir() else None),
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": winning,
            }
            replay_manifest = _discover_invocation_manifest_path(raw_result, out=None)
            return (
                run_id,
                task_id,
                winning,
                Path(replay_manifest) if replay_manifest is not None else None,
                raw_result,
                row["status"] == "succeeded",
                None,
            )
        claim_key = f"{idempotency_key}:claim"
        claim = UnitOfWork(writer).run(
            lambda u: tasks.claim(u, project_id=project_id, idempotency_key=claim_key)
        )
        if claim is None:
            # Idempotent replay after task already succeeded but run not yet
            # marked terminal (task succeeded before run derived status).
            raw_result: dict[str, Any] = {
                "ok": True,
                "run_id": run_id,
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": claim_key,
            }
            return run_id, task_id, claim_key, None, raw_result, True, None
        handler = CapabilityTaskHandler(
            capability_kind=capability.capability_type,
            capability_id=capability.id,
            projects_root=projects_root,
        )
        svc = ExecutionService(projects_root=projects_root, task_repo=tasks)
        exec_res = svc.execute(
            UnitOfWork(writer),
            project_id=project_id,
            task_id=claim.task.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key=f"{idempotency_key}:exec",
            handler=handler,
        )
        if exec_res.outcome == "failed":
            raw_result: dict[str, Any] = {
                "ok": False,
                "run_id": run_id,
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": claim.attempt.id,
                "error": exec_res.error,
            }
            return run_id, task_id, claim.attempt.id, None, raw_result, False, None
        assert exec_res.prepared is not None
        prepared = exec_res.prepared
        capability_result = handler.last_result
        if capability_result is None:
            raise RuntimeError("capability handler produced no public result")
        if capability.capability_type == "executor":
            raw_result = _normalize_executor_result(capability_result)
        else:
            raw_result = _normalize_orchestrator_result(capability_result)
        comp = svc.complete(
            UnitOfWork(writer),
            prepared=prepared,
            media_repo=media_repo,
            idempotency_key=f"{idempotency_key}:complete",
        )
        ok = comp.outcome == "completed"
        if not ok:
            raw_result.update(
                {
                    "ok": False,
                    "run_id": run_id,
                    "kernel_run_id": run_id,
                    "kernel_task_id": task_id,
                    "kernel_attempt_id": prepared.attempt.id,
                    "error": comp.error,
                }
            )
            return (
                run_id,
                task_id,
                prepared.attempt.id,
                None,
                raw_result,
                False,
                None,
            )

        durable_run_root = _promote_staged_run_outputs(
            projects_root=projects_root,
            project_slug=project_slug,
            run_id=run_id,
            staging_dir=prepared.staging_dir,
        )
        rewritten = _rewrite_promoted_paths(
            raw_result,
            staging_output=prepared.staging_dir / "out",
            run_root=durable_run_root,
        )
        if not isinstance(rewritten, dict):  # pragma: no cover - mapping input
            raise RuntimeError("promoted capability result is not an object")
        raw_result = rewritten
        raw_result.update(
            {
                "ok": True,
                "run_id": run_id,
                "run_root": str(durable_run_root),
                "kernel_run_id": run_id,
                "kernel_task_id": task_id,
                "kernel_attempt_id": prepared.attempt.id,
            }
        )
        manifest = _discover_invocation_manifest_path(raw_result, out=None)
        mpath = Path(manifest) if manifest is not None else None
        return run_id, task_id, prepared.attempt.id, mpath, raw_result, ok, None
    finally:
        writer.close()


def invoke(
    capability_id: str,
    *,
    kind: Any,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    out: Path | str | None = None,
    project: str | None = None,
    inputs: Mapping[str, Any] | None = None,
    outputs: Mapping[str, Any] | None = None,
    brief: Path | str | None = None,
    dry_run: bool = False,
    check_binaries: bool = False,
    python_exec: str | None = None,
    verbose: bool = False,
    execution_mode: str = "subprocess",
    argv: tuple[str, ...] = (),
    orchestrator_args: tuple[str, ...] = (),
) -> InvocationResult:
    sdk_module = _sdk_module()
    include_elements = kind == "element"
    registries = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        include_elements=include_elements,
    )
    capability = sdk_module.get_capability(
        capability_id,
        kind=kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        banodoco_config=banodoco_config,
        active_theme=active_theme,
        include_missing_roots=include_missing_roots,
        _registries=registries,
    )
    if capability.capability_type == "element":
        raise UnsupportedCapabilityError(f"elements are not invokable via the SDK: {capability.id}")

    # Ledger exemption: dry_run never admitted
    if dry_run:
        try:
            if capability.capability_type == "executor":
                from astrid.core.execution.executor.runner import ExecutorRunRequest

                executor_registry, _, _ = registries
                request = ExecutorRunRequest(
                    executor_id=capability.id,
                    out=out,
                    project=project,
                    inputs=dict(inputs or {}),
                    outputs=dict(outputs or {}),
                    brief=brief,
                    dry_run=True,
                    check_binaries=check_binaries,
                    python_exec=python_exec,
                    verbose=verbose,
                    execution_mode=execution_mode,
                    argv=tuple(argv),
                    invocation="sdk",
                    projects_root=project_root,
                )
                with redirect_stdout(StringIO()):
                    result = sdk_module.run_executor(request, executor_registry)
                raw_result = _normalize_executor_result(result)
            else:
                from astrid.core.execution.orchestrator.runner import OrchestratorRunRequest

                _, orchestrator_registry, _ = registries
                request = OrchestratorRunRequest(
                    orchestrator_id=capability.id,
                    out=out,
                    project=project,
                    inputs=dict(inputs or {}),
                    outputs=dict(outputs or {}),
                    brief=brief,
                    orchestrator_args=tuple(orchestrator_args),
                    dry_run=True,
                    python_exec=python_exec,
                    verbose=verbose,
                    execution_mode=execution_mode,
                    invocation="sdk",
                    projects_root=project_root,
                )
                with redirect_stdout(StringIO()):
                    result = sdk_module.run_orchestrator(request, orchestrator_registry)
                raw_result = _normalize_orchestrator_result(result)
        except AstridSDKError:
            raise
        except Exception as exc:
            mapped = _sdk_error_from_exception(exc)
            if mapped is not None:
                raise mapped from exc
            raise CapabilityInvocationError(
                f"failed to invoke {capability.capability_type} {capability.id!r}"
            ) from exc
        internal_error = _internal_error_from_result(result)
        error = (
            _error_payload_from_internal_error(internal_error, json_safe=_json_safe)
            if internal_error is not None
            else None
        )
        manifest_path = _discover_invocation_manifest_path(raw_result, out=out)
        run_id_raw = raw_result.get("run_id")
        run_root_raw = raw_result.get("run_root")
        executor_version_raw = raw_result.get("executor_version")
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=bool(getattr(result, "ok", False)),
            error=error,
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else None,
            run_root=str(Path(run_root_raw).expanduser().resolve())
            if isinstance(run_root_raw, str) and run_root_raw
            else None,
            outputs=_invocation_outputs(raw_result, manifest_path=manifest_path),
            executor_version=executor_version_raw
            if isinstance(executor_version_raw, str) and executor_version_raw
            else None,
            kernel_run_id=None,
            kernel_task_id=None,
            kernel_attempt_id=None,
        )

    # Real kernel admission path — no fallback; failures raise CapabilityInvocationError.
    # Project is required: mirror runner's selected_project check so missing
    # project maps to CapabilityValidationError (not silent default).
    from astrid.core.project.guidance import format_project_required_guidance, selected_project

    resolved_project, _src = selected_project(project)
    if resolved_project is None:
        raise CapabilityValidationError(
            format_project_required_guidance(operation=f"{capability.capability_type} run")
        )
    # Use resolved project (handles auto-resolved via selected_project)
    project = resolved_project
    projects_root = _resolve_projects_root(project_root, project)
    try:
        kr, kt, ka, mpath, raw_result, ok, _ = _kernel_invoke(
            capability,
            kind=kind,
            project=project,
            projects_root=projects_root,
            inputs=inputs,
            outputs=outputs,
        )
        executor_version_raw = (
            raw_result.get("executor_version") if isinstance(raw_result, dict) else None
        )
        run_id_raw = raw_result.get("run_id") if isinstance(raw_result, dict) else None
        run_root_raw = raw_result.get("run_root") if isinstance(raw_result, dict) else None
        raw_result = dict(raw_result) if isinstance(raw_result, dict) else {}
        raw_result.setdefault("kernel_run_id", kr)
        raw_result.setdefault("kernel_task_id", kt)
        raw_result.setdefault("kernel_attempt_id", ka)
        manifest_path = None
        if ok:
            manifest_path = (
                str(mpath) if mpath else _discover_invocation_manifest_path(raw_result, out=out)
            )
        raw_error = raw_result.get("error")
        if ok:
            public_error = None
        elif isinstance(raw_error, Mapping):
            public_error = _json_safe_mapping(raw_error)
        else:
            public_error = {
                "reason": "capability_failed",
                "message": f"{capability.capability_type} {capability.id!r} failed",
            }
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=ok,
            error=public_error,
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else kr,
            run_root=str(Path(run_root_raw).expanduser().resolve())
            if isinstance(run_root_raw, str) and run_root_raw
            else None,
            outputs=_invocation_outputs(raw_result, manifest_path=manifest_path),
            executor_version=executor_version_raw
            if isinstance(executor_version_raw, str) and executor_version_raw
            else None,
            kernel_run_id=kr,
            kernel_task_id=kt,
            kernel_attempt_id=ka,
        )
    except AstridSDKError:
        raise
    except Exception as exc:
        mapped = _sdk_error_from_exception(exc)
        if mapped is not None:
            raise mapped from exc
        raise CapabilityInvocationError(
            f"failed to invoke {capability.capability_type} {capability.id!r}"
        ) from exc
