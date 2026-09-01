"""Product-family CLI registry and canonical mount adapters.

Runtime mount ownership comes from the operation's frozen canonical registry.
Help construction uses the static mount grammar and never opens a session or
database.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:
    from astrid.core.schema_packs.registry import FrozenSchemaPackRegistry

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
"""The canonical CLI mount contract used by static help and projection checks."""

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
    """One CLI mount entry projected from canonical registry data."""

    family: str
    token: str
    pack_id: str


    


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


def _static_manifest_mounts() -> tuple[ManifestMount, ...]:
    """Return the frozen mount grammar for session-free help construction."""
    owners = {"timelines": "timeline", "shots": "shots", "references": "references"}
    return tuple(
        ManifestMount(family, " ".join(path), owners[family])
        for family, path in REQUIRED_MANIFEST_MOUNTS.items()
    )

def _projection_mounts(
    registry: "FrozenSchemaPackRegistry",
) -> tuple[ManifestMount, ...]:
    """Adapt the operation-owned registry's CLI projection to mount records."""
    cli_mounts = getattr(registry, "cli_mounts", None)
    if not isinstance(cli_mounts, Mapping):
        raise ProductRegistryError("canonical registry has no CLI mount projection")
    mounts: list[ManifestMount] = []
    for family, value in sorted(cli_mounts.items()):
        if (
            not isinstance(family, str)
            or not isinstance(value, tuple)
            or len(value) != 2
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
        ):
            raise ProductRegistryError(
                f"canonical CLI mount {family!r} must project to "
                "(pack id, mount path)"
            )
        mounts.append(ManifestMount(family, value[1], value[0]))
    return tuple(mounts)


def _build_product_mounts_from_registry(
    registry: "FrozenSchemaPackRegistry",
) -> tuple[ProductMount, ...]:
    """Validate mounts from the exact operation-owned registry."""
    return _validate_mounts(PRODUCT_FAMILIES, _projection_mounts(registry))


def build_product_mounts() -> tuple[ProductMount, ...]:
    """Validate the static product mount grammar for help and parsers.

    Runtime dispatch uses :func:`_build_product_mounts_from_registry` so the
    bound operation's canonical projection remains authoritative.  This
    public no-argument helper preserves the session-free parser/help seam.
    """
    return _validate_mounts(PRODUCT_FAMILIES, _static_manifest_mounts())


def product_top_level_commands() -> frozenset[str]:
    """The exact five-family top-level product census."""
    return PRODUCT_FAMILY_SET


def is_product_family(name: object) -> bool:
    """True when *name* is one of the five product families."""
    return isinstance(name, str) and name in PRODUCT_FAMILY_SET


def is_registered_family(name: object) -> bool:
    """True for a core family or a manifest-declared nested family."""
    if not isinstance(name, str):
        return False
    return name in PRODUCT_FAMILY_SET or name in REQUIRED_MANIFEST_MOUNTS


def family_mount(
    family: str, *, registry: "FrozenSchemaPackRegistry | None" = None
) -> ProductMount:
    """Return the validated mount for one registered family."""
    mounts = (
        build_product_mounts()
        if registry is None
        else _build_product_mounts_from_registry(registry)
    )
    for mount in mounts:
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
    the shared ``AstridClient``. Normal dispatch validates the client's exact
    ``app.registry.cli_mounts`` projection before the parser exposes nested
    routes; help and isolated parser tests use only the static grammar.
    """
    if family not in PRODUCT_FAMILY_SET:
        raise ProductRegistryError(
            f"{family!r} is not a product family; product dispatch accepts "
            f"exactly {sorted(PRODUCT_FAMILY_SET)}"
        )
    # Normal dispatch validates the exact operation projection before a
    # parser can expose a nested mount. Static parser tests and help remain
    # session-free when no application is supplied.
    app = getattr(client, "app", None) if client is not None else None
    operation_registry = getattr(app, "registry", None)
    if operation_registry is None:
        build_product_mounts()
    else:
        _build_product_mounts_from_registry(operation_registry)
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
    parsed = build_parser(client).parse_args(list(args))
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
            from astrid.core.cli.domain_output import print_result
            from astrid.sdk.contracts import DomainResult, ErrorObject

            return print_result(
                DomainResult.failure(
                    ErrorObject(
                        code="validation_error",
                        message="no current project is selected; pass --project or run projects select",
                        details={
                            "field": "project",
                            "reason": "no_current_project",
                            "recovery": "run `astrid projects select <slug-or-id>` or pass --project",
                        },
                    )
                ),
                as_json=bool(getattr(parsed, "json", False)),
            )
        parsed.project = selected
    return int(handler(parsed))
