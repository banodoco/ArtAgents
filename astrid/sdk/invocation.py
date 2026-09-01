"""Public SDK discovery and invocation helpers.

This module keeps invocation orchestration behind the SDK package boundary.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._module import _sdk_module
from .exceptions import (
    AstridSDKError,
    CapabilityInvocationError,
    CapabilityMissingInputError,
    CapabilityPreconditionError,
    CapabilityValidationError,
    UnsupportedCapabilityError,
    _sdk_error_from_exception,
)
from .results import DiscoveryResult, InvocationResult, _json_safe, _json_safe_mapping


def _expanded_config_hash(config: Mapping[str, Any]) -> str:
    """Hash the exact in-memory expansion sent to the renderer."""
    payload = json.dumps(
        config, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def discover(
    *,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    banodoco_config: Any | None = None,
    active_theme: str | Path | None = None,
    include_missing_roots: bool = False,
    kind: str | None = None,
) -> DiscoveryResult:
    sdk_module = _sdk_module()
    discovered_packs = sdk_module._discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    pack_permission_ids_by_pack_id = sdk_module._pack_permission_ids_by_pack_id(discovered_packs)
    executor_registry, orchestrator_registry, element_registry = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        banodoco_config=banodoco_config,
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
            banodoco_config=banodoco_config,
            include_missing_roots=include_missing_roots,
            include_elements=include_elements or kind == "element" or kind is None,
        )
    else:
        executor_registry, orchestrator_registry, element_registry = _registries

    resolved = sdk_module._resolve_capability(
        capability_id,
        kind=kind,
        element_kind=element_kind,
        executor_registry=executor_registry,
        orchestrator_registry=orchestrator_registry,
        element_registry=element_registry,
    )
    # Keep direct describes consistent with discover(): pack-level and
    # capability-specific safety permissions are part of the public handle,
    # not only of the full inventory DTO.
    discovered_packs = sdk_module._discover_pack_inventory(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    return sdk_module._apply_pack_permission_ids(
        resolved,
        pack_permission_ids_by_pack_id=sdk_module._pack_permission_ids_by_pack_id(discovered_packs),
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


def _validate_manifest_preview_inputs(
    capability: Any,
    *,
    inputs: Mapping[str, Any] | None,
    orchestrator_args: tuple[str, ...],
) -> dict[str, Any]:
    """Validate only manifest-owned inputs for a read-only invocation preview.

    Dry-run is deliberately a ledger/manifest operation.  It must not build a
    runner request (which imports project/run helpers), inspect an output tree,
    or resolve a local project.  Port requirements and declared orchestrator
    inputs are still checked here so callers retain the useful typed failures
    they receive from a live admission attempt.
    """

    values = dict(inputs or {})
    ports = tuple(getattr(capability, "inputs", ()) or ())
    # Defaults belong to the manifest ledger.  Include them in the effective
    # preview values without consulting runtime or project state.
    for port in ports:
        if port.name not in values and getattr(port, "default", None) is not None:
            values[port.name] = port.default
    missing = [
        str(port.name)
        for port in ports
        if bool(getattr(port, "required", False))
        and getattr(port, "default", None) is None
        and values.get(port.name) in (None, "")
    ]
    if missing:
        raise CapabilityMissingInputError(
            f"{capability.capability_type} {capability.id!r} missing required input(s): "
            f"{', '.join(missing)}"
        )

    if capability.capability_type == "executor":
        metadata = capability.definition.get("metadata", {})
        choices = metadata.get("input_choices") if isinstance(metadata, Mapping) else None
        if isinstance(choices, Mapping):
            for input_name, raw_options in choices.items():
                if not isinstance(raw_options, (list, tuple)) or input_name not in values:
                    continue
                options = tuple(str(option) for option in raw_options)
                if str(values[input_name]) not in options:
                    rendered = ", ".join(options)
                    raise CapabilityValidationError(
                        f"invalid {input_name} {values[input_name]!r} for executor "
                        f"{capability.id!r}; valid options: {rendered}; recovery: retry with "
                        f"--{str(input_name).replace('_', '-')} <one of: {rendered}>"
                    )
        requirements = (
            metadata.get("input_requirements_by_choice")
            if isinstance(metadata, Mapping)
            else None
        )
        if isinstance(requirements, Mapping):
            for selector, choices_by_value in requirements.items():
                selected = values.get(str(selector))
                if selected is None or not isinstance(choices_by_value, Mapping):
                    continue
                required = choices_by_value.get(str(selected))
                if not isinstance(required, (list, tuple)):
                    continue
                missing_choice = [
                    str(name)
                    for name in required
                    if values.get(str(name)) in (None, "")
                ]
                if missing_choice:
                    raise CapabilityMissingInputError(
                        f"executor {capability.id!r} missing required input(s) for "
                        f"{selector}={selected!r}: {', '.join(missing_choice)}"
                    )
    else:
        declared = {str(port.name) for port in ports}
        unknown = sorted(set(values) - declared)
        if unknown:
            declared_hint = ", ".join(sorted(declared)) or "none"
            raise CapabilityValidationError(
                f"orchestrator {capability.id!r} does not declare SDK input(s): "
                f"{', '.join(unknown)}; declared inputs: {declared_hint}. recovery: pass the "
                "runtime flags through orchestrator_args=(\"--flag\", \"value\") and retry"
            )

    return _json_safe_mapping(values)


def _manifest_dry_run_result(
    capability: Any,
    *,
    inputs: Mapping[str, Any] | None,
    outputs: Mapping[str, Any] | None,
    brief: Path | str | None,
    python_exec: str | None,
    out: Path | str | None = None,
    orchestrator_args: tuple[str, ...] = (),
) -> tuple[dict[str, Any], bool]:
    """Build the stable no-side-effect preview envelope from a capability DTO."""

    validation_inputs = dict(inputs or {})
    if brief is not None:
        validation_inputs.setdefault("brief", brief)
    preview_inputs = _validate_manifest_preview_inputs(
        capability,
        inputs=validation_inputs,
        orchestrator_args=orchestrator_args,
    )
    if brief is not None:
        preview_inputs.setdefault("brief", _json_safe(brief))
    if python_exec is not None:
        preview_inputs.setdefault("python_exec", python_exec)
    preview = {
        "kind": "manifest-ledger",
        "capability_id": str(capability.id),
        "inputs": preview_inputs,
        "outputs": _json_safe_mapping(dict(outputs or {})),
    }
    command = _manifest_preview_command(
        capability,
        inputs=preview_inputs,
        outputs=outputs,
        brief=brief,
        python_exec=python_exec,
        out=out,
        orchestrator_args=orchestrator_args,
    )
    if capability.capability_type == "executor":
        return {
            "executor_id": capability.id,
            "kind": capability.native_kind,
            "command": command,
            "cwd": None,
            "env": {},
            "payload": {"preview": preview},
            "returncode": None,
            "dry_run": True,
            "skipped": False,
            "skipped_reason": "",
            "missing_binaries": [],
            "error": None,
            "ok": True,
            "run_id": None,
            "run_root": None,
            "outputs": {},
            "executor_version": None,
        }, True

    runtime = capability.definition.get("runtime", {})
    runtime_kind = runtime.get("kind") if isinstance(runtime, Mapping) else None
    return {
        "orchestrator_id": capability.id,
        "kind": capability.native_kind,
        "runtime_kind": runtime_kind or "unknown",
        "command": command,
        "planned_commands": [command] if command else [],
        "cwd": None,
        "env": {},
        "returncode": None,
        "dry_run": True,
        "outputs": {},
        "errors": [],
        "plan": {
            "steps": [],
            "summary": "manifest-ledger preview; execution deferred to the runtime",
        },
        "preview": preview,
        "ok": True,
    }, True


def _manifest_preview_command(
    capability: Any,
    *,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any] | None,
    brief: Path | str | None,
    python_exec: str | None,
    out: Path | str | None = None,
    orchestrator_args: tuple[str, ...] = (),
) -> list[str]:
    """Expand a manifest command without importing a runner or touching disk.

    This is intentionally a lightweight display-only expansion. It expands
    manifest placeholders and input mappings only; no runner or project
    authority is imported. Pipeline-step executors without an explicit
    command use their manifest runtime module and declared inputs/defaults.
    """

    definition = capability.definition
    if capability.capability_type == "executor":
        raw_command = definition.get("command")
        if not isinstance(raw_command, Mapping):
            module = definition.get("metadata", {}).get("runtime_module")
            if not isinstance(module, str) or not module:
                return []
            values = {str(key): value for key, value in inputs.items()}
            values.setdefault("python_exec", python_exec or "python")
            command = [str(values["python_exec"]), "-m", module]
            for port in tuple(getattr(capability, "inputs", ()) or ()):
                value = values.get(port.name)
                if value in (None, ""):
                    continue
                flag = f"--{str(port.name).replace('_', '-')}"
                if str(getattr(port, "type", "")) == "boolean":
                    if _manifest_truthy(value):
                        command.append(flag)
                else:
                    for item in _manifest_input_items(value):
                        if item not in (None, ""):
                            command.extend((flag, _manifest_stringify(item)))
            if out not in (None, ""):
                command.extend(("--out", _manifest_stringify(out)))
            return command
    else:
        runtime = definition.get("runtime")
        raw_command = runtime.get("command") if isinstance(runtime, Mapping) else None
    if not isinstance(raw_command, Mapping):
        return []
    raw_argv = raw_command.get("argv")
    if not isinstance(raw_argv, (list, tuple)):
        return []
    ports = tuple(getattr(capability, "inputs", ()) or ())
    port_by_name = {str(port.name): port for port in ports}
    values: dict[str, Any] = {str(key): value for key, value in inputs.items()}
    for port in ports:
        if port.name not in values and getattr(port, "default", None) is not None:
            values[port.name] = port.default
    values.setdefault("brief", brief)
    values.setdefault("python_exec", python_exec or "python")
    values.setdefault("verbose", "false")
    if out not in (None, ""):
        values["out"] = out
    elif isinstance(outputs, Mapping) and "out" in outputs:
        values["out"] = outputs.get("out")
    pattern = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
    command: list[str] = []
    for raw_part in raw_argv:
        if not isinstance(raw_part, str):
            continue
        if raw_part == "{orchestrator_args}":
            command.extend(str(value) for value in orchestrator_args)
            continue
        command.append(
            pattern.sub(
                lambda match: (
                    _manifest_stringify(values[match.group(1)])
                    if match.group(1) in values and values[match.group(1)] is not None
                    else match.group(0)
                ),
                raw_part,
            )
        )
    mappings = raw_command.get("input_args", ())
    if isinstance(mappings, (list, tuple)):
        appended: list[str] = []
        for raw_mapping in mappings:
            if not isinstance(raw_mapping, Mapping):
                continue
            name = str(raw_mapping.get("input", ""))
            if not name:
                continue
            value = values.get(name)
            if value in (None, ""):
                if bool(raw_mapping.get("optional", False)):
                    continue
                raise CapabilityMissingInputError(
                    f"capability {capability.id!r} missing mapped input {name!r}"
                )
            items = _manifest_input_items(value)
            if len(items) > 1 and not bool(raw_mapping.get("repeatable", False)):
                raise CapabilityValidationError(
                    f"capability {capability.id!r} input {name!r} is not repeatable"
                )
            port = port_by_name.get(name)
            expanded: list[str] = []
            for item in items:
                if item in (None, ""):
                    continue
                flag = raw_mapping.get("flag")
                if str(getattr(port, "type", "")) == "boolean":
                    if _manifest_truthy(item) and flag:
                        expanded.append(str(flag))
                else:
                    if flag:
                        expanded.append(str(flag))
                    expanded.append(_manifest_stringify(item))
            before = raw_mapping.get("before")
            if before is None:
                appended.extend(expanded)
            else:
                try:
                    insert_at = command.index(str(before))
                except ValueError:
                    appended.extend(expanded)
                else:
                    command[insert_at:insert_at] = expanded
        command.extend(appended)

    # Auto-forward only declared inputs, matching live command semantics and
    # avoiding accidental flags for SDK-only controls such as ``verbose``.
    # Explicit-command executors may opt out when their entrypoint accepts a
    # deliberately narrower CLI than the manifest's SDK input surface (for
    # an explicit command template may have a narrower CLI than the manifest's
    # SDK input surface. Keep this in lockstep with the
    # runtime runner's metadata.auto_forward_inputs contract.
    metadata = definition.get("metadata", {})
    if isinstance(metadata, Mapping) and metadata.get("auto_forward_inputs") is False:
        return command
    raw_text = " ".join(str(part) for part in raw_argv)
    mapped_names = {
        str(item.get("input"))
        for item in mappings
        if isinstance(item, Mapping) and item.get("input")
    } if isinstance(mappings, (list, tuple)) else set()
    for port in ports:
        name = str(port.name)
        value = values.get(name)
        if name in mapped_names or f"{{{name}}}" in raw_text or value in (None, ""):
            continue
        flag = f"--{name.replace('_', '-')}"
        if str(getattr(port, "type", "")) == "boolean":
            if _manifest_truthy(value):
                command.append(flag)
            continue
        for item in _manifest_input_items(value):
            if item not in (None, ""):
                command.extend((flag, _manifest_stringify(item)))
    return command


def _manifest_input_items(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    if isinstance(value, (set, frozenset)):
        # Repeatable inputs may arrive as sets from SDK callers.  Preserve
        # list/tuple order, but canonicalize set order for stable previews
        # across Python processes with different hash seeds.
        return tuple(sorted(value, key=lambda item: (type(item).__name__, str(item))))
    return (value,)


def _manifest_stringify(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return ",".join(str(item) for item in _manifest_input_items(value))
    return str(value)


def _manifest_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _validate_timeline_visualize_inputs(
    inputs: Mapping[str, Any] | None,
    *,
    project: str | None,
    project_root: str | Path | None = None,
    out: str | Path | None = None,
) -> dict[str, Any]:
    """Validate visualization's selector/ownership contract before admission.

    This is intentionally read-only.  Timeline visualization's runner repeats
    the checks as defense-in-depth, but a public SDK call must reject a
    foreign, missing, or malformed timeline before kernel admission.
    """

    values = dict(inputs or {})
    raw_formats = values.get("formats")
    if raw_formats is not None:
        if isinstance(raw_formats, str):
            raw_formats = [raw_formats]
        if not isinstance(raw_formats, (list, tuple, set)):
            raise CapabilityValidationError(
                "rendering.timeline_visualize formats must be a list of png, svg, md, or all"
            )
        formats = {
            part.strip().lower()
            for token in raw_formats
            for part in str(token).split(",")
            if part.strip()
        }
        if not formats:
            raise CapabilityValidationError(
                "rendering.timeline_visualize formats must contain png, svg, md, or all"
            )
        allowed = {"png", "svg", "md", "all"}
        invalid = sorted(formats - allowed)
        if invalid:
            raise CapabilityValidationError(
                f"invalid visualization format(s): {', '.join(invalid)}; "
                "choose png, svg, md, or all"
            )
        if "all" in formats and len(formats) > 1:
            raise CapabilityValidationError(
                "visualization format 'all' cannot be combined with another format"
            )
    if out not in (None, ""):
        raise CapabilityValidationError(
            "--out is not supported for project timeline visualization; "
            "omit it and use the returned durable manifest_path"
        )
    # Timeline files are authoring/migration inputs only.  A live product
    # invocation must address a runtime-owned timeline by its stable ref.
    if "timeline_source" in values:
        raise CapabilityValidationError(
            "timeline_source is not a supported product input; use timeline_slug "
            "or the runtime-selected default"
        )
    has_ref = values.get("timeline_slug") not in (None, "")
    select_all = bool(values.get("all", False))
    if has_ref and select_all:
        raise CapabilityValidationError(
            "timeline_slug and all are mutually exclusive; choose one timeline ref or all"
        )
    from_view = values.get("from_view") not in (None, "")
    focus = values.get("focus") not in (None, "")
    if from_view != focus:
        raise CapabilityValidationError(
            "from_view and focus must be supplied together for visualization navigation"
        )
    cold_selectors = [
        name
        for name in ("shot", "range", "at", "clip", "asset")
        if values.get(name) not in (None, "")
    ]
    if len(cold_selectors) > 1:
        raise CapabilityValidationError(
            "cold selectors are mutually exclusive: "
            + ", ".join(f"--{name}" for name in cold_selectors)
        )
    refresh_root = bool(values.get("refresh_root", False))
    if refresh_root and not from_view:
        raise CapabilityValidationError("refresh_root requires from_view and focus")
    if from_view:
        conflicts = [
            name
            for name, present in (
                ("timeline_slug", has_ref),
                ("all", select_all),
                *((name, name in cold_selectors) for name in cold_selectors),
            )
            if present
        ]
        if conflicts:
            raise CapabilityValidationError(
                "from_view/focus cannot be combined with "
                + ", ".join(f"--{name.replace('_', '-')}" for name in conflicts)
            )
    filmstrip = values.get("filmstrip")
    rendered_video = values.get("rendered_video")
    layout = values.get("layout")
    if layout is not None and (
        not isinstance(layout, str) or layout not in {"time-scaled", "linear", "both"}
    ):
        raise CapabilityValidationError(
            "layout must be time-scaled, linear, or both"
        )
    if filmstrip is not None and (
        not isinstance(filmstrip, str)
        or filmstrip not in {"auto", "off", "assets", "rendered"}
    ):
        raise CapabilityValidationError(
            "filmstrip must be auto, off, assets, or rendered"
        )
    scope = values.get("scope")
    if scope is not None and (
        not isinstance(scope, str)
        or scope not in {
            "project",
            "timeline",
            "shot",
            "range",
            "clip",
            "asset",
            "timestamp",
        }
    ):
        raise CapabilityValidationError(
            "scope must be project, timeline, shot, range, clip, asset, or timestamp"
        )
    raw_context = values.get("context", 3.0)
    if (
        isinstance(raw_context, bool)
        or not isinstance(raw_context, (int, float))
        or not math.isfinite(float(raw_context))
        or float(raw_context) < 0
    ):
        raise CapabilityValidationError("context must be a finite non-negative number")
    raw_neighbors = values.get("neighbors", 0)
    if (
        isinstance(raw_neighbors, bool)
        or not isinstance(raw_neighbors, int)
        or raw_neighbors < 0
    ):
        raise CapabilityValidationError("neighbors must be a non-negative integer")
    if rendered_video not in (None, "") and filmstrip not in (None, "auto", "rendered"):
        raise CapabilityValidationError(
            "rendered_video requires filmstrip auto or rendered"
        )
    if filmstrip == "rendered" and rendered_video in (None, ""):
        raise CapabilityValidationError("filmstrip rendered requires rendered_video")
    requested_project = values.get("project_slug")
    if (
        requested_project not in (None, "")
        and project not in (None, "")
        and requested_project != project
    ):
        raise CapabilityValidationError(
            f"project_slug {requested_project!r} does not match project {project!r}"
        )

    if project is None or not str(project).strip():
        raise CapabilityValidationError(
            "rendering.timeline_visualize requires project=<slug> to resolve a managed timeline"
        )

    # Timeline identity and content come from the neutral runtime.  The
    # executor's local root is only a disposable materialization base for
    # frozen result rehydration; it is never scanned for a project or timeline.
    from astrid.packs.rendering.executors.timeline_visualize.select import (
        select_kernel_timelines,
    )

    managed_project = (
        Path(project_root).expanduser().resolve() if project_root is not None else None
    )

    if from_view:
        if managed_project is None:
            raise CapabilityValidationError(
                "from_view requires an explicit attempt-local project_root"
            )
        raw_view = Path(str(values["from_view"])).expanduser()
        if not raw_view.is_absolute():
            raise CapabilityValidationError(
                "from_view must be an absolute path; cwd-relative visualization paths "
                "are not accepted"
            )
        view_path = raw_view
        if not view_path.is_file():
            raise CapabilityValidationError(
                f"from_view must name an existing visualization manifest: {view_path}"
            )
        from astrid.packs.rendering.executors.timeline_visualize.frozen import (
            FrozenViewError,
            discard_rehydrated_pack,
            load_frozen_view,
            resolve_focus,
        )
        from astrid.packs.rendering.executors.timeline_visualize.ids import (
            parse_qualified_ref,
        )

        try:
            frozen = load_frozen_view(view_path, project_root=managed_project)
        except FrozenViewError as exc:
            raise CapabilityValidationError(f"from_view rejected: {exc}") from exc
        try:
            try:
                resolved_focus = resolve_focus(
                    frozen,
                    str(values["focus"]),
                    context_seconds=float(raw_context),
                    neighbors=raw_neighbors,
                )
                parsed_focus = parse_qualified_ref(str(values["focus"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise CapabilityValidationError(f"focus rejected: {exc}") from exc
            if refresh_root and (
                parsed_focus.kind != "TL" or resolved_focus.kind != "timeline"
            ):
                raise CapabilityValidationError(
                    "refresh_root focus must be the frozen timeline reference"
                )
            return {
                "mode": "frozen_view",
                "manifest_sha256": hashlib.sha256(view_path.read_bytes()).hexdigest(),
                "focus": str(values["focus"]),
                "snapshot_sns": frozen.snapshot_sns,
            }
        finally:
            discard_rehydrated_pack(frozen.pack_root)

    selected: list[Any] = []
    diagnostics: list[str] = []
    selected, diagnostics = select_kernel_timelines(
        managed_project,
        project_slug=str(project),
        slug=str(values["timeline_slug"]) if has_ref else None,
        all=select_all,
        default=not has_ref and not select_all,
    )
    if not selected:
        detail = "; ".join(diagnostics) or "no eligible managed timeline was selected"
        raise CapabilityValidationError(f"timeline selection failed: {detail}")

    return {
        "mode": "kernel",
        "timelines": [
            {
                "timeline_id": row.timeline_id,
                "head_version": row.config_version,
                "head_event_id": row.head_event_id,
                "head_hash": row.head_hash,
            }
            for row in selected
        ],
    }


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


_RENDER_PROFILE_REQUIRED_FIELDS = (
    "width",
    "height",
    "fps_rational",
    "time_base",
    "container",
    "video_codec",
    "video_profile",
    "video_level",
    "pixel_format",
    "duration_tolerance",
)
_RENDER_PROFILE_AUDIO_FIELDS = (
    "audio_codec",
    "audio_sample_rate",
    "audio_channel_layout",
)
_RENDER_PROFILE_ALLOWED_FIELDS = frozenset(
    (*_RENDER_PROFILE_REQUIRED_FIELDS, *_RENDER_PROFILE_AUDIO_FIELDS)
)
_RENDER_PROFILE_EXAMPLE = {
    "width": 1920,
    "height": 1080,
    "fps_rational": [30, 1],
    "time_base": [1, 90000],
    "container": "mp4",
    "video_codec": "h264",
    "video_profile": None,
    "video_level": None,
    "pixel_format": "yuv420p",
    "audio_codec": "aac",
    "audio_sample_rate": 48000,
    "audio_channel_layout": "stereo",
    "duration_tolerance": 1,
}


def _render_profile_guidance() -> str:
    example = json.dumps(_RENDER_PROFILE_EXAMPLE, separators=(",", ":"))
    return (
        "--profile uses the flat RenderProfile v1 object (no video/audio nesting); "
        "audio_codec, audio_sample_rate, and audio_channel_layout must be supplied "
        "together or all omitted. Explicit profiles must match the authoritative "
        "theme canvas; set theme_overrides.visual.canvas for a different size. "
        f"Complete Remotion MP4 example: {example}"
    )


def _validate_explicit_render_profile(profile: Any) -> None:
    """Validate the frozen flat profile contract before kernel admission."""

    if profile is None:
        return
    if not isinstance(profile, Mapping):
        raise CapabilityValidationError(
            f"invalid render profile: expected a JSON object. {_render_profile_guidance()}"
        )
    missing = [field for field in _RENDER_PROFILE_REQUIRED_FIELDS if field not in profile]
    unknown = sorted(str(field) for field in profile if field not in _RENDER_PROFILE_ALLOWED_FIELDS)
    key_issues: list[str] = []
    if missing:
        key_issues.append("missing required field(s): " + ", ".join(missing))
    if unknown:
        key_issues.append("unknown field(s): " + ", ".join(unknown))
    if key_issues:
        raise CapabilityValidationError(
            "invalid render profile: " + "; ".join(key_issues) + ". " + _render_profile_guidance()
        )
    from astrid.core.rendering.contracts import RenderProfile

    try:
        RenderProfile.from_dict(profile)
    except (TypeError, ValueError) as exc:
        raise CapabilityValidationError(
            f"invalid render profile: {exc}. {_render_profile_guidance()}"
        ) from exc


def _validate_managed_profile_theme_compatibility(
    profile: Mapping[str, Any] | None,
    *,
    timeline: Mapping[str, Any],
    registry: Mapping[str, Any],
    timeline_slug: str,
) -> None:
    """Reject canvas/fps profiles that cannot match the canonical theme.

    This is intentionally managed-ref-only. Explicit file-mode callers retain
    the renderer's historical support-selection semantics.
    """

    if profile is None:
        return
    from astrid.core.rendering.profile import resolve_render_profile

    try:
        authoritative = resolve_render_profile(
            timeline,
            registry,
            audio_ownership="rendered",
        )
    except (TypeError, ValueError, OSError, FileNotFoundError) as exc:
        raise CapabilityValidationError(
            f"cannot resolve authoritative theme canvas for canonical timeline "
            f"{timeline_slug!r}: {exc}. Fix the timeline theme and retry"
        ) from exc

    mismatches: list[str] = []
    for field, expected in (
        ("width", authoritative.width),
        ("height", authoritative.height),
        ("fps_rational", list(authoritative.fps_rational)),
    ):
        requested = profile.get(field)
        if requested != expected:
            mismatches.append(
                f"{field}={requested!r} (authoritative theme canvas produces {expected!r})"
            )
    if mismatches:
        raise CapabilityValidationError(
            f"invalid render profile for canonical timeline {timeline_slug!r}: "
            + "; ".join(mismatches)
            + ". Explicit profiles must match the authoritative theme canvas; "
            "use the default profile from timelines render --help or set "
            "theme_overrides.visual.canvas to the requested width, height, and fps, then retry"
        )


def _prepare_managed_render_inputs(
    inputs: Mapping[str, Any] | None,
    *,
    project: str | None,
    _client: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve the explicit render ref and hand it to the runtime host.

    Snapshot bytes remain in the admission envelope until the generic host
    materializes them beneath the assigned attempt.
    """

    values = dict(inputs or {})
    timeline_ref = values.get("timeline_ref")
    expected_version = values.get("expected_version")
    if timeline_ref in (None, ""):
        raise CapabilityValidationError(
            "rendering.render requires timeline_ref=<runtime timeline slug/UUID/ULID>; "
            "path-backed timeline inputs are not supported"
        )
    if values.get("timeline") not in (None, ""):
        raise CapabilityValidationError(
            "timeline and timeline_ref are mutually exclusive; use timeline for explicit "
            "file mode or timeline_ref for canonical managed mode"
        )
    if values.get("assets_registry") not in (None, ""):
        raise CapabilityValidationError(
            "assets_registry cannot be overridden with timeline_ref; the canonical timeline "
            "registry is pinned with the snapshot"
        )
    if project is None or not str(project).strip():
        raise CapabilityValidationError("rendering.render timeline_ref requires project=<slug>")
    if not isinstance(timeline_ref, str) or not timeline_ref.strip():
        raise CapabilityValidationError("timeline_ref must be a non-empty slug, UUID, or ULID")
    if expected_version is not None and (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 1
    ):
        raise CapabilityValidationError("expected_version must be a positive integer")
    _validate_explicit_render_profile(values.get("profile"))
    from astrid.packs.rendering.executors.render.managed_timeline import (
        ManagedRenderValidationError,
        _runtime_snapshot_registry,
        resolve_managed_render_snapshot,
        validate_managed_render_snapshot,
    )

    if _client is None:
        raise CapabilityInvocationError(
            "explicit generated runtime client is required for managed render admission"
        )
    try:
        snapshot = resolve_managed_render_snapshot(
            project_ref=str(project),
            timeline_ref=timeline_ref.strip(),
            expected_version=expected_version,
            client=_client,
        )
        from astrid.core.timeline.expand_shots import expand_shot_clips

        # Admission is intentionally split: the authoring parent may contain
        # composite ``shot`` clips, but every reference must resolve through
        # the SDK before expansion. The expander never invents or fetches a
        # missing shot and never talks to storage itself.
        child_records: list[dict[str, Any]] = []
        raw_clips = snapshot.config.get("clips", [])
        for index, clip in enumerate(raw_clips):
            if not isinstance(clip, Mapping) or clip.get("clipType") != "shot":
                continue
            params = clip.get("params")
            shot_id = params.get("shot_id") if isinstance(params, Mapping) else None
            timeline_document_id = (
                params.get("timeline_document_id") if isinstance(params, Mapping) else None
            )
            if not isinstance(shot_id, str) or not shot_id:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} shot clip at index {index} "
                    "is missing a registered shot_id"
                )
            shot_result = _client.shots.show(str(project), shot_id)
            if not shot_result.ok or not shot_result.data:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} references unregistered shot "
                    f"{shot_id!r}"
                )
            if not isinstance(timeline_document_id, str) or not timeline_document_id:
                raise CapabilityValidationError(
                    f"canonical timeline {snapshot.timeline_slug!r} shot {shot_id!r} "
                    "is missing timeline_document_id"
                )

        def load_child(ref: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
            child_result = _client.timelines.show(str(project), ref)
            if not child_result.ok or not child_result.data:
                raise ValueError(f"timeline {ref!r} was not found")
            child = child_result.data
            child_config = child.get("config")
            child_registry = child.get("registry")
            if not isinstance(child_config, Mapping) or not isinstance(child_registry, Mapping):
                raise ValueError(f"timeline {ref!r} has an invalid snapshot")
            child_records.append(
                {
                    "timeline_id": str(child["timeline_id"]),
                    "timeline_ulid": str(child["timeline_ulid"]),
                    "slug": str(child["slug"]),
                    "config_version": int(child["config_version"]),
                    "config_hash": _expanded_config_hash(child_config),
                }
            )
            return child_config, child_registry

        try:
            expanded_config, expanded_registry = expand_shot_clips(
                snapshot.config,
                snapshot.registry,
                load_timeline=load_child,
            )
        except ValueError as exc:
            raise CapabilityValidationError(str(exc)) from exc
        from dataclasses import replace

        expanded_registry = _runtime_snapshot_registry(
            expanded_registry,
            project_ref=str(project),
            client=_client,
        )
        snapshot = replace(
            snapshot,
            config=expanded_config,
            registry=expanded_registry,
            materialized_registry_hash=_expanded_config_hash(expanded_registry),
            expansion={
                "children": child_records,
                "expanded_config_hash": _expanded_config_hash(expanded_config),
            },
        )
        validate_managed_render_snapshot(snapshot)
    except ManagedRenderValidationError as exc:
        raise CapabilityValidationError(str(exc), details=exc.details) from exc
    except ValueError as exc:
        raise CapabilityValidationError(str(exc)) from exc
    _validate_managed_profile_theme_compatibility(
        values.get("profile"),
        timeline=snapshot.config,
        registry=snapshot.registry,
        timeline_slug=snapshot.timeline_slug,
    )
    from astrid.core.rendering.output_policy import (
        DEFAULT_RENDER_OUTPUT_NAME,
        RenderOutputPolicyError,
        validate_render_output_policy,
    )

    output_name = values.get("output_name", DEFAULT_RENDER_OUTPUT_NAME)
    if output_name is None:
        output_name = DEFAULT_RENDER_OUTPUT_NAME
    try:
        validate_render_output_policy(
            output_name,
            timeline=snapshot.config,
            profile=values.get("profile"),
        )
    except RenderOutputPolicyError as exc:
        raise CapabilityValidationError(str(exc), details=exc.details) from exc
    authority = snapshot.authority()
    values.update(
        {
            # The generic host materializes this immutable snapshot below the
            # assigned attempt.  The SDK never writes a project-side render
            # snapshot or hands a project-root locator to a renderer.
            "timeline_snapshot": {
                "config": dict(snapshot.config),
                "registry": dict(snapshot.registry),
            },
            "timeline_authority": authority,
        }
    )
    # The public selector and CAS guard are admission-only controls. The
    # resolved authority object below is the durable run input/cache identity;
    # do not leak these two controls as undeclared renderer CLI flags.
    values.pop("expected_version", None)
    return values, authority


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
    capability_id: str | None = None,
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
        is_timeline_manifest = isinstance(document, dict) and document.get("kind") in {
            "timeline_visualize",
            "timeline_visualize_project",
        }
        if capability_id == "rendering.timeline_visualize" or is_timeline_manifest:
            pack_root = manifest.parent
            # Kernel completion publishes every evidence-pack member as its
            # own managed CAS object and removes private staging.  The parent
            # of the durable manifest is therefore a hash fan-out directory,
            # not the logical pack root.  Reuse the frozen loader's verified
            # task-output rehydration so the long-standing ``pack_root`` SDK
            # convenience remains an actually navigable directory.
            # The manifest is the runtime-owned result handle.  Rehydration,
            # when needed for navigation, is attempt-local; Astrid never
            # persists a project-side ``.astrid/views`` copy.
            outputs["pack_root"] = str(pack_root)
            outputs["manifest_path"] = str(manifest)
            outputs["pages"] = [
                str(path)
                for path in sorted(pack_root.rglob("PG*.png"))
                if "filmstrip" not in path.relative_to(pack_root).parts
            ]
            outputs["file_hashes"] = {
                path.relative_to(pack_root).as_posix(): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(pack_root.rglob("*"))
                if path.is_file()
            }
    return _json_safe_mapping(outputs)


def _runtime_selected_project() -> str | None:
    """Project selection is never inferred by the SDK runtime boundary."""
    return None


def _kernel_invoke(
    capability: Any,
    *,
    kind: Any,
    project: str | None,
    inputs: Mapping[str, Any] | None,
    outputs: Mapping[str, Any] | None,
    extra_pack_roots: tuple[str, ...] = (),
    idempotency_context: Mapping[str, Any] | None = None,
    registry: Any | None = None,
    _client: Any | None = None,
) -> tuple[str, str, str, Path | None, dict[str, Any], bool, Any]:
    """Admit an invocation through the runtime client and generic host.

    The SDK is a client of the workspace runtime.  It must not compose a
    local application, open SQLite, or execute a capability in-process on the
    normal invocation path. ``registry`` is an explicit dependency-injection
    seam for callers that provide test doubles and is intentionally unused by
    the runtime admission request.
    """
    del registry

    spec: dict[str, Any] = {
        "capability_id": str(capability.id),
        "kind": str(kind),
        "inputs": _json_safe_mapping(dict(inputs or {})),
        "outputs": _json_safe_mapping(dict(outputs or {})),
        "extra_pack_roots": list(extra_pack_roots),
    }
    if idempotency_context:
        spec["authority_context"] = _json_safe_mapping(dict(idempotency_context))
    idempotency_key = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()

    if _client is None:
        raise CapabilityInvocationError(
            "explicit generated runtime client is required for task admission"
        )

    tasks = getattr(_client, "tasks", None)
    create_task = getattr(tasks, "create", None)
    if not callable(create_task):
        raise CapabilityInvocationError(
            "runtime client does not expose generated task admission"
        )
    result = create_task(
        project_id=project,
        capability=str(capability.id),
        spec=spec,
        input_manifest=[],
        idempotency_key=idempotency_key,
    )
    result_ok = bool(getattr(result, "ok", isinstance(result, Mapping)))
    data = getattr(result, "data", result if isinstance(result, Mapping) else None)
    if not result_ok:
        error = getattr(result, "error", None)
        if hasattr(error, "as_dict"):
            error = error.as_dict()
        elif isinstance(error, Mapping):
            error = dict(error)
        else:
            error = {
                "code": "runtime_error",
                "message": "runtime rejected task admission",
                "details": {},
            }
        return "", "", "", None, {"ok": False, "error": error}, False, None
    if not isinstance(data, Mapping):
        raise CapabilityInvocationError("runtime task admission returned no task resource")

    run_id = str(data.get("run_id") or "")
    task_id = str(data.get("task_id") or "")
    if not run_id or not task_id:
        raise CapabilityInvocationError(
            "runtime task admission returned an incomplete task resource"
        )
    attempt_id = str(data.get("attempt_id") or "")
    raw_result = {
        "ok": True,
        "run_id": run_id,
        "kernel_run_id": run_id,
        "kernel_task_id": task_id,
        "kernel_attempt_id": attempt_id,
        "task": dict(data),
    }
    return run_id, task_id, attempt_id, None, raw_result, True, None


def invoke(
    capability_id: str,
    *,
    kind: Any,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
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
    argv: tuple[str, ...] = (),
    orchestrator_args: tuple[str, ...] = (),
    registry: Any | None = None,
    client: Any | None = None,
) -> InvocationResult:
    _client = client
    sdk_module = _sdk_module()
    include_elements = kind == "element"
    registries = sdk_module._load_registries(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        banodoco_config=banodoco_config,
        include_missing_roots=include_missing_roots,
        include_elements=include_elements,
    )
    capability = sdk_module.get_capability(
        capability_id,
        kind=kind,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        banodoco_config=banodoco_config,
        include_missing_roots=include_missing_roots,
        _registries=registries,
    )
    if capability.capability_type == "element":
        raise UnsupportedCapabilityError(f"elements are not invokable via the SDK: {capability.id}")

    if not dry_run and project is None:
        project = _runtime_selected_project()
        if project is None:
            from astrid.core.project.guidance import format_project_required_guidance

            raise CapabilityPreconditionError(
                format_project_required_guidance(
                    operation=f"{capability.capability_type} invocation"
                )
            )

    # Validate the public selector/format contract before the runner can
    # create a ledger row or spawn a subprocess.  The runner repeats these
    # checks for direct CLI callers, but SDK callers should get the same
    # actionable typed error at admission time.
    invocation_authority_context: dict[str, Any] | None = None
    # These are managed-authority checks, not manifest checks.  A dry-run is
    # intentionally limited to the source ledger and therefore cannot inspect
    # a project tree or materialize a render snapshot.
    if not dry_run:
        if capability.id == "rendering.timeline_visualize":
            invocation_authority_context = _validate_timeline_visualize_inputs(
                inputs,
                project=project,
                project_root=project_root,
                out=out,
            )
        elif capability.id == "rendering.render":
            inputs, invocation_authority_context = _prepare_managed_render_inputs(
                inputs,
                project=project,
                _client=_client,
            )

    # Generation requests have a single read-only preflight for both dry-run
    # and live invocation.  This keeps generic ``sdk.invoke`` from accepting
    # an impossible model/mode/backend cell (or FLF request missing its end
    # frame) and discovering the problem only after kernel admission.
    generation_modalities = {
        "generation.generate_image": "image",
        "generation.generate_video": "video",
        "generation.generate_audio": "audio",
    }
    modality = generation_modalities.get(capability.id)
    if modality is not None:
        request_inputs = dict(inputs or {})
        model_registry = sdk_module._load_model_registry(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
        )
        from astrid.core.generation.preflight import (
            require_local_generation_readiness,
            validate_generation_request,
        )

        model_entry, _mode_spec = validate_generation_request(
            model_registry,
            model=request_inputs.get("model"),
            mode=request_inputs.get("mode"),
            execution=request_inputs.get("execution"),
            inputs=request_inputs,
            modality=modality,
        )
        if request_inputs.get("execution") == "local":
            require_local_generation_readiness(
                model_entry,
                request_inputs["mode"],
                python_executable=python_exec,
            )

    # Ledger exemption: dry_run never admitted.  The preview is built from the
    # already resolved manifest DTO and does not import either runner or any
    # local project/run authority.
    if dry_run:
        try:
            raw_result, preview_ok = _manifest_dry_run_result(
                capability,
                inputs=inputs,
                outputs=outputs,
                brief=brief,
                python_exec=python_exec,
                out=out,
                orchestrator_args=tuple(orchestrator_args),
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
        error = raw_result.get("error") if isinstance(raw_result.get("error"), Mapping) else None
        manifest_path = None
        run_id_raw = None
        run_root_raw = None
        executor_version_raw = raw_result.get("executor_version")
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=preview_ok,
            error=error,
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else None,
            run_root=str(Path(run_root_raw).expanduser().resolve())
            if isinstance(run_root_raw, str) and run_root_raw
            else None,
            outputs={},
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
    kernel_capability_version: str | None = None
    if capability.capability_type == "executor":
        from astrid.core.foundation.hash import executor_definition_digest

        executor_registry, _, _ = registries
        kernel_capability_version = executor_definition_digest(executor_registry.get(capability.id))
        invocation_authority_context = dict(invocation_authority_context or {})
        invocation_authority_context["executor_version"] = kernel_capability_version
    try:
        # Keep the private seam backwards-compatible for callers that replace
        # it with a narrow test double, while still forwarding an explicitly
        # composed registry for long-lived clients.  ``None`` means the
        # kernel will build its normal standard composition; passing it as a
        # keyword adds no information and needlessly breaks older doubles.
        kernel_kwargs: dict[str, Any] = {
            "kind": kind,
            "project": project,
            "inputs": inputs,
            "outputs": outputs,
            "extra_pack_roots": extra_pack_roots,
            "idempotency_context": invocation_authority_context,
        }
        if registry is not None:
            kernel_kwargs["registry"] = registry
        kr, kt, ka, mpath, raw_result, ok, _ = _kernel_invoke(
            capability,
            **kernel_kwargs,
            _client=_client,
        )
        run_id_raw = raw_result.get("run_id") if isinstance(raw_result, dict) else None
        run_root_raw = raw_result.get("run_root") if isinstance(raw_result, dict) else None
        raw_result = dict(raw_result) if isinstance(raw_result, dict) else {}
        if kernel_capability_version is not None:
            raw_result.setdefault("executor_version", kernel_capability_version)
        executor_version_raw = raw_result.get("executor_version")
        raw_result.setdefault("kernel_run_id", kr)
        raw_result.setdefault("kernel_task_id", kt)
        raw_result.setdefault("kernel_attempt_id", ka)
        manifest_path = (
            str(mpath) if mpath else _discover_invocation_manifest_path(raw_result, out=out)
        )
        return InvocationResult(
            capability_id=capability.id,
            capability_type=capability.capability_type,
            native_kind=capability.native_kind,
            ok=ok,
            # Preserve the kernel's typed handler failure on the primary
            # result surface.  Historically this was only available under
            # ``raw_result.error`` and task events, forcing callers to make a
            # second ledger query to understand a failed invocation.
            error=(
                {
                    **dict(raw_result.get("error")),
                    "sdk_error": "CapabilityRuntimeError",
                    "sdk_category": "runtime",
                }
                if isinstance(raw_result.get("error"), Mapping)
                else None
            ),
            manifest_path=manifest_path,
            raw_result=raw_result,
            run_id=run_id_raw if isinstance(run_id_raw, str) and run_id_raw else kr,
            # Kernel-managed invocations publish through private staging and
            # then remove it. Only propagate a run_root explicitly supplied
            # by a durable/custom kernel result; never synthesize the projects
            # root or leak the attempt staging path.
            run_root=(
                str(Path(run_root_raw).expanduser().resolve())
                if isinstance(run_root_raw, str) and run_root_raw
                else None
            ),
            outputs=_invocation_outputs(
                raw_result,
                manifest_path=manifest_path,
                capability_id=capability.id,
            ),
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


def invoke_result(
    capability_id: str,
    *,
    kind: Any,
    **kwargs: Any,
) -> InvocationResult:
    """Invoke while keeping typed preflight failures in the result contract.

    ``invoke`` remains the exception-oriented API for callers that want typed
    recovery branches.  Maker-facing agents that need one uniform JSON-safe
    branch can use this sibling: validation/precondition failures raised before
    kernel admission become an ``InvocationResult(ok=False)`` with the same
    ``error`` mapping used by a post-admission failure.  No run, task, staging
    directory, network call, or provider request is created by this adapter.
    """

    try:
        return invoke(capability_id, kind=kind, **kwargs)
    except AstridSDKError as exc:
        category = getattr(exc, "category", "invocation")
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "sdk_error": type(exc).__name__,
            "sdk_category": category,
        }
        details = getattr(exc, "details", None)
        if isinstance(details, Mapping) and details:
            error["validation"] = _json_safe(dict(details))
        return InvocationResult(
            capability_id=capability_id,
            capability_type=kind if kind in ("executor", "orchestrator") else "executor",
            native_kind="unknown",
            ok=False,
            error=error,
            raw_result={"ok": False, "error": error},
        )
