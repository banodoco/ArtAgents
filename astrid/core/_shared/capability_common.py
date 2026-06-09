"""Shared leaf helpers for executor and orchestrator packages.

These were previously duplicated verbatim (or near-verbatim) in
``astrid.core.executor.{runner,cli}`` and ``astrid.core.orchestrator.{runner,cli}``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from astrid.core.contracts.capability_schema import SchemaValidator
from astrid.core.contracts.schema import (
    CACHE_MODES,
    ISOLATION_MODES,
    CacheMode,
    CachePolicy,
    IsolationMetadata,
    IsolationMode,
)

# ---------------------------------------------------------------------------
# runner.py helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _stringify_value(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


# ---------------------------------------------------------------------------
# cli.py helpers
# ---------------------------------------------------------------------------


def _eprint(*args: object) -> None:
    """Shared stderr sink for command previews and legacy override diagnostics."""
    print(*args, file=sys.stderr)


def _gateway_resolved_project(explicit_project: str | None) -> str | None:
    if explicit_project is not None:
        return None
    from astrid.core.env_vars import ASTRID_GATEWAY_RESOLVED_PROJECT

    value = sys.modules["os"].environ.get(ASTRID_GATEWAY_RESOLVED_PROJECT)
    return value or None


def _require_qualified_id(value: str, label: str) -> None:
    if "." not in value or any(not part for part in value.split(".")):
        raise ValueError(f"{label} must be qualified as <pack>.<name>")


def _aliases_text(resolver: Any, canonical_id: str) -> str:
    """Return a space-joined string of alias ids for *canonical_id*.

    Deprecated aliases get a ``[deprecated]`` suffix so the deprecation
    status is visible to search scoring and human-readable output.
    Returns the empty string when there are no aliases.
    """
    records = resolver.get_aliases_for(canonical_id)
    if not records:
        return ""
    parts: list[str] = []
    for r in records:
        part = r.alias
        if r.deprecated:
            part += " [deprecated]"
        if r.deprecation_message:
            part += " " + r.deprecation_message
        parts.append(part)
    return " ".join(parts)


def _example_path_for_port(port: Any) -> str:
    """Render a plausible ``<path>`` placeholder for an input port.

    Uses the port name as the filename so the example looks like a real
    invocation; the suffix is best-effort based on the port type (image →
    .png, video → .mp4, audio → .wav, text → .txt, otherwise no suffix).
    """
    type_to_ext = {
        "image": ".png",
        "video": ".mp4",
        "audio": ".wav",
        "text": ".txt",
        "json": ".json",
        "directory": "",
        "dir": "",
    }
    port_type = getattr(port, "type", None) or ""
    suffix = type_to_ext.get(str(port_type).lower(), "")
    return f"/path/to/{port.name}{suffix}"


def _format_invocation_hint(verb: str, qid: str, inputs: tuple[Any, ...]) -> str:
    parts = [f"astrid {verb} run {qid}"]
    required = [port for port in inputs if getattr(port, "required", False)]
    for port in required[:3]:
        flag = str(getattr(port, "name", "input")).replace("_", "-")
        parts.append(f"--{flag} <path>")
    if len(required) > 3:
        parts.append("...")
    return " ".join(parts)


def _print_invocation_example(verb: str, qid: str, inputs: tuple[Any, ...]) -> None:
    """Synthesize an example invocation for ``inspect`` output.

    ``verb`` is ``"executors"`` or ``"orchestrators"``.
    """
    print()
    print("Example:")
    parts = [f"  astrid {verb} run {qid}"]
    for port in inputs:
        if not getattr(port, "required", False):
            continue
        parts.append(f"--input {port.name}={_example_path_for_port(port)}")
    parts.append("--out /path/to/output")
    print(" ".join(parts))


def _print_ports(label: str, ports: tuple[Any, ...]) -> None:
    if not ports:
        return
    print(f"{label}:")
    for port in ports:
        required = "required" if port.required else "optional"
        print(f"  - {port.name} ({port.type}, {required})")


# ---------------------------------------------------------------------------
# schema.py helpers — parse / validate (parametrized on error_cls / primitives)
# ---------------------------------------------------------------------------


def _parse_cache(raw: Any, path: str, *, primitives: SchemaValidator) -> CachePolicy:
    """Parse a ``cache`` block into a ``CachePolicy`` (shared between executor and orchestrator)."""
    data = primitives.require_mapping(raw, path)
    return CachePolicy(
        mode=primitives.require_literal(
            data.get("mode", "sentinel"), CACHE_MODES, f"{path}.mode", CacheMode
        ),
        sentinels=tuple(primitives.optional_string_list(data, "sentinels", f"{path}.sentinels")),
        always_run=primitives.optional_bool(data, "always_run", f"{path}.always_run", default=False),
        per_brief=primitives.optional_bool(data, "per_brief", f"{path}.per_brief", default=False),
    )


def _parse_isolation(raw: Any, path: str, *, primitives: SchemaValidator) -> IsolationMetadata:
    """Parse an ``isolation`` block into ``IsolationMetadata`` (shared)."""
    data = primitives.require_mapping(raw, path)
    return IsolationMetadata(
        mode=primitives.require_literal(
            data.get("mode", "subprocess"), ISOLATION_MODES, f"{path}.mode", IsolationMode
        ),
        requirements=tuple(primitives.optional_string_list(data, "requirements", f"{path}.requirements")),
        binaries=tuple(primitives.optional_string_list(data, "binaries", f"{path}.binaries")),
        network=primitives.optional_bool(data, "network", f"{path}.network", default=False),
        env_passthrough=tuple(primitives.optional_string_list(data, "env_passthrough", f"{path}.env_passthrough")),
    )


def _validate_cache(cache: CachePolicy, *, error_cls: type[ValueError]) -> None:
    """Validate a ``CachePolicy`` (shared; parametrized on *error_cls*)."""
    if cache.mode not in CACHE_MODES:
        raise error_cls(f"cache.mode must be one of {sorted(CACHE_MODES)}")
    if cache.always_run and cache.sentinels:
        raise error_cls("cache.always_run cannot be combined with cache.sentinels")
    if cache.mode == "none" and (cache.sentinels or cache.always_run or cache.per_brief):
        raise error_cls("cache.mode 'none' cannot include sentinels, always_run, or per_brief")
    if cache.mode == "always_run" and not cache.always_run:
        raise error_cls("cache.mode 'always_run' requires cache.always_run=true")


def _validate_isolation(isolation: IsolationMetadata, *, error_cls: type[ValueError]) -> None:
    """Validate ``IsolationMetadata`` (shared; parametrized on *error_cls*)."""
    if isolation.mode not in ISOLATION_MODES:
        raise error_cls(f"isolation.mode must be one of {sorted(ISOLATION_MODES)}")
    _validate_unique_env_passthrough(isolation.env_passthrough, error_cls=error_cls)


def _validate_unique_env_passthrough(
    values: tuple[str, ...],
    *,
    error_cls: type[ValueError],
) -> None:
    """Validate that ``env_passthrough`` entries are unique and well-formed (shared)."""
    p = SchemaValidator(error_cls)
    seen: set[str] = set()
    for index, value in enumerate(values):
        p.validate_env_name(value, f"isolation.env_passthrough[{index}]")
        if value in seen:
            raise error_cls(f"isolation.env_passthrough contains duplicate name {value!r}")
        seen.add(value)


# ---------------------------------------------------------------------------
# cli.py helpers — pack id, filtering, content root (parametrized on type label)
# ---------------------------------------------------------------------------


@runtime_checkable
class _HasIdAndMetadata(Protocol):
    """Structural protocol for anything that carries ``.id`` and ``.metadata``."""

    id: str
    metadata: dict[str, Any]


def _definition_pack_id(definition: _HasIdAndMetadata) -> str:
    """Return the pack id for *definition* — from metadata or the id prefix."""
    source_pack = definition.metadata.get("source_pack")
    if isinstance(source_pack, str) and source_pack:
        return source_pack
    return definition.id.split(".", 1)[0]


def _filter_by_pack(
    definitions: list[_HasIdAndMetadata],
    pack_id: str | None,
) -> list[_HasIdAndMetadata]:
    """Filter *definitions* to those belonging to *pack_id* (no-op when None)."""
    if not pack_id:
        return definitions
    return [d for d in definitions if _definition_pack_id(d) == pack_id]


def _require_pack_match(
    definition: _HasIdAndMetadata,
    pack_id: str | None,
    *,
    component_type: str,
) -> None:
    """Raise ``ValueError`` if *definition* does not belong to *pack_id*."""
    if pack_id and _definition_pack_id(definition) != pack_id:
        raise ValueError(
            f"{component_type} {definition.id!r} does not belong to pack {pack_id!r}"
        )


def _definition_content_root(
    definition: _HasIdAndMetadata,
    *,
    fallback_root_key: str,
) -> Path:
    """Extract content root from definition metadata.

    Tries ``content_root`` first, then *fallback_root_key* (e.g.
    ``"executor_root"`` or ``"orchestrator_root"``), then ``Path.cwd()``.
    """
    root_str = definition.metadata.get("content_root")
    if root_str:
        return Path(root_str)
    root_str = definition.metadata.get(fallback_root_key)
    if root_str:
        return Path(root_str)
    return Path.cwd()


# ---------------------------------------------------------------------------
# Shared runner helpers — moved from executor/runner.py + orchestrator/runner.py
# ---------------------------------------------------------------------------


def _expand_placeholders(
    value: str,
    placeholders: Mapping[str, str],
    *,
    error_cls: type[Exception],
) -> str:
    """Replace ``{placeholder}`` tokens in *value* using *placeholders*.

    Raises *error_cls* when a token has no corresponding entry.
    Previously duplicated in executor/runner.py and orchestrator/runner.py;
    only the error class differed.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in placeholders:
            raise error_cls(f"missing value for placeholder {{{key}}}")
        return placeholders[key]

    return _PLACEHOLDER_RE.sub(replace, value)


