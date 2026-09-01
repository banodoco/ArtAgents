"""Generic capability-registry kernel shared by executor, orchestrator, and
element registries.

See ``astrid/core/registry/_design.md`` for the full contract and rationale.

.. code-block:: text

   CapabilityRegistry[K, T]
   ├── _entries: dict[K, list[T]]
   ├── _register_impl(key, definition, *, priority_key)
   ├── _resolve_entry(entry) → T          (static)
   ├── _iter_entries(entry) → Iterable[T]  (static)
   ├── _winner_for(key) → T | None
   ├── list() → tuple[T, ...]
   ├── as_mapping() → MappingProxyType[K, T]
   └── conflicts() → tuple[RegistryConflict[K, T], ...]

Subclasses own:

* ``register()`` — input type differs (SD2)
* ``get()`` — lookup assembly differs by registry
* ``_resolve_requested_id()`` — only executor / orchestrator
* ``validate_all()`` — pack-specific plumbing
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Generic, Iterable, TypeVar

if TYPE_CHECKING:
    from astrid.core.pack.alias_resolver import AliasResolver

K = TypeVar("K")
T = TypeVar("T")


class RegistryError(Exception):
    """Base exception for all registry inconsistencies."""


@dataclass(frozen=True)
class RegistryConflict(Generic[K, T]):
    """One conflict record: a winning definition and its shadowed alternates."""

    key: K
    winner: T
    shadowed: tuple[T, ...]


class CapabilityRegistry(Generic[K, T]):
    """Generic in-memory registry keyed by *K*, storing ordered lists of *T*.

    Each key maps to a priority-ordered list where index ``[0]`` is the
    winning definition and indices ``[1:]`` are shadowed (lower-priority)
    alternates.  Subclasses supply the sort discipline via the
    *priority_key* callable passed to ``_register_impl()``.

    Parameters
    ----------
    alias_resolver:
        Optional shared :class:`~astrid.core.pack.alias_resolver.AliasResolver`
        for alias→canonical-id lookups.  Only executor/orchestrator subclasses
        use this; the element registry leaves it as ``None``.
    """

    def __init__(
        self,
        *,
        alias_resolver: "AliasResolver | None" = None,
    ) -> None:
        self._entries: dict[K, list[T]] = {}
        self.alias_resolver = alias_resolver

    # ------------------------------------------------------------------
    # Protected helpers (called by subclasses)
    # ------------------------------------------------------------------

    def _register_impl(
        self,
        key: K,
        definition: T,
        *,
        priority_key: Callable[[T], object] | None = None,
    ) -> None:
        """Append *definition* under *key* and optionally re-sort.

        Subclass ``register()`` validates the definition, computes the
        key, then calls this helper to insert into ``_entries``.

        When *priority_key* is supplied the entry list is re-sorted so
        that index ``[0]`` is always the highest-priority definition.
        """
        entry = self._entries.setdefault(key, [])
        entry.append(definition)
        if priority_key is not None:
            entry.sort(key=priority_key)

    @staticmethod
    def _resolve_entry(entry: list[T]) -> T:
        """Return the winning definition from a canonical storage entry."""

        return entry[0]

    @staticmethod
    def _iter_entries(entry: list[T]) -> Iterable[T]:
        """Yield every definition from a storage entry (winner + shadowed)."""
        yield from entry

    def _winner_for(self, key: K) -> T | None:
        """Return the winning definition for *key*, or ``None`` if absent."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        return self._resolve_entry(entry)

    # ------------------------------------------------------------------
    # Public read surface
    # ------------------------------------------------------------------

    def list(self) -> tuple[T, ...]:
        """Return every winning definition, sorted by key.

        Subclasses may override to add *kind* filtering (see SD2).
        """
        winners = (self._resolve_entry(entry) for entry in self._entries.values())
        return tuple(sorted(winners, key=str))

    def as_mapping(self) -> MappingProxyType[K, T]:
        """Immutable key → winning-definition mapping for fast lookups."""
        return MappingProxyType(
            {key: self._resolve_entry(entry) for key, entry in self._entries.items()}
        )

    def conflicts(self) -> tuple[RegistryConflict[K, T], ...]:
        """Return every entry where more than one definition is registered.

        Each :class:`RegistryConflict` records the winning definition and its
        shadowed alternates.  Subclasses may override to return a more
        specific conflict type (e.g. :class:`~astrid.core.element.registry.ElementConflict`).
        """
        result: list[RegistryConflict[K, T]] = []
        for key, definitions in self._entries.items():
            if len(definitions) > 1:
                result.append(
                    RegistryConflict(
                        key=key,
                        winner=definitions[0],
                        shadowed=tuple(definitions[1:]),
                    )
                )
        return tuple(sorted(result, key=lambda c: str(c.key)))
