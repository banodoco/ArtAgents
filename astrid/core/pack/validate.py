"""Static pack validation module.

Uses yaml.safe_load for author-facing YAML, validates each manifest against its
JSON Schema (v1), rejects unknown schema_version values, and normalizes errors
into file-specific builder-facing messages.

Validation is static: checks declared content roots, docs, STAGE.md,
runtime entrypoint files, and component manifests exist on disk without
importing run.py.
"""

from __future__ import annotations

import json as _json
import logging
import re as _re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Optional

import jsonschema
from referencing import Registry, Resource

from astrid.core.pack.alias_resolver import AliasResolutionError, AliasResolver
from astrid.core.pack.manifest import ManifestParseError, load_manifest_mapping
from astrid.core.pack import (
    EXECUTOR_MANIFEST_NAMES,
    ORCHESTRATOR_MANIFEST_NAMES,
    PackDefinition,
    _normalize_pack_permissions,
    _optional_pack_aliases,
    _optional_pack_extensions,
    element_kind_registry_for_pack,
    iter_element_roots,
    iter_executor_roots,
    iter_orchestrator_roots,
    pack_manifest_path,
    pack_taxonomy_from_manifest,
    validate_content_id_in_pack,
    validate_element_pack_id,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known schema versions and their schema files
# ---------------------------------------------------------------------------

_SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ELEMENT_MANIFEST_NAMES = ("element.yaml", "element.yml", "element.json")
_FIRST_PARTY_PACKS_ROOT = _REPO_ROOT / "astrid" / "packs"
_FIRST_PARTY_PACK_IDS = (
    "builtin",
    "comfy_wrap",
    "editorial",
    "fal",
    "foley",
    "generation",
    "iteration",
    "media",
    "moirae",
    "reigh",
    "rendering",
    "runpod",
    "stream_content",
    "text_analysis",
    "training",
    "understanding",
    "vibecomfy",
    "video_editing",
    "youtube",
)
_FIRST_PARTY_INTERNAL_DIRS = {"_core"}
_IGNORED_PACKS_ROOT_DIRS = {"__pycache__"}

KNOWN_SCHEMA_VERSIONS: dict[int, dict[str, Path]] = {
    1: {
        "pack": _SCHEMAS_ROOT / "v1" / "pack.json",
        "executor": _SCHEMAS_ROOT / "v1" / "executor.json",
        "orchestrator": _SCHEMAS_ROOT / "v1" / "orchestrator.json",
        "element": _SCHEMAS_ROOT / "v1" / "element.json",
    }
}

KNOWN_VERSIONS_STR = ", ".join(str(v) for v in sorted(KNOWN_SCHEMA_VERSIONS))
V1_TRUST_BLOCK: dict[str, Any] = {
    "sandbox": "none",
    "runs_with_user_process_permissions": True,
    "permission_enforcement": "disclosure_only",
}


class LayoutExceptionClass(str, Enum):
    """Named exceptions the pack layout contract allows temporarily or permanently."""

    IMPORTABLE_COMPONENT_CODE = "importable_component_code"
    LEGACY_PUBLIC_SHIM = "legacy_public_shim"
    DOMAIN_EXCEPTION = "domain_exception"
    GENERATED_IGNORED = "generated_ignored"
    SKILL_ONLY_SHELL = "skill_only_shell"
    MACHINERY_SHIM = "machinery_shim"
    DSL_ORCHESTRATOR_SHIM = "dsl_orchestrator_shim"


class LayoutExceptionLifecycle(str, Enum):
    """Lifecycle for declared layout exceptions."""

    M1 = "M1"
    M2 = "M2"
    PERMANENT = "permanent"


_TEMPORARY_LAYOUT_EXCEPTION_CLASSES = {
    LayoutExceptionClass.LEGACY_PUBLIC_SHIM,
    LayoutExceptionClass.MACHINERY_SHIM,
    LayoutExceptionClass.DSL_ORCHESTRATOR_SHIM,
}

_LAYOUT_EXCEPTION_DECLARATION_PATH = "metadata.layout.exceptions"
_CANONICAL_PACK_ROOT_DIRS = {
    "build",
    "docs",
    "elements",
    "examples",
    "executors",
    "fixtures",
    "golden",
    "orchestrators",
    "schemas",
    "skill",
}
_CANONICAL_COMPONENT_SUPPORT_FILES = {"STAGE.md"}
_CANONICAL_COMPONENT_SUPPORT_DIRS = {"skill"}


@dataclass(frozen=True)
class CanonicalLayoutRule:
    """Agent-readable description of a canonical pack path family."""

    pattern: str
    description: str


@dataclass(frozen=True)
class PackLayoutException:
    """One declared exception to the canonical pack layout contract."""

    path: str
    exception_class: LayoutExceptionClass
    reason: str
    defer_to: LayoutExceptionLifecycle = LayoutExceptionLifecycle.PERMANENT

    @property
    def is_temporary(self) -> bool:
        return self.exception_class in _TEMPORARY_LAYOUT_EXCEPTION_CLASSES


@dataclass(frozen=True)
class LayoutValidationIssue:
    """One layout-contract problem surfaced under the aggregate failure heading."""

    path: str
    message: str


CANONICAL_PACK_LAYOUT_RULES: tuple[CanonicalLayoutRule, ...] = (
    CanonicalLayoutRule("pack.yaml|pack.yml|pack.json", "pack manifest at the pack root"),
    CanonicalLayoutRule("skill/SKILL.md", "optional pack-level skill guidance"),
    CanonicalLayoutRule("executors/<name>/...", "executor capability directories"),
    CanonicalLayoutRule("orchestrators/<name>/...", "orchestrator capability directories"),
    CanonicalLayoutRule("elements/<kind>/<name>/...", "element capability directories"),
    CanonicalLayoutRule("fixtures/...|golden/...", "optional checked-in fixture data"),
    CanonicalLayoutRule("build/...", "generated build output when explicitly classified"),
    CanonicalLayoutRule("docs/...|examples/...|schemas/...", "declared supporting assets"),
)

# ---------------------------------------------------------------------------
# M1 machinery-shim exceptions (not relocated during Plan v1.0)
# ---------------------------------------------------------------------------
# These files remain at ``astrid/packs/`` during M1 and will be relocated
# to ``astrid/core/pack_machinery/`` in M2.  They are documented here so the
# layout contract is explicit about every known deviation.
#
#   astrid/packs/_canonical_entrypoint.py
#       class:       machinery_shim
#       defer_to:    M2
#       reason:      50+ import sites across pack run.py files, in_process.py,
#                   and test files create disproportionate regression risk
#                   for M1.  Relocation deferred to M2.
#
# ---------------------------------------------------------------------------
# M1 root pack Python shim exceptions (classified in pack metadata)
# ---------------------------------------------------------------------------
# These shims live at the root of their respective pack directories and are
# kept in place for M1; each is declared as a layout exception in the pack's
# ``pack.yaml`` under ``metadata.layout.exceptions`` (see T12).
#
#   builtin/agent_probe.py
#       class:       dsl_orchestrator_shim
#       defer_to:    M2 (declared in builtin/pack.yaml)
#       reason:      DSL @orchestrator("builtin.agent_probe") definition with
#                    16+ test-file references.  Not a canonical executor.
#                    Migration to orchestrators/ deferred to M2.
#
#   video_editing/hype.py
#       class:       legacy_public_shim
#       defer_to:    M2 (declared in video_editing/pack.yaml)
#       reason:      Legacy author-test DSL shim that duplicates
#                    video_editing.hype (canonically at
#                    orchestrators/hype/run.py).  Kept for backward
#                    compatibility until M2 removes it.
#
# ---------------------------------------------------------------------------
# M1 special non-manifest directories (classified in this contract)
# ---------------------------------------------------------------------------
# These directories under ``astrid/packs/`` are not regular packs (they
# lack a ``pack.yaml``) but serve documented roles.  They are listed here
# so the layout contract remains explicit about every known deviation.
#
#   _core/
#       class:       skill_only_shell
#       defer_to:    permanent (not a pack — skill documentation surface)
#       reason:      Contains only ``skill/SKILL.md`` providing the root
#                    Astrid skill description for agent harnesses.  No
#                    ``pack.yaml``, executors, or orchestrators exist.
#                    Discovered via ``astrid.skills.discovery``, not via
#                    ``astrid.core.pack.discover_packs``.
#
# ---------------------------------------------------------------------------
# M1 relocated / removed directories (validated by contract tests)
# ---------------------------------------------------------------------------
#   astrid/packs/schemas/
#       status:      relocated to astrid/core/pack/schemas/ (M2 T10)
#       contract:    ``test_schemas_directory_absent_from_pack_tree`` in
#                    ``tests/test_pack_layout_contract.py`` enforces
#                    continued absence.
#   astrid/core/pack_machinery/schemas/
#       status:      relocated to astrid/core/pack/schemas/ (M2 T10)
#       contract:    ``test_schemas_relocated_to_pack`` in
#                    ``tests/test_pack_layout_contract.py`` enforces
#                    presence at the new canonical location.


def _check_schema_version(version_value: Any, manifest_relpath: str) -> int:
    """Validate that schema_version is a known integer."""
    if not isinstance(version_value, int) and not (
        isinstance(version_value, float) and version_value == int(version_value)
    ):
        raise ValidationError(
            f"{manifest_relpath}: schema_version must be an integer, got "
            f"{type(version_value).__name__}"
        )
    version = int(version_value)
    if version not in KNOWN_SCHEMA_VERSIONS:
        raise ValidationError(
            f"{manifest_relpath}: unknown schema_version {version} "
            f"(known: {KNOWN_VERSIONS_STR})"
        )
    return version


def _normalize_jsonschema_error(
    error: jsonschema.ValidationError,
    manifest_relpath: str,
    raw_data: dict[str, Any],
) -> str:
    """Convert a jsonschema ValidationError into a file-specific message."""
    # Build the field path from the error's absolute path
    path_parts: list[str] = list(error.absolute_path)
    field = ".".join(str(p) for p in path_parts) if path_parts else "<root>"

    prefix = f"{manifest_relpath}"

    # Special-case schema_version since we handle it separately upstream,
    # but jsonschema may still report it for missing/wrong-type.
    if path_parts == ["schema_version"]:
        if "schema_version" not in raw_data:
            return f"{prefix}: missing required field schema_version"
        return f"{prefix}: schema_version must be 1 (known: {KNOWN_VERSIONS_STR})"

    message = error.message
    # Clean up verbose jsonschema messages
    if message and len(message) > 200:
        message = message[:200] + "..."

    if error.validator == "required":
        # error.validator_value is the full required array from the schema.
        # error.message names the actually missing property.
        # Extract the missing field name from the message.
        msg = error.message
        # Typical message: "'name' is a required property"
        m = _re.match(r"'([^']+)' is a required property", msg)
        if m:
            missing_field = m.group(1)
            if field == "<root>":
                return f"{prefix}: missing required field {missing_field}"
            return f"{prefix}: missing required field {field}.{missing_field}"
        # Fallback
        return f"{prefix}: missing required field(s) — {msg}"

    if error.validator == "additionalProperties":
        return f"{prefix}: unknown field(s) in {field}"

    if error.validator == "enum":
        allowed = error.validator_value
        actual = raw_data
        for p in path_parts:
            if isinstance(actual, dict):
                actual = actual.get(p)
            else:
                break
        return f"{prefix}: {field} must be one of {allowed}, got {actual!r}"

    if error.validator == "type":
        expected = error.validator_value
        actual_val = raw_data
        for p in path_parts:
            if isinstance(actual_val, dict):
                actual_val = actual_val.get(p)
            else:
                break
        actual_type = type(actual_val).__name__
        expected_str = expected if isinstance(expected, str) else ", ".join(expected)
        return f"{prefix}: {field} must be {expected_str}, got {actual_type}"

    if error.validator == "pattern":
        actual_val = raw_data
        for p in path_parts:
            if isinstance(actual_val, dict):
                actual_val = actual_val.get(p)
            else:
                break
        return f"{prefix}: {field} value {actual_val!r} does not match required pattern"

    return f"{prefix}: {field} — {message}"


class ValidationError(ValueError):
    """Raised when pack validation fails."""


class PackLayoutContractError(ValidationError):
    """Aggregate layout-contract failure with per-path detail."""

    def __init__(self, issues: list[LayoutValidationIssue]):
        self.issues = tuple(issues)
        count = len(issues)
        noun = "issue" if count == 1 else "issues"
        super().__init__(f"pack layout contract failed ({count} {noun})")

    def lines(self) -> list[str]:
        lines = [str(self)]
        for issue in self.issues:
            lines.append(f"{issue.path}: {issue.message}")
        return lines


class PackValidator:
    """Validates an external pack directory statically."""

    def __init__(self, pack_root: Path):
        self.pack_root = pack_root.resolve()
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self._pack_data: Optional[dict[str, Any]] = None
        self._layout_issues: list[LayoutValidationIssue] = []
        self._layout_exceptions: list[PackLayoutException] = []

    def validate(self) -> list[str]:
        """Run all validations. Returns list of error strings (empty = valid)."""
        self.errors = []
        self.warnings = []
        self._layout_issues = []
        self._layout_exceptions = []
        self._capability_locations: dict[str, str] = {}
        self._pack_capability_locations: dict[str, dict[str, str]] = {
            "executor": {},
            "orchestrator": {},
        }
        self._alias_targets: list[tuple[str, str, str]] = []
        self._pack_alias_resolvers: dict[str, AliasResolver] = {
            "executor": AliasResolver(),
            "orchestrator": AliasResolver(),
        }
        self._pack_alias_targets: list[tuple[str, str, str, str]] = []

        if (self.pack_root / ".no-pack").exists():
            return self.errors

        pack_yaml = pack_manifest_path(self.pack_root)
        if pack_yaml is None:
            self.errors.append(
                f"{self._rel(self.pack_root)}: pack manifest not found "
                f"(pack.yaml, pack.yml, or pack.json)"
            )
            return self.errors

        # Parse pack.yaml
        pack_data = self._load_yaml(pack_yaml)
        if pack_data is None:
            return self.errors  # parse error already recorded
        self._pack_data = pack_data

        # Check schema_version and validate against JSON Schema
        version = self._validate_manifest(
            pack_data, "pack", self._rel(pack_yaml)
        )
        if version is None:
            return self.errors  # schema_version error already recorded

        # Validate content roots exist
        content = pack_data.get("content", {})
        if isinstance(content, dict):
            self._validate_content_roots(content)

        # Validate docs exist
        docs = pack_data.get("docs", {})
        if isinstance(docs, dict):
            self._validate_docs(docs)

        # Validate component manifests
        self._validate_components(content)
        self._validate_pack_aliases()
        self._validate_alias_targets()
        self._validate_layout_contract()
        self._flush_layout_issues()

        return self.errors

    def validate_component_manifest(
        self,
        manifest_path: str | Path,
        manifest_kind: str,
    ) -> dict[str, Any] | None:
        """Load and schema-validate one component manifest.

        This uses the same parsing and JSON Schema path as full pack validation,
        without requiring callers to validate a whole pack tree.
        """
        path = Path(manifest_path)
        data = self._load_yaml(path)
        if data is None:
            return None
        self._validate_manifest(data, manifest_kind, self._rel(path))
        return data

    def _load_yaml(self, path: Path) -> Optional[dict[str, Any]]:
        """Load a YAML file with safe_load. Returns None on error."""
        rel = self._rel(path)
        try:
            data = load_manifest_mapping(path, manifest_kind="pack")
        except ManifestParseError as e:
            self.errors.append(f"{rel}: {e}")
            return None

        return data

    def _validate_manifest(
        self,
        data: dict[str, Any],
        manifest_kind: str,
        relpath: str,
    ) -> Optional[int]:
        """Validate a manifest dict against its JSON Schema.

        Returns the schema_version on success, None on failure.
        """
        # Pack and component manifests are schema-versioned. If a component
        # omits schema_version, validate against v1 so the schema reports the
        # same missing-field error direct JSON Schema validation would report.
        if "schema_version" not in data:
            if manifest_kind == "pack":
                self.errors.append(f"{relpath}: missing required field schema_version")
                return None
            version = 1
        else:
            try:
                version = _check_schema_version(data["schema_version"], relpath)
            except ValidationError as e:
                self.errors.append(str(e))
                return None

        # Load and validate against JSON Schema
        schema_path = KNOWN_SCHEMA_VERSIONS[version].get(manifest_kind)
        if schema_path is None:
            self.errors.append(
                f"{relpath}: no schema for {manifest_kind} in version {version}"
            )
            return None

        try:
            schema, registry = self._load_schema(schema_path, manifest_kind, version)
        except Exception as e:
            self.errors.append(
                f"{relpath}: cannot load schema {schema_path} — {e}"
            )
            return None

        validator = jsonschema.Draft7Validator(schema, registry=registry)
        raw_errors = list(validator.iter_errors(data))
        raw_errors = self._filter_dynamic_element_kind_errors(
            raw_errors,
            data=data,
            manifest_kind=manifest_kind,
        )

        if raw_errors:
            # Take the first few errors to avoid overwhelming output
            for err in raw_errors[:5]:
                self.errors.append(
                    _normalize_jsonschema_error(err, relpath, data)
                )
            if len(raw_errors) > 5:
                self.errors.append(
                    f"{relpath}: ... and {len(raw_errors) - 5} more validation errors"
                )
            return None

        return version

    def _filter_dynamic_element_kind_errors(
        self,
        errors: list[jsonschema.ValidationError],
        *,
        data: dict[str, Any],
        manifest_kind: str,
    ) -> list[jsonschema.ValidationError]:
        if manifest_kind != "element" or self._pack_data is None:
            return errors
        kind_value = data.get("kind")
        if not isinstance(kind_value, str):
            return errors
        try:
            pack = self._pack_definition_for_discovery({})
            element_kind_registry_for_pack(pack).normalize(kind_value)
        except Exception:
            return errors
        return [
            error
            for error in errors
            if not (error.validator == "enum" and list(error.absolute_path) == ["kind"])
        ]

    def _load_schema(
        self, schema_path: Path, manifest_kind: str, version: int
    ) -> tuple[dict[str, Any], Registry]:
        """Load a JSON Schema file and build a referencing.Registry.

        Returns (schema_dict, registry) for use with jsonschema validators.
        Cached per (manifest_kind, version).
        """
        schema_key = (manifest_kind, version)
        if not hasattr(self, "_schema_cache"):
            self._schema_cache: dict[tuple, tuple[dict[str, Any], Registry]] = {}
        if schema_key in self._schema_cache:
            return self._schema_cache[schema_key]

        # Load the _defs.json first
        defs_path = schema_path.parent / "_defs.json"
        registry = Registry()
        if defs_path.is_file():
            with open(defs_path, "r", encoding="utf-8") as f:
                defs_schema = json_loads(f.read())
            registry = registry.with_resource(
                "_defs.json", Resource.from_contents(defs_schema)
            )

        # Load the schema
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json_loads(f.read())

        # Also register the schema itself if it has an $id
        schema_id = schema.get("$id")
        if schema_id:
            registry = registry.with_resource(
                schema_id, Resource.from_contents(schema)
            )

        self._schema_cache[schema_key] = (schema, registry)

        return schema, registry

    def _validate_content_roots(self, content: dict[str, Any]) -> None:
        """Verify that declared content root directories exist."""
        supported = {"executors", "orchestrators", "elements", "schemas", "examples", "docs"}
        for key in sorted(set(content) - supported):
            self.warnings.append(
                f"pack.yaml: unsupported content root {key!r}"
            )
        for key in ("executors", "orchestrators", "elements", "schemas", "examples"):
            if key not in content:
                continue
            root_rel = content[key]
            if not isinstance(root_rel, str) or not root_rel.strip():
                continue
            root_path = self.pack_root / root_rel
            if not root_path.is_dir():
                self.warnings.append(
                    f"{self._rel(root_path)}/: declared content root does not exist"
                )

    def _validate_docs(self, docs: dict[str, Any]) -> None:
        """Verify that declared doc files exist."""
        for doc_key, doc_rel in docs.items():
            if not isinstance(doc_rel, str) or not doc_rel.strip():
                continue
            doc_path = self.pack_root / doc_rel
            if not doc_path.is_file():
                self.warnings.append(
                    f"{self._rel(doc_path)}: declared docs file not found"
                )

    def _validate_components(self, content: dict[str, Any]) -> None:
        """Validate all component manifests declared via content roots."""
        if self._pack_data is None:
            return
        self._validate_discovered_components(content)

    def _validate_component_dir(
        self, root_dir: Path, manifest_kind: str
    ) -> None:
        """Validate all component directories under a content root."""
        for comp_dir in sorted(root_dir.iterdir()):
            if not comp_dir.is_dir() or comp_dir.name.startswith("."):
                continue
            if comp_dir.name == "__pycache__":
                continue

            manifest_path = self._find_component_manifest(comp_dir, manifest_kind)
            if manifest_path is None:
                expected_path = comp_dir / f"{manifest_kind}.yaml"
                self.errors.append(
                    f"{self._rel(expected_path)}: {manifest_kind} manifest not found"
                )
                continue

            self._validate_component_manifest_file(comp_dir, manifest_path, manifest_kind)

    def _validate_element_dir(self, root_dir: Path) -> None:
        """Validate element directories under the elements content root."""
        # Elements are organized as elements/<kind>/<element_name>/
        for kind_dir in sorted(root_dir.iterdir()):
            if not kind_dir.is_dir() or kind_dir.name.startswith("."):
                continue
            if kind_dir.name == "__pycache__":
                continue

            for elem_dir in sorted(kind_dir.iterdir()):
                if not elem_dir.is_dir() or elem_dir.name.startswith("."):
                    continue
                if elem_dir.name == "__pycache__":
                    continue

                manifest_path = self._find_component_manifest(elem_dir, "element")
                if manifest_path is None:
                    self.errors.append(
                        f"{self._rel(elem_dir / 'element.yaml')}: element manifest not found"
                    )
                    continue

                self._validate_element_manifest_file(kind_dir.name, manifest_path)

    def _pack_definition_for_discovery(self, content: dict[str, Any]) -> PackDefinition:
        data = self._pack_data or {}
        status = str(data.get("status") or "active")
        taxonomy = pack_taxonomy_from_manifest(data, status=status)
        return PackDefinition(
            id=str(data.get("id") or self.pack_root.name),
            name=str(data.get("name") or data.get("id") or self.pack_root.name),
            version=str(data.get("version") or ""),
            root=self.pack_root,
            manifest_path=self.pack_root / "pack.yaml",
            schema_version=data.get("schema_version"),
            description=str(data.get("description") or ""),
            status=status,
            visibility=str(data.get("visibility") or "visible"),
            content=dict(content),
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
            agent=dict(data.get("agent", {})) if isinstance(data.get("agent", {}), dict) else {},
            aliases=_optional_pack_aliases(data.get("aliases"), path="pack.aliases"),
            permissions=_normalize_pack_permissions(data.get("permissions")),
            extensions=_optional_pack_extensions(data.get("extensions"), path="pack.extensions"),
            **taxonomy,
        )

    def _validate_discovered_components(self, content: dict[str, Any]) -> None:
        # Lazy-import through the public shim so that tests mocking
        # astrid.packs.validate.iter_*_roots can intercept these calls.
        from astrid.packs.validate import (
            iter_element_roots,
            iter_executor_roots,
            iter_orchestrator_roots,
        )

        pack = self._pack_definition_for_discovery(content)
        for comp_dir in iter_executor_roots(pack):
            manifest_path = self._find_component_manifest(comp_dir, "executor")
            if manifest_path is not None:
                self._validate_component_manifest_file(
                    pack, comp_dir, manifest_path, "executor"
                )
        for comp_dir in iter_orchestrator_roots(pack):
            manifest_path = self._find_component_manifest(comp_dir, "orchestrator")
            if manifest_path is not None:
                self._validate_component_manifest_file(
                    pack, comp_dir, manifest_path, "orchestrator"
                )
        for kind, elem_dir in iter_element_roots(pack):
            manifest_path = self._find_component_manifest(elem_dir, "element")
            if manifest_path is not None:
                self._validate_element_manifest_file(pack, kind, manifest_path)

    def _find_component_manifest(self, component_dir: Path, manifest_kind: str) -> Path | None:
        names = {
            "executor": EXECUTOR_MANIFEST_NAMES,
            "orchestrator": ORCHESTRATOR_MANIFEST_NAMES,
            "element": _ELEMENT_MANIFEST_NAMES,
        }[manifest_kind]
        for name in names:
            candidate = component_dir / name
            if candidate.is_file():
                return candidate
        return None

    def _validate_component_manifest_file(
        self,
        pack: PackDefinition,
        component_dir: Path,
        manifest_path: Path,
        manifest_kind: str,
    ) -> None:
        data = self._load_yaml(manifest_path)
        if data is None:
            return

        rel = self._rel(manifest_path)
        version = self._validate_manifest(data, manifest_kind, rel)
        if version is None:
            return
        component_id = data.get("id")
        if isinstance(component_id, str):
            self._register_capability_id(component_id, rel)
            if manifest_kind in self._pack_capability_locations:
                self._pack_capability_locations[manifest_kind][component_id] = rel
            self._register_aliases(data, rel)
            try:
                validate_content_id_in_pack(
                    component_id,
                    pack,
                    content_type=manifest_kind,
                )
            except ValueError as exc:
                self.errors.append(f"{rel}: {exc}")

        self._validate_runtime_entrypoints(component_dir, data, manifest_kind, rel)
        self._validate_runtime_definition(data, manifest_kind, rel)

        docs = data.get("docs", {})
        stage = docs.get("stage", "STAGE.md") if isinstance(docs, dict) else "STAGE.md"
        stage_path = component_dir / stage
        if not stage_path.is_file():
            self.warnings.append(f"{self._rel(stage_path)}: STAGE.md not found")

    def _validate_runtime_definition(
        self, data: dict[str, Any], manifest_kind: str, rel: str
    ) -> None:
        """Run the raising runtime validators after the JSON-Schema pass.

        The JSON Schema is permissive about shapes the runtime parser rejects
        (e.g. a manifest declaring its runtime module twice with conflicting
        values). The runtime validators ``validate_executor_definition`` /
        ``validate_orchestrator_definition`` RAISE on those, so translate their
        errors into the collected error structure rather than letting them
        escape ``packs validate``.
        """
        if manifest_kind == "executor":
            from astrid.core.executor.schema import (
                ExecutorValidationError,
                validate_executor_definition,
            )

            try:
                if isinstance(data, dict) and isinstance(data.get("executors"), list):
                    for item in data["executors"]:
                        validate_executor_definition(item)
                else:
                    validate_executor_definition(data)
            except ExecutorValidationError as exc:
                self.errors.append(f"{rel}: {exc}")
        elif manifest_kind == "orchestrator":
            from astrid.core.orchestrator.schema import (
                OrchestratorValidationError,
                validate_orchestrator_definition,
            )

            try:
                validate_orchestrator_definition(data)
            except OrchestratorValidationError as exc:
                self.errors.append(f"{rel}: {exc}")

    def _validate_element_manifest_file(
        self,
        pack: PackDefinition,
        kind: str,
        manifest_path: Path,
    ) -> None:
        data = self._load_yaml(manifest_path)
        if data is None:
            return

        rel = self._rel(manifest_path)
        version = self._validate_manifest(data, "element", rel)
        if version is None:
            return
        element_id = data.get("id")
        if isinstance(element_id, str):
            self._register_capability_id(f"{kind}/{element_id}", rel)
            self._register_aliases(data, rel)
        try:
            validate_element_pack_id(
                data.get("pack_id"),
                pack,
                element_root=manifest_path.parent,
            )
        except ValueError as exc:
            self.errors.append(f"{rel}: {exc}")

    def _validate_runtime_entrypoints(
        self,
        component_dir: Path,
        data: dict[str, Any],
        manifest_kind: str,
        rel: str,
    ) -> None:
        if manifest_kind == "executor":
            self._check_runtime_entrypoint(component_dir, data.get("entrypoint"), "entrypoint")
            runtime = data.get("runtime", {})
            if isinstance(runtime, dict):
                self._check_runtime_entrypoint(component_dir, runtime.get("entrypoint"), "runtime entrypoint")
                self._check_command_entrypoint(component_dir, runtime.get("command"))
            self._check_command_entrypoint(component_dir, data.get("command"))
            self._check_metadata_runtime_file(component_dir, data)
            return

        if manifest_kind != "orchestrator":
            return

        runtime = data.get("runtime", {})
        if not isinstance(runtime, dict):
            return
        kind = runtime.get("kind")
        if kind == "python":
            self._check_python_module(component_dir, runtime.get("module"), rel, "runtime.module")
        elif kind == "command":
            self._check_command_entrypoint(component_dir, runtime.get("command"))

    def _check_runtime_entrypoint(self, component_dir: Path, value: Any, label: str) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        if "{" in value or "}" in value:
            return
        entrypoint_path = component_dir / value
        if not entrypoint_path.is_file():
            self.errors.append(f"{self._rel(entrypoint_path)}: {label} file not found")

    def _check_metadata_runtime_file(self, component_dir: Path, data: dict[str, Any]) -> None:
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            return
        self._check_runtime_entrypoint(component_dir, metadata.get("runtime_file"), "metadata.runtime_file")
        self._check_python_module(
            component_dir,
            metadata.get("runtime_module"),
            self._rel(component_dir),
            "metadata.runtime_module",
        )

    def _check_command_entrypoint(self, component_dir: Path, command: Any) -> None:
        if isinstance(command, dict):
            argv = command.get("argv")
        else:
            argv = command
        if not isinstance(argv, list):
            return
        parts = [part for part in argv if isinstance(part, str)]
        for index, part in enumerate(parts):
            if part == "-m" and index + 1 < len(parts):
                self._check_python_module(
                    component_dir,
                    parts[index + 1],
                    self._rel(component_dir),
                    "command.argv module",
                )
                return
        for part in parts:
            if not self._looks_like_local_entrypoint(part):
                continue
            self._check_runtime_entrypoint(component_dir, part, "command.argv entrypoint")
            return

    def _looks_like_local_entrypoint(self, value: str) -> bool:
        if not value or value.startswith("-") or "{" in value or "}" in value:
            return False
        return value.endswith(".py") or "/" in value or "\\" in value

    def _check_python_module(
        self,
        component_dir: Path,
        module: Any,
        rel: str,
        label: str,
    ) -> None:
        if not isinstance(module, str) or not module.strip():
            return
        if "{" in module or "}" in module:
            return
        module_path = self._module_path(component_dir, module)
        if module_path is None:
            return
        if not module_path.is_file():
            self.errors.append(
                f"{rel}: {label} file not found for module {module!r}: {self._rel(module_path)}"
            )

    def _module_path(self, component_dir: Path, module: str) -> Path | None:
        parts = module.split(".")
        pack_id = self._pack_data.get("id") if self._pack_data is not None else None
        if (
            len(parts) >= 6
            and parts[0:2] == ["astrid", "packs"]
            and parts[2] == pack_id
            and parts[3] in {"executors", "orchestrators"}
            and parts[4] == component_dir.name
        ):
            return component_dir / Path(*parts[5:]).with_suffix(".py")
        if (
            len(parts) >= 4
            and parts[0] == pack_id
            and parts[1] in {"executors", "orchestrators"}
            and parts[2] == component_dir.name
        ):
            return self.pack_root / Path(*parts[1:]).with_suffix(".py")
        if (
            len(parts) >= 5
            and parts[0:2] == ["astrid", "packs"]
            and parts[2] == pack_id
            and parts[3] == component_dir.name
        ):
            return component_dir / Path(*parts[4:]).with_suffix(".py")
        if len(parts) >= 5 and parts[0:2] == ["astrid", "packs"]:
            pack_root = _REPO_ROOT / "astrid" / "packs" / parts[2]
            component_name = parts[3]
            tail = Path(*parts[4:]).with_suffix(".py")
            for kind_root in ("executors", "orchestrators"):
                candidate = pack_root / kind_root / component_name / tail
                if candidate.is_file():
                    return candidate
        if module.startswith("astrid."):
            return _REPO_ROOT / Path(*module.split(".")).with_suffix(".py")
        if "." not in module:
            return component_dir / f"{module}.py"
        return component_dir / Path(*module.split(".")).with_suffix(".py")

    def _register_capability_id(self, capability_id: str, relpath: str) -> None:
        existing = self._capability_locations.get(capability_id)
        if existing is not None:
            self.errors.append(
                f"{relpath}: duplicate capability id {capability_id!r}; already declared in {existing}"
            )
            return
        self._capability_locations[capability_id] = relpath

    def _register_aliases(self, data: dict[str, Any], relpath: str) -> None:
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            return
        aliases = metadata.get("aliases", [])
        if not isinstance(aliases, list):
            self.errors.append(f"{relpath}: metadata.aliases must be an array")
            return
        for index, alias in enumerate(aliases):
            if isinstance(alias, str):
                self._alias_targets.append((relpath, f"metadata.aliases[{index}]", alias))
            elif isinstance(alias, dict):
                target = alias.get("canonical_id") or alias.get("target") or alias.get("id")
                if isinstance(target, str):
                    self._alias_targets.append((relpath, f"metadata.aliases[{index}]", target))
                else:
                    self.errors.append(f"{relpath}: metadata.aliases[{index}] must declare canonical_id")
            else:
                self.errors.append(f"{relpath}: metadata.aliases[{index}] must be a string or object")

    def _validate_pack_aliases(self) -> None:
        if self._pack_data is None:
            return
        aliases = self._pack_data.get("aliases")
        if aliases is None:
            return
        try:
            normalized_aliases = _optional_pack_aliases(aliases, path="pack.aliases")
        except ValueError as exc:
            self.errors.append(f"pack.yaml: {exc}")
            return

        for index, alias in enumerate(normalized_aliases):
            kind = str(alias["kind"])
            alias_id = str(alias["alias"])
            canonical_id = str(alias["canonical_id"])
            resolver = self._pack_alias_resolvers[kind]
            if resolver.is_alias(alias_id):
                self.errors.append(
                    f"pack.yaml: pack.aliases[{index}] duplicates existing {kind} alias {alias_id!r}"
                )
                continue
            try:
                resolver.register_alias(
                    alias_id,
                    canonical_id,
                    deprecated=bool(alias.get("deprecated", False)),
                    deprecation_message=str(alias.get("deprecation_message", "")),
                )
            except AliasResolutionError as exc:
                self.errors.append(f"pack.yaml: pack.aliases[{index}] {exc}")
                continue
            self._pack_alias_targets.append(
                ("pack.yaml", f"pack.aliases[{index}]", kind, canonical_id)
            )

        for relpath, alias_path, kind, target in self._pack_alias_targets:
            pack_id = target.split(".", 1)[0]
            if pack_id != self._pack_id():
                continue
            if target not in self._pack_capability_locations[kind]:
                self.errors.append(
                    f"{relpath}: {alias_path} points to unknown {kind} id {target!r}"
                )

    def _validate_alias_targets(self) -> None:
        for relpath, alias_path, target in self._alias_targets:
            if target not in self._capability_locations:
                self.errors.append(
                    f"{relpath}: {alias_path} points to unknown capability id {target!r}"
                )

    def _validate_layout_contract(self) -> None:
        if self._pack_data is None:
            return
        self._layout_exceptions = self._parse_layout_exceptions(self._pack_data)

    def _parse_layout_exceptions(
        self,
        pack_data: dict[str, Any],
    ) -> list[PackLayoutException]:
        metadata = pack_data.get("metadata")
        if metadata is None:
            return []
        if not isinstance(metadata, dict):
            self._record_layout_issue(
                "pack.yaml",
                "metadata must be an object before layout exceptions can be parsed",
            )
            return []

        layout = metadata.get("layout")
        if layout is None:
            return []
        if not isinstance(layout, dict):
            self._record_layout_issue(
                "pack.yaml",
                "metadata.layout must be an object",
            )
            return []

        declarations = layout.get("exceptions")
        if declarations is None:
            return []
        if not isinstance(declarations, list):
            self._record_layout_issue(
                "pack.yaml",
                f"{_LAYOUT_EXCEPTION_DECLARATION_PATH} must be an array",
            )
            return []

        parsed: list[PackLayoutException] = []
        seen_paths: dict[str, int] = {}
        for index, raw in enumerate(declarations):
            item_path = f"{_LAYOUT_EXCEPTION_DECLARATION_PATH}[{index}]"
            parsed_decl = self._parse_layout_exception_declaration(raw, item_path)
            if parsed_decl is None:
                continue
            first_index = seen_paths.get(parsed_decl.path)
            if first_index is not None:
                self._record_layout_issue(
                    "pack.yaml",
                    f"{item_path}.path duplicates {_LAYOUT_EXCEPTION_DECLARATION_PATH}[{first_index}].path ({parsed_decl.path!r})",
                )
                continue
            seen_paths[parsed_decl.path] = index
            if self._is_canonical_pack_path(parsed_decl.path):
                self._record_layout_issue(
                    parsed_decl.path,
                    "declared as a layout exception even though the path already matches the canonical pack layout",
                )
                continue
            parsed.append(parsed_decl)
        return parsed

    def _parse_layout_exception_declaration(
        self,
        raw: Any,
        item_path: str,
    ) -> PackLayoutException | None:
        if not isinstance(raw, dict):
            self._record_layout_issue("pack.yaml", f"{item_path} must be an object")
            return None

        allowed_fields = {"path", "class", "reason", "defer_to"}
        extra_fields = sorted(set(raw) - allowed_fields)
        if extra_fields:
            fields = ", ".join(extra_fields)
            self._record_layout_issue(
                "pack.yaml",
                f"{item_path} has unknown field(s): {fields}",
            )
            return None

        path_value = raw.get("path")
        normalized_path = self._normalize_layout_exception_path(path_value, item_path)
        if normalized_path is None:
            return None

        class_value = raw.get("class")
        try:
            exception_class = LayoutExceptionClass(str(class_value))
        except Exception:
            valid = ", ".join(member.value for member in LayoutExceptionClass)
            self._record_layout_issue(
                normalized_path,
                f"{item_path}.class must be one of [{valid}]",
            )
            return None

        reason_value = raw.get("reason")
        if not isinstance(reason_value, str) or not reason_value.strip():
            self._record_layout_issue(
                normalized_path,
                f"{item_path}.reason must be a non-empty string",
            )
            return None

        lifecycle = self._parse_layout_lifecycle(
            raw.get("defer_to"),
            item_path=item_path,
            path=normalized_path,
            exception_class=exception_class,
        )
        if lifecycle is None:
            return None

        return PackLayoutException(
            path=normalized_path,
            exception_class=exception_class,
            reason=reason_value.strip(),
            defer_to=lifecycle,
        )

    def _parse_layout_lifecycle(
        self,
        raw_lifecycle: Any,
        *,
        item_path: str,
        path: str,
        exception_class: LayoutExceptionClass,
    ) -> LayoutExceptionLifecycle | None:
        if raw_lifecycle is None:
            if exception_class in _TEMPORARY_LAYOUT_EXCEPTION_CLASSES:
                self._record_layout_issue(
                    path,
                    f"{item_path}.defer_to is required for temporary exception class {exception_class.value!r}",
                )
                return None
            return LayoutExceptionLifecycle.PERMANENT

        try:
            lifecycle = LayoutExceptionLifecycle(str(raw_lifecycle))
        except Exception:
            valid = ", ".join(member.value for member in LayoutExceptionLifecycle)
            self._record_layout_issue(
                path,
                f"{item_path}.defer_to must be one of [{valid}]",
            )
            return None

        if exception_class in _TEMPORARY_LAYOUT_EXCEPTION_CLASSES:
            if lifecycle == LayoutExceptionLifecycle.PERMANENT:
                self._record_layout_issue(
                    path,
                    f"{item_path}.defer_to must be M1 or M2 for temporary exception class {exception_class.value!r}",
                )
                return None
            return lifecycle

        if lifecycle != LayoutExceptionLifecycle.PERMANENT:
            self._record_layout_issue(
                path,
                f"{item_path}.defer_to must be permanent for non-temporary exception class {exception_class.value!r}",
            )
            return None
        return lifecycle

    def _normalize_layout_exception_path(
        self,
        raw_path: Any,
        item_path: str,
    ) -> str | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            self._record_layout_issue(
                "pack.yaml",
                f"{item_path}.path must be a non-empty relative path",
            )
            return None
        try:
            normalized = PurePosixPath(raw_path.strip())
        except Exception:
            self._record_layout_issue(
                "pack.yaml",
                f"{item_path}.path must be a valid relative path",
            )
            return None
        if normalized.is_absolute() or ".." in normalized.parts or "." in normalized.parts:
            self._record_layout_issue(
                "pack.yaml",
                f"{item_path}.path must stay within the pack root",
            )
            return None
        if str(normalized) in {"", "."}:
            self._record_layout_issue(
                "pack.yaml",
                f"{item_path}.path must be a non-empty relative path",
            )
            return None
        return str(normalized)

    def _is_canonical_pack_path(self, relpath: str) -> bool:
        normalized = PurePosixPath(relpath)
        if normalized.name in {"pack.yaml", "pack.yml", "pack.json"} and len(normalized.parts) == 1:
            return True
        parts = normalized.parts
        if len(parts) == 2 and parts[0] == "skill" and parts[1] == "SKILL.md":
            return True
        if not parts:
            return False
        if parts[0] in {"fixtures", "golden", "build", "docs", "examples", "schemas"}:
            return True
        if len(parts) >= 2 and parts[0] in {"executors", "orchestrators"}:
            if len(parts) == 3 and parts[2] in {
                f"{parts[0][:-1]}.yaml",
                f"{parts[0][:-1]}.yml",
                f"{parts[0][:-1]}.json",
                "run.py",
            }:
                return True
            if len(parts) == 3 and parts[2] in _CANONICAL_COMPONENT_SUPPORT_FILES:
                return True
            if len(parts) == 4 and parts[2] in _CANONICAL_COMPONENT_SUPPORT_DIRS and parts[3] == "SKILL.md":
                return True
            return False
        if len(parts) >= 3 and parts[0] == "elements":
            if len(parts) == 4 and parts[3] in {"element.yaml", "element.yml", "element.json"}:
                return True
            return False
        if parts[0] in _CANONICAL_PACK_ROOT_DIRS:
            return True
        return False

    def _record_layout_issue(self, path: str, message: str) -> None:
        self._layout_issues.append(LayoutValidationIssue(path=path, message=message))

    def _flush_layout_issues(self) -> None:
        if not self._layout_issues:
            return
        aggregate = PackLayoutContractError(self._layout_issues)
        self.errors.extend(aggregate.lines())
        self._layout_issues = []

    def _pack_id(self) -> str:
        if self._pack_data is None:
            return self.pack_root.name
        value = self._pack_data.get("id")
        if isinstance(value, str) and value.strip():
            return value
        return self.pack_root.name

    def _rel(self, path: Path) -> str:
        """Return a path relative to the pack root for error messages."""
        try:
            return str(path.relative_to(self.pack_root))
        except ValueError:
            return str(path)


def validate_pack(pack_root: str | Path) -> tuple[list[str], list[str]]:
    """Validate an external pack directory.

    Args:
        pack_root: Path to the pack root directory.

    Returns:
        A tuple of (errors, warnings). Empty errors list means valid.
    """
    validator = PackValidator(Path(pack_root))
    errors = validator.validate()
    return errors, validator.warnings


def is_first_party_packs_root_candidate(path: str | Path) -> bool:
    """Return True when *path* looks like Astrid's multi-pack source root."""
    root = Path(path).resolve()
    if not root.is_dir() or pack_manifest_path(root) is not None:
        return False
    recognized_dirs = {
        child.name
        for child in root.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in _IGNORED_PACKS_ROOT_DIRS
        and child.name in set(_FIRST_PARTY_PACK_IDS) | _FIRST_PARTY_INTERNAL_DIRS
    }
    if root == _FIRST_PARTY_PACKS_ROOT:
        return True
    return "_core" in recognized_dirs and len(recognized_dirs) >= len(_FIRST_PARTY_PACK_IDS)


def validate_first_party_packs_root(packs_root: str | Path) -> tuple[list[str], list[str]]:
    """Validate the canonical first-party ``astrid/packs`` source tree."""
    root = Path(packs_root).resolve()
    internal_schema_errors = _validate_first_party_packs_root_inventory(root)
    layout_errors: list[str] = []
    warnings: list[str] = []

    for pack_id in _FIRST_PARTY_PACK_IDS:
        pack_dir = root / pack_id
        if not pack_dir.is_dir():
            continue
        pack_errors, pack_warnings = validate_pack(pack_dir)
        layout_errors.extend(f"{pack_id}: {error}" for error in pack_errors)
        warnings.extend(f"{pack_id}: {warning}" for warning in pack_warnings)

    errors = _aggregate_first_party_packs_root_errors(
        internal_schema_errors=internal_schema_errors,
        layout_errors=layout_errors,
    )
    return errors, warnings


def _validate_first_party_packs_root_inventory(root: Path) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"{root}: first-party packs root does not exist"]

    child_dirs = {
        child.name: child
        for child in root.iterdir()
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name not in _IGNORED_PACKS_ROOT_DIRS
    }
    expected_pack_ids = set(_FIRST_PARTY_PACK_IDS)
    allowed_names = expected_pack_ids | _FIRST_PARTY_INTERNAL_DIRS

    for pack_id in sorted(expected_pack_ids - set(child_dirs)):
        errors.append(f"missing first-party pack directory: {pack_id}")

    for name in sorted(set(child_dirs) - allowed_names):
        if name == "schemas":
            errors.append(
                "unexpected top-level directory: schemas (relocated to "
                "astrid/core/pack/schemas/)"
            )
            continue
        errors.append(f"unexpected top-level directory: {name}")

    for pack_id in sorted(expected_pack_ids & set(child_dirs)):
        pack_dir = child_dirs[pack_id]
        if pack_manifest_path(pack_dir) is None:
            errors.append(
                f"{pack_id}: pack manifest not found "
                f"(pack.yaml, pack.yml, or pack.json)"
            )

    core_dir = child_dirs.get("_core")
    if core_dir is None:
        errors.append("missing internal directory: _core")
        return errors

    for manifest_name in ("pack.yaml", "pack.yml", "pack.json"):
        if (core_dir / manifest_name).is_file():
            errors.append(
                f"_core: skill-only shell must not contain {manifest_name}"
            )
    if not (core_dir / "skill" / "SKILL.md").is_file():
        errors.append("_core: skill-only shell must provide skill/SKILL.md")
    for forbidden in sorted(
        child.name
        for child in core_dir.iterdir()
        if child.is_dir() and child.name in {"executors", "orchestrators", "elements", "build"}
    ):
        errors.append(
            f"_core: skill-only shell must not contain top-level {forbidden}/"
        )

    return errors


