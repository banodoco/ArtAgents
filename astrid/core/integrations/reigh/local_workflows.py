"""Declared custom workflows (doc 27 §3.3) — data, never plugins.

A user-facing YAML file trimmed to ``{id, ports, workflow_path, digest,
output_policy}`` declares one local capability ``local.<id>`` that feeds
the same generic VibeComfy handler as every shipped workflow. Admission
snapshots and hashes the workflow bytes; there is no runtime Python/plugin
loading and no promotion service — moving a vetted workflow into the
vendored tree is an in-repo, restart-visible change.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DECLARATIONS_ENV = "ASTRID_LOCAL_WORKFLOWS"
"""Colon-separated extra search directories for declaration YAML files."""

DECLARATIONS_SUBDIR = ".astrid/workflows"
"""Projects-root subdirectory scanned for declaration YAML files."""

_ALLOWED_KEYS = frozenset(
    {"id", "ports", "workflow_path", "digest", "output_policy"}
)

#: Port names the generic handler can inject (typed ports only).
INJECTABLE_PORTS = frozenset(
    {
        "prompt",
        "negative_prompt",
        "seed",
        "size",
        "image_url",
        "image_ref",
        "mask_url",
        "strength",
        "steps",
        "guidance_scale",
    }
)


class LocalWorkflowError(Exception):
    """Typed failure of the custom-workflow declaration path."""


@dataclass(frozen=True, slots=True)
class LocalWorkflowDeclaration:
    """One trimmed custom-workflow declaration row."""

    id: str
    ports: dict[str, Any]
    workflow_path: str
    digest: str
    output_policy: dict[str, Any]

    @property
    def capability_id(self) -> str:
        return f"local.{self.id}"

    @property
    def path(self) -> Path:
        return Path(self.workflow_path)


def declaration_dirs(projects_root: str | Path | None = None) -> list[Path]:
    """Declaration search directories, in precedence order."""
    dirs: list[Path] = []
    env_value = os.environ.get(DECLARATIONS_ENV)
    if env_value:
        dirs.extend(
            Path(part) for part in env_value.split(":") if part.strip()
        )
    if projects_root is not None:
        dirs.append(Path(projects_root) / DECLARATIONS_SUBDIR)
    return dirs


def parse_declaration(raw: Mapping[str, Any], *, source: Path) -> LocalWorkflowDeclaration:
    """Trim and validate one YAML mapping into a declaration.

    Unknown keys are trimmed away per doc 27 §3.3; the five contract
    fields are validated fail-closed (missing id/workflow_path/digest,
    undigestable bytes, or a non-injectable port all refuse admission).
    """
    workflow_id = raw.get("id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise LocalWorkflowError(
            f"{source}: declaration 'id' must be a non-empty string"
        )
    slug = workflow_id.strip()
    if slug != _slugify(slug):
        raise LocalWorkflowError(
            f"{source}: declaration id {slug!r} must be a lowercase slug "
            "(a-z0-9._-)"
        )

    workflow_path = raw.get("workflow_path")
    if not isinstance(workflow_path, str) or not workflow_path.strip():
        raise LocalWorkflowError(
            f"{source}: declaration 'workflow_path' must be a non-empty string"
        )
    path = Path(workflow_path).expanduser()
    if not path.is_absolute():
        path = (source.resolve().parent / path).resolve()

    digest = raw.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise LocalWorkflowError(
            f"{source}: declaration 'digest' must be a 64-char sha256 hex string"
        )
    try:
        bytes.fromhex(digest)
    except ValueError:
        raise LocalWorkflowError(
            f"{source}: declaration 'digest' must be sha256 hex"
        ) from None
    try:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise LocalWorkflowError(
            f"{source}: workflow_path {workflow_path!r} unreadable "
            f"({exc.strerror})"
        ) from None
    if actual != digest:
        raise LocalWorkflowError(
            f"{source}: workflow bytes digest mismatch: declared {digest}, "
            f"found {actual}"
        )

    ports_raw = raw.get("ports")
    if ports_raw is None:
        ports_raw = {}
    if not isinstance(ports_raw, Mapping):
        raise LocalWorkflowError(
            f"{source}: declaration 'ports' must be a mapping of "
            "port name to type"
        )
    ports: dict[str, Any] = {}
    for name, port_type in ports_raw.items():
        if name not in INJECTABLE_PORTS:
            raise LocalWorkflowError(
                f"{source}: port {name!r} is not injectable by the generic "
                f"handler; injectable ports: {sorted(INJECTABLE_PORTS)}"
            )
        ports[name] = port_type

    output_policy_raw = raw.get("output_policy")
    if output_policy_raw is None:
        output_policy_raw = {}
    if not isinstance(output_policy_raw, Mapping):
        raise LocalWorkflowError(
            f"{source}: declaration 'output_policy' must be a mapping"
        )
    return LocalWorkflowDeclaration(
        id=slug,
        ports=ports,
        workflow_path=str(path),
        digest=digest,
        output_policy=dict(output_policy_raw),
    )


def _slugify(raw: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    lowered = raw.lower().strip()
    return lowered if lowered and set(lowered) <= allowed else "\0"


def load_declarations(
    projects_root: str | Path | None = None,
) -> dict[str, LocalWorkflowDeclaration]:
    """Load every declaration YAML from the search directories.

    Returns ``{id: declaration}``; a malformed file is a typed refusal
    (fail-closed), not a skipped row.
    """
    import yaml

    declarations: dict[str, LocalWorkflowDeclaration] = {}
    seen_dirs: set[Path] = set()
    for directory in declaration_dirs(projects_root):
        if not directory.is_dir():
            continue
        resolved = directory.resolve()
        if resolved in seen_dirs:
            continue
        seen_dirs.add(resolved)
        for source in sorted(directory.glob("*.yaml")):
            try:
                raw = yaml.safe_load(source.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise LocalWorkflowError(
                    f"{source}: unreadable declaration: {exc}"
                ) from None
            if raw is None:
                raw = {}
            if not isinstance(raw, Mapping):
                raise LocalWorkflowError(
                    f"{source}: declaration must be a YAML mapping"
                )
            declaration = parse_declaration(raw, source=source)
            if declaration.id in declarations:
                raise LocalWorkflowError(
                    f"{source}: duplicate declaration id {declaration.id!r}"
                )
            declarations[declaration.id] = declaration
    return declarations


def resolve_local_declaration(
    capability_id: str,
    projects_root: str | Path | None = None,
) -> LocalWorkflowDeclaration | None:
    """Resolve ``local.<id>`` against the declared rows, or ``None``."""
    if not capability_id.startswith("local."):
        return None
    return load_declarations(projects_root).get(
        capability_id.removeprefix("local.")
    )


def declaration_entry(declaration: LocalWorkflowDeclaration) -> Any:
    """Build the registry-shaped capability entry for one declaration."""
    from astrid.core.integrations.reigh.capabilities import (
        BINDING_VIBECOMFY,
        CapabilityEntry,
        FAMILY_LOCAL_WORKFLOW,
        _policy,
    )

    required_inputs: dict[str, Any] = {}
    for name, port_type in declaration.ports.items():
        if port_type in ("int", "integer"):
            required_inputs[name] = int
        elif port_type in ("float", "number"):
            required_inputs[name] = (int, float)
        else:
            required_inputs[name] = str
    return CapabilityEntry(
        declaration.capability_id,
        FAMILY_LOCAL_WORKFLOW,
        BINDING_VIBECOMFY,
        # Frozen-shape policy with declared overrides (doc 16 §1.1); an
        # empty declaration keeps create_generation=True.
        _policy(**dict(declaration.output_policy)),
        required_inputs=required_inputs,
        template=(declaration.workflow_path, declaration.digest),
    )


__all__ = [
    "DECLARATIONS_ENV",
    "DECLARATIONS_SUBDIR",
    "INJECTABLE_PORTS",
    "LocalWorkflowDeclaration",
    "LocalWorkflowError",
    "declaration_dirs",
    "declaration_entry",
    "load_declarations",
    "parse_declaration",
    "resolve_local_declaration",
]
