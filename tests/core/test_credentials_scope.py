"""Tests for CredentialsScope — scoped API key resolution.

Covers:
- All 6 canonical providers resolve via CredentialsScope.get()
- Missing key → AstridError
- Unknown provider → AstridError
- Secret scrubbing intact
- SCOPE_REGISTRY integration
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.contracts.scoped_config import SCOPE_REGISTRY, ScopeRequest
from astrid.core.util.credentials_scope import CredentialsScope

# ---------------------------------------------------------------------------
# Provider → env-var mapping
# ---------------------------------------------------------------------------

PROVIDER_ENV = {
    "fal": "FAL_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_file_with_key(tmp_path: Path) -> Path:
    """Create a .env file with a known API key."""
    env_path = tmp_path / ".env"
    env_path.write_text("FAL_KEY=fal_test_value\n")
    return env_path


# ---------------------------------------------------------------------------
# All 6 providers resolve via CredentialsScope.get()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider,env_var", PROVIDER_ENV.items())
def test_get_resolves_via_env_file(provider: str, env_var: str, tmp_path: Path, monkeypatch):
    """Each provider resolves when its env var is in a .env file."""
    # Hermetic: the process environment must not shadow the env-file tier
    # (frozen precedence: explicit > process env > keychain > env file).
    monkeypatch.delenv(env_var, raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text(f"{env_var}=test_key_{provider}\n")
    result = CredentialsScope.get(provider, env_file=env_path)
    assert result == f"test_key_{provider}"


@pytest.mark.parametrize("provider,env_var", PROVIDER_ENV.items())
def test_get_resolves_via_os_environ(provider: str, env_var: str):
    """Each provider resolves via load_api_key delegation."""
    with patch(
        "astrid.core.util.credentials_scope.load_api_key",
        return_value=f"os_{provider}_key",
    ):
        result = CredentialsScope.get(provider)
        assert result == f"os_{provider}_key"


# ---------------------------------------------------------------------------
# Missing key → AstridError
# ---------------------------------------------------------------------------


def test_missing_key_raises_astrid_error():
    """CredentialsScope.get raises AstridError when load_api_key raises."""
    with patch(
        "astrid.core.util.credentials_scope.load_api_key",
        side_effect=AstridError("FAL_KEY not found"),
    ):
        with pytest.raises(AstridError) as exc_info:
            CredentialsScope.get("fal")
        assert "FAL_KEY not found" in str(exc_info.value.cause)


# ---------------------------------------------------------------------------
# Unknown provider → AstridError
# ---------------------------------------------------------------------------


def test_unknown_provider_raises_astrid_error():
    """Unknown provider raises AstridError with helpful valid-options."""
    with pytest.raises(AstridError) as exc_info:
        CredentialsScope.get("nonexistent")
    assert "Unknown credentials provider" in str(exc_info.value.cause)
    assert "nonexistent" in str(exc_info.value.cause)


# ---------------------------------------------------------------------------
# Secret scrubbing intact (via load_api_key → scrub_secret)
# ---------------------------------------------------------------------------


def test_secret_scrubbing_still_works():
    """Secret scrubbing via secrets.scrub_secret is unaffected."""
    from astrid.core.util.secrets import scrub_secret

    result = scrub_secret("secret123", "prefix secret123 suffix")
    assert "secret123" not in result
    assert "***" in result


# ---------------------------------------------------------------------------
# All 6 providers registered in SCOPE_REGISTRY
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", PROVIDER_ENV.keys())
def test_provider_registered_in_scope_registry(provider: str):
    """Each credentials.<provider> key is registered."""
    key = f"credentials.{provider}"
    assert SCOPE_REGISTRY.is_registered(key)


# ---------------------------------------------------------------------------
# CredentialsScope is a ScopedConfig subclass
# ---------------------------------------------------------------------------


def test_credentials_scope_is_scoped_config():
    """CredentialsScope is a subclass of ScopedConfig."""
    from astrid.core.contracts.scoped_config import ScopedConfig

    assert issubclass(CredentialsScope, ScopedConfig)


# ---------------------------------------------------------------------------
# CredentialsScope is frozen
# ---------------------------------------------------------------------------


def test_credentials_scope_is_frozen():
    """CredentialsScope instances cannot be mutated."""
    scope = CredentialsScope(provider="fal", value="key123")
    with pytest.raises(Exception):
        scope.value = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# File-not-found .env fallback to os.environ
# ---------------------------------------------------------------------------


def test_fallback_to_os_environ_when_env_file_not_found():
    """When explicit env_file doesn't exist, load_api_key still delegates."""
    with patch(
        "astrid.core.util.credentials_scope.load_api_key",
        return_value="fallback_key",
    ):
        result = CredentialsScope.get("fal", env_file=Path("/nonexistent/.env"))
        assert result == "fallback_key"


