"""Unit tests for the generic :class:`CapabilityRegistry` kernel."""

import unittest
from dataclasses import dataclass

from astrid.core.registry import CapabilityRegistry, RegistryConflict, RegistryError


@dataclass
class FakeDef:
    """Minimal definition for testing the generic kernel."""

    name: str
    priority: int = 30

    def __str__(self) -> str:
        return self.name


class CapabilityRegistrySmokeTests(unittest.TestCase):
    """Basic lifecycle: register, list, as_mapping, conflicts."""

    def setUp(self):
        self.reg: CapabilityRegistry[str, FakeDef] = CapabilityRegistry()

    def _register(self, key: str, name: str, priority: int = 30) -> None:
        self.reg._register_impl(
            key,
            FakeDef(name, priority),
            priority_key=lambda d: d.priority,
        )

    # ------------------------------------------------------------------
    # _register_impl
    # ------------------------------------------------------------------

    def test_register_impl_stores_entries(self):
        self._register("a", "a1", 30)
        self._register("b", "b1", 20)
        self.assertEqual(len(self.reg._entries), 2)

    def test_register_impl_sorts_by_priority_key(self):
        self._register("a", "a_low", 30)
        self._register("a", "a_high", 10)
        winner = self.reg._winner_for("a")
        self.assertIsNotNone(winner)
        self.assertEqual(winner.name, "a_high")

    def test_register_impl_without_priority_key_no_sort(self):
        reg: CapabilityRegistry[str, FakeDef] = CapabilityRegistry()
        reg._register_impl("a", FakeDef("first", 30))
        reg._register_impl("a", FakeDef("second", 10))
        # Without priority_key, order is insertion order
        self.assertEqual(reg._winner_for("a").name, "first")

    # ------------------------------------------------------------------
    # _resolve_entry / _iter_entries (static)
    # ------------------------------------------------------------------

    def test_resolve_entry_from_list(self):
        entry = [FakeDef("a", 10), FakeDef("b", 20)]
        self.assertEqual(CapabilityRegistry._resolve_entry(entry).name, "a")

    def test_resolve_entry_from_scalar(self):
        entry = FakeDef("single", 10)
        self.assertEqual(CapabilityRegistry._resolve_entry(entry).name, "single")

    def test_iter_entries_from_list(self):
        entry = [FakeDef("a", 10), FakeDef("b", 20)]
        names = [d.name for d in CapabilityRegistry._iter_entries(entry)]
        self.assertEqual(names, ["a", "b"])

    def test_iter_entries_from_scalar(self):
        entry = FakeDef("single", 10)
        names = [d.name for d in CapabilityRegistry._iter_entries(entry)]
        self.assertEqual(names, ["single"])

    # ------------------------------------------------------------------
    # _winner_for
    # ------------------------------------------------------------------

    def test_winner_for_present(self):
        self._register("a", "a1", 30)
        self._register("a", "a2", 10)
        self.assertEqual(self.reg._winner_for("a").name, "a2")

    def test_winner_for_absent(self):
        self.assertIsNone(self.reg._winner_for("nonexistent"))

    # ------------------------------------------------------------------
    # list()
    # ------------------------------------------------------------------

    def test_list_empty(self):
        self.assertEqual(self.reg.list(), ())

    def test_list_returns_winners_sorted_by_key(self):
        self._register("b", "b1", 30)
        self._register("a", "a1", 30)
        result = self.reg.list()
        self.assertEqual(len(result), 2)
        self.assertEqual([d.name for d in result], ["a1", "b1"])

    def test_list_only_winners(self):
        self._register("a", "winner", 10)
        self._register("a", "shadowed", 30)
        result = self.reg.list()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "winner")

    # ------------------------------------------------------------------
    # as_mapping()
    # ------------------------------------------------------------------

    def test_as_mapping_empty(self):
        self.assertEqual(len(self.reg.as_mapping()), 0)

    def test_as_mapping_winners(self):
        self._register("a", "a_win", 10)
        self._register("a", "a_shadow", 30)
        self._register("b", "b1", 20)
        mp = self.reg.as_mapping()
        self.assertEqual(len(mp), 2)
        self.assertEqual(mp["a"].name, "a_win")
        self.assertEqual(mp["b"].name, "b1")

    # ------------------------------------------------------------------
    # conflicts()
    # ------------------------------------------------------------------

    def test_conflicts_empty(self):
        self.assertEqual(self.reg.conflicts(), ())

    def test_conflicts_no_overlap(self):
        self._register("a", "a1", 30)
        self._register("b", "b1", 30)
        self.assertEqual(self.reg.conflicts(), ())

    def test_conflicts_detected(self):
        self._register("a", "winner", 10)
        self._register("a", "shadowed", 30)
        conflicts = self.reg.conflicts()
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.key, "a")
        self.assertEqual(c.winner.name, "winner")
        self.assertEqual(len(c.shadowed), 1)
        self.assertEqual(c.shadowed[0].name, "shadowed")

    def test_conflicts_sorted_by_key(self):
        self._register("b", "b_win", 10)
        self._register("b", "b_shadow", 30)
        self._register("a", "a_win", 10)
        self._register("a", "a_shadow", 30)
        conflicts = self.reg.conflicts()
        self.assertEqual(conflicts[0].key, "a")
        self.assertEqual(conflicts[1].key, "b")


