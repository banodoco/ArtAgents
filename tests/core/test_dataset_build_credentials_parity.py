"""Parity test: every env var referenced by dataset_build providers maps
to a registered ``credentials.<provider>`` scope, and all 8 canonical
providers are registered.

This is a static-grep test — it does not require real API keys.
"""

from __future__ import annotations

import pytest

# Ensure the credentials scope module is loaded so its import-time
# SCOPE_REGISTRY.register() calls have executed.
import astrid.core.util.credentials_scope  # noqa: F401

from astrid.core.contracts.scoped_config import SCOPE_REGISTRY


# ---------------------------------------------------------------------------
# Canonical env var → credentials scope mapping
# ---------------------------------------------------------------------------

_ENV_TO_SCOPE: dict[str, str] = {
    "FAL_KEY": "credentials.fal",
    "WAVESPEED_API_KEY": "credentials.wavespeed",
    "OPENAI_API_KEY": "credentials.openai",
    "ANTHROPIC_API_KEY": "credentials.anthropic",
    "DEEPSEEK_API_KEY": "credentials.deepseek",
    "FIREWORKS_API_KEY": "credentials.fireworks",
    "GEMINI_API_KEY": "credentials.gemini",
    "GIPHY_API_KEY": "credentials.giphy",
}

_CANONICAL_PROVIDERS = {
    "fal",
    "wavespeed",
    "openai",
    "anthropic",
    "deepseek",
    "fireworks",
    "gemini",
    "giphy",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dataset_build_env_vars() -> set[str]:
    """Collect every unique env var referenced by dataset_build config providers."""
    from astrid.packs.training.orchestrators.dataset_build.config import (
        API_BACKED_CAPTION_PROVIDERS,
        API_BACKED_TRANSCRIPT_PROVIDERS,
    )

    env_vars: set[str] = set()
    for env_names in API_BACKED_CAPTION_PROVIDERS.values():
        env_vars.update(env_names)
    for env_names in API_BACKED_TRANSCRIPT_PROVIDERS.values():
        env_vars.update(env_names)
    return env_vars


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_dataset_build_env_vars_map_to_registered_scopes() -> None:
    """Every env var referenced in API_BACKED_*_PROVIDERS must have a
    corresponding ``credentials.*`` scope registered in SCOPE_REGISTRY."""
    env_vars = _dataset_build_env_vars()

    missing: list[str] = []
    for env_var in sorted(env_vars):
        scope_key = _ENV_TO_SCOPE.get(env_var)
        if scope_key is None:
            missing.append(f"{env_var!r} → no mapping in _ENV_TO_SCOPE")
        elif not SCOPE_REGISTRY.is_registered(scope_key):
            missing.append(f"{env_var!r} → {scope_key!r} not registered")

    assert not missing, (
        f"Dataset-build env vars without registered credentials scopes:\n"
        + "\n".join(missing)
    )


def test_all_canonical_providers_registered() -> None:
    """All 8 canonical providers must have credentials.<provider> scopes registered."""
    missing: list[str] = []
    for provider in sorted(_CANONICAL_PROVIDERS):
        scope_key = f"credentials.{provider}"
        if not SCOPE_REGISTRY.is_registered(scope_key):
            missing.append(scope_key)

    assert not missing, (
        f"Canonical providers missing from SCOPE_REGISTRY: {', '.join(missing)}"
    )


def test_env_to_scope_self_consistent() -> None:
    """Every entry in _ENV_TO_SCOPE maps to a registered scope."""
    missing: list[str] = []
    for env_var, scope_key in sorted(_ENV_TO_SCOPE.items()):
        if not SCOPE_REGISTRY.is_registered(scope_key):
            missing.append(f"{env_var!r} → {scope_key!r} not registered")

    assert not missing, (
        f"_ENV_TO_SCOPE entries not in SCOPE_REGISTRY:\n" + "\n".join(missing)
    )


def test_canonical_provider_count() -> None:
    """The canonical provider set covers exactly the 8 defined providers."""
    # This is a shape guard: if a new credentials scope is registered but
    # _ENV_TO_SCOPE is not updated, this test catches the mismatch.
    from astrid.core.util.credentials_scope import _PROVIDER_ENV

    assert len(_PROVIDER_ENV) == len(_CANONICAL_PROVIDERS), (
        f"_PROVIDER_ENV has {len(_PROVIDER_ENV)} entries but "
        f"_CANONICAL_PROVIDERS expects {len(_CANONICAL_PROVIDERS)}"
    )
    assert set(_PROVIDER_ENV) == _CANONICAL_PROVIDERS, (
        f"Provider mismatch: "
        f"_PROVIDER_ENV keys={set(_PROVIDER_ENV)}, "
        f"_CANONICAL_PROVIDERS={_CANONICAL_PROVIDERS}"
    )