# ---------------------------------------------------------------------------
# Provide env_file but key is not in it → falls back to os.environ
# ---------------------------------------------------------------------------


def test_env_file_without_target_key_falls_back_to_os_environ(tmp_path: Path):
    """When env_file exists but doesn't have the target key, delegates correctly."""
    env_path = tmp_path / ".env"
    env_path.write_text("OTHER_KEY=other_value\n")
    with patch(
        "astrid.core.util.credentials_scope.load_api_key",
        return_value="os_value",
    ) as mock_load:
        result = CredentialsScope.get("fal", env_file=env_path)
        assert result == "os_value"
        mock_load.assert_called_once_with(
            "FAL_KEY",
            env_file=env_path,
            explicit=None,
            keychain=None,
        )


# ---------------------------------------------------------------------------
# Frozen precedence at the CredentialsScope boundary (m4 Step 31)
# ---------------------------------------------------------------------------


class _FakeKeychain:
    """Injected keychain boundary returning a fixed value for one name."""

    def __init__(self, name: str, value: str) -> None:
        self._name = name
        self._value = value
        self.calls = 0

    def get(self, name: str) -> str | None:
        self.calls += 1
        return self._value if name == self._name else None


def test_get_precedence_explicit_over_environment_over_keychain_over_env_file(
    monkeypatch, tmp_path: Path
):
    """explicit > process env > injected keychain > named env file."""
    env_path = tmp_path / "keys.env"
    env_path.write_text("FAL_KEY=from-env-file\n")
    keychain = _FakeKeychain("FAL_KEY", "from-keychain")

    monkeypatch.setenv("FAL_KEY", "from-environment")
    assert (
        CredentialsScope.get(
            "fal", env_file=env_path, explicit="from-explicit", keychain=keychain
        )
        == "from-explicit"
    )
    assert keychain.calls == 0

    assert (
        CredentialsScope.get("fal", env_file=env_path, keychain=keychain)
        == "from-environment"
    )
    assert keychain.calls == 0  # environment satisfied the request

    monkeypatch.delenv("FAL_KEY", raising=False)
    assert (
        CredentialsScope.get("fal", env_file=env_path, keychain=keychain)
        == "from-keychain"
    )
    assert keychain.calls == 1

    # A keychain that has no value for this name falls through to the env file.
    empty_keychain = _FakeKeychain("OTHER_KEY", "ignored")
    assert (
        CredentialsScope.get("fal", env_file=env_path, keychain=empty_keychain)
        == "from-env-file"
    )


def test_get_without_keychain_never_touches_a_keychain(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("FAL_KEY", raising=False)
    env_path = tmp_path / "keys.env"
    env_path.write_text("FAL_KEY=from-env-file\n")

    # The default boundary is a null provider: resolution succeeds without any
    # keychain access.
    assert CredentialsScope.get("fal", env_file=env_path) == "from-env-file"


def test_registry_resolver_explicit_wins_and_env_is_read_from_request():
    """SCOPE_REGISTRY resolution honors explicit first, then request env."""
    scope = SCOPE_REGISTRY.resolve(
        "credentials.fal",
        ScopeRequest(explicit={"credentials.fal": "from-explicit"}),
    )
    assert scope is not None and scope.value == "from-explicit"

    scope = SCOPE_REGISTRY.resolve(
        "credentials.fal",
        ScopeRequest(env={"FAL_KEY": "from-request-env"}),
    )
    assert scope is not None and scope.value == "from-request-env"

    # The request env mapping is authoritative: a key missing from it is not
    # resolved from os.environ, so resolution fails closed.
    with pytest.raises(AstridError):
        SCOPE_REGISTRY.resolve(
            "credentials.fal",
            ScopeRequest(env={"OTHER": "x"}),
        )

    # With no request env, the process environment is the tier-2 source.
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FAL_KEY", "from-os-environ")
    try:
        scope = SCOPE_REGISTRY.resolve("credentials.fal", ScopeRequest())
        assert scope is not None and scope.value == "from-os-environ"
    finally:
        monkeypatch.undo()


def test_registry_resolver_never_accesses_a_keychain(monkeypatch):
    """Domain-only registry resolution performs no keychain access."""
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(AstridError):
        SCOPE_REGISTRY.resolve("credentials.fal", ScopeRequest())