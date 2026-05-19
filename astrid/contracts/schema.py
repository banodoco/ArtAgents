"""Neutral shared schema dataclasses for Astrid executable contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args


PortType = Literal[
    "string", "path", "file", "directory", "json", "boolean", "number", "integer"
]
OutputMode = Literal["mutate", "create", "create_or_replace"]
CacheMode = Literal["none", "sentinel", "always_run"]
IsolationMode = Literal["in_process", "subprocess"]

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


__all__ = [
    "CACHE_MODES",
    "CacheMode",
    "ISOLATION_MODES",
    "IsolationMode",
    "OUTPUT_MODES",
    "OutputMode",
    "PORT_REQUIRED_TYPES",
    "PortType",
    "CachePolicy",
    "CommandSpec",
    "IsolationMetadata",
    "Output",
    "Port",
    "PerformerOutput",
    "PerformerPort",
]
