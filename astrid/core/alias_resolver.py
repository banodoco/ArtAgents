"""Capability alias resolver for the Astrid pack system.

Resolves public-facing alias names to their canonical capability ids,
validates alias graphs for cycles, and tracks deprecated aliases.
"""

from __future__ import annotations

from astrid.contracts.schema import AliasRecord


class AliasResolutionError(ValueError):
    """Raised when an alias cannot be resolved or a cycle is detected."""


class AliasResolver:
    """Resolves capability aliases to canonical ids with cycle detection.

    Aliases are one-way mappings from a short public name (the alias) to
    a fully-qualified canonical id.  Multiple aliases can point to the same
    canonical id, and aliases are resolved transitively (chains of aliases
    are flattened to the ultimate canonical target).

    Cycle detection runs eagerly on every ``register_alias`` call so that
    invalid alias graphs are rejected at registration time rather than
    surfacing as infinite loops during resolution.
    """

    def __init__(self) -> None:
        self._aliases: dict[str, AliasRecord] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_alias(
        self,
        alias: str,
        canonical_id: str,
        *,
        deprecated: bool = False,
        deprecation_message: str = "",
    ) -> None:
        """Register *alias* as a public name for *canonical_id*.

        Raises:
            AliasResolutionError: if the alias would create a cycle.
        """
        if not alias or not alias.strip():
            raise AliasResolutionError("alias must be a non-empty string")
        if not canonical_id or not canonical_id.strip():
            raise AliasResolutionError("canonical_id must be a non-empty string")

        record = AliasRecord(
            alias=alias,
            canonical_id=canonical_id,
            deprecated=deprecated,
            deprecation_message=deprecation_message,
        )

        # Snapshot current state so we can roll back on cycle detection.
        previous = self._aliases.get(alias)
        self._aliases[alias] = record
        try:
            self.validate_no_cycles()
        except AliasResolutionError:
            # Restore previous state.
            if previous is None:
                del self._aliases[alias]
            else:
                self._aliases[alias] = previous
            raise

    def register_pack_aliases(
        self,
        pack_id: str,
        aliases: list[dict[str, str | bool]],
    ) -> None:
        """Register every alias declared by *pack_id* from a list of raw dicts.

        Each dict may contain the keys ``alias`` (required), ``canonical_id``
        (required), ``deprecated`` (optional bool), and
        ``deprecation_message`` (optional str).
        """
        for entry in aliases:
            alias = entry.get("alias")
            canonical_id = entry.get("canonical_id")
            if not alias or not canonical_id:
                raise AliasResolutionError(
                    f"pack {pack_id!r}: alias entry missing 'alias' or 'canonical_id'"
                )
            self.register_alias(
                alias=str(alias),
                canonical_id=str(canonical_id),
                deprecated=bool(entry.get("deprecated", False)),
                deprecation_message=str(entry.get("deprecation_message", "")),
            )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, alias_or_id: str) -> str:
        """Resolve *alias_or_id* to its canonical id.

        If *alias_or_id* is not a registered alias it is returned unchanged
        (idempotent for canonical ids).  Alias chains are followed
        transitively until a non-alias canonical id is reached.
        """
        visited: set[str] = set()
        current = alias_or_id
        while current in self._aliases:
            if current in visited:
                raise AliasResolutionError(
                    f"alias cycle detected while resolving {alias_or_id!r}"
                )
            visited.add(current)
            current = self._aliases[current].canonical_id
        return current

    # ------------------------------------------------------------------
    # Cycle detection
    # ------------------------------------------------------------------

    def validate_no_cycles(self) -> None:
        """Raise ``AliasResolutionError`` if any alias chain contains a cycle.

        Uses depth-first search with three-colour marking (white / grey /
        black) to detect back-edges.
        """
        WHITE = 0
        GREY = 1
        BLACK = 2

        colour: dict[str, int] = {}

        def visit(node: str) -> None:
            colour[node] = GREY
            target = self._aliases[node].canonical_id
            if target in self._aliases:
                if colour.get(target) == GREY:
                    raise AliasResolutionError(
                        f"alias cycle detected: {node} -> {target}"
                    )
                if colour.get(target) == WHITE:
                    visit(target)
            colour[node] = BLACK

        for alias in self._aliases:
            colour.setdefault(alias, WHITE)

        for alias in self._aliases:
            if colour[alias] == WHITE:
                visit(alias)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_deprecated(self) -> list[AliasRecord]:
        """Return every alias record marked as deprecated."""
        return [r for r in self._aliases.values() if r.deprecated]

    def get_aliases_for(self, canonical_id: str) -> list[AliasRecord]:
        """Return all alias records that resolve (directly) to *canonical_id*."""
        return [r for r in self._aliases.values() if r.canonical_id == canonical_id]

    def is_alias(self, value: str) -> bool:
        """Return ``True`` if *value* is a registered alias."""
        return value in self._aliases


def create_shared_alias_resolver() -> AliasResolver:
    """Factory that returns a fresh ``AliasResolver`` instance.

    All three registries call this from ``load_default_registry()`` so
    that alias resolution infrastructure is wired in from the start,
    even when no aliases have been declared yet (M1: empty dicts).
    """
    return AliasResolver()


def _register_pack_aliases(
    resolver: AliasResolver,
    pack_aliases: dict[str, list[dict[str, str | bool]]],
) -> None:
    """Register every pack's declared aliases into *resolver*.

    *pack_aliases* maps ``pack_id`` to a list of alias entry dicts.
    For M1 this dict is empty — the helpers exists so that
    ``load_default_registry()`` can call it unconditionally and
    future milestones only need to change the data, not the wiring.
    """
    for pack_id, aliases in pack_aliases.items():
        resolver.register_pack_aliases(pack_id, aliases)