def _validate_required_inputs(
    capability_id: str,
    inputs: tuple[Any, ...],
    values: Mapping[str, Any],
    *,
    noun: str,
    error_cls: type[Exception],
) -> None:
    """Raise *error_cls* when any required input is missing.

    *noun* is the human-readable capability type (``"executor"`` or ``"orchestrator"``).
    """
    missing = [
        port.name
        for port in inputs
        if port.required and port.default is None and not _has_value(values.get(port.name))
    ]
    if missing:
        raise error_cls(
            f"{noun} {capability_id!r} missing required input(s): {', '.join(missing)}"
        )


def _output_value(
    output: Any,
    request: Any,
    placeholders: Mapping[str, str],
    *,
    error_cls: type[Exception],
) -> str:
    """Derive the filesystem path for an output port.

    *output* must have ``.name``, ``.placeholder``, and ``.path_template``
    attributes (both ``Output`` and ``ExecutorOutput`` satisfy this).
    *request* must have ``.out`` (``Path | str | None``) and ``.outputs``
    (``Mapping[str, Any]``).

    BUG FIX: the previous executor copy silently assumed ``request.out`` was
    always set, which could produce a traceback escaping the runner error
    boundary.  The orchestrator already had a guard; this is now unified with
    the guard applied to both.
    """
    if output.name in request.outputs:
        return _stringify_value(request.outputs[output.name])
    if output.placeholder and output.placeholder in request.outputs:
        return _stringify_value(request.outputs[output.placeholder])
    if output.path_template:
        return _expand_placeholders(output.path_template, placeholders, error_cls=error_cls)
    if request.out is None:
        raise error_cls(f"--out is required to derive output {output.name!r}")
    return str((Path(request.out).expanduser().resolve() / output.name).resolve())


def _has_cli_option(args: Sequence[str], option: str) -> bool:
    """Return ``True`` if *option* appears in *args* (bare or ``--opt=val`` form).

    Accepts any ``Sequence[str]`` so both ``list[str]`` (gateway) and
    ``tuple[str, ...]`` (orchestrator runner) work.
    Previously duplicated in orchestrator/runner.py (tuple) and
    gateway/project.py (list).
    """
    return any(arg == option or arg.startswith(f"{option}=") for arg in args)
