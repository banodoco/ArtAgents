"""Scoped-config primitive (tier-1, stdlib-only).

Defines the kernel scope types and a module-level registry singleton.
Concrete scope resolvers (for example ``CredentialsScope``) live at tier-3 in
their data-owning modules and register themselves against ``SCOPE_REGISTRY``.

Key design points (per S3 RFC):
- ``ScopeKey`` is a plain ``str`` alias so there is no coupling to any
  concrete scope in the tier-1 primitive.
- ``ScopeRequest`` is frozen — it captures the ambient context the
  caller wants to hand to a scope resolver without needing to know
  which resolver will consume it.
- ``ScopeRegistry`` is a dict-backed registry with ``register``,
  ``resolve``, and ``is_registered``.  It is deliberately not a mapping
  — callers must use the methods so that registration and resolution
  are always explicit.
- ``ScopedConfig`` is a frozen-dataclass marker that concrete scope
  result types subclass (e.g. ``StyleConfig(ScopedConfig)``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Scope key alias
# ---------------------------------------------------------------------------

ScopeKey = str
"""Opaque scope key (e.g. ``"style"``, ``"credentials.fal"``)."""


# ---------------------------------------------------------------------------
# ScopedConfig — marker base class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopedConfig:
    """Marker base class for typed scope results.

    Concrete scope result types (``CredentialsScope``,
    etc.) subclass this so that downstream code can use ``isinstance``
    to tell scope results from plain dataclasses.

    This class intentionally carries no fields — it exists solely as a
    type-hierarchy sentinel.
    """


# ---------------------------------------------------------------------------
# ScopeRequest — frozen ambient context captured once per pipeline context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeRequest:
    """Ambient context needed by scope resolvers.

    Captured once during pipeline-context construction and handed to
    every scope resolver.  Frozen so it cannot be mutated after capture.

    Fields
    ------
    project_slug:
        The current project slug (``None`` when not inside a project).
    env:
        Full subprocess environment mapping (keys are env-var names,
        values are strings).  Scope resolvers that need an env variable
        fish it out of this mapping rather than reading ``os.environ``
        directly — this keeps resolution deterministic and testable.
    explicit:
        Opaque explicit override dictionary.  Keys are scope keys
        (``"style"``, ``"credentials.fal"``, ...) and values are the
        caller-supplied override for that scope.  ``None`` means "no
        explicit overrides".
    """

    project_slug: str | None = None
    env: Mapping[str, str] | None = None
    explicit: Mapping[ScopeKey, Any] | None = None


# ---------------------------------------------------------------------------
# ScopeResolver protocol (runtime-checkable)
# ---------------------------------------------------------------------------


class ScopeResolver:
    """Protocol for a scope resolver callable.

    A scope resolver is a callable that accepts a ``ScopeRequest`` and
    returns either a ``ScopedConfig`` subclass instance or ``None``
    (meaning "this scope does not apply in the given context").

    We use a simple class with ``__call__`` instead of
    ``typing.Protocol`` to avoid a stdlib-only typing import
    (``runtime_checkable``) that still works at runtime.
    """

    def __call__(self, request: ScopeRequest) -> ScopedConfig | None:
        ...


# ---------------------------------------------------------------------------
# ScopeRegistry — module-level singleton backing store
# ---------------------------------------------------------------------------


class ScopeRegistry:
    """Dict-backed registry of scope resolvers.

    Scope keys are strings (``"style"``, ``"credentials.fal"``, etc.).
    Resolvers are callables ``(ScopeRequest) -> ScopedConfig | None``.

    The registry is deliberately **not** a ``MutableMapping`` — callers
    must use the ``register`` / ``resolve`` / ``is_registered`` methods
    so that registration and resolution are always explicit.
    """

    def __init__(self) -> None:
        self._resolvers: dict[ScopeKey, ScopeResolver] = {}

    def register(self, key: ScopeKey, resolver: ScopeResolver) -> None:
        """Register a scope resolver for *key*.

        Raises ``ValueError`` if *key* is already registered (double-
        registration is almost always a bug).
        """
        if key in self._resolvers:
            raise ValueError(
                f"Scope key {key!r} is already registered"
            )
        self._resolvers[key] = resolver

    def resolve(self, key: ScopeKey, request: ScopeRequest) -> ScopedConfig | None:
        """Resolve *key* against *request*.

        Returns the result of calling the registered resolver, or
        ``None`` if *key* is not registered.
        """
        resolver = self._resolvers.get(key)
        if resolver is None:
            return None
        return resolver(request)

    def is_registered(self, key: ScopeKey) -> bool:
        """Return ``True`` if *key* has a registered resolver."""
        return key in self._resolvers


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

SCOPE_REGISTRY = ScopeRegistry()
"""Module-level singleton scope registry.

Concrete scope resolvers import this and call ``SCOPE_REGISTRY.register``
at module level to wire themselves in.  The runner calls
``SCOPE_REGISTRY.resolve`` at dispatch time to evaluate declared scope
keys against the captured ``ScopeRequest``.
"""