def _aggregate_first_party_packs_root_errors(
    *,
    internal_schema_errors: list[str],
    layout_errors: list[str],
) -> list[str]:
    body: list[str] = []
    body.extend(f"[internal-schema] {error}" for error in internal_schema_errors)
    body.extend(f"[layout] {error}" for error in layout_errors)
    if not body:
        return []
    count = len(body)
    noun = "issue" if count == 1 else "issues"
    return [f"first-party pack validation failed ({count} {noun})", *body]


def json_loads(text: str) -> Any:
    """Load JSON, wrapping decode errors for consistent messaging."""
    return _json.loads(text)


def _check_semantic_secrets(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    secrets_raw = data.get("secrets")
    if not isinstance(secrets_raw, list):
        return warnings
    for idx, item in enumerate(secrets_raw):
        if not isinstance(item, dict):
            warnings.append(f"secrets[{idx}]: not a mapping, skipping")
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            warnings.append(f"secrets[{idx}]: empty or missing secret name")
            continue
        if not item.get("required", False):
            description = item.get("description")
            if not isinstance(description, str) or not description.strip():
                warnings.append(f"secret '{name.strip()}': optional secret has no description")
    return warnings


def _check_semantic_deps(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    deps = data.get("dependencies")
    if not isinstance(deps, dict):
        return warnings
    python_deps = deps.get("python")
    if isinstance(python_deps, list):
        for idx, dep in enumerate(python_deps):
            if not isinstance(dep, str) or not dep.strip():
                warnings.append(f"dependencies.python[{idx}]: empty entry")
            elif not _re.match(r"^[A-Za-z0-9_.-]+(\s*[><=!~]+\s*[A-Za-z0-9_.*-]+)*(\s*;\s*.*)?$", dep.strip()):
                warnings.append(f"dependencies.python[{idx}]: '{dep}' does not look like a pip requirement")
    npm_deps = deps.get("npm")
    if isinstance(npm_deps, list):
        for idx, dep in enumerate(npm_deps):
            if not isinstance(dep, str) or not dep.strip():
                warnings.append(f"dependencies.npm[{idx}]: empty entry")
            elif not _re.match(r"^@?[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?(@[A-Za-z0-9_.-]+)?$", dep.strip()):
                warnings.append(f"dependencies.npm[{idx}]: '{dep}' does not look like an npm package specifier")
    system_deps = deps.get("system")
    if isinstance(system_deps, list):
        for idx, dep in enumerate(system_deps):
            if not isinstance(dep, str) or not dep.strip():
                warnings.append(f"dependencies.system[{idx}]: empty entry")
            elif not _re.match(r"^[A-Za-z0-9_.-]+$", dep.strip()):
                warnings.append(f"dependencies.system[{idx}]: '{dep}' does not look like a system command name")
    return warnings


def extract_trust_summary(pack_root: str | Path) -> dict[str, Any]:
    """Extract a lightweight trust summary for pack install dry-runs."""
    root = Path(pack_root).resolve()
    manifest_path = pack_manifest_path(root)
    if manifest_path is None:
        raise ValidationError(f"No pack manifest found in {root}")

    try:
        data = load_manifest_mapping(manifest_path, manifest_kind="pack")
    except ManifestParseError as exc:
        raise ValidationError(f"Failed to parse {manifest_path}: {exc}") from exc

    pack_id = data.get("id", root.name)
    name = data.get("name", pack_id)
    version = data.get("version", "0.0.0")
    schema_version = data.get("schema_version", "unknown")

    content = data.get("content", {}) if isinstance(data.get("content"), dict) else {}
    component_counts: dict[str, int] = {}
    for key in ("executors", "orchestrators", "elements"):
        comp_root_rel = content.get(key)
        if isinstance(comp_root_rel, str) and comp_root_rel.strip():
            comp_dir = root / comp_root_rel
            component_counts[key] = sum(
                1 for child in comp_dir.iterdir() if child.is_dir() and not child.name.startswith(".")
            ) if comp_dir.is_dir() else 0
        else:
            component_counts[key] = 0

    agent = data.get("agent", {}) if isinstance(data.get("agent"), dict) else {}
    normal_entrypoints = [str(ep) for ep in agent.get("normal_entrypoints", []) if ep] if isinstance(agent.get("normal_entrypoints"), list) else []
    legacy_entrypoints = [str(ep) for ep in agent.get("entrypoints", []) if ep] if isinstance(agent.get("entrypoints"), list) else []
    display_entrypoints = normal_entrypoints or legacy_entrypoints

    secrets_raw = data.get("secrets")
    secrets_list: list[str] = []
    if isinstance(secrets_raw, list):
        for item in secrets_raw:
            if isinstance(item, dict) and item.get("name"):
                label = str(item["name"])
                if item.get("required"):
                    label += " (required)"
                description = item.get("description")
                if description:
                    label += f": {description}"
                secrets_list.append(label)
    elif isinstance(secrets_raw, dict) and isinstance(secrets_raw.get("required"), list):
        secrets_list = [str(secret) for secret in secrets_raw["required"] if secret]

    deps_raw = data.get("dependencies", {}) if isinstance(data.get("dependencies"), dict) else {}
    dependencies: list[str] = []
    dependencies_struct: dict[str, list[str]] = {}
    for ecosystem in ("python", "npm", "system"):
        values = deps_raw.get(ecosystem) if isinstance(deps_raw, dict) else None
        if isinstance(values, list):
            clean = [str(value) for value in values if value]
            dependencies_struct[ecosystem] = clean
            dependencies.extend(f"{ecosystem}:{value}" for value in clean)
    if isinstance(deps_raw.get("packs"), list):
        for value in deps_raw["packs"]:
            if value and str(value) not in dependencies:
                dependencies.append(str(value))

    docs = data.get("docs", {}) if isinstance(data.get("docs"), dict) else {}
    doc_info = {key: str(docs.get(key)) if docs.get(key) else None for key in ("readme", "agents", "stage")}

    warnings: list[str] = []
    for key, comp_root_rel in content.items():
        if isinstance(comp_root_rel, str) and not (root / comp_root_rel).exists():
            warnings.append(f"Declared content root does not exist: {comp_root_rel}")
    warnings.extend(_check_semantic_secrets(data))
    warnings.extend(_check_semantic_deps(data))

    keywords = [str(value) for value in data.get("keywords", []) if value] if isinstance(data.get("keywords"), list) else []
    capabilities = [str(value) for value in data.get("capabilities", []) if value] if isinstance(data.get("capabilities"), list) else []
    required_context = [str(value) for value in agent.get("required_context", []) if value] if isinstance(agent.get("required_context"), list) else []
    permissions = _normalize_pack_permissions(data.get("permissions"))
    normalized_permissions = [permission.to_dict() for permission in permissions]
    permission_ids = [permission.id for permission in permissions]

    return {
        "pack_id": pack_id,
        "name": name,
        "version": version,
        "schema_version": schema_version,
        "source_path": str(root),
        "component_counts": component_counts,
        "entrypoints": display_entrypoints,
        "normal_entrypoints": normal_entrypoints,
        "declared_secrets": secrets_list,
        "dependencies": dependencies,
        "dependencies_struct": dependencies_struct,
        "docs": doc_info,
        "warnings": warnings,
        "do_not_use_for": str(agent.get("do_not_use_for")) if agent.get("do_not_use_for") else None,
        "required_context": required_context,
        "keywords": keywords,
        "capabilities": capabilities,
        "permissions": normalized_permissions,
        "permission_ids": permission_ids,
        "trust": dict(V1_TRUST_BLOCK),
        "astrid_version": data.get("astrid_version"),
    }


__all__ = [
    "CANONICAL_PACK_LAYOUT_RULES",
    "CanonicalLayoutRule",
    "KNOWN_SCHEMA_VERSIONS",
    "KNOWN_VERSIONS_STR",
    "LayoutExceptionClass",
    "LayoutExceptionLifecycle",
    "LayoutValidationIssue",
    "PackLayoutContractError",
    "PackLayoutException",
    "PackValidator",
    "V1_TRUST_BLOCK",
    "ValidationError",
    "extract_trust_summary",
    "is_first_party_packs_root_candidate",
    "json_loads",
    "validate_first_party_packs_root",
    "validate_pack",
    # Re-exported for backward compatibility — used by tests that mock
    # through the astrid.packs.validate shim path.
    "iter_executor_roots",
    "iter_orchestrator_roots",
    "iter_element_roots",
]
