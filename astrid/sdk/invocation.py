"""Public SDK discovery and invocation helpers.

This module keeps invocation orchestration behind the SDK package boundary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from ._module import _sdk_module
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
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
                dry_run=dry_run,
                check_binaries=check_binaries,
                python_exec=python_exec,
                verbose=verbose,
                execution_mode=execution_mode,
                argv=tuple(argv),
                invocation="sdk",
            )
            # SDK callers own stdout (the timeline CLI emits one JSON object).
            # Executor stdout remains available in managed run logs.
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
                dry_run=dry_run,
                python_exec=python_exec,
                verbose=verbose,
                execution_mode=execution_mode,
                invocation="sdk",
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
        run_root=(
            str(Path(run_root_raw).expanduser().resolve())
            if isinstance(run_root_raw, str) and run_root_raw
            else None
        ),
        outputs=_invocation_outputs(raw_result, manifest_path=manifest_path),
        executor_version=(
            executor_version_raw
            if isinstance(executor_version_raw, str) and executor_version_raw
            else None
        ),
    )
