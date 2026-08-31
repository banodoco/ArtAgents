"""Neutral shared schema dataclasses for Astrid executable contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol, get_args, runtime_checkable

PortType = Literal[
    "string", "path", "file", "directory", "json", "boolean", "number", "integer", "html"
]
OutputMode = Literal["mutate", "create", "create_or_replace"]
CacheMode = Literal["none", "sentinel", "always_run"]
IsolationMode = Literal["subprocess"]
LocalEditState = Literal["clean", "dirty", "conflict"]

# Runtime-validation allowlists, derived from the Literal aliases so the two
# can never drift out of sync.
PORT_REQUIRED_TYPES: frozenset[str] = frozenset(get_args(PortType))
OUTPUT_MODES: frozenset[str] = frozenset(get_args(OutputMode))
CACHE_MODES: frozenset[str] = frozenset(get_args(CacheMode))
ISOLATION_MODES: frozenset[str] = frozenset(get_args(IsolationMode))


@dataclass(frozen=True)
class Port:
    name: str
    type: PortType = "path"
    required: bool = True
    description: str = ""
    default: Any = None
    placeholder: str | None = None
    artifact_type: str | None = None


@dataclass(frozen=True)
class Output:
    name: str
    type: PortType = "path"
    mode: OutputMode = "create_or_replace"
    description: str = ""
    placeholder: str | None = None
    path_template: str | None = None
    extension: str | None = None
    artifact_type: str | None = None


@dataclass(frozen=True)
class CommandInputArg:
    input: str
    flag: str | None = None
    repeatable: bool = False
    optional: bool = False
    before: str | None = None


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    input_args: tuple[CommandInputArg, ...] = ()


@dataclass(frozen=True)
class CachePolicy:
    mode: CacheMode = "sentinel"
    sentinels: tuple[str, ...] = ()
    always_run: bool = False
    per_brief: bool = False


@dataclass(frozen=True)
class IsolationMetadata:
    mode: IsolationMode = "subprocess"
    requirements: tuple[str, ...] = ()
    binaries: tuple[str, ...] = ()
    network: bool = False
    env_passthrough: tuple[str, ...] = ()
    # Credentials required by the executable itself.  This lives in the
    # isolation contract (rather than only in free-form metadata) so every
    # discovery/host path sees the same readiness declaration.
    secrets_required: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# M1 Capability Identity dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Provenance:
    """Where a capability came from and how it was discovered."""

    source: str
    pack_id: str = ""
    manifest_path: str = ""
    content_root: str = ""
    resolved_alias: str | None = None
    forked_from: str | None = None
    upstream_version: str | None = None
    compatibility_token: str | None = None


@dataclass(frozen=True)
class SafetyDeclaration:
    """Minimal safety / cost / permission metadata for a capability."""

    network: bool = False
    cost_estimate: str = ""
    secrets_required: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True)
class AliasRecord:
    """A single public-id alias pointing to a canonical capability id."""

    alias: str
    canonical_id: str
    deprecated: bool = False
    deprecation_message: str = ""
    source_pack_id: str = ""


@dataclass(frozen=True)
class CapabilityHandle:
    """Shared identity handle carried by every exec, orch, and element.

    All three registries adapt their native definitions into this shape so
    that list / search / inspect surfaces a uniform identity across the
    whole pack system.
    """

    canonical_id: str
    local_id: str
    pack_id: str
    kind: str
    name: str
    version: str
    provenance: Provenance
    safety: SafetyDeclaration = field(default_factory=SafetyDeclaration)
    description: str = ""
    short_description: str = ""
    keywords: tuple[str, ...] = ()
    category: str = ""
    status: str = "stable"
    visibility: str = "public"
    local_edit_state: LocalEditState = "clean"
    override_target: str | None = None
    aliases: tuple[AliasRecord, ...] = ()
    inputs: tuple[Port, ...] = ()
    outputs: tuple[Output, ...] = ()
    deprecated: bool = False
    deprecated_alternatives: tuple[str, ...] = ()
    deprecation_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shared ``to_json`` helper (used by both ExecutorDefinition and
# OrchestratorDefinition — their implementations were 100 % identical).
# ---------------------------------------------------------------------------


def to_capability_json(obj: Any, *, indent: int | None = 2) -> str:
    """Serialize *obj* (which must have ``.to_dict()``) to sorted JSON."""
    return json.dumps(obj.to_dict(), indent=indent, sort_keys=True)


# ---------------------------------------------------------------------------
# Protocol for capability definitions that can be adapted into a CapabilityHandle
# ---------------------------------------------------------------------------


@runtime_checkable
class HasCapabilityFields(Protocol):
    """Structural protocol for any Definition that carries capability identity fields.

    Both ``ExecutorDefinition`` and ``OrchestratorDefinition`` satisfy this
    protocol, which allows ``to_capability_handle`` to be a single generic
    function in the shared contracts layer.
    """

    id: str
    name: str
    kind: str
    version: str
    description: str
    short_description: str
    keywords: tuple[str, ...]
    inputs: tuple[Port, ...]
    outputs: tuple[Output, ...]
    isolation: IsolationMetadata
    metadata: dict[str, Any]


def to_capability_handle(
    definition: HasCapabilityFields,
    *,
    aliases: tuple[AliasRecord, ...] = (),
    resolved_alias: str | None = None,
    deprecated: bool = False,
    deprecation_message: str = "",
) -> CapabilityHandle:
    """Adapt a capability definition into a shared ``CapabilityHandle``.

    Works with any definition that satisfies ``HasCapabilityFields``
    (``ExecutorDefinition``, ``OrchestratorDefinition``, etc.).

    Field mapping:

    * ``canonical_id`` — ``definition.id`` (qualified form ``pack.name``)
    * ``local_id`` — the portion after the first dot in ``definition.id``
    * ``pack_id`` — the portion before the first dot in ``definition.id``
    * ``kind`` — ``definition.kind`` (preserved as-is)
    * ``provenance`` — source derived from metadata, default ``"pack"``
    * ``safety`` — network flag from ``definition.isolation.network``

    Alias metadata (*aliases*, *resolved_alias*, *deprecated*,
    *deprecation_message*) is carried on the handle and never mutates
    the definition's ``.metadata``.
    """
    parts = definition.id.split(".", 1)
    pack_id = parts[0]
    local_id = parts[1] if len(parts) > 1 else definition.id

    metadata = definition.metadata
    metadata_source = metadata.get("source")
    provenance_source = str(metadata_source) if metadata_source else "pack"

    forked_from = str(metadata.get("forked_from") or "")
    upstream_version = str(metadata.get("upstream_version") or "")
    compatibility_token = str(metadata.get("compatibility_token") or "")
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
        safety=SafetyDeclaration(
            network=definition.isolation.network,
            secrets_required=tuple(dict.fromkeys(
                str(item)
                for item in (
                    *definition.isolation.secrets_required,
                    *(metadata.get("secrets_required", ()) or ()),
                )
                if isinstance(item, str) and item
            )),
        ),
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


__all__ = [
    "CACHE_MODES",
    "CacheMode",
    "ISOLATION_MODES",
    "IsolationMode",
    "LocalEditState",
    "OUTPUT_MODES",
    "OutputMode",
    "PORT_REQUIRED_TYPES",
    "PortType",
    "AliasRecord",
    "CachePolicy",
    "CommandInputArg",
    "CapabilityHandle",
    "CommandSpec",
    "HasCapabilityFields",
    "IsolationMetadata",
    "Output",
    "Port",
    "Provenance",
    "SafetyDeclaration",
    "to_capability_handle",
]
