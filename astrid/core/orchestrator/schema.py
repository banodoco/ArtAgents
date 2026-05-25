"""Stdlib schema and validation for Astrid orchestrators."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from typing import Literal as _Literal
from typing import TypeVar as _TypeVar
from typing import cast as _cast
from typing import get_args as _get_args

from astrid.contracts.schema import (
    CACHE_MODES,
    ISOLATION_MODES,
    OUTPUT_MODES,
    PORT_REQUIRED_TYPES,
    AliasRecord,
    CacheMode,
    CachePolicy,
    CapabilityHandle,
    CommandSpec,
    IsolationMetadata,
    IsolationMode,
    Output,
    OutputMode,
    Port,
    PortType,
    Provenance,
    SafetyDeclaration,
)
from astrid.core.manifest import ManifestParseError, load_manifest_payload

OrchestratorKind = _Literal["built_in", "external"]
RuntimeKind = _Literal["python", "command"]

ORCHESTRATOR_KINDS: frozenset[str] = frozenset(_get_args(OrchestratorKind))
RUNTIME_KINDS: frozenset[str] = frozenset(_get_args(RuntimeKind))


class OrchestratorValidationError(ValueError):
    """Raised when a orchestrator manifest or definition is structurally invalid."""


_LiteralT = _TypeVar("_LiteralT")


def _require_literal(value: Any, allowed: frozenset[str], path: str, literal_type: type[_LiteralT]) -> _LiteralT:
    """Validate ``value`` is a string in ``allowed`` and return it typed as the Literal alias."""
    if not isinstance(value, str):
        raise OrchestratorValidationError(f"{path} must be a string")
    if value not in allowed:
        raise OrchestratorValidationError(f"{path} must be one of {sorted(allowed)} (got {value!r})")
    return _cast(literal_type, value)


@dataclass(frozen=True)
class RuntimeSpec:
    kind: RuntimeKind
    module: str | None = None
    function: str | None = None
    command: CommandSpec | None = None


@dataclass(frozen=True)
class OrchestratorDefinition:
    id: str
    name: str
    kind: OrchestratorKind
    version: str
    runtime: RuntimeSpec
    description: str = ""
    short_description: str = ""
    keywords: tuple[str, ...] = ()
    inputs: tuple[Port, ...] = ()
    outputs: tuple[Output, ...] = ()
    child_executors: tuple[str, ...] = ()
    child_orchestrators: tuple[str, ...] = ()
    cache: CachePolicy = field(default_factory=CachePolicy)
    isolation: IsolationMetadata = field(default_factory=IsolationMetadata)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _drop_none(asdict(self))

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def to_capability_handle(
    definition: OrchestratorDefinition,
    *,
    aliases: tuple[AliasRecord, ...] = (),
    resolved_alias: str | None = None,
    deprecated: bool = False,
    deprecation_message: str = "",
) -> CapabilityHandle:
    """Adapt an ``OrchestratorDefinition`` into a ``CapabilityHandle``.

    Field mapping mirrors the executor adapter:

    * ``canonical_id`` — ``definition.id`` (qualified form ``pack.name``)
    * ``local_id`` — the portion after the first dot in ``definition.id``
    * ``pack_id`` — the portion before the first dot in ``definition.id``
    * ``kind`` — ``definition.kind`` (preserved as-is)
    * ``provenance`` — source derived from metadata, default ``"pack"``
    * ``safety`` — network flag from ``definition.isolation.network``

    Alias metadata (*aliases*, *resolved_alias*, *deprecated*,
    *deprecation_message*) is carried on the handle and never mutates
    ``OrchestratorDefinition.metadata``.
    """
    parts = definition.id.split(".", 1)
    pack_id = parts[0]
    local_id = parts[1] if len(parts) > 1 else definition.id

    metadata = definition.metadata
    metadata_source = metadata.get("source")
    provenance_source = str(metadata_source) if metadata_source else "pack"

    forked_from = str(metadata.get("forked_from") or "")
    upstream_version = str(metadata.get("upstream_version") or "")
    compatibility_token=str(metadata.get("compatibility_token") or "")
    local_edit_state = str(metadata.get("local_edit_state") or "clean")
    override_target = str(metadata.get("override_target") or "")

    return CapabilityHandle(
        canonical_id=definition.id,
        local_id=local_id,
        pack_id=pack_id,
        kind=definition.kind,
        name=definition.name,
        version=definition.version,
        provenance=Provenance(
            source=provenance_source,
            forked_from=forked_from or None,
            upstream_version=upstream_version or None,
            compatibility_token=compatibility_token or None,
            resolved_alias=resolved_alias,
        ),
        safety=SafetyDeclaration(network=definition.isolation.network),
        description=definition.description,
        short_description=definition.short_description,
        keywords=definition.keywords,
        local_edit_state=local_edit_state,
        override_target=override_target or None,
        aliases=aliases,
        deprecated=deprecated,
        deprecation_message=deprecation_message,
        inputs=definition.inputs,
        outputs=definition.outputs,
    )


def validate_orchestrator_definition(raw: Any) -> OrchestratorDefinition:
    if isinstance(raw, OrchestratorDefinition):
        orchestrator = raw
    else:
        orchestrator = _parse_orchestrator(raw)
    _validate_orchestrator(orchestrator)
    return orchestrator


def load_orchestrator_manifest(path: str | Path) -> OrchestratorDefinition:
    manifest_path = Path(path)
    try:
        raw = load_manifest_payload(manifest_path, manifest_kind="orchestrator")
    except ManifestParseError as exc:
        raise OrchestratorValidationError(f"invalid orchestrator manifest {manifest_path}: {exc}") from exc
    try:
        return validate_orchestrator_definition(raw)
    except OrchestratorValidationError as exc:
        raise OrchestratorValidationError(f"{manifest_path}: {exc}") from exc


def _parse_orchestrator(raw: Any) -> OrchestratorDefinition:
    data = _require_mapping(raw, "orchestrator")
    for field_name in ("id", "name", "kind", "version"):
        _require_string(data, field_name, f"orchestrator.{field_name}")
    if "runtime" not in data:
        raise OrchestratorValidationError("missing required field orchestrator.runtime")

    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise OrchestratorValidationError("orchestrator.metadata must be an object")

    child_executors = _canonical_child_list(
        data,
        legacy_key="child_executors",
        canonical_key="child_executors",
        path="orchestrator.child_executors",
    )
    child_orchestrators = _canonical_child_list(
        data,
        legacy_key="child_orchestrators",
        canonical_key="child_orchestrators",
        path="orchestrator.child_orchestrators",
    )

    return OrchestratorDefinition(
        id=data["id"],
        name=data["name"],
        kind=_require_literal(data.get("kind"), ORCHESTRATOR_KINDS, "orchestrator.kind", OrchestratorKind),
        version=data["version"],
        runtime=_parse_runtime(data["runtime"], "orchestrator.runtime"),
        description=_optional_string(data, "description", "orchestrator.description"),
        short_description=_optional_string(data, "short_description", "orchestrator.short_description"),
        keywords=tuple(_optional_string_list(data, "keywords", "orchestrator.keywords")),
        inputs=tuple(_parse_port(item, f"orchestrator.inputs[{index}]") for index, item in enumerate(_optional_list(data, "inputs", "orchestrator.inputs"))),
        outputs=tuple(_parse_output(item, f"orchestrator.outputs[{index}]") for index, item in enumerate(_optional_list(data, "outputs", "orchestrator.outputs"))),
        child_executors=tuple(child_executors),
        child_orchestrators=tuple(child_orchestrators),
        cache=_parse_cache(data.get("cache", {}), "orchestrator.cache"),
        isolation=_parse_isolation(data.get("isolation", {}), "orchestrator.isolation"),
        metadata=dict(metadata),
    )


def _canonical_child_list(data: dict[str, Any], *, legacy_key: str, canonical_key: str, path: str) -> list[str]:
    legacy_present = legacy_key in data
    canonical_present = canonical_key in data
    legacy_values = _optional_string_list(data, legacy_key, f"orchestrator.{legacy_key}") if legacy_present else []
    canonical_values = _optional_string_list(data, canonical_key, f"orchestrator.{canonical_key}") if canonical_present else []
    if legacy_present and canonical_present and legacy_values != canonical_values:
        raise OrchestratorValidationError(
            f"orchestrator.{legacy_key} and orchestrator.{canonical_key} conflict; use identical values or only one field"
        )
    return canonical_values if canonical_present else legacy_values


def _parse_runtime(raw: Any, path: str) -> RuntimeSpec:
    data = _require_mapping(raw, path)
    if "type" in data and "kind" not in data:
        v1_type = _require_string(data, "type", f"{path}.type")
        if v1_type == "python-cli":
            callable_name = _optional_string(data, "callable", f"{path}.callable", default="")
            if not callable_name:
                callable_name = _optional_string(data, "function", f"{path}.function", default="main")
            return RuntimeSpec(kind="python", module=None, function=callable_name)
        if v1_type == "command":
            return RuntimeSpec(kind="command", command=_parse_command(data.get("command"), f"{path}.command"))
        raise OrchestratorValidationError(
            f"{path}.type must be 'python-cli' or 'command', got {v1_type!r}"
        )
    kind = _require_literal(
        _require_string(data, "kind", f"{path}.kind"),
        RUNTIME_KINDS, f"{path}.kind", RuntimeKind,
    )
    if kind == "python":
        return RuntimeSpec(
            kind=kind,
            module=_optional_nullable_string(data, "module", f"{path}.module"),
            function=_optional_nullable_string(data, "function", f"{path}.function"),
        )
    return RuntimeSpec(kind=kind, command=_parse_command(data.get("command"), f"{path}.command"))


def _parse_port(raw: Any, path: str) -> Port:
    data = _require_mapping(raw, path)
    return Port(
        name=_require_string(data, "name", f"{path}.name"),
        type=_require_literal(
            data.get("type", "path"), PORT_REQUIRED_TYPES, f"{path}.type", PortType
        ),
        required=_optional_bool(data, "required", f"{path}.required", default=True),
        description=_optional_string(data, "description", f"{path}.description"),
        default=data.get("default"),
        placeholder=_optional_nullable_string(data, "placeholder", f"{path}.placeholder"),
    )


def _parse_output(raw: Any, path: str) -> Output:
    data = _require_mapping(raw, path)
    return Output(
        name=_require_string(data, "name", f"{path}.name"),
        type=_require_literal(
            data.get("type", "path"), PORT_REQUIRED_TYPES, f"{path}.type", PortType
        ),
        mode=_require_literal(
            data.get("mode", "create_or_replace"), OUTPUT_MODES, f"{path}.mode", OutputMode
        ),
        description=_optional_string(data, "description", f"{path}.description"),
        placeholder=_optional_nullable_string(data, "placeholder", f"{path}.placeholder"),
        path_template=_optional_nullable_string(data, "path_template", f"{path}.path_template"),
    )


def _parse_command(raw: Any, path: str) -> CommandSpec | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return CommandSpec(argv=tuple(_string_list(raw, f"{path}.argv")))
    data = _require_mapping(raw, path)
    env_raw = data.get("env", {})
    if not isinstance(env_raw, dict):
        raise OrchestratorValidationError(f"{path}.env must be an object")
    env: dict[str, str] = {}
    for key, value in env_raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise OrchestratorValidationError(f"{path}.env keys and values must be strings")
        env[key] = value
    return CommandSpec(
        argv=tuple(_string_list(data.get("argv"), f"{path}.argv")),
        cwd=_optional_nullable_string(data, "cwd", f"{path}.cwd"),
        env=env,
    )


def _parse_cache(raw: Any, path: str) -> CachePolicy:
    data = _require_mapping(raw, path)
    return CachePolicy(
        mode=_require_literal(
            data.get("mode", "sentinel"), CACHE_MODES, f"{path}.mode", CacheMode
        ),
        sentinels=tuple(_optional_string_list(data, "sentinels", f"{path}.sentinels")),
        always_run=_optional_bool(data, "always_run", f"{path}.always_run", default=False),
        per_brief=_optional_bool(data, "per_brief", f"{path}.per_brief", default=False),
    )


def _parse_isolation(raw: Any, path: str) -> IsolationMetadata:
    data = _require_mapping(raw, path)
    return IsolationMetadata(
        mode=_require_literal(
            data.get("mode", "subprocess"), ISOLATION_MODES, f"{path}.mode", IsolationMode
        ),
        requirements=tuple(_optional_string_list(data, "requirements", f"{path}.requirements")),
        binaries=tuple(_optional_string_list(data, "binaries", f"{path}.binaries")),
        network=_optional_bool(data, "network", f"{path}.network", default=False),
    )


def _validate_orchestrator(orchestrator: OrchestratorDefinition) -> None:
    _validate_qualified_identifier(orchestrator.id, "orchestrator.id")
    _validate_non_empty_string(orchestrator.name, "orchestrator.name")
    if orchestrator.kind not in ORCHESTRATOR_KINDS:
        raise OrchestratorValidationError(f"orchestrator.kind must be one of {sorted(ORCHESTRATOR_KINDS)}")
    _validate_non_empty_string(orchestrator.version, "orchestrator.version")
    _validate_capability_text(
        orchestrator.description,
        orchestrator.short_description,
        orchestrator.keywords,
        manifest_id=orchestrator.id,
        error_cls=OrchestratorValidationError,
    )
    _validate_runtime(orchestrator.runtime)

    input_names = _validate_unique_named(orchestrator.inputs, "input")
    output_names = _validate_unique_named(orchestrator.outputs, "output")
    placeholders = set(input_names) | set(output_names)
    placeholders.update({"out", "brief", "python_exec", "orchestrator_args", "verbose"})

    for port in orchestrator.inputs:
        _validate_port(port)
        if port.placeholder:
            _validate_non_empty_identifier(port.placeholder, f"input {port.name!r}.placeholder")
            placeholders.add(port.placeholder)
    for output in orchestrator.outputs:
        _validate_output(output)
        if output.placeholder:
            _validate_non_empty_identifier(output.placeholder, f"output {output.name!r}.placeholder")
            placeholders.add(output.placeholder)
        if output.path_template:
            _validate_placeholders(output.path_template, placeholders, f"output {output.name!r}.path_template")
    for index, child_executor in enumerate(orchestrator.child_executors):
        _validate_qualified_identifier(child_executor, f"orchestrator.child_executors[{index}]")
    for index, child_orchestrator in enumerate(orchestrator.child_orchestrators):
        _validate_qualified_identifier(child_orchestrator, f"orchestrator.child_orchestrators[{index}]")
    _validate_cache(orchestrator.cache)
    _validate_isolation(orchestrator.isolation)
    if orchestrator.runtime.command is not None:
        _validate_command(orchestrator.runtime.command, placeholders)


def _validate_runtime(runtime: RuntimeSpec) -> None:
    if runtime.kind not in RUNTIME_KINDS:
        raise OrchestratorValidationError(f"runtime.kind must be one of {sorted(RUNTIME_KINDS)}")
    if runtime.kind == "python":
        if runtime.module is not None:
            _validate_non_empty_string(runtime.module, "runtime.module")
        _validate_non_empty_string(runtime.function, "runtime.function")
        if runtime.command is not None:
            raise OrchestratorValidationError("python runtime cannot include runtime.command")
    if runtime.kind == "command":
        if runtime.command is None:
            raise OrchestratorValidationError("command runtime requires runtime.command")
        if runtime.module is not None or runtime.function is not None:
            raise OrchestratorValidationError("command runtime cannot include runtime.module or runtime.function")


def _validate_port(port: Port) -> None:
    _validate_non_empty_identifier(port.name, "input.name")
    if port.required and port.default is not None:
        raise OrchestratorValidationError(f"input {port.name!r} cannot be both required and have a default")


def _validate_output(output: Output) -> None:
    _validate_non_empty_identifier(output.name, "output.name")
    if output.mode not in OUTPUT_MODES:
        raise OrchestratorValidationError(f"output {output.name!r}.mode must be one of ['create', 'create_or_replace', 'mutate']")


def _validate_cache(cache: CachePolicy) -> None:
    if cache.mode not in CACHE_MODES:
        raise OrchestratorValidationError("cache.mode must be one of ['always_run', 'none', 'sentinel']")
    if cache.always_run and cache.sentinels:
        raise OrchestratorValidationError("cache.always_run cannot be combined with cache.sentinels")
    if cache.mode == "none" and (cache.sentinels or cache.always_run or cache.per_brief):
        raise OrchestratorValidationError("cache.mode 'none' cannot include sentinels, always_run, or per_brief")
    if cache.mode == "always_run" and not cache.always_run:
        raise OrchestratorValidationError("cache.mode 'always_run' requires cache.always_run=true")


def _validate_isolation(isolation: IsolationMetadata) -> None:
    if isolation.mode not in ISOLATION_MODES:
        raise OrchestratorValidationError("isolation.mode must be one of ['in_process', 'subprocess']")


def _validate_command(command: CommandSpec, placeholders: set[str]) -> None:
    if not command.argv:
        raise OrchestratorValidationError("runtime.command.argv must contain at least one argument")
    for index, part in enumerate(command.argv):
        _validate_non_empty_string(part, f"runtime.command.argv[{index}]")
        _validate_placeholders(part, placeholders, f"runtime.command.argv[{index}]")
    if command.cwd:
        _validate_placeholders(command.cwd, placeholders, "runtime.command.cwd")
    for key, value in command.env.items():
        _validate_non_empty_string(key, "runtime.command.env key")
        _validate_placeholders(value, placeholders, f"runtime.command.env[{key!r}]")


SHORT_DESCRIPTION_MAX_LEN = 120
DESCRIPTION_MAX_LEN = 500
KEYWORD_MAX_LEN = 32
KEYWORDS_MAX_COUNT = 12


def _validate_capability_text(
    description: str,
    short_description: str,
    keywords: tuple[str, ...],
    *,
    manifest_id: str,
    error_cls: type[Exception],
) -> None:
    if len(description) > DESCRIPTION_MAX_LEN:
        raise error_cls(
            f"{manifest_id}: description is {len(description)} chars; max is {DESCRIPTION_MAX_LEN}"
        )
    if len(short_description) > SHORT_DESCRIPTION_MAX_LEN:
        raise error_cls(
            f"{manifest_id}: short_description is {len(short_description)} chars; max is {SHORT_DESCRIPTION_MAX_LEN}"
        )
    if len(keywords) > KEYWORDS_MAX_COUNT:
        raise error_cls(
            f"{manifest_id}: keywords has {len(keywords)} entries; max is {KEYWORDS_MAX_COUNT}"
        )
    seen: set[str] = set()
    for index, keyword in enumerate(keywords):
        if len(keyword) > KEYWORD_MAX_LEN:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] is {len(keyword)} chars; max is {KEYWORD_MAX_LEN}"
            )
        if any(ch.isspace() for ch in keyword):
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword!r} must not contain whitespace"
            )
        if keyword.lower() != keyword:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword!r} must be lowercase"
            )
        if keyword in seen:
            raise error_cls(
                f"{manifest_id}: keywords[{index}] {keyword!r} is a duplicate"
            )
        seen.add(keyword)


def _validate_placeholders(value: str, allowed: set[str], path: str) -> None:
    for placeholder in re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", value):
        if placeholder not in allowed:
            raise OrchestratorValidationError(f"{path} uses unknown placeholder {{{placeholder}}}")


def _validate_unique_named(values: tuple[Port, ...] | tuple[Output, ...], label: str) -> set[str]:
    names: set[str] = set()
    for value in values:
        if value.name in names:
            raise OrchestratorValidationError(f"duplicate {label} name {value.name!r}")
        names.add(value.name)
    return names


def _validate_non_empty_identifier(value: Any, path: str) -> None:
    _validate_non_empty_string(value, path)
    if not re.match(r"^[A-Za-z][A-Za-z0-9_.-]*$", value):
        raise OrchestratorValidationError(f"{path} must start with a letter and contain only letters, numbers, '.', '_' or '-'")


def _validate_qualified_identifier(value: Any, path: str) -> None:
    _validate_non_empty_identifier(value, path)
    if "." not in value or any(not part for part in value.split(".")):
        raise OrchestratorValidationError(f"{path} must be qualified as <pack>.<name>")


def _validate_non_empty_string(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{path} must be a non-empty string")


def _require_mapping(raw: Any, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise OrchestratorValidationError(f"{path} must be an object")
    return raw


def _require_string(data: dict[str, Any], key: str, path: str) -> str:
    if key not in data:
        raise OrchestratorValidationError(f"missing required field {path}")
    value = data[key]
    _validate_non_empty_string(value, path)
    return value


def _optional_string(data: dict[str, Any], key: str, path: str, *, default: str = "") -> str:
    if key not in data:
        return default
    value = data[key]
    _validate_non_empty_string(value, path)
    return value


def _optional_nullable_string(data: dict[str, Any], key: str, path: str) -> str | None:
    if key not in data or data[key] is None:
        return None
    value = data[key]
    _validate_non_empty_string(value, path)
    return value


def _optional_bool(data: dict[str, Any], key: str, path: str, *, default: bool) -> bool:
    if key not in data:
        return default
    value = data[key]
    if not isinstance(value, bool):
        raise OrchestratorValidationError(f"{path} must be a boolean")
    return value


def _optional_list(data: dict[str, Any], key: str, path: str) -> list[Any]:
    if key not in data:
        return []
    value = data[key]
    if not isinstance(value, list):
        raise OrchestratorValidationError(f"{path} must be a list")
    return value


def _string_list(raw: Any, path: str) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        raise OrchestratorValidationError(f"{path} must be a list")
    result: list[str] = []
    for index, value in enumerate(raw):
        if not isinstance(value, str) or not value.strip():
            raise OrchestratorValidationError(f"{path}[{index}] must be a non-empty string")
        result.append(value)
    return result


def _optional_string_list(data: dict[str, Any], key: str, path: str) -> list[str]:
    if key not in data:
        return []
    return _string_list(data[key], path)


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, tuple):
        return [_drop_none(item) for item in value]
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


__all__ = [
    "CACHE_MODES",
    "DESCRIPTION_MAX_LEN",
    "ISOLATION_MODES",
    "KEYWORDS_MAX_COUNT",
    "KEYWORD_MAX_LEN",
    "OUTPUT_MODES",
    "ORCHESTRATOR_KINDS",
    "RUNTIME_KINDS",
    "SHORT_DESCRIPTION_MAX_LEN",
    "CachePolicy",
    "CommandSpec",
    "OrchestratorDefinition",
    "OrchestratorValidationError",
    "IsolationMetadata",
    "Output",
    "Port",
    "RuntimeSpec",
    "load_orchestrator_manifest",
    "to_capability_handle",
    "validate_orchestrator_definition",
]
