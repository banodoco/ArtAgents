"""Neutral shared schema dataclasses for Astrid executable contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, get_args


PortType = Literal[
    "string", "path", "file", "directory", "json", "boolean", "number", "integer", "html"
]
OutputMode = Literal["mutate", "create", "create_or_replace"]
CacheMode = Literal["none", "sentinel", "always_run"]
IsolationMode = Literal["in_process", "subprocess"]
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


@dataclass(frozen=True)
class Output:
    name: str
    type: PortType = "path"
    mode: OutputMode = "create_or_replace"
    description: str = ""
    placeholder: str | None = None
    path_template: str | None = None
    extension: str | None = None


PerformerPort = Port
PerformerOutput = Output


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)


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
    "CapabilityHandle",
    "CommandSpec",
    "IsolationMetadata",
    "Output",
    "Port",
    "PerformerOutput",
    "PerformerPort",
    "Provenance",
    "SafetyDeclaration",
]