class CapabilityRegistryOverrideStoreTests(unittest.TestCase):
    """Tests for _resolve_override_key with and without an OverrideStore."""

    def setUp(self):
        self.reg: CapabilityRegistry[str, FakeDef] = CapabilityRegistry()

    def test_resolve_override_key_no_store(self):
        self.assertIsNone(self.reg.override_store)
        result = self.reg._resolve_override_key("executor", "shots")
        self.assertIsNone(result)

    def test_resolve_override_key_with_store(self):
        from astrid.core.pack.override import OverrideStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = OverrideStore(project_root=tmpdir)
            store.set_override("executor", "shots", "local.shots")
            reg = CapabilityRegistry[str, FakeDef](override_store=store)
            result = reg._resolve_override_key("executor", "shots")
            self.assertEqual(result, "local.shots")

    def test_resolve_override_key_no_match(self):
        from astrid.core.pack.override import OverrideStore
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            store = OverrideStore(project_root=tmpdir)
            reg = CapabilityRegistry[str, FakeDef](override_store=store)
            result = reg._resolve_override_key("executor", "nonexistent")
            self.assertIsNone(result)


class CapabilityRegistryAliasResolverTests(unittest.TestCase):
    """Verify alias_resolver is accepted as a constructor parameter."""

    def test_alias_resolver_none_by_default(self):
        reg: CapabilityRegistry[str, FakeDef] = CapabilityRegistry()
        self.assertIsNone(reg.alias_resolver)

    def test_alias_resolver_set(self):
        from astrid.core.pack.alias_resolver import AliasResolver

        resolver = AliasResolver()
        reg = CapabilityRegistry[str, FakeDef](alias_resolver=resolver)
        self.assertIs(reg.alias_resolver, resolver)


class RegistryErrorTests(unittest.TestCase):
    """Ensure RegistryError is a usable base exception."""

    def test_raise_and_catch(self):
        with self.assertRaises(RegistryError):
            raise RegistryError("test message")

    def test_str(self):
        exc = RegistryError("something went wrong")
        self.assertEqual(str(exc), "something went wrong")


class RegistryConflictTests(unittest.TestCase):
    """Smoke-test the RegistryConflict dataclass."""

    def test_construction(self):
        winner = FakeDef("w", 10)
        shadowed = (FakeDef("s1", 20), FakeDef("s2", 30))
        rc = RegistryConflict(key="my_key", winner=winner, shadowed=shadowed)
        self.assertEqual(rc.key, "my_key")
        self.assertEqual(rc.winner.name, "w")
        self.assertEqual(len(rc.shadowed), 2)

    def test_immutable(self):
        rc = RegistryConflict(key="k", winner=FakeDef("w", 10), shadowed=())
        with self.assertRaises(Exception):
            rc.key = "other"  # type: ignore[misc]


class CapabilityRegistryTupleKeyTests(unittest.TestCase):
    """Verify the kernel works with tuple keys (element-style)."""

    def setUp(self):
        self.reg: CapabilityRegistry[tuple[str, str], FakeDef] = CapabilityRegistry()

    def test_tuple_key_lifecycle(self):
        key = ("effects", "text_card")
        self.reg._register_impl(key, FakeDef("pack_def", 30), priority_key=lambda d: d.priority)
        self.reg._register_impl(key, FakeDef("theme_def", 10), priority_key=lambda d: d.priority)

        winner = self.reg._winner_for(key)
        self.assertEqual(winner.name, "theme_def")

        mp = self.reg.as_mapping()
        self.assertEqual(mp[key].name, "theme_def")

        conflicts = self.reg.conflicts()
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].key, key)


if __name__ == "__main__":
    unittest.main()
