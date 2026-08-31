"""Artifact type registry — pack-extensible, mirrors ElementKindRegistry shape.

The registry is a flat namespace (no catalog concept). It supports:
- Canonical ids with aliases
- Atomic registration with duplicate detection
- Resolve (returns None for unknown — opaque fallthrough) and normalize (raises)
- Pack-extension integration via ``extensions.artifact_types.types``
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ArtifactTypeDescriptor:
    """Describes one canonical artifact type with optional aliases."""

    id: str
    aliases: tuple[str, ...] = ()
    description: str = ""


class ArtifactTypeRegistryError(ValueError):
    """Raised when artifact type registry state is inconsistent."""


class ArtifactTypeRegistry:
    """Runtime registry for artifact types.

    Mirrors ``ElementKindRegistry`` but uses a flat namespace (no catalogs).
    """

    def __init__(
        self,
        descriptors: Iterable[ArtifactTypeDescriptor] | None = None,
    ) -> None:
        self._descriptors: OrderedDict[str, ArtifactTypeDescriptor] = OrderedDict()
        self._aliases: dict[str, str] = {}
        self.register_many(_builtin_artifact_types())
        self.register_many(descriptors or ())

    # -- registration --------------------------------------------------------

    @staticmethod
    def _require_token(value: str, *, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    def register(self, descriptor: ArtifactTypeDescriptor) -> None:
        self.register_many((descriptor,))

    def register_many(self, descriptors: Iterable[ArtifactTypeDescriptor]) -> None:
        """Atomically register descriptors.

        Builds a trial state and only commits if every descriptor is valid
        (no duplicate ids, no conflicting aliases).
        """
        new_descriptors = OrderedDict(self._descriptors)
        new_aliases = dict(self._aliases)

        for descriptor in descriptors:
            canonical = self._require_token(descriptor.id, field_name="artifact type id")

            if canonical in new_descriptors:
                raise ArtifactTypeRegistryError(
                    f"duplicate artifact type {canonical!r}"
                )

            normalized_aliases: list[str] = []
            for alias in descriptor.aliases:
                alias = self._require_token(alias, field_name="artifact type alias")
                existing = new_aliases.get(alias)
                if existing is not None:
                    raise ArtifactTypeRegistryError(
                        f"duplicate artifact type alias {alias!r}: "
                        f"{existing!r} and {canonical!r}"
                    )
                normalized_aliases.append(alias)

            new_descriptors[canonical] = ArtifactTypeDescriptor(
                id=canonical,
                aliases=tuple(normalized_aliases),
                description=descriptor.description,
            )
            for alias in normalized_aliases:
                new_aliases[alias] = canonical

        self._descriptors = new_descriptors
        self._aliases = new_aliases

    # -- query ---------------------------------------------------------------

    def canonical_ids(self) -> tuple[str, ...]:
        """Return every canonical artifact type id."""
        return tuple(self._descriptors.keys())

    def accepted_names(self) -> tuple[str, ...]:
        """Return canonical ids and all aliases (deduplicated, registration order)."""
        names: list[str] = []
        for canonical, descriptor in self._descriptors.items():
            names.append(canonical)
            for alias in descriptor.aliases:
                if alias not in names:
                    names.append(alias)
        return tuple(names)

    def resolve(self, name: str) -> str | None:
        """Resolve an alias or canonical id to its canonical form.

        Returns ``None`` when *name* is unknown — callers use this for the
        opaque fallthrough contract for open-string callers.
        """
        name = name.strip()
        if name in self._descriptors:
            return name
        return self._aliases.get(name)

    def normalize(
        self,
        name: str,
        *,
        error_cls: type[Exception] = ArtifactTypeRegistryError,
    ) -> str:
        """Resolve to canonical, raising *error_cls* when unknown."""
        canonical = self.resolve(name)
        if canonical is None:
            available = ", ".join(self.canonical_ids())
            raise error_cls(f"artifact type must be one of [{available}]")
        return canonical

    def is_known(self, name: str) -> bool:
        """Return ``True`` if *name* is a canonical id or registered alias."""
        return self.resolve(name) is not None

    def descriptors(self) -> tuple[ArtifactTypeDescriptor, ...]:
        """Return every registered descriptor in registration order."""
        return tuple(self._descriptors.values())


# ---------------------------------------------------------------------------
# Built-in seed
# ---------------------------------------------------------------------------


def _builtin_artifact_types() -> tuple[ArtifactTypeDescriptor, ...]:
    """The ~11 canonical artifact types from MIGRATION-PLAN §2.

    ``clip/visual`` is the canonical id; ``video/clip`` and ``visual`` are
    registered aliases (per SD1).
    """
    return (
        ArtifactTypeDescriptor(
            id="clip/visual",
            aliases=("video/clip", "visual"),
            description="A visual clip (video or image) — the core rendering artifact.",
        ),
        ArtifactTypeDescriptor(id="image", description="A still image."),
        ArtifactTypeDescriptor(id="audio", description="An audio clip or stream."),
        ArtifactTypeDescriptor(id="mask", description="An alpha / segmentation mask."),
        ArtifactTypeDescriptor(id="prompt", description="A text prompt for generation."),
        ArtifactTypeDescriptor(id="transcript", description="A timed transcript or caption track."),
        ArtifactTypeDescriptor(id="timeline", description="An Astrid timeline document."),
        ArtifactTypeDescriptor(id="asset_registry", description="A registry of assets."),
        ArtifactTypeDescriptor(id="lora", description="A LoRA adapter weight file."),
        ArtifactTypeDescriptor(id="pool", description="A pool / collection reference."),
        ArtifactTypeDescriptor(id="arrangement", description="A timeline arrangement / composition."),
    )


ARTIFACT_TYPE_REGISTRY = ArtifactTypeRegistry()
