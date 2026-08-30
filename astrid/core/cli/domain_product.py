"""Product-family CLI registry (m4 plan step 24, task T25).

This module is the ownership authority for the product command census and
manifest mounts. It declares **exactly** the five product families —
``projects``, ``media``, ``tasks``, ``runs``, and the manifest-owned
``timelines`` — and attaches the two manifest-declared nested mounts
(``shots`` beneath ``timelines`` and ``references`` beneath ``media``)
from the explicit in-tree schema-pack manifests (``cli_mounts``).

Rules enforced before any dispatch (sense check SC25):

- **Missing mounts** — a required manifest declaration (timelines, shots,
  references) that the shipped manifests do not declare is rejected.
- **Duplicate mounts** — two declarations for the same family or the same
  mount path are rejected.
- **Unexpected mounts** — a manifest declaring a family outside the frozen
  declarations, or a declared family at a different path, is rejected.
- **Dynamic mounts** — the loader reads only the three fixed in-tree
  manifests (``astrid/packs/{timeline,shots,references}/schema-pack.yaml``);
  there is no discovery, no scanning, and no injection point, so a mount
  from any other source is impossible by construction.

The product census also excludes the operational commands (``serve``,
``doctor``, ``backup``): they are never part of the five-family product
registry, help, or product dispatch.

The dispatch boundary (:func:`run_product_family`) composes one
``AstridClient`` and passes it to the family's in-tree parser builder, so
every product handler is a rule-free SDK adapter (m4 plan step 24).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

__all__ = [
    "FAMILY_PARSER_MODULES",
    "PRODUCT_FAMILIES",
    "PRODUCT_FAMILY_SET",
    "EXCLUDED_FROM_PRODUCT_CENSUS",
    "REQUIRED_MANIFEST_MOUNTS",
    "ProductMount",
    "ProductRegistryError",
    "build_product_mounts",
    "family_mount",
    "is_product_family",
    "is_registered_family",
    "product_top_level_commands",
    "read_manifest_cli_mounts",
    "run_product_family",
]

PRODUCT_FAMILIES: tuple[str, ...] = (
    "projects",
    "media",
    "tasks",
    "runs",
    "timelines",
)
"""Exactly the five product families (frozen m4 contract, plan step 24)."""

PRODUCT_FAMILY_SET: frozenset[str] = frozenset(PRODUCT_FAMILIES)

EXCLUDED_FROM_PRODUCT_CENSUS: frozenset[str] = frozenset(
    {"serve", "doctor", "backup"}
)
"""Operational commands excluded from the product census.

``serve``, ``doctor``, and ``backup`` are operational families (tooling
over the single SQLite file and managed-media root). None of them is a
product family, appears in the product census, or dispatches through the
product boundary.
"""

REQUIRED_MANIFEST_MOUNTS: dict[str, tuple[str, ...]] = {
    # The timeline pack owns the top-level ``timelines`` family mount.
    "timelines": ("timelines",),
    # The shots pack declares its nested mount beneath timelines.
    "shots": ("timelines", "shots"),
    # The references pack declares its nested mount beneath media.
    "references": ("media", "references"),
}
"""The frozen manifest-declared mounts (family -> mount path).

