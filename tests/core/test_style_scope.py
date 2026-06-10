"""Parity tests for StyleScope precedence vs the S0 spike.

The spike at ``astrid.core._spike.scoped_config_spike`` defines
the canonical resolution order:

    explicit > env(HYPE_ACTIVE_THEME) > project binding > None

These tests assert that the production ``resolve_style_scope``
behaves identically for all precedence branches.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.contracts.scoped_config import SCOPE_REGISTRY, ScopeRequest
from astrid.core.env_vars import HYPE_ACTIVE_THEME
from astrid.core.theme.scope import StyleScope, resolve_style_scope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env_hype_active_theme():
    """Remove HYPE_ACTIVE_THEME from os.environ so tests don't leak."""
    old = os.environ.pop(HYPE_ACTIVE_THEME, None)
    yield
    if old is not None:
        os.environ[HYPE_ACTIVE_THEME] = old


@pytest.fixture
def existing_theme_dir(tmp_path: Path) -> Path:
    """Create a real theme directory on disk so resolve_theme_dir succeeds."""
    theme_dir = tmp_path / "my_theme"
    theme_dir.mkdir()
    (theme_dir / "theme.json").write_text('{"id":"my_theme","visual":{"color":{"fg":"#fff","bg":"#000","accent":"#f00"},"type":{"families":{"heading":"Arial","body":"Arial"},"size":{"base":16,"small":12,"large":24},"weight":{"normal":400,"bold":700},"lineHeight":1.5},"motion":{"fadeMs":300},"canvas":{"width":1920,"height":1080,"fps":30}}}')
    return theme_dir


# ---------------------------------------------------------------------------
# Precedence: explicit > env > project > None
# ---------------------------------------------------------------------------


def test_explicit_wins_over_env(existing_theme_dir: Path):
    """explicit['theme'] should win even when HYPE_ACTIVE_THEME is set."""
    request = ScopeRequest(
        explicit={"theme": str(existing_theme_dir)},
        env={HYPE_ACTIVE_THEME: str(existing_theme_dir.parent / "other")},
    )
    result = resolve_style_scope(request)
    assert isinstance(result, StyleScope)
    assert result.theme_dir == existing_theme_dir.resolve()


def test_explicit_wins_over_project(existing_theme_dir: Path):
    """explicit['theme'] should win over project binding."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=str(existing_theme_dir.parent / "project_theme"),
    ):
        request = ScopeRequest(
            explicit={"theme": str(existing_theme_dir)},
            project_slug="test-proj",
        )
        result = resolve_style_scope(request)
        assert result.theme_dir == existing_theme_dir.resolve()


def test_env_wins_over_project(existing_theme_dir: Path):
    """HYPE_ACTIVE_THEME should win over project binding."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=str(existing_theme_dir.parent / "project_theme"),
    ):
        request = ScopeRequest(
            env={HYPE_ACTIVE_THEME: str(existing_theme_dir)},
            project_slug="test-proj",
        )
        result = resolve_style_scope(request)
        assert result.theme_dir == existing_theme_dir.resolve()


def test_project_resolves_when_explicit_and_env_absent(existing_theme_dir: Path):
    """Project binding resolves when explicit and env are absent."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=str(existing_theme_dir),
    ):
        request = ScopeRequest(project_slug="test-proj")
        result = resolve_style_scope(request)
        assert result.theme_dir == existing_theme_dir.resolve()


def test_none_when_all_absent():
    """None returned when no precedence level provides a theme."""
    request = ScopeRequest()
    result = resolve_style_scope(request)
    assert isinstance(result, StyleScope)
    assert result.theme_dir is None


def test_none_when_project_theme_returns_none():
    """None when project binding returns None."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=None,
    ):
        request = ScopeRequest(project_slug="test-proj")
        result = resolve_style_scope(request)
        assert result.theme_dir is None


# ---------------------------------------------------------------------------
# Explicit overrides (edge cases)
# ---------------------------------------------------------------------------


def test_explicit_without_theme_key_falls_through(existing_theme_dir: Path):
    """explicit dict without 'theme' key should fall through to env."""
    request = ScopeRequest(
        explicit={"other_key": "value"},
        env={HYPE_ACTIVE_THEME: str(existing_theme_dir)},
    )
    result = resolve_style_scope(request)
    assert result.theme_dir == existing_theme_dir.resolve()


def test_explicit_theme_none_falls_through(existing_theme_dir: Path):
    """explicit['theme']=None should fall through to env."""
    request = ScopeRequest(
        explicit={"theme": None},
        env={HYPE_ACTIVE_THEME: str(existing_theme_dir)},
    )
    result = resolve_style_scope(request)
    assert result.theme_dir == existing_theme_dir.resolve()


# ---------------------------------------------------------------------------
# Empty env value falls through
# ---------------------------------------------------------------------------


def test_empty_env_string_falls_through_to_project(existing_theme_dir: Path):
    """Empty HYPE_ACTIVE_THEME value should fall through."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=str(existing_theme_dir),
    ):
        request = ScopeRequest(
            env={HYPE_ACTIVE_THEME: ""},
            project_slug="test-proj",
        )
        result = resolve_style_scope(request)
        assert result.theme_dir == existing_theme_dir.resolve()


# ---------------------------------------------------------------------------
# env=None (no mapping at all) falls through
# ---------------------------------------------------------------------------


def test_env_none_falls_through(existing_theme_dir: Path):
    """When env mapping is None, fall through to project."""
    with patch(
        "astrid.core.project.project.get_project_theme",
        return_value=str(existing_theme_dir),
    ):
        request = ScopeRequest(env=None, project_slug="test-proj")
        result = resolve_style_scope(request)
        assert result.theme_dir == existing_theme_dir.resolve()


# ---------------------------------------------------------------------------
# explicit=None falls through
# ---------------------------------------------------------------------------


def test_explicit_none_falls_through(existing_theme_dir: Path):
    """When explicit mapping is None, fall through to env."""
    request = ScopeRequest(
        explicit=None,
        env={HYPE_ACTIVE_THEME: str(existing_theme_dir)},
    )
    result = resolve_style_scope(request)
    assert result.theme_dir == existing_theme_dir.resolve()


# ---------------------------------------------------------------------------
# SCOPE_REGISTRY integration
# ---------------------------------------------------------------------------


def test_style_registered_in_scope_registry():
    """'style' key is registered in SCOPE_REGISTRY."""
    assert SCOPE_REGISTRY.is_registered("style")


def test_style_scope_via_registry_resolve(existing_theme_dir: Path):
    """SCOPE_REGISTRY.resolve('style', ...) resolves correctly."""
    request = ScopeRequest(
        explicit={"theme": str(existing_theme_dir)},
    )
    result = SCOPE_REGISTRY.resolve("style", request)
    assert isinstance(result, StyleScope)
    assert result.theme_dir == existing_theme_dir.resolve()


# ---------------------------------------------------------------------------
# StyleScope is a ScopedConfig subclass (marker check)
# ---------------------------------------------------------------------------


def test_style_scope_is_scoped_config():
    """StyleScope is a subclass of ScopedConfig."""
    from astrid.core.contracts.scoped_config import ScopedConfig

    assert issubclass(StyleScope, ScopedConfig)


# ---------------------------------------------------------------------------
# StyleScope is frozen (immutability)
# ---------------------------------------------------------------------------


def test_style_scope_is_frozen():
    """StyleScope instances cannot be mutated."""
    scope = StyleScope(theme_dir=None)
    with pytest.raises(Exception):
        scope.theme_dir = Path("/tmp")  # type: ignore[misc]
