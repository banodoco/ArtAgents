"""Unit tests for the scoped-config primitive (tier-1).

Covers ``ScopeRegistry`` register/resolve/is_registered, unknown key
resolution, ``ScopeRequest`` frozenness and defaults, ``ScopedConfig``
marker subclassing, and the ``SCOPE_REGISTRY`` module-level singleton.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from astrid.core.contracts.scoped_config import (
    SCOPE_REGISTRY,
    ScopeRegistry,
    ScopeRequest,
    ScopedConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_echo_resolver(tag: str):
    """Return a resolver that returns a minimal ``ScopedConfig`` subclass."""

    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Echo(ScopedConfig):
        tag: str

    def _resolve(request: ScopeRequest) -> _Echo:
        return _Echo(tag=tag)

    return _resolve


# ---------------------------------------------------------------------------
# ScopeRegistry basics
# ---------------------------------------------------------------------------


class TestScopeRegistryBasics:
    """Core register / resolve / is_registered lifecycle."""

    def test_register_and_resolve(self) -> None:
        """Registering a key and resolving it returns the resolver result."""
        registry = ScopeRegistry()
        registry.register("style", _make_echo_resolver("style"))

        request = ScopeRequest()
        result = registry.resolve("style", request)

        assert result is not None
        assert isinstance(result, ScopedConfig)
        assert result.tag == "style"

    def test_is_registered_true(self) -> None:
        """``is_registered`` returns True for a registered key."""
        registry = ScopeRegistry()
        registry.register("style", _make_echo_resolver("style"))
        assert registry.is_registered("style") is True

    def test_is_registered_false(self) -> None:
        """``is_registered`` returns False for an unknown key."""
        registry = ScopeRegistry()
        assert registry.is_registered("style") is False

    def test_resolve_unknown_key_returns_none(self) -> None:
        """Resolving an unregistered key returns None."""
        registry = ScopeRegistry()
        result = registry.resolve("nonexistent", ScopeRequest())
        assert result is None

    def test_double_register_raises(self) -> None:
        """Registering the same key twice raises ValueError."""
        registry = ScopeRegistry()
        registry.register("style", _make_echo_resolver("first"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register("style", _make_echo_resolver("second"))

    def test_multiple_independent_keys(self) -> None:
        """Multiple keys can coexist in the same registry."""
        registry = ScopeRegistry()
        registry.register("style", _make_echo_resolver("style"))
        registry.register("credentials.fal", _make_echo_resolver("fal"))

        style_result = registry.resolve("style", ScopeRequest())
        creds_result = registry.resolve("credentials.fal", ScopeRequest())

        assert style_result is not None
        assert creds_result is not None
        assert style_result.tag == "style"
        assert creds_result.tag == "fal"


# ---------------------------------------------------------------------------
# ScopeRequest — frozenness and defaults
# ---------------------------------------------------------------------------


class TestScopeRequest:
    """``ScopeRequest`` is frozen and carries ambient context."""

    def test_defaults_are_none(self) -> None:
        """All fields default to None."""
        request = ScopeRequest()
        assert request.project_slug is None
        assert request.env is None
        assert request.explicit is None

    def test_construction_with_values(self) -> None:
        """Fields can be set at construction time."""
        request = ScopeRequest(
            project_slug="demo",
            env={"HYPE_ACTIVE_THEME": "banodoco-default"},
            explicit={"style": "banodoco-default"},
        )
        assert request.project_slug == "demo"
        assert request.env == {"HYPE_ACTIVE_THEME": "banodoco-default"}
        assert request.explicit == {"style": "banodoco-default"}

    def test_frozen_project_slug(self) -> None:
        """``ScopeRequest`` is frozen — setting a field raises FrozenInstanceError."""
        request = ScopeRequest(project_slug="demo")
        with pytest.raises(FrozenInstanceError):
            request.project_slug = "other"  # type: ignore[misc]

    def test_frozen_env(self) -> None:
        """``ScopeRequest.env`` is frozen."""
        request = ScopeRequest(env={"K": "V"})
        with pytest.raises(FrozenInstanceError):
            request.env = None  # type: ignore[misc]

    def test_frozen_explicit(self) -> None:
        """``ScopeRequest.explicit`` is frozen."""
        request = ScopeRequest(explicit={"style": "x"})
        with pytest.raises(FrozenInstanceError):
            request.explicit = {}  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        """Two ``ScopeRequest`` instances with the same fields are equal."""
        a = ScopeRequest(project_slug="demo", env={"K": "V"})
        b = ScopeRequest(project_slug="demo", env={"K": "V"})
        assert a == b
        assert not (a != b)

    def test_inequality_different_fields(self) -> None:
        """Two ``ScopeRequest`` instances with different fields are not equal."""
        a = ScopeRequest(project_slug="demo")
        b = ScopeRequest(project_slug="other")
        assert a != b

    def test_hashable(self) -> None:
        """Frozen ScopeRequest instances are hashable."""
        request = ScopeRequest(project_slug="demo")
        # If the dataclass were not frozen this would raise TypeError.
        _ = hash(request)


# ---------------------------------------------------------------------------
# ScopedConfig marker
# ---------------------------------------------------------------------------


class TestScopedConfigMarker:
    """``ScopedConfig`` is a frozen-dataclass marker base."""

    def test_isinstance_check(self) -> None:
        """Subclasses pass ``isinstance`` against ``ScopedConfig``."""

        @pytest.mark.filterwarnings("ignore")
        class _Concrete(ScopedConfig):
            value: str = "test"

        instance = _Concrete()
        assert isinstance(instance, ScopedConfig)

    def test_frozen_subclass_with_explicit_decorator(self) -> None:
        """Subclasses of ``ScopedConfig`` that declare ``@dataclass(frozen=True)`` are frozen."""

        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _Concrete(ScopedConfig):
            value: str = "test"

        instance = _Concrete()
        with pytest.raises(FrozenInstanceError):
            instance.value = "mutated"  # type: ignore[misc]

    def test_scopedconfig_is_frozen_dataclass(self) -> None:
        """``ScopedConfig`` itself is a frozen dataclass."""
        params = getattr(ScopedConfig, "__dataclass_params__", None)
        assert params is not None, "ScopedConfig should be a dataclass"
        assert params.frozen is True, "ScopedConfig should be frozen"


# ---------------------------------------------------------------------------
# Module-level SCOPE_REGISTRY singleton
# ---------------------------------------------------------------------------


class TestModuleLevelSingleton:
    """``SCOPE_REGISTRY`` is a module-level singleton."""

    def test_singleton_is_scope_registry(self) -> None:
        """The singleton is a ``ScopeRegistry`` instance."""
        assert isinstance(SCOPE_REGISTRY, ScopeRegistry)

    def test_singleton_identity(self) -> None:
        """Importing the singleton twice returns the same object."""
        from astrid.core.contracts.scoped_config import (
            SCOPE_REGISTRY as sr2,
        )

        assert SCOPE_REGISTRY is sr2

    def test_singleton_can_register_and_resolve(self) -> None:
        """The singleton can register and resolve a key."""
        key = "test_singleton_scope"
        if not SCOPE_REGISTRY.is_registered(key):
            SCOPE_REGISTRY.register(key, _make_echo_resolver(key))
        result = SCOPE_REGISTRY.resolve(key, ScopeRequest())
        assert result is not None
        assert isinstance(result, ScopedConfig)
        assert result.tag == key
