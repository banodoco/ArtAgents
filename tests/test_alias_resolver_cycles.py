"""Targeted tests for the ~5 uncovered lines in astrid/core/alias_resolver.py.

Coverage gaps at 98% before this file (missing lines 76, 120):

  Line 76  — ``self._aliases[alias] = previous`` in ``register_alias``'s rollback
              branch.  Reached only when re-registering an *existing* alias with
              a value that creates a cycle (the previous binding is restored).

  Line 120 — ``raise AliasResolutionError(...)`` inside ``resolve()``'s visited-
              set guard.  Reached only when a cycle bypasses ``register_alias``'s
              validation (e.g. by directly patching ``_aliases``).

Target: ≥99% coverage of astrid/core/alias_resolver.py.
"""

from __future__ import annotations

import pytest

from astrid.core.pack.alias_resolver import AliasResolutionError, AliasResolver
from astrid.contracts.schema import AliasRecord


class TestRegisterAliasRollbackBranch:
    """Line 76: restore previous alias when a cycle-creating update is rejected."""

    def test_rollback_restores_previous_alias_on_cycle(self) -> None:
        """Re-registering an existing alias to create a cycle restores the old target."""
        resolver = AliasResolver()
        # Valid: a -> b
        resolver.register_alias("a", "b")
        assert resolver.resolve("a") == "b"

        # Invalid: a -> a (self-loop cycle) — must be rejected and a -> b restored.
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("a", "a")

        # After rejection, the original a -> b mapping is still in place.
        assert resolver.is_alias("a") is True
        assert resolver.resolve("a") == "b"

    def test_rollback_restores_previous_on_indirect_cycle(self) -> None:
        """a -> c, b -> c are valid; update a -> b creates a -> b -> c (fine),
        but updating b -> a creates b -> a -> b cycle — b's previous c binding
        must be restored."""
        resolver = AliasResolver()
        resolver.register_alias("a", "canonical.target")
        resolver.register_alias("b", "canonical.target")

        # a is now registered as an alias. Update b to point at a (chain b -> a -> canonical.target)
        resolver.register_alias("b", "a")
        assert resolver.resolve("b") == "canonical.target"

        # Now try to update a to point at b (creates a -> b -> a cycle).
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("a", "b")

        # a's previous target (canonical.target) must be restored.
        assert resolver.resolve("a") == "canonical.target"

    def test_new_alias_deleted_on_first_register_cycle(self) -> None:
        """A brand-new alias (no previous) that would create a self-cycle is removed
        entirely, not left with a stale entry."""
        resolver = AliasResolver()
        # Manually register 'x' -> 'x' by patching _aliases so register_alias
        # can be called for another entry that references it.  Actually, use
        # register_alias for a legitimate alias first, then create the cycle.
        resolver.register_alias("y", "canonical")

        # Try to register 'canonical' -> 'y' — this would create a cycle because
        # y -> canonical -> y.  'canonical' has no prior mapping (it's a new entry).
        with pytest.raises(AliasResolutionError, match="cycle"):
            resolver.register_alias("canonical", "y")

        # 'canonical' must have been removed (it was new before the failing call).
        assert resolver.is_alias("canonical") is False


class TestResolveInternalCycleGuard:
    """Line 120: raise in resolve() when _aliases contains a direct cycle."""

    def test_resolve_raises_on_bypassed_cycle(self) -> None:
        """Directly inject a cycle into _aliases, then call resolve() to hit line 120."""
        resolver = AliasResolver()
        # Bypass register_alias to insert a cycle undetected by validate_no_cycles.
        resolver._aliases["x"] = AliasRecord(alias="x", canonical_id="y")
        resolver._aliases["y"] = AliasRecord(alias="y", canonical_id="x")

        with pytest.raises(AliasResolutionError, match="alias cycle detected"):
            resolver.resolve("x")

    def test_resolve_raises_on_longer_cycle(self) -> None:
        """A -> B -> C -> A cycle injected directly should trigger line 120."""
        resolver = AliasResolver()
        resolver._aliases["a"] = AliasRecord(alias="a", canonical_id="b")
        resolver._aliases["b"] = AliasRecord(alias="b", canonical_id="c")
        resolver._aliases["c"] = AliasRecord(alias="c", canonical_id="a")

        with pytest.raises(AliasResolutionError, match="alias cycle detected"):
            resolver.resolve("a")