Every entry must be declared by the corresponding shipped schema-pack
manifest's ``cli_mounts``; a missing, duplicate, or unexpected
declaration is a registry error.
"""

# The manifest-declared families that are not core families: exactly the
# two nested mounts (sense check SC25: only the two declared nested mounts).
NESTED_FAMILIES: frozenset[str] = frozenset(
    family
    for family in REQUIRED_MANIFEST_MOUNTS
    if family not in PRODUCT_FAMILY_SET
)

_PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"
"""The fixed in-tree packs directory (never discovered dynamically)."""

_STANDARD_PACK_DIRS: tuple[str, ...] = ("timeline", "shots", "references")
"""Exactly the three in-tree schema packs consulted for ``cli_mounts``."""


class ProductRegistryError(ValueError):
    """Raised when the product mount registry is invalid.

    Covers missing, duplicate, unexpected, and dynamically sourced mounts:
    the registry fails closed before any dispatch can occur.
    """


@dataclass(frozen=True, slots=True)
class ProductMount:
    """One validated product mount declaration.

    ``mount_path`` is the CLI path segments: ``("projects",)`` for a core
    family, ``("timelines", "shots")`` for the nested shots family.
    ``declared_by`` is ``"core"`` for the four kernel families and
    ``"manifest:<pack-id>"`` for manifest-owned mounts (timelines, shots,
    references).
    """

    family: str
    mount_path: tuple[str, ...]
    declared_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.family, str) or not self.family:
            raise ProductRegistryError("family must be a non-empty string")
        if not isinstance(self.mount_path, tuple) or not self.mount_path:
            raise ProductRegistryError(
                f"mount path for {self.family!r} must be non-empty"
            )

    @property
    def mount_token(self) -> str:
        """The space-joined CLI mount token (e.g. ``timelines shots``)."""
        return " ".join(self.mount_path)


@dataclass(frozen=True, slots=True)
class ManifestMount:
    """One ``cli_mounts`` entry read from an in-tree schema-pack manifest."""

    family: str
    token: str
    pack_id: str


def read_manifest_cli_mounts() -> tuple[ManifestMount, ...]:
    """Read ``cli_mounts`` from the three fixed in-tree pack manifests.

    Only ``astrid/packs/{timeline,shots,references}/schema-pack.yaml`` is
    consulted — the same explicit paths :func:`register_standard_schema_packs`
    uses. There is no scanning, no loader, and no injection point: mounts
    sourced anywhere else are impossible by construction (reject dynamic
    mounts).
    """
    from astrid.core.schema_packs.manifest import load_schema_pack_manifest

    mounts: list[ManifestMount] = []
    for pack_id in _STANDARD_PACK_DIRS:
        manifest = load_schema_pack_manifest(
            _PACKS_ROOT / pack_id / "schema-pack.yaml"
        )
        for family, token in manifest.cli_mounts.items():
            mounts.append(
                ManifestMount(family=str(family), token=str(token), pack_id=pack_id)
            )
    return tuple(mounts)


def _validate_mounts(
    core_families: Sequence[str],
    manifest_mounts: Sequence[ManifestMount],
) -> tuple[ProductMount, ...]:
    """Validate the frozen product census and return the mount registry.

    Raises :class:`ProductRegistryError` for a missing required
    declaration, a duplicate family or mount path, or an unexpected
    family/path (including any declaration outside the frozen
    ``REQUIRED_MANIFEST_MOUNTS`` contract).
    """
    core_set = frozenset(core_families)
    mounts: list[ProductMount] = []
    seen_paths: dict[tuple[str, ...], str] = {}

    for family in core_families:
        path = (family,)
        mounts.append(ProductMount(family, path, "core"))
        seen_paths[path] = family

    declared_families: set[str] = set()
    for declared in manifest_mounts:
        family = declared.family
        if family in declared_families:
            raise ProductRegistryError(
                f"duplicate mount declaration for family {family!r}: "
                f"both {declared.pack_id!r} and a prior manifest declare it"
            )
        declared_families.add(family)

        token = declared.token
        if not isinstance(token, str) or not token.strip():
            raise ProductRegistryError(
                f"missing mount for family {family!r}: manifest "
                f"{declared.pack_id!r} declares an empty cli_mounts entry"
            )
        declared_path = tuple(token.split())

        expected = REQUIRED_MANIFEST_MOUNTS.get(family)
        if expected is None:
            raise ProductRegistryError(
                f"unexpected mount for family {family!r}: manifest "
                f"{declared.pack_id!r} declares {token!r} but the family is "
                "not part of the frozen product registry"
            )
        if declared_path != expected:
            raise ProductRegistryError(
                f"unexpected mount for family {family!r}: manifest "
                f"{declared.pack_id!r} declares {token!r}, expected "
                f"{' '.join(expected)}"
            )

        if family in core_set:
            # Manifest-owned confirmation of a core top-level mount (the
            # timelines family). The path is identical, so there is no
            # duplicate; ownership transfers to the manifest.
            mounts = [
                ProductMount(m.family, m.mount_path, f"manifest:{declared.pack_id}")
                if m.family == family
                else m
                for m in mounts
            ]
            continue

        if declared_path in seen_paths:
            raise ProductRegistryError(
                f"duplicate mount {' '.join(declared_path)} declared by family "
                f"{family!r} and {seen_paths[declared_path]!r}"
            )
        mounts.append(
            ProductMount(family, declared_path, f"manifest:{declared.pack_id}")
        )
        seen_paths[declared_path] = family

    missing = set(REQUIRED_MANIFEST_MOUNTS) - declared_families
    if missing:
        raise ProductRegistryError(
            f"missing mount for family {sorted(missing)}: no shipped "
            "manifest declares the required cli_mounts entry"
        )
    return tuple(mounts)


def build_product_mounts() -> tuple[ProductMount, ...]:
    """Validate and return the complete product mount registry.

    Exactly the five core families plus the two manifest-declared nested
    mounts (shots, references) — seven mounts total (sense check SC25).
    """
    return _validate_mounts(PRODUCT_FAMILIES, read_manifest_cli_mounts())


def product_top_level_commands() -> frozenset[str]:
    """The exact five-family top-level product census."""
    return PRODUCT_FAMILY_SET


def is_product_family(name: object) -> bool:
    """True when *name* is one of the five product families."""
    return isinstance(name, str) and name in PRODUCT_FAMILY_SET


def is_registered_family(name: object) -> bool:
    """True for a core family or a manifest-declared nested family.

    Nested families (shots, references) are not top-level product
    commands but are registered parsers beneath their parents.
    """
    if not isinstance(name, str):
        return False
    return name in PRODUCT_FAMILY_SET or name in REQUIRED_MANIFEST_MOUNTS


def family_mount(family: str) -> ProductMount:
    """Return the validated mount for one registered family.

    Raises :class:`ProductRegistryError` for an unregistered family.
    """
    for mount in build_product_mounts():
        if mount.family == family:
            return mount
    raise ProductRegistryError(f"{family!r} is not a registered product family")


# The explicit in-tree parser builders per family (m4 plan step 24: map
# declared mount tokens to explicit in-tree parser builders). The modules
# are created by the family cutover tasks (steps 25/27-31); the mapping is
# the static contract, and the import stays lazy until dispatch.
FAMILY_PARSER_MODULES: dict[str, str] = {
    "projects": "astrid.core.cli.domain_projects",
    "timelines": "astrid.packs.timeline.cli",
    "shots": "astrid.packs.shots.cli",
    "media": "astrid.core.cli.domain_media",
    "references": "astrid.packs.references.cli",
    "tasks": "astrid.core.cli.domain_tasks",
    "runs": "astrid.core.cli.domain_runs",
}


def run_product_family(
    family: str,
    args: Sequence[str],
    *,
    client: Any,
    _parser_modules: Mapping[str, str] | None = None,
) -> int:
    """Run one product-family command with the composed *client*.

    The family's in-tree parser builder is resolved from the static
    :data:`FAMILY_PARSER_MODULES` mapping (never discovered) and receives
    the shared ``AstridClient``; the configured handler then runs with
    zero domain rules in this module. Only the five core families dispatch
    here — nested families (shots, references) are routed by their parent
    family parsers. ``_parser_modules`` is a test seam that replaces the
    module-name mapping with module objects.
    """
    if family not in PRODUCT_FAMILY_SET:
        raise ProductRegistryError(
            f"{family!r} is not a product family; product dispatch accepts "
            f"exactly {sorted(PRODUCT_FAMILY_SET)}"
        )
    modules = FAMILY_PARSER_MODULES if _parser_modules is None else _parser_modules
    module_name = modules.get(family)
    if not module_name:
        raise ProductRegistryError(
            f"no in-tree parser builder is declared for family {family!r}"
        )
    module = (
        module_name
        if not isinstance(module_name, str)
        else importlib.import_module(module_name)
    )
    build_parser = getattr(module, "build_parser", None)
    if build_parser is None:
        raise ProductRegistryError(
            f"family parser module {module.__name__!r} has no build_parser()"
        )
    parser_kwargs: dict[str, Any] = {}
    if family == "media":
        references_module_name = modules.get("references")
        if not references_module_name:
            raise ProductRegistryError(
                "media requires the manifest-owned references parser"
            )
        references_module = (
            references_module_name
            if not isinstance(references_module_name, str)
            else importlib.import_module(references_module_name)
        )
        reference_commands = getattr(references_module, "COMMANDS", None)
        if reference_commands is None:
            raise ProductRegistryError(
                "references parser module has no COMMANDS declaration"
            )
        parser_kwargs["reference_commands"] = reference_commands
    parser = build_parser(client, **parser_kwargs)
    parsed = parser.parse_args(list(args))
    handler = getattr(parsed, "handler", None)
    if handler is None:
        raise ProductRegistryError(
            f"family {family!r} parser did not configure a handler"
        )
    # Project-scoped product commands may omit ``--project`` when a
    # workspace/user selection exists. Resolve only the preference here; the
    # single SDK service call in the handler still resolves the selected ref
    # against the bound kernel and therefore fails closed if it is stale.
    if hasattr(parsed, "project") and parsed.project is None:
        selected_project = getattr(client, "selected_project_ref", None)
        try:
            selected = selected_project() if callable(selected_project) else None
        except ValueError as exc:
            from astrid.core.cli.domain_output import print_result
            from astrid.sdk.contracts import DomainResult, ErrorObject

            details = {
                "field": "project",
                "reason": "invalid_selection_preference",
                "recovery": "repair or remove the malformed preference, then run `astrid projects select <slug-or-id>`",
            }
            for key in ("scope", "path"):
                value = getattr(exc, key, None)
                if value is not None:
                    details[key] = value
            return print_result(
                DomainResult.failure(
                    ErrorObject(
                        code="validation_error",
                        message="the current project preference is invalid",
                        details=details,
                    )
                ),
                as_json=bool(getattr(parsed, "json", False)),
            )
        if selected is None:
            # Task identity and event reads are globally unique kernel reads;
            # their SDK methods deliberately accept an omitted project and
            # can therefore be used without a workspace selection.  Every
            # other project-scoped command needs an address before dispatch.
            # Make that absence a parser/usage error (exit 2), rather than a
            # domain failure (exit 1), so the CLI contract is consistent with
            # other missing required arguments.
            if not (
                family == "tasks"
                and getattr(parsed, "command", None) in {"show", "events"}
            ):
                parser.error(
                    "the following arguments are required: --project "
                    "(or select a current project)"
                )
        parsed.project = selected
    return int(handler(parsed))
